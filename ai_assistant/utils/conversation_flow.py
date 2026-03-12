"""
ConversationFlowManager — orchestrates Spectra's multi-turn action flows.

Flows supported:
  • Task creation   (mode = 'collecting_task')
  • Board creation  (mode = 'collecting_board')
  • Automation activation (mode = 'collecting_automation')
  • Confirmation    (mode = 'awaiting_confirmation')

Every public method returns a plain-text response string that Spectra sends
back to the user.  State is read/written through ``SpectraConversationState``.
"""
import logging
import re
from datetime import datetime, timedelta

from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone

from ai_assistant.models import SpectraConversationState
from ai_assistant.utils.action_service import SpectraActionService
from ai_assistant.utils.chatbot_service import detect_action_intent

logger = logging.getLogger(__name__)

action_service = SpectraActionService()


# ──────────────────────────────────────────────────────────────────────────────
# State helper
# ──────────────────────────────────────────────────────────────────────────────

def get_or_create_state(user, board=None):
    """
    Return the ``SpectraConversationState`` for *user* + *board*.

    Because ``unique_together = ['user', 'board']`` does not enforce
    uniqueness when ``board`` is NULL, we handle that case explicitly.
    """
    if board is not None:
        state, _ = SpectraConversationState.objects.get_or_create(
            user=user,
            board=board,
        )
        _auto_reset_stale(state)
        return state

    # board is None — NULLs are distinct in unique constraints
    state = SpectraConversationState.objects.filter(
        user=user,
        board__isnull=True,
    ).first()
    if state is None:
        try:
            state = SpectraConversationState.objects.create(user=user, board=None)
        except IntegrityError:
            # Concurrent request beat us — re-fetch
            state = SpectraConversationState.objects.filter(
                user=user,
                board__isnull=True,
            ).first()
    _auto_reset_stale(state)
    return state


STALE_STATE_MINUTES = 30


def _auto_reset_stale(state):
    """Auto-reset state if the user hasn't interacted in >30 minutes."""
    if state and state.mode != 'normal':
        cutoff = timezone.now() - timedelta(minutes=STALE_STATE_MINUTES)
        if state.updated_at < cutoff:
            logger.info(
                'Auto-resetting stale conversation state %s (last updated %s)',
                state.id, state.updated_at,
            )
            state.reset()


# ──────────────────────────────────────────────────────────────────────────────
# Date parsing helper
# ──────────────────────────────────────────────────────────────────────────────

def _parse_date(text):
    """
    Attempt to parse a natural-language date string.

    Returns a timezone-aware ``datetime`` or ``None``.
    """
    text = text.strip()
    if not text or text.lower() in ('skip', 'none', 'no', 'n/a', '-'):
        return None

    today = timezone.now().date()

    # Handle "tomorrow"
    if text.lower() == 'tomorrow':
        dt = datetime.combine(today + timedelta(days=1), datetime.min.time())
        return timezone.make_aware(dt)

    # Handle "today"
    if text.lower() == 'today':
        dt = datetime.combine(today, datetime.min.time())
        return timezone.make_aware(dt)

    # Handle "next <weekday>" / "this <weekday>"
    day_names = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6,
    }
    rel_match = re.match(
        r'^(next|this)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$',
        text.strip(),
        re.IGNORECASE,
    )
    if rel_match:
        modifier = rel_match.group(1).lower()
        target_day = day_names[rel_match.group(2).lower()]
        current_day = today.weekday()
        days_ahead = (target_day - current_day) % 7
        if modifier == 'next':
            # "next Friday" always means at least 1 day ahead;
            # if today IS that day, go to the following week
            if days_ahead == 0:
                days_ahead = 7
        else:
            # "this Friday" — this week's occurrence (could be today)
            if days_ahead == 0:
                days_ahead = 0
        dt = datetime.combine(today + timedelta(days=days_ahead), datetime.min.time())
        return timezone.make_aware(dt)

    try:
        from dateutil import parser as dateutil_parser
        dt = dateutil_parser.parse(text, fuzzy=True, dayfirst=False)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt
    except (ValueError, OverflowError):
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Duplicate checkers
# ──────────────────────────────────────────────────────────────────────────────

def _check_duplicate_task(title, board):
    from kanban.models import Task
    return Task.objects.filter(
        title__iexact=title,
        column__board=board,
    ).exists()


def _check_duplicate_board(name, user):
    from kanban.models import Board
    return Board.objects.filter(
        name__iexact=name,
        created_by=user,
    ).exists()


# ──────────────────────────────────────────────────────────────────────────────
# Inline field extraction — parse title/priority/date/assignee from one message
# ──────────────────────────────────────────────────────────────────────────────

_TITLE_RE = re.compile(
    r"""(?:called|named|titled)\s+['\u2018\u201c"]+(.+?)['\u2019\u201d"]+"""
    r"""|(?:called|named|titled)\s+(.+?)(?:\s+with\b|\s+due\b|\s+assign|\s*$)""",
    re.IGNORECASE,
)

_PRIORITY_RE = re.compile(
    r'\b(low|medium|high|urgent|critical)\s*priority\b',
    re.IGNORECASE,
)

_DUE_DATE_RE = re.compile(
    r'(?:due\s+(?:on\s+)?|by\s+)(next\s+\w+|tomorrow|today|'
    r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2}(?:,?\s+\d{4})?|'
    r'\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?)',
    re.IGNORECASE,
)

_ASSIGNEE_RE = re.compile(
    r'assign(?:ed)?\s+(?:(?:the\s+)?(?:task\s+)?to|it\s+to)\s+["\']?(\w+(?:\s+\w+)?)["\']?',
    re.IGNORECASE,
)


def _extract_task_fields(message):
    """
    Extract task fields (title, priority, due_date_text, assignee_text)
    from a single-sentence task-creation message.

    Returns a dict with only the fields that were found.
    """
    result = {}

    m = _TITLE_RE.search(message)
    if m:
        result['title'] = (m.group(1) or m.group(2) or '').strip()

    m = _PRIORITY_RE.search(message)
    if m:
        result['priority'] = m.group(1).lower()

    m = _DUE_DATE_RE.search(message)
    if m:
        result['due_date_text'] = m.group(1).strip()

    m = _ASSIGNEE_RE.search(message)
    if m:
        result['assignee_text'] = m.group(1).strip()

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Question detection helper (for board name collection)
# ──────────────────────────────────────────────────────────────────────────────

def _looks_like_question(text):
    """Return True if *text* looks like a question rather than a board name."""
    txt = text.strip()
    if txt.endswith('?'):
        return True
    low = txt.lower()
    question_starters = [
        'can we', 'can i', 'how ', 'what ', 'when ', 'where ', 'why ',
        'who ', 'which ', 'is there', 'are there', 'do we', 'does ',
        'will ', 'would ', 'could ', 'should ', 'show me', 'tell me',
        'list ', 'compare ', 'summarize ', 'analyze ',
    ]
    return any(low.startswith(q) for q in question_starters)


# ──────────────────────────────────────────────────────────────────────────────
# Board list helper
# ──────────────────────────────────────────────────────────────────────────────

def _user_board_names(user):
    """Return a list of board names the user can access."""
    from kanban.models import Board
    boards = Board.objects.filter(
        Q(created_by=user) | Q(members=user)
    ).distinct().values_list('name', flat=True)[:20]
    return list(boards)


# ══════════════════════════════════════════════════════════════════════════════
# ConversationFlowManager
# ══════════════════════════════════════════════════════════════════════════════

class ConversationFlowManager:
    """
    Stateless helper — each call receives the ``SpectraConversationState``
    object, mutates it as needed, and returns a response string.
    """

    # ------------------------------------------------------------------
    # Main dispatcher
    # ------------------------------------------------------------------

    def handle_message(self, user, board, message, state):
        """
        Route *message* to the appropriate handler according to *state.mode*.

        Returns a response string.  The caller is responsible for saving the
        state (``state.save()`` is called internally when needed).
        """
        mode = state.mode

        # ── Already in a flow ────────────────────────────────────────────
        if mode == 'awaiting_confirmation':
            return self._handle_awaiting_confirmation(user, board, message, state)

        if mode in ('collecting_task', 'collecting_board', 'collecting_automation'):
            return self._handle_collecting(user, board, message, state)

        # ── Normal mode — detect new action intent ───────────────────────
        intent = detect_action_intent(message)
        if intent == 'create_task':
            return self._start_task_flow(user, board, message, state)
        if intent == 'create_board':
            return self._start_board_flow(user, message, state)
        if intent == 'activate_automation':
            return self._start_automation_flow(user, board, message, state)

        # Not an action intent — caller should fall through to normal Q&A
        return None

    # ------------------------------------------------------------------
    # TASK CREATION flow
    # ------------------------------------------------------------------

    def _start_task_flow(self, user, board, message, state):
        if board is None:
            # Auto-select if user has exactly one board
            from kanban.models import Board
            user_boards = list(
                Board.objects.filter(
                    Q(created_by=user) | Q(members=user),
                    is_archived=False,
                ).distinct()[:2]
            )
            if len(user_boards) == 1:
                board = user_boards[0]
            else:
                boards = _user_board_names(user)
                if boards:
                    board_list = ', '.join(f'**{b}**' for b in boards)
                    # Enter collecting_task at step -1 (awaiting board selection)
                    # so the next message is intercepted by the flow
                    state.mode = 'collecting_task'
                    state.pending_action = 'create_task'
                    state.collected_data = {
                        'step': -1,
                        'original_message': message,
                    }
                    state.save()
                    return (
                        "I'd love to help you create a task! But I need to know which board "
                        f"it belongs to. Please select a board from the dropdown above first.\n\n"
                        f"Your boards: {board_list}"
                    )
                return (
                    "I'd love to help you create a task, but you don't seem to have any boards yet. "
                    "Would you like to **create a board** first?"
                )

        state.mode = 'collecting_task'
        state.pending_action = 'create_task'
        data = {'step': 0, 'board_id': board.id, 'board_name': board.name}

        # Try to extract fields from the initial message
        extracted = _extract_task_fields(message)
        if extracted.get('title'):
            data['title'] = extracted['title']
            data['step'] = 1
            if extracted.get('priority'):
                data['priority'] = extracted['priority']

            # Resolve due date if provided inline
            if extracted.get('due_date_text'):
                parsed = _parse_date(extracted['due_date_text'])
                if parsed:
                    data['due_date'] = parsed.isoformat()
                    data['due_date_display'] = parsed.strftime('%A, %B %d, %Y')
                else:
                    data['due_date'] = None
                    data['due_date_display'] = 'Not set'
                data['step'] = 2

            # Resolve assignee if provided inline
            if extracted.get('assignee_text'):
                assignee, _ = action_service._resolve_assignee(
                    extracted['assignee_text'], board,
                )
                if assignee:
                    data['assignee_id'] = assignee.id
                    data['assignee_display'] = (
                        assignee.get_full_name() or assignee.username
                    )
                    data['step'] = 3

            state.collected_data = data

            # If we have all fields, go straight to confirmation
            if data['step'] == 3:
                state.mode = 'awaiting_confirmation'
                state.save()
                return self._format_task_confirmation(data)

            state.save()

            # Check for duplicate
            if _check_duplicate_task(data['title'], board):
                data['duplicate_warned'] = True
                data['step'] = 0.5
                state.collected_data = data
                state.save()
                return (
                    f"There's already a task called **\"{data['title']}\"** on this board. "
                    "Do you still want to create another one, or would you like a different name?"
                )

            if data['step'] == 1:
                return (
                    f"Got it — **\"{data['title']}\"**. "
                    "**Any due date?** You can say something like 'next Friday' or 'skip'."
                )
            if data['step'] == 2:
                return (
                    f"Got it — **\"{data['title']}\"**, due {data['due_date_display']}. "
                    "**Who should this be assigned to?** (Type a name or 'skip')"
                )

        state.collected_data = data
        state.save()
        return "Sure! Let's create a task. **What should the task be called?**"

    def _continue_task_flow(self, user, board, message, state):
        data = state.collected_data
        step = data.get('step', 0)
        msg = message.strip()

        if step == -1:
            # Awaiting board selection
            from kanban.models import Board
            user_boards = list(
                Board.objects.filter(
                    Q(created_by=user) | Q(members=user),
                    is_archived=False,
                ).distinct()
            )
            # Try to match the user's reply to a board name
            selected = None
            msg_lower = msg.lower()
            for b in user_boards:
                if b.name.lower() == msg_lower or b.name.lower() in msg_lower:
                    selected = b
                    break
            if selected is None:
                # Fuzzy: check if any board name is contained in the message
                for b in user_boards:
                    if msg_lower in b.name.lower():
                        selected = b
                        break

            if selected is None:
                boards = [b.name for b in user_boards]
                board_list = ', '.join(f'**{b}**' for b in boards)
                return (
                    f"I couldn't find a board matching **\"{msg}\"**. "
                    f"Please pick one of these: {board_list}"
                )

            board = selected
            data['board_id'] = board.id
            data['board_name'] = board.name
            # Try to extract fields from the original create message
            original = data.pop('original_message', '')
            extracted = _extract_task_fields(original) if original else {}
            data.update(extracted)
            if data.get('title'):
                # We already have the title from the original message
                data['step'] = 1
                state.collected_data = data
                state.save()
                title = data['title']
                if board and _check_duplicate_task(title, board):
                    data['duplicate_warned'] = True
                    data['step'] = 0.5
                    state.collected_data = data
                    state.save()
                    return (
                        f"OK, I'll use **{board.name}**. "
                        f"But there's already a task called **\"{title}\"** on this board. "
                        "Do you still want to create another one, or would you like a different name?"
                    )
                return (
                    f"OK, I'll use **{board.name}**. "
                    "**Any due date?** You can say something like 'next Friday' or 'skip'."
                )
            else:
                data['step'] = 0
                state.collected_data = data
                state.save()
                return f"OK, I'll use **{board.name}**. **What should the task be called?**"

        if step == 0:
            # Collecting title
            data['title'] = msg

            # Duplicate check
            if board and _check_duplicate_task(msg, board):
                data['duplicate_warned'] = True
                data['step'] = 0.5  # special sub-step
                state.collected_data = data
                state.save()
                return (
                    f"There's already a task called **\"{msg}\"** on this board. "
                    "Do you still want to create another one, or would you like a different name?"
                )

            data['step'] = 1
            state.collected_data = data
            state.save()
            return "Got it! **Any due date?** You can say something like 'March 20' or 'skip'."

        if step == 0.5:
            # Duplicate confirmation
            low = msg.lower()
            if any(w in low for w in ['yes', 'still', 'create', 'go ahead', 'another']):
                data['step'] = 1
                state.collected_data = data
                state.save()
                return "OK, I'll create it anyway. **Any due date?** (e.g. 'March 20' or 'skip')"
            else:
                # They want a different name — ask again
                data['step'] = 0
                data.pop('title', None)
                data.pop('duplicate_warned', None)
                state.collected_data = data
                state.save()
                return "No problem. **What should the task be called instead?**"

        if step == 1:
            # Collecting due date
            parsed = _parse_date(msg)
            if parsed:
                data['due_date'] = parsed.isoformat()
                data['due_date_display'] = parsed.strftime('%B %d, %Y')
            else:
                data['due_date'] = None
                data['due_date_display'] = 'Not set'
            data['step'] = 2
            state.collected_data = data
            state.save()
            return (
                "**Who should this be assigned to?** "
                "(Type a name or 'skip')"
            )

        if step == 2:
            # Collecting assignee
            low = msg.lower().strip()
            if low in ('skip', 'none', 'no one', 'unassigned', '-'):
                data['assignee_id'] = None
                data['assignee_display'] = 'Unassigned'
            else:
                if board:
                    assignee, member_names = action_service._resolve_assignee(msg, board)
                    if assignee:
                        data['assignee_id'] = assignee.id
                        data['assignee_display'] = assignee.get_full_name() or assignee.username
                    else:
                        names = ', '.join(f'**{n}**' for n in member_names) if member_names else 'No members found'
                        return (
                            f"I couldn't find **\"{msg}\"** as a member of this board. "
                            f"Here are the current members: {names}.\n\n"
                            "Who did you mean, or should I leave it **unassigned**?"
                        )
                else:
                    data['assignee_id'] = None
                    data['assignee_display'] = 'Unassigned'

            # Move to confirmation
            data['step'] = 3
            state.collected_data = data
            state.mode = 'awaiting_confirmation'
            state.save()
            return self._format_task_confirmation(data)

        # Shouldn't reach here, but safety net
        return self._format_task_confirmation(data)

    # ------------------------------------------------------------------
    # BOARD CREATION flow
    # ------------------------------------------------------------------

    def _start_board_flow(self, user, message, state):
        state.mode = 'collecting_board'
        state.pending_action = 'create_board'
        state.collected_data = {'step': 0}
        state.save()

        return "Let's create a new board! **What should the board be called?**"

    def _continue_board_flow(self, user, board, message, state):
        data = state.collected_data
        step = data.get('step', 0)
        msg = message.strip()

        if step == 0:
            # Collecting name — detect if the user typed a question instead
            if _looks_like_question(msg):
                return (
                    f"That looks like a question rather than a board name. "
                    f"Would you like me to **cancel** creating this board so I can answer your question? "
                    f"Or if you really want that as the board name, just type it again."
                )

            # Collecting name
            data['name'] = msg

            # Duplicate check
            if _check_duplicate_board(msg, user):
                data['duplicate_warned'] = True
                data['step'] = 0.5
                state.collected_data = data
                state.save()
                return (
                    f"There's already a board called **\"{msg}\"**. "
                    "Do you still want to create another one, or would you like a different name?"
                )

            data['step'] = 1
            state.collected_data = data
            state.save()
            return "**Any description for this board?** (or say 'skip')"

        if step == 0.5:
            low = msg.lower()
            if any(w in low for w in ['yes', 'still', 'create', 'go ahead', 'another']):
                data['step'] = 1
                state.collected_data = data
                state.save()
                return "OK, I'll create it anyway. **Any description for this board?** (or say 'skip')"
            else:
                data['step'] = 0
                data.pop('name', None)
                data.pop('duplicate_warned', None)
                state.collected_data = data
                state.save()
                return "No problem. **What should the board be called instead?**"

        if step == 1:
            # Collecting description
            low = msg.lower().strip()
            if low in ('skip', 'none', 'no', '-', 'n/a'):
                data['description'] = ''
                data['description_display'] = 'None'
            else:
                data['description'] = msg
                data['description_display'] = msg

            data['step'] = 2
            state.collected_data = data
            state.mode = 'awaiting_confirmation'
            state.save()
            return self._format_board_confirmation(data)

        return self._format_board_confirmation(data)

    # ------------------------------------------------------------------
    # AUTOMATION ACTIVATION flow
    # ------------------------------------------------------------------

    def _start_automation_flow(self, user, board, message, state):
        if board is None:
            # Auto-select if user has exactly one board
            from kanban.models import Board
            user_boards = list(
                Board.objects.filter(
                    Q(created_by=user) | Q(members=user),
                    is_archived=False,
                ).distinct()[:2]
            )
            if len(user_boards) == 1:
                board = user_boards[0]
            else:
                boards = _user_board_names(user)
                if boards:
                    board_list = ', '.join(f'**{b}**' for b in boards)
                    # Enter collecting_automation at step -1 (awaiting board)
                    state.mode = 'collecting_automation'
                    state.pending_action = 'activate_automation'
                    state.collected_data = {'step': -1}
                    state.save()
                    return (
                        "I can set up automations, but I need a board to work with. "
                        f"Please select a board from the dropdown above first.\n\n"
                        f"Your boards: {board_list}"
                    )
                return (
                    "I can set up automations, but you don't have any boards yet. "
                    "Would you like to **create a board** first?"
                )

        state.mode = 'collecting_automation'
        state.pending_action = 'activate_automation'
        state.collected_data = {'step': 0, 'board_id': board.id, 'board_name': board.name}
        state.save()

        return (
            "I can set up one of these automations for this board:\n\n"
            "1. **Mark overdue tasks as Urgent**\n"
            "2. **Notify creator when task is completed**\n"
            "3. **Alert assignee 2 days before deadline**\n\n"
            "Which would you like? (say the number or describe what you need)"
        )

    def _continue_automation_flow(self, user, board, message, state):
        data = state.collected_data
        step = data.get('step', 0)
        msg = message.strip()

        if step == -1:
            # Awaiting board selection
            from kanban.models import Board
            user_boards = list(
                Board.objects.filter(
                    Q(created_by=user) | Q(members=user),
                    is_archived=False,
                ).distinct()
            )
            selected = None
            msg_lower = msg.lower()
            for b in user_boards:
                if b.name.lower() == msg_lower or b.name.lower() in msg_lower:
                    selected = b
                    break
            if selected is None:
                for b in user_boards:
                    if msg_lower in b.name.lower():
                        selected = b
                        break

            if selected is None:
                boards = [b.name for b in user_boards]
                board_list = ', '.join(f'**{b}**' for b in boards)
                return (
                    f"I couldn't find a board matching **\"{msg}\"**. "
                    f"Please pick one of these: {board_list}"
                )

            board = selected
            data['board_id'] = board.id
            data['board_name'] = board.name
            data['step'] = 0
            state.collected_data = data
            state.save()
            return (
                f"OK, I'll use **{board.name}**.\n\n"
                "I can set up one of these automations for this board:\n\n"
                "1. **Mark overdue tasks as Urgent**\n"
                "2. **Notify creator when task is completed**\n"
                "3. **Alert assignee 2 days before deadline**\n\n"
                "Which would you like? (say the number or describe what you need)"
            )

        if step == 0:
            # Trying to parse template selection
            template_num = self._match_automation_template(msg)
            if template_num:
                data['template_number'] = template_num
                data['step'] = 1
                state.collected_data = data
                state.mode = 'awaiting_confirmation'
                state.save()
                return self._format_automation_confirmation(template_num, data.get('board_name', ''))
            else:
                # Could not match — ask again
                return (
                    "I'm not sure which automation you mean. Could you pick a number?\n\n"
                    "1. Mark overdue tasks as Urgent\n"
                    "2. Notify creator when task is completed\n"
                    "3. Alert assignee 2 days before deadline"
                )

        return self._format_automation_confirmation(
            data.get('template_number', 1),
            data.get('board_name', ''),
        )

    @staticmethod
    def _match_automation_template(text):
        """
        Try to match user text to one of the 3 templates.
        Returns 1, 2, or 3, or ``None``.
        """
        t = text.lower().strip()

        # Direct number
        if t in ('1', 'one', 'first'):
            return 1
        if t in ('2', 'two', 'second'):
            return 2
        if t in ('3', 'three', 'third'):
            return 3

        # Keyword matching
        if any(w in t for w in ['overdue', 'urgent', 'escalate']):
            return 1
        if any(w in t for w in ['completed', 'done', 'creator', 'notify creator']):
            return 2
        if any(w in t for w in ['deadline', 'before', 'approaching', 'assignee', 'alert assignee', '2 day']):
            return 3

        return None

    # ------------------------------------------------------------------
    # Collection dispatcher (routes to the right _continue_ method)
    # ------------------------------------------------------------------

    def _handle_collecting(self, user, board, message, state):
        """Route to the correct continuation handler based on state mode."""
        # First check if user wants to cancel mid-flow
        intent = detect_action_intent(message)
        if intent == 'cancel_action':
            return self._handle_cancellation(state)

        # Check for off-topic: if it's not a confirm/cancel and the message
        # looks like a normal question rather than data entry, warn the user
        # but still process it as data.  We only flag truly off-topic messages
        # when they start a *new* action intent of a different type.
        if intent and intent not in ('confirm_action', 'cancel_action'):
            # User is trying to start a different action mid-flow
            flow_name = {
                'collecting_task': 'creating a task',
                'collecting_board': 'creating a board',
                'collecting_automation': 'setting up an automation',
            }.get(state.mode, 'something')
            return (
                f"I'm currently in the middle of **{flow_name}** for you. "
                "Would you like to **continue** with that, or should I **cancel** it and start fresh?"
            )

        if state.mode == 'collecting_task':
            return self._continue_task_flow(user, board, message, state)
        if state.mode == 'collecting_board':
            return self._continue_board_flow(user, board, message, state)
        if state.mode == 'collecting_automation':
            return self._continue_automation_flow(user, board, message, state)

        # Shouldn't happen, but reset as safety
        state.reset()
        return "Something went wrong with the conversation flow. Let's start over — how can I help you?"

    # ------------------------------------------------------------------
    # Confirmation / Cancellation
    # ------------------------------------------------------------------

    def _handle_awaiting_confirmation(self, user, board, message, state):
        intent = detect_action_intent(message)
        msg_lower = message.lower().strip()

        if intent == 'cancel_action':
            return self._handle_cancellation(state)

        if intent == 'confirm_action':
            return self._execute_pending_action(user, board, state)

        # User might want to change something — check for specific change requests
        if any(w in msg_lower for w in ['change', 'modify', 'edit', 'update', 'different']):
            # Re-enter the collection flow
            pending = state.pending_action
            if pending == 'create_task':
                state.mode = 'collecting_task'
                data = state.collected_data
                data['step'] = 0
                data.pop('title', None)
                state.collected_data = data
                state.save()
                return "OK, let's start over. **What should the task be called?**"
            elif pending == 'create_board':
                state.mode = 'collecting_board'
                data = state.collected_data
                data['step'] = 0
                data.pop('name', None)
                state.collected_data = data
                state.save()
                return "OK, let's start over. **What should the board be called?**"
            elif pending == 'activate_automation':
                state.mode = 'collecting_automation'
                data = state.collected_data
                data['step'] = 0
                state.collected_data = data
                state.save()
                return (
                    "OK, which automation would you prefer?\n\n"
                    "1. Mark overdue tasks as Urgent\n"
                    "2. Notify creator when task is completed\n"
                    "3. Alert assignee 2 days before deadline"
                )

        # Unrecognised response — gently prompt
        return (
            "I need a **confirm** or **cancel** to proceed. "
            "You can also say what you'd like to change."
        )

    def _handle_cancellation(self, state):
        state.reset()
        return "No problem! I've cancelled that. Feel free to ask me anything. 😊"

    def _execute_pending_action(self, user, board, state):
        pending = state.pending_action
        data = state.collected_data

        if pending == 'create_task':
            return self._execute_task_creation(user, board, state, data)
        elif pending == 'create_board':
            return self._execute_board_creation(user, state, data)
        elif pending == 'activate_automation':
            return self._execute_automation(user, board, state, data)
        else:
            state.reset()
            return "I'm not sure what to create. Let's start over — how can I help?"

    # ── Execute: Task ─────────────────────────────────────────────────

    def _execute_task_creation(self, user, board, state, data):
        from kanban.models import Board
        from django.contrib.auth.models import User as AuthUser

        # Resolve board from stored data if not available from request
        if board is None:
            board_id = data.get('board_id')
            if board_id:
                try:
                    board = Board.objects.get(id=board_id)
                except Board.DoesNotExist:
                    state.reset()
                    return "The board no longer exists. Please try again."

        if board is None:
            state.reset()
            return (
                "I need a board to create the task in. "
                "Please select a board from the dropdown above and try again."
            )

        # Prepare collected_data for the service
        create_data = {
            'title': data.get('title', 'Untitled Task'),
            'priority': data.get('priority', 'medium'),
        }
        if data.get('due_date'):
            create_data['due_date'] = data['due_date']
        if data.get('assignee_id'):
            try:
                assignee = AuthUser.objects.get(id=data['assignee_id'])
                create_data['assignee'] = assignee
            except AuthUser.DoesNotExist:
                create_data['assignee'] = None

        result = action_service.create_task(user, board, create_data)

        state.reset()

        if result['success']:
            task = result['task']
            url = result['url']
            return (
                f"✅ **Task created successfully!**\n\n"
                f"📋 **{task.title}** has been added to **{board.name}** "
                f"in the **{task.column.name}** column.\n\n"
                f"[View task]({url})"
            )
        else:
            return (
                f"Something went wrong while creating that task. Please try again, "
                f"or create it manually from the board.\n\n"
                f"The error was: {result['error']}"
            )

    # ── Execute: Board ────────────────────────────────────────────────

    def _execute_board_creation(self, user, state, data):
        create_data = {
            'name': data.get('name', 'Untitled Board'),
            'description': data.get('description', ''),
        }

        result = action_service.create_board(user, create_data)

        state.reset()

        if result['success']:
            board_obj = result['board']
            url = result['url']
            return (
                f"✅ **Board created successfully!**\n\n"
                f"🗂️ **{board_obj.name}** is ready with columns: "
                f"To Do → In Progress → Done.\n\n"
                f"[Open board]({url})"
            )
        else:
            return (
                f"Something went wrong while creating the board. Please try again, "
                f"or create it manually.\n\n"
                f"The error was: {result['error']}"
            )

    # ── Execute: Automation ───────────────────────────────────────────

    def _execute_automation(self, user, board, state, data):
        from kanban.models import Board

        if board is None:
            board_id = data.get('board_id')
            if board_id:
                try:
                    board = Board.objects.get(id=board_id)
                except Board.DoesNotExist:
                    state.reset()
                    return "The board no longer exists. Please try again."

        if board is None:
            state.reset()
            return (
                "I need a board to set up the automation. "
                "Please select a board from the dropdown above and try again."
            )

        template_number = data.get('template_number', 1)
        result = action_service.activate_automation_template(user, board, template_number)

        state.reset()

        if result['success']:
            automation = result['automation']
            return (
                f"✅ **Automation activated!**\n\n"
                f"⚡ **{automation.name}** is now active on **{board.name}**.\n\n"
                f"It will run automatically whenever the trigger condition is met."
            )
        else:
            return (
                f"I couldn't activate that automation. {result['error']}"
            )

    # ------------------------------------------------------------------
    # Confirmation message formatters
    # ------------------------------------------------------------------

    @staticmethod
    def _format_task_confirmation(data):
        title = data.get('title', 'Untitled')
        board_name = data.get('board_name', 'Unknown')
        column = data.get('column_name', 'To Do')
        priority = data.get('priority', 'Medium').capitalize()
        due = data.get('due_date_display', 'Not set')
        assignee = data.get('assignee_display', 'Unassigned')

        return (
            "Here's what I'll create:\n\n"
            f"📋 **Task:** {title}\n"
            f"📁 **Board:** {board_name}\n"
            f"📌 **Column:** {column}\n"
            f"⚡ **Priority:** {priority}\n"
            f"📅 **Due date:** {due}\n"
            f"👤 **Assigned to:** {assignee}\n\n"
            "Type **confirm** to create this task, or tell me what to change."
        )

    @staticmethod
    def _format_board_confirmation(data):
        name = data.get('name', 'Untitled')
        desc = data.get('description_display', 'None')

        return (
            "Here's what I'll create:\n\n"
            f"🗂️ **Board:** {name}\n"
            f"📝 **Description:** {desc}\n"
            f"📋 **Default columns:** To Do → In Progress → Done\n\n"
            "Type **confirm** to create this board, or tell me what to change."
        )

    @staticmethod
    def _format_automation_confirmation(template_number, board_name):
        templates = {
            1: {
                'name': 'Mark overdue tasks as Urgent',
                'trigger': 'When a task passes its due date without being completed',
                'action': "Automatically set the task's priority to Urgent",
            },
            2: {
                'name': 'Notify creator when task is completed',
                'trigger': 'When a task reaches 100% progress',
                'action': 'Send a notification to the person who created the task',
            },
            3: {
                'name': 'Alert assignee 2 days before deadline',
                'trigger': 'When the due date is only 2 days away',
                'action': 'Send an in-app notification to the task assignee',
            },
        }
        tpl = templates.get(template_number, templates[1])

        return (
            "Here's what I'll activate:\n\n"
            f"⚡ **Automation:** {tpl['name']}\n"
            f"🎯 **Trigger:** {tpl['trigger']}\n"
            f"🔔 **Action:** {tpl['action']}\n"
            f"📁 **Board:** {board_name}\n\n"
            "Type **confirm** to activate this automation, or say **cancel**."
        )
