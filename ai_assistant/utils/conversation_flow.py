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

from django.contrib.auth import get_user_model

from ai_assistant.models import SpectraConversationState
from ai_assistant.utils.action_service import SpectraActionService
from ai_assistant.utils.chatbot_service import detect_action_intent, classify_intent_with_ai

logger = logging.getLogger(__name__)

action_service = SpectraActionService()


# ──────────────────────────────────────────────────────────────────────────────
# FC context prompt builder (compact context for Flash Function Calling)
# ──────────────────────────────────────────────────────────────────────────────

def build_fc_context(user, board):
    """
    Build a compact system prompt for the Flash Function-Calling model.

    Includes just enough context to resolve names, dates, and board details
    — much smaller than the full Q&A system prompt.
    """
    now = timezone.localtime(timezone.now())
    tz_name = str(timezone.get_current_timezone())
    user_name = user.get_full_name() or user.username
    parts = [
        f"Today: {now.strftime('%A, %B %d, %Y')}. Current time: {now.strftime('%H:%M')} ({tz_name}).",
        f"User: {user_name} (username: {user.username}).",
        f"All dates and times should be in the user's local timezone ({tz_name}).",
    ]

    if board:
        parts.append(f"Active board: {board.name} (ID {board.id}).")

        # Board members for resolving names like "Alex" → user object
        members = list(get_user_model().objects.filter(board_memberships__board=board).select_related())
        if board.created_by and board.created_by not in members:
            members.append(board.created_by)
        if members:
            member_strs = [
                f"{m.get_full_name() or m.username} (@{m.username})"
                for m in members[:20]
            ]
            parts.append(f"Board members: {', '.join(member_strs)}.")

        # Column names for task placement context
        from kanban.models import Column
        columns = list(
            Column.objects.filter(board=board)
            .order_by('position')
            .values_list('name', flat=True)[:10]
        )
        if columns:
            parts.append(f"Columns: {' → '.join(columns)}.")

        # Recent tasks (for time-entry matching / context)
        from kanban.models import Task
        recent_tasks = list(
            Task.objects.filter(column__board=board)
            .order_by('-updated_at')
            .values_list('title', flat=True)[:10]
        )
        if recent_tasks:
            parts.append(f"Recent tasks: {', '.join(recent_tasks)}.")

    # Recent Spectra-created artifacts for cross-session reference
    from ai_assistant.models import SpectraConversationState
    global_state = SpectraConversationState.objects.filter(
        user=user, board__isnull=True,
    ).first()
    if global_state:
        artifacts = (global_state.collected_data or {}).get('_recent_artifacts', [])[:3]
        if artifacts:
            art_strs = [f"{a['type']}: {a['name']}" for a in artifacts]
            parts.append(f"Recently created by Spectra: {', '.join(art_strs)}.")

    parts.append(
        "Extract the action parameters from the user's message. "
        "If a required parameter is missing, ask for it concisely."
    )

    # RBAC context — tell the FC model about the user's access level
    from ai_assistant.utils.rbac_utils import build_rbac_context_for_fc_prompt
    rbac_ctx = build_rbac_context_for_fc_prompt(user, board)
    if rbac_ctx:
        parts.append(rbac_ctx)

    return '\n'.join(parts)


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

    # Handle "tomorrow" optionally with a time (e.g. "tomorrow at 2 PM")
    tomorrow_match = re.match(
        r'^tomorrow(?:\s+(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?$',
        text.strip(),
        re.IGNORECASE,
    )
    if tomorrow_match:
        time_part = datetime.min.time()
        if tomorrow_match.group(1):
            try:
                from dateutil import parser as dateutil_parser
                time_dt = dateutil_parser.parse(tomorrow_match.group(1))
                time_part = time_dt.time()
            except (ValueError, OverflowError):
                pass
        dt = datetime.combine(today + timedelta(days=1), time_part)
        return timezone.make_aware(dt)

    # Handle "today" optionally with a time
    today_match = re.match(
        r'^today(?:\s+(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?$',
        text.strip(),
        re.IGNORECASE,
    )
    if today_match:
        time_part = datetime.min.time()
        if today_match.group(1):
            try:
                from dateutil import parser as dateutil_parser
                time_dt = dateutil_parser.parse(today_match.group(1))
                time_part = time_dt.time()
            except (ValueError, OverflowError):
                pass
        dt = datetime.combine(today, time_part)
        return timezone.make_aware(dt)

    # Handle "next <weekday>" / "this <weekday>", optionally with a time
    day_names = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6,
    }
    rel_match = re.match(
        r'^(next|this)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)'
        r'(?:\s+(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?',
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
        target_date = today + timedelta(days=days_ahead)
        # Parse optional time component
        time_part = datetime.min.time()
        if rel_match.group(3):
            try:
                from dateutil import parser as dateutil_parser
                time_dt = dateutil_parser.parse(rel_match.group(3))
                time_part = time_dt.time()
            except (ValueError, OverflowError):
                pass
        dt = datetime.combine(target_date, time_part)
        return timezone.make_aware(dt)

    try:
        from dateutil import parser as dateutil_parser
        dt = dateutil_parser.parse(text, fuzzy=True, dayfirst=False)
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        else:
            # Convert to the project's configured timezone so that
            # "10 AM" in the user's prompt stays 10 AM local.
            dt = timezone.localtime(dt)
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
    r'\b(low|medium|high|urgent|critical)[\s-]*priority\b'
    r'|\bpriority[\s:-]*(low|medium|high|urgent|critical)\b',
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
        title = (m.group(1) or m.group(2) or '').strip().strip("'\"\u2018\u2019\u201c\u201d")
        result['title'] = title.rstrip('.,;:!?')

    m = _PRIORITY_RE.search(message)
    if m:
        result['priority'] = (m.group(1) or m.group(2)).lower()

    m = _DUE_DATE_RE.search(message)
    if m:
        result['due_date_text'] = m.group(1).strip()

    m = _ASSIGNEE_RE.search(message)
    if m:
        result['assignee_text'] = m.group(1).strip()

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Board-name extraction from "Create a board called X" messages
# ──────────────────────────────────────────────────────────────────────────────

_BOARD_NAME_RE = re.compile(
    r"""(?:called|named|titled)\s+['\u2018\u201c"]+(.+?)['\u2019\u201d"]+"""
    r"""|(?:called|named|titled)\s+(.+?)(?:\s+with\b|\s*$)""",
    re.IGNORECASE,
)


def _extract_board_name(message):
    """Extract board name from a 'create board called X' message. Returns str or None."""
    m = _BOARD_NAME_RE.search(message)
    if m:
        name = (m.group(1) or m.group(2) or '').strip().strip("'\"‘’“”")
        return name if name else None
    return None


_BOARD_DESC_RE = re.compile(
    r'\bwith\s+(?:(?:a|the)\s+)?desc(?:ription)?[\s:]+(.+?)$',
    re.IGNORECASE,
)


def _extract_board_description(message):
    """Extract inline description from 'create board called X with description Y'."""
    m = _BOARD_DESC_RE.search(message)
    if m:
        desc = m.group(1).strip()
        return desc if desc else None
    return None



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
    """Return a list of board names the user can access (demo-aware)."""
    from kanban.utils.demo_protection import get_user_boards
    boards = get_user_boards(user).values_list('name', flat=True)[:20]
    return list(boards)


def _user_board_names_for_env(user, is_demo_mode):
    """Return board names visible in the user's current workspace."""
    from kanban.models import Board
    if is_demo_mode:
        boards = Board.objects.filter(
            owner=user,
            is_sandbox_copy=True,
        ).distinct().values_list('name', flat=True)[:20]
    else:
        boards = Board.objects.filter(
            Q(created_by=user) | Q(memberships__user=user),
            is_official_demo_board=False,
            is_sandbox_copy=False,
        ).exclude(
            created_by_session__startswith='spectra_demo_'
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
    # Board persistence helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _remember_board(state, board):
        """Persist the last-used board so subsequent actions auto-select it."""
        if board and state:
            # Store in the global (board=None) state for the user so it
            # survives across state resets.
            global_state = SpectraConversationState.objects.filter(
                user=state.user, board__isnull=True,
            ).first()
            if global_state is None:
                global_state = state
            data = global_state.collected_data or {}
            if data.get('_last_board_id') != board.id:
                data['_last_board_id'] = board.id
                data['_last_board_name'] = board.name
                global_state.collected_data = data
                global_state.save(update_fields=['collected_data', 'updated_at'])

    @staticmethod
    def _get_last_board(user, is_demo_mode=False):
        """Retrieve the last-used board from the global state, if still valid."""
        from kanban.models import Board
        global_state = SpectraConversationState.objects.filter(
            user=user, board__isnull=True,
        ).first()
        if not global_state:
            return None
        board_id = (global_state.collected_data or {}).get('_last_board_id')
        if not board_id:
            return None
        try:
            board = Board.objects.get(id=board_id, is_archived=False)
            # Verify the board is accessible in the current workspace
            if is_demo_mode:
                if not (board.is_official_demo_board or
                        (board.created_by_session or '').startswith(f'spectra_demo_{user.id}')):
                    return None
            else:
                if board.is_official_demo_board or \
                        (board.created_by_session or '').startswith('spectra_demo_'):
                    return None
                if not (board.created_by_id == user.id or board.memberships.filter(user_id=user.id).exists()):
                    return None
            return board
        except Board.DoesNotExist:
            return None

    # ------------------------------------------------------------------
    # Artifact memory — track recent Spectra-created artifacts
    # ------------------------------------------------------------------

    @staticmethod
    def _remember_artifact(user, artifact_type, artifact_info):
        """
        Store a recently created artifact so Spectra can reference it later.
        Keeps the last 5 artifacts per user in the global state.
        artifact_info: dict with at minimum 'name' and 'id'.
        """
        global_state = SpectraConversationState.objects.filter(
            user=user, board__isnull=True,
        ).first()
        if global_state is None:
            global_state, _ = SpectraConversationState.objects.get_or_create(
                user=user, board=None,
                defaults={'mode': 'normal'},
            )
        data = global_state.collected_data or {}
        artifacts = data.get('_recent_artifacts', [])
        artifacts.insert(0, {
            'type': artifact_type,
            **artifact_info,
        })
        data['_recent_artifacts'] = artifacts[:5]  # keep last 5
        global_state.collected_data = data
        global_state.save(update_fields=['collected_data', 'updated_at'])

    @staticmethod
    def _get_recent_artifacts(user, limit=5):
        """Retrieve recent Spectra-created artifacts for context."""
        global_state = SpectraConversationState.objects.filter(
            user=user, board__isnull=True,
        ).first()
        if not global_state:
            return []
        return (global_state.collected_data or {}).get('_recent_artifacts', [])[:limit]

    # ------------------------------------------------------------------
    # Compound action detection
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_second_action(data):
        """
        Check if the original message contained a second action clause
        after delimiters like 'and then', 'then also', 'and also', ', also'.
        Returns the second clause text or None.
        """
        original = data.get('_original_message') or data.get('original_message', '')
        if not original:
            return None
        import re
        # Split on compound delimiters
        parts = re.split(
            r'\b(?:and\s+then|then\s+also|and\s+also|,\s*also|,\s*then)\b',
            original, maxsplit=1, flags=re.IGNORECASE,
        )
        if len(parts) < 2:
            return None
        second = parts[1].strip()
        # Only return if it looks like an action (reasonably long)
        if len(second) > 10:
            intent = detect_action_intent(second)
            if intent and intent not in ('confirm_action', 'cancel_action'):
                return second
        return None

    # ------------------------------------------------------------------
    # Main dispatcher
    # ------------------------------------------------------------------

    def handle_message(self, user, board, message, state, is_demo_mode=False):
        """
        Route *message* to the appropriate handler according to *state.mode*.

        Returns a response string.  The caller is responsible for saving the
        state (``state.save()`` is called internally when needed).
        """
        self._is_demo_mode = is_demo_mode
        mode = state.mode

        # ── Already in a flow ────────────────────────────────────────────
        if mode == 'awaiting_confirmation':
            return self._handle_awaiting_confirmation(user, board, message, state)

        if mode in ('collecting_task', 'collecting_board', 'collecting_automation'):
            return self._handle_collecting(user, board, message, state)

        # FC-based collecting modes
        if mode in self._FC_NEW_MODES:
            return self._handle_collecting(user, board, message, state)

        # ── Normal mode — detect new action intent ───────────────────────
        # Tier 1: Try AI classification first, fall back to regex
        from ai_assistant.utils.ai_clients import GeminiClient
        try:
            client = GeminiClient()
        except Exception:
            client = None
        classification = classify_intent_with_ai(message, gemini_client=client)
        intent = classification['intent']

        if intent == 'create_task':
            return self._start_task_flow(user, board, message, state)
        if intent == 'create_board':
            return self._start_board_flow(user, message, state)
        if intent == 'activate_automation':
            return self._start_automation_flow(user, board, message, state)

        # FC-based intents
        if intent in self._FC_INTENT_META:
            return self._start_fc_flow(user, board, message, state, intent)

        # Not an action intent — caller should fall through to normal Q&A
        return None

    # ------------------------------------------------------------------
    # TASK CREATION flow
    # ------------------------------------------------------------------

    def _start_task_flow(self, user, board, message, state):
        is_demo = getattr(self, '_is_demo_mode', False)
        if board is None:
            # Try last-used board first
            board = self._get_last_board(user, is_demo)
        if board is None:
            from kanban.models import Board

            # Build workspace-appropriate board list
            if is_demo:
                user_boards = list(
                    Board.objects.filter(
                        Q(is_official_demo_board=True)
                        | Q(created_by_session=f'spectra_demo_{user.id}'),
                        is_archived=False,
                    ).distinct()[:2]
                )
            else:
                user_boards = list(
                    Board.objects.filter(
                        Q(created_by=user) | Q(memberships__user=user),
                        is_archived=False,
                    ).exclude(
                        created_by_session__startswith='spectra_demo_'
                    ).exclude(
                        is_official_demo_board=True,
                    ).distinct()[:2]
                )

            if len(user_boards) == 1:
                board = user_boards[0]
            else:
                boards = _user_board_names_for_env(user, is_demo)
                if boards:
                    board_list = ', '.join(f'**{b}**' for b in boards)
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
                # No boards in this environment
                if is_demo:
                    return (
                        "There are no boards in **Demo Workspace** right now. "
                        "Would you like to **create a board** here to experiment with?"
                    )
                return (
                    "I'd love to help you create a task, but you don't seem to have any boards yet. "
                    "Would you like to **create a board** first?"
                )

        state.mode = 'collecting_task'
        state.pending_action = 'create_task'

        # ── RBAC pre-check: viewer can't create tasks ────────────────
        from ai_assistant.utils.rbac_utils import check_spectra_action_permission
        allowed, denial = check_spectra_action_permission(user, board, 'create_task')
        if not allowed:
            state.reset()
            return denial

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

        # Resolve board from collected_data when not provided by the view
        if board is None and data.get('board_id'):
            from kanban.models import Board
            try:
                board = Board.objects.get(id=data['board_id'])
            except Board.DoesNotExist:
                state.reset()
                return "The board no longer exists. Please try again."

        # Handle inline priority change from confirmation screen
        if data.get('_awaiting_priority_change'):
            data.pop('_awaiting_priority_change')
            new_p = None
            for p in ('low', 'medium', 'high', 'urgent'):
                if p in msg.lower():
                    new_p = p
                    break
            if new_p:
                data['priority'] = new_p
                state.collected_data = data
                state.mode = 'awaiting_confirmation'
                state.save()
                return self._format_task_confirmation(data)
            return (
                "I didn't catch a valid priority. "
                "Please choose: **Low**, **Medium**, **High**, or **Urgent**."
            )

        if step == -1:
            # Awaiting board selection
            from kanban.utils.demo_protection import get_user_boards
            user_boards = list(
                get_user_boards(user).filter(is_archived=False)
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
            self._remember_board(state, board)
            # Try to extract fields from the original create message
            original = data.pop('original_message', '')
            extracted = _extract_task_fields(original) if original else {}
            data.update(extracted)
            if data.get('title'):
                # We already have the title from the original message
                title = data['title']
                if data.get('priority'):
                    pass  # already stored

                # Resolve due date if extracted inline
                if data.get('due_date_text') and not data.get('due_date'):
                    parsed = _parse_date(data.pop('due_date_text'))
                    if parsed:
                        data['due_date'] = parsed.isoformat()
                        data['due_date_display'] = parsed.strftime('%A, %B %d, %Y')

                # Resolve assignee if extracted inline
                if data.get('assignee_text') and not data.get('assignee_id'):
                    assignee_text = data.pop('assignee_text')
                    assignee, _ = action_service._resolve_assignee(assignee_text, board)
                    if assignee:
                        data['assignee_id'] = assignee.id
                        data['assignee_display'] = assignee.get_full_name() or assignee.username

                # Determine which step to skip to
                if data.get('assignee_id') is not None or data.get('assignee_display'):
                    data['step'] = 3
                    state.mode = 'awaiting_confirmation'
                    state.collected_data = data
                    state.save()
                    return (
                        f"OK, I'll use **{board.name}**.\n\n"
                        + self._format_task_confirmation(data)
                    )
                elif data.get('due_date'):
                    data['step'] = 2
                    state.collected_data = data
                    state.save()
                    return (
                        f"OK, I'll use **{board.name}**. Got it — **\"{title}\"**, "
                        f"due {data.get('due_date_display', '')}. "
                        "**Who should this be assigned to?** (Type a name or 'skip')"
                    )
                else:
                    data['step'] = 1
                    state.collected_data = data
                    state.save()
                    if board and _check_duplicate_task(title, board):
                        data['duplicate_warned'] = True
                        data['step'] = 0.5
                        state.collected_data = data
                        state.save()
                        return (
                            f"OK, I'll use **{board.name}**. "
                            f"But there's already a task called **\"{title}\"** on this board. "
                            "Do you still want to create another one, or a different name?"
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

            # If due date already collected (editing from confirmation), skip ahead
            if 'due_date_display' in data and 'assignee_display' in data:
                data['step'] = 3
                state.mode = 'awaiting_confirmation'
                state.collected_data = data
                state.save()
                return self._format_task_confirmation(data)

            state.collected_data = data
            state.save()
            return "Got it! **Any due date?** You can say something like 'March 20' or 'skip'."

        if step == 0.5:
            # Duplicate confirmation
            low = msg.lower()
            if any(w in low for w in ['yes', 'still', 'create', 'go ahead', 'another']):
                data['step'] = 1

                # If due date already collected (editing from confirmation), skip ahead
                if 'due_date_display' in data and 'assignee_display' in data:
                    data['step'] = 3
                    state.mode = 'awaiting_confirmation'
                    state.collected_data = data
                    state.save()
                    return self._format_task_confirmation(data)

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

            # If assignee was already collected (editing from confirmation),
            # jump back to confirmation instead of re-asking.
            if 'assignee_display' in data:
                data['step'] = 3
                state.mode = 'awaiting_confirmation'
                state.collected_data = data
                state.save()
                return self._format_task_confirmation(data)

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
        data = {'step': 0}

        # Notify user about workspace context if they're in demo mode
        demo_prefix = ''
        if getattr(self, '_is_demo_mode', False):
            demo_prefix = (
                "📌 You're in **Demo Workspace**. The board will be created here "
                "so you can experiment freely — it won't appear in your personal workspace.\n\n"
            )

        # Try to extract board name from the initial message
        name = _extract_board_name(message)
        if name and not _looks_like_question(name):
            data['name'] = name
            # Duplicate check
            if _check_duplicate_board(name, user):
                data['duplicate_warned'] = True
                data['step'] = 0.5
                state.collected_data = data
                state.save()
                return (
                    f"{demo_prefix}"
                    f"There's already a board called **\"{name}\"**. "
                    "Do you still want to create another one, or would you like a different name?"
                )
            # Try to extract inline description ("...with description Y")
            desc = _extract_board_description(message)
            if desc:
                data['description'] = desc
                data['description_display'] = desc
                data['step'] = 2
                state.collected_data = data
                state.mode = 'awaiting_confirmation'
                state.save()
                return self._format_board_confirmation(data)
            data['step'] = 1
            state.collected_data = data
            state.save()
            return f"{demo_prefix}I'll name it **\"{name}\"**. **Any description for this board?** (or say 'skip')"

        state.collected_data = data
        state.save()
        return f"{demo_prefix}Let's create a new board! **What should the board be called?**"

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
                # Strip common command prefixes like "Add this description:" or "description: ..."
                desc = re.sub(
                    r'^(?:(?:add|set|use)\s+(?:this\s+)?description\s*[:;\-]?\s*'
                    r'|description\s*[:;\-]\s*)',
                    '', msg, flags=re.IGNORECASE,
                ).strip() or msg
                # Strip surrounding quotes (single, double, curly)
                desc = re.sub(r'^["\u201c\u2018\']+|["\u201d\u2019\']+$', '', desc).strip() or desc
                data['description'] = desc
                data['description_display'] = desc

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
            from kanban.utils.demo_protection import get_user_boards
            user_boards = list(
                get_user_boards(user).filter(
                    is_archived=False,
                )[:2]
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

        # ── RBAC pre-check: automations need owner access ────────────
        from ai_assistant.utils.rbac_utils import check_spectra_action_permission
        allowed, denial = check_spectra_action_permission(user, board, 'activate_automation')
        if not allowed:
            state.reset()
            return denial

        state.collected_data = {'step': 0, 'board_id': board.id, 'board_name': board.name}
        state.save()

        # Dynamically list available templates
        try:
            from kanban.automation_models import AutomationTemplate
            templates = list(AutomationTemplate.objects.filter(is_builtin=True).order_by('id').values_list('name', flat=True))
        except Exception:
            templates = []

        if templates:
            lines = [f"{i+1}. **{name}**" for i, name in enumerate(templates)]
            menu = "\n".join(lines)
        else:
            menu = (
                "1. **Mark overdue tasks as Urgent**\n"
                "2. **Notify creator when task is completed**\n"
                "3. **Alert assignee 2 days before deadline**"
            )

        return (
            "I can set up one of these automations for this board:\n\n"
            f"{menu}\n\n"
            "Which would you like? (say the number or describe what you need)"
        )

    def _continue_automation_flow(self, user, board, message, state):
        data = state.collected_data
        step = data.get('step', 0)
        msg = message.strip()

        if step == -1:
            # Awaiting board selection
            from kanban.utils.demo_protection import get_user_boards
            user_boards = list(
                get_user_boards(user).filter(
                    is_archived=False,
                )
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

            try:
                from kanban.automation_models import AutomationTemplate
                templates = list(AutomationTemplate.objects.filter(is_builtin=True).order_by('id').values_list('name', flat=True))
            except Exception:
                templates = []

            if templates:
                lines = [f"{i+1}. **{name}**" for i, name in enumerate(templates)]
                menu = "\n".join(lines)
            else:
                menu = (
                    "1. **Mark overdue tasks as Urgent**\n"
                    "2. **Notify creator when task is completed**\n"
                    "3. **Alert assignee 2 days before deadline**"
                )

            return (
                f"OK, I'll use **{board.name}**.\n\n"
                "I can set up one of these automations for this board:\n\n"
                f"{menu}\n\n"
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
                try:
                    from kanban.automation_models import AutomationTemplate
                    templates = list(AutomationTemplate.objects.filter(is_builtin=True).order_by('id').values_list('name', flat=True))
                    lines = [f"{i+1}. {name}" for i, name in enumerate(templates)]
                    menu = "\n".join(lines)
                except Exception:
                    menu = (
                        "1. Mark overdue tasks as Urgent\n"
                        "2. Notify creator when task is completed\n"
                        "3. Alert assignee 2 days before deadline"
                    )
                return (
                    f"I'm not sure which automation you mean. Could you pick a number?\n\n{menu}"
                )

        return self._format_automation_confirmation(
            data.get('template_number', 1),
            data.get('board_name', ''),
        )

    @staticmethod
    def _match_automation_template(text):
        """
        Try to match user text to a template.
        Returns a 1-based index, or ``None``.
        """
        t = text.lower().strip()

        # Direct number (1-10)
        try:
            num = int(t)
            from kanban.automation_models import AutomationTemplate
            count = AutomationTemplate.objects.filter(is_builtin=True).count()
            if 1 <= num <= max(count, 3):
                return num
        except (ValueError, Exception):
            pass

        word_map = {'one': 1, 'first': 1, 'two': 2, 'second': 2, 'three': 3, 'third': 3,
                    'four': 4, 'fourth': 4, 'five': 5, 'fifth': 5, 'six': 6, 'seventh': 7,
                    'eight': 8, 'nine': 9, 'ten': 10}
        if t in word_map:
            return word_map[t]

        # Keyword matching (covers the original 3 + common new ones)
        if any(w in t for w in ['overdue', 'urgent', 'escalate']):
            return 1
        if any(w in t for w in ['completed', 'done', 'creator', 'notify creator']):
            return 2
        if any(w in t for w in ['deadline', 'before', 'approaching', 'assignee', 'alert assignee', '2 day']):
            return 3

        # Try fuzzy match against template names
        try:
            from kanban.automation_models import AutomationTemplate
            templates = list(AutomationTemplate.objects.filter(is_builtin=True).order_by('id').values_list('name', flat=True))
            for i, name in enumerate(templates, 1):
                if t in name.lower() or name.lower() in t:
                    return i
        except Exception:
            pass

        return None

    # ------------------------------------------------------------------
    # FC-BASED flows (message, time entry, event, retrospective,
    #                 custom automation, scheduled automation)
    # ------------------------------------------------------------------

    _FC_NEW_MODES = frozenset({
        'collecting_message', 'collecting_time_entry',
        'collecting_event', 'collecting_retrospective',
        'collecting_task_update',
    })

    _FC_INTENT_META = {
        'send_message': {
            'mode': 'collecting_message',
            'pending': 'send_message',
            'label': 'sending a message',
            'needs_board': True,
        },
        'log_time': {
            'mode': 'collecting_time_entry',
            'pending': 'log_time',
            'label': 'logging time',
            'needs_board': True,
        },
        'schedule_event': {
            'mode': 'collecting_event',
            'pending': 'schedule_event',
            'label': 'scheduling an event',
            'needs_board': False,
        },
        'create_retrospective': {
            'mode': 'collecting_retrospective',
            'pending': 'create_retrospective',
            'label': 'creating a retrospective',
            'needs_board': True,
        },
        'create_automation': {
            'mode': 'collecting_automation',
            'pending': 'create_custom_automation',
            'label': 'creating an automation',
            'needs_board': True,
        },
        'create_scheduled_automation': {
            'mode': 'collecting_automation',
            'pending': 'create_scheduled_automation',
            'label': 'creating a scheduled automation',
            'needs_board': True,
        },
        'update_task': {
            'mode': 'collecting_task_update',
            'pending': 'update_task',
            'label': 'updating a task',
            'needs_board': True,
        },
        # Living Commitment Protocols — stateless (no collection needed)
        'get_commitment_status': {
            'mode': 'awaiting_confirmation',
            'pending': 'get_commitment_status',
            'label': 'getting commitment status',
            'needs_board': True,
            'immediate': True,   # skip confirmation, execute right away
        },
        'list_at_risk_commitments': {
            'mode': 'awaiting_confirmation',
            'pending': 'list_at_risk_commitments',
            'label': 'listing at-risk commitments',
            'needs_board': True,
            'immediate': True,
        },
        'place_commitment_bet': {
            'mode': 'awaiting_confirmation',
            'pending': 'place_commitment_bet',
            'label': 'placing a commitment bet',
            'needs_board': True,
        },
    }

    def _start_fc_flow(self, user, board, message, state, intent):
        """
        Generic entry point for all FC-based action flows.

        Sends the user message + compact context to Flash with Function Calling.
        If the model returns a function_call, we store the args and go to
        confirmation.  If it returns text, that's a follow-up question.
        """
        meta = self._FC_INTENT_META.get(intent)
        if not meta:
            return None  # caller falls through to Q&A

        # Board requirement check — try last-used board before asking
        if meta['needs_board'] and board is None:
            is_demo = getattr(self, '_is_demo_mode', False)
            board = self._get_last_board(user, is_demo)
            if board is None:
                board = self._auto_select_board(user)
            if board is None:
                boards = _user_board_names(user)
                if boards:
                    board_list = ', '.join(f'**{b}**' for b in boards)
                    state.mode = meta['mode']
                    state.pending_action = meta['pending']
                    state.collected_data = {
                        'awaiting_board': True,
                        'original_message': message,
                    }
                    state.save()
                    return (
                        f"I'd love to help with **{meta['label']}**, but I need a board. "
                        f"Please select one from the dropdown above.\n\n"
                        f"Your boards: {board_list}"
                    )
                return (
                    f"I'd love to help with **{meta['label']}**, but you don't have any boards yet. "
                    "Would you like to **create a board** first?"
                )

        # Build compact context and call Flash FC
        from ai_assistant.utils.spectra_tools import get_action_tools, FUNCTION_TO_ACTION
        from ai_assistant.utils.ai_clients import GeminiClient

        # ── RBAC pre-check before engaging the FC model ──────────────
        from ai_assistant.utils.rbac_utils import check_spectra_action_permission
        allowed, denial = check_spectra_action_permission(
            user, board, meta['pending'],
        )
        if not allowed:
            state.reset()
            return denial

        context = build_fc_context(user, board)
        tools = get_action_tools()
        client = GeminiClient()
        result = client.get_function_call_response(message, context, tools)

        if result.get('error'):
            logger.error(f"FC flow error: {result['error']}")
            return (
                "I ran into a problem understanding that request. "
                "Could you try rephrasing it?"
            )

        if result.get('function_call'):
            fc = result['function_call']
            pending = FUNCTION_TO_ACTION.get(fc['name'], meta['pending'])
            data = dict(fc['args'])
            data['_fc_function'] = fc['name']
            if board:
                data['board_id'] = board.id
                data['board_name'] = board.name

            # Immediate (stateless) actions — execute without a confirmation step
            if meta.get('immediate'):
                state.reset()
                method_map = {
                    'get_commitment_status': 'get_commitment_status',
                    'list_at_risk_commitments': 'list_at_risk_commitments',
                }
                method_name = method_map.get(pending)
                if method_name and hasattr(action_service, method_name):
                    result_exec = getattr(action_service, method_name)(user, board, data)
                    return result_exec.get('message', '✅ Done!') if result_exec.get('success') else f"Error: {result_exec.get('error')}"
                return "Couldn't execute that query right now."

            state.mode = 'awaiting_confirmation'
            state.pending_action = pending
            data['_original_message'] = message
            state.collected_data = data
            state.save()
            return self._format_fc_confirmation(pending, data)

        # Model returned text — it needs more info
        state.mode = meta['mode']
        state.pending_action = meta['pending']
        state.collected_data = {
            'history': [f"User: {message}", f"Spectra: {result.get('text', '')}"],
        }
        if board:
            state.collected_data['board_id'] = board.id
            state.collected_data['board_name'] = board.name
        state.save()
        return result.get('text', "Could you provide a few more details?")

    def _continue_fc_flow(self, user, board, message, state):
        """
        Continue an FC-based flow when the model previously asked a follow-up.
        Re-sends the full conversation history to Flash FC.
        """
        data = state.collected_data

        # ── Task disambiguation sub-step ────────────────────────────────
        if data.get('awaiting_task_disambiguation'):
            candidates = data.get('task_candidates', [])
            msg = message.strip()
            matched = None

            # Try numeric pick first ("1", "2", ...)
            if msg.isdigit():
                idx = int(msg) - 1
                if 0 <= idx < len(candidates):
                    matched = candidates[idx]
            # Then try name matching
            if not matched:
                msg_lower = msg.lower()
                for c in candidates:
                    if msg_lower == c['title'].lower() or msg_lower in c['title'].lower():
                        matched = c
                        break
            # Fuzzy: check if any candidate name is contained in the message
            if not matched:
                for c in candidates:
                    if c['title'].lower() in msg_lower:
                        matched = c
                        break

            if matched:
                # Update task_name to the exact title and re-show confirmation
                data.pop('awaiting_task_disambiguation')
                data.pop('task_candidates', None)
                data['task_name'] = matched['title']
                state.mode = 'awaiting_confirmation'
                state.collected_data = data
                state.save()
                return self._format_fc_confirmation(state.pending_action, data)
            else:
                names_list = '\n'.join(
                    f'{i+1}. **{c["title"]}**' for i, c in enumerate(candidates)
                )
                return (
                    f"Sorry, I couldn't match that. Please pick one:\n\n{names_list}"
                )

        # Handle board selection if we were waiting for it
        if data.get('awaiting_board'):
            board = self._resolve_board_from_reply(user, message)
            if board is None:
                boards = _user_board_names(user)
                board_list = ', '.join(f'**{b}**' for b in boards) if boards else 'None'
                return (
                    f"I couldn't find a board matching **\"{message}\"**. "
                    f"Choose one of: {board_list}"
                )
            data.pop('awaiting_board', None)
            original = data.pop('original_message', message)
            data['board_id'] = board.id
            data['board_name'] = board.name
            self._remember_board(state, board)
            state.collected_data = data
            state.save()
            # Re-run the original message now that we have a board
            return self._start_fc_flow(
                user, board, original, state,
                self._pending_to_intent(state.pending_action),
            )

        # Resolve board from stored data
        if board is None and data.get('board_id'):
            from kanban.models import Board
            try:
                board = Board.objects.get(id=data['board_id'])
            except Board.DoesNotExist:
                state.reset()
                return "The board no longer exists. Please try again."

        from ai_assistant.utils.spectra_tools import get_action_tools, FUNCTION_TO_ACTION
        from ai_assistant.utils.ai_clients import GeminiClient

        context = build_fc_context(user, board)
        tools = get_action_tools()
        history = data.get('history', [])
        history.append(f"User: {message}")

        client = GeminiClient()
        result = client.get_function_call_response(
            message, context, tools, conversation_history=history,
        )

        if result.get('error'):
            logger.error(f"FC continue error: {result['error']}")
            return "Something went wrong. Could you rephrase that?"

        if result.get('function_call'):
            fc = result['function_call']
            meta = self._FC_INTENT_META.get(
                self._pending_to_intent(state.pending_action), {}
            )
            pending = FUNCTION_TO_ACTION.get(fc['name'], state.pending_action)
            new_data = dict(fc['args'])
            new_data['_fc_function'] = fc['name']
            if board:
                new_data['board_id'] = board.id
                new_data['board_name'] = board.name

            state.mode = 'awaiting_confirmation'
            state.pending_action = pending
            state.collected_data = new_data
            state.save()
            return self._format_fc_confirmation(pending, new_data)

        # Still asking follow-up
        follow_up = result.get('text', "Could you give me a bit more detail?")
        history.append(f"Spectra: {follow_up}")
        data['history'] = history
        state.collected_data = data
        state.save()
        return follow_up

    @staticmethod
    def _auto_select_board(user):
        """Return the user's sole board, or None."""
        from kanban.utils.demo_protection import get_user_boards
        boards = list(
            get_user_boards(user).filter(
                is_archived=False,
            )[:2]
        )
        return boards[0] if len(boards) == 1 else None

    @staticmethod
    def _resolve_board_from_reply(user, message):
        """Try to match a user reply to one of their boards."""
        from kanban.utils.demo_protection import get_user_boards
        user_boards = list(
            get_user_boards(user).filter(
                is_archived=False,
            )
        )
        msg_lower = message.lower().strip()
        for b in user_boards:
            if b.name.lower() == msg_lower or b.name.lower() in msg_lower:
                return b
        for b in user_boards:
            if msg_lower in b.name.lower():
                return b
        return None

    @staticmethod
    def _pending_to_intent(pending_action):
        """Map pending_action back to an intent key."""
        _map = {
            'create_task': 'create_task',
            'create_board': 'create_board',
            'activate_automation': 'activate_automation',
            'send_message': 'send_message',
            'log_time': 'log_time',
            'schedule_event': 'schedule_event',
            'create_retrospective': 'create_retrospective',
            'create_custom_automation': 'create_automation',
            'create_scheduled_automation': 'create_scheduled_automation',
            'update_task': 'update_task',
            'get_commitment_status': 'get_commitment_status',
            'list_at_risk_commitments': 'list_at_risk_commitments',
            'place_commitment_bet': 'place_commitment_bet',
        }
        return _map.get(pending_action, 'conversation')

    # ── FC confirmation formatters ────────────────────────────────────

    def _format_fc_confirmation(self, pending, data):
        """Build a human-readable confirmation for any FC-extracted action."""
        formatters = {
            'send_message': self._format_message_confirmation,
            'log_time': self._format_time_confirmation,
            'schedule_event': self._format_event_confirmation,
            'create_retrospective': self._format_retro_confirmation,
            'create_custom_automation': self._format_custom_auto_confirmation,
            'create_scheduled_automation': self._format_sched_auto_confirmation,
            'place_commitment_bet': self._format_commitment_bet_confirmation,
            'update_task': self._format_update_task_confirmation,
        }
        formatter = formatters.get(pending)
        if formatter:
            return formatter(data)
        # Fallback for task/board (shouldn't normally reach here)
        return (
            "Here's what I'll do:\n\n"
            + '\n'.join(f"**{k}:** {v}" for k, v in data.items() if not k.startswith('_'))
            + "\n\nType **confirm** to proceed, or tell me what to change."
        )

    @staticmethod
    def _format_message_confirmation(data):
        return (
            "Here's the message I'll send:\n\n"
            f"👤 **To:** {data.get('recipient', 'Unknown')}\n"
            f"💬 **Message:** {data.get('message_content', '')}\n\n"
            "Type **confirm** to send, or tell me what to change."
        )

    @staticmethod
    def _format_time_confirmation(data):
        return (
            "Here's the time entry I'll log:\n\n"
            f"📋 **Task:** {data.get('task_name', 'Unknown')}\n"
            f"⏱️ **Hours:** {data.get('hours', 0)}\n"
            f"📅 **Date:** {data.get('work_date', 'Today')}\n"
            f"📝 **Description:** {data.get('description', 'None')}\n\n"
            "Type **confirm** to log this, or tell me what to change."
        )

    @staticmethod
    def _format_event_confirmation(data):
        participants = data.get('participants', [])
        if isinstance(participants, list):
            participants = ', '.join(participants) if participants else 'None'
        return (
            "Here's the event I'll schedule:\n\n"
            f"📅 **Event:** {data.get('title', 'Untitled')}\n"
            f"🕐 **Start:** {data.get('start_datetime', 'Not set')}\n"
            f"🕑 **End:** {data.get('end_datetime', '1 hour after start')}\n"
            f"📍 **Location:** {data.get('location', 'Not set')}\n"
            f"👥 **Participants:** {participants}\n"
            f"📝 **Type:** {data.get('event_type', 'meeting')}\n\n"
            "Type **confirm** to schedule, or tell me what to change."
        )

    @staticmethod
    def _format_retro_confirmation(data):
        return (
            "Here's the retrospective I'll generate:\n\n"
            f"📊 **Type:** {data.get('retrospective_type', 'sprint').capitalize()}\n"
            f"📅 **Period:** {data.get('period_start', '?')} → {data.get('period_end', '?')}\n"
            f"📝 **Notes:** {data.get('manual_insights', 'None')}\n"
            f"📁 **Board:** {data.get('board_name', 'Current board')}\n\n"
            "⏳ *Note: Generation may take a few seconds as I analyze board activity.*\n\n"
            "Type **confirm** to generate, or tell me what to change."
        )

    @staticmethod
    def _format_custom_auto_confirmation(data):
        return (
            "Here's the automation I'll create:\n\n"
            f"⚡ **Name:** {data.get('name', 'Untitled')}\n"
            f"🎯 **Trigger:** {data.get('trigger_type', '?')}"
            f"{' (' + data['trigger_value'] + ')' if data.get('trigger_value') else ''}\n"
            f"🔔 **Action:** {data.get('action_type', '?')}"
            f"{' (' + data['action_value'] + ')' if data.get('action_value') else ''}\n"
            f"📁 **Board:** {data.get('board_name', 'Current board')}\n\n"
            "Type **confirm** to create, or tell me what to change."
        )

    @staticmethod
    def _format_sched_auto_confirmation(data):
        return (
            "Here's the scheduled automation I'll create:\n\n"
            f"⚡ **Name:** {data.get('name', 'Untitled')}\n"
            f"🕐 **Schedule:** {data.get('schedule_type', 'daily')}"
            f" at {data.get('scheduled_time', '09:00')}\n"
            f"🔔 **Action:** {data.get('action', '?')}\n"
            f"🎯 **Target:** {data.get('notify_target', 'board_members')}\n"
            f"📋 **Filter:** {data.get('task_filter', 'all')} tasks\n"
            f"📁 **Board:** {data.get('board_name', 'Current board')}\n\n"
            "Type **confirm** to create, or tell me what to change."
        )

    @staticmethod
    def _format_commitment_bet_confirmation(data):
        return (
            "Here's the commitment bet I'll place:\n\n"
            f"🎯 **Commitment ID:** {data.get('commitment_id', '?')}\n"
            f"📊 **Your predicted confidence:** {data.get('predicted_confidence', '?')}%\n"
            f"🪙 **Tokens to wager:** {data.get('tokens_wagered', 1)}\n"
            f"📁 **Board:** {data.get('board_name', 'Current board')}\n\n"
            "Type **confirm** to place the bet, or **cancel** to abort."
        )

    @staticmethod
    def _format_update_task_confirmation(data):
        field_labels = {
            'status': '📊 Move to', 'priority': '⚡ New priority',
            'assignee': '👤 Reassign to', 'due_date': '📅 New due date',
            'title': '✏️ Rename to', 'description': '📝 New description',
        }
        field = data.get('field', '?')
        label = field_labels.get(field, f'🔧 {field}')
        return (
            "Here's the task update I'll apply:\n\n"
            f"📋 **Task:** {data.get('task_name', 'Unknown')}\n"
            f"{label}: **{data.get('new_value', '?')}**\n"
            f"📁 **Board:** {data.get('board_name', 'Current board')}\n\n"
            "Type **confirm** to apply, or tell me what to change."
        )

    def _handle_collecting(self, user, board, message, state):
        """Route to the correct continuation handler based on state mode."""
        # First check if user wants to cancel mid-flow
        intent = detect_action_intent(message)
        if intent == 'cancel_action':
            return self._handle_cancellation(state)

        # If regex found nothing but the message looks like a command (not a
        # short single-word reply like "Sam", "skip", or "1"), ask the AI
        # classifier whether it's a different action intent.
        if intent is None and len(message.strip()) > 15:
            from ai_assistant.utils.ai_clients import GeminiClient
            try:
                client = GeminiClient()
            except Exception:
                client = None
            ai_cls = classify_intent_with_ai(message, gemini_client=client)
            if ai_cls['intent'] not in ('conversation', 'confirm_action', 'cancel_action'):
                intent = ai_cls['intent']

        # If the user repeats the same action intent that matches the
        # current flow, restart that flow instead of blocking them.
        _INTENT_TO_MODE = {
            'create_task': 'collecting_task',
            'create_board': 'collecting_board',
            'activate_automation': 'collecting_automation',
            'send_message': 'collecting_message',
            'log_time': 'collecting_time_entry',
            'schedule_event': 'collecting_event',
            'create_retrospective': 'collecting_retrospective',
            'create_automation': 'collecting_automation',
            'create_scheduled_automation': 'collecting_automation',
            'update_task': 'collecting_task_update',
        }
        if intent and intent not in ('confirm_action', 'cancel_action'):
            expected_mode = _INTENT_TO_MODE.get(intent)
            if expected_mode == state.mode:
                # Same intent — restart the flow from scratch
                state.reset()
                if intent == 'create_task':
                    return self._start_task_flow(user, board, message, state)
                if intent == 'create_board':
                    return self._start_board_flow(user, message, state)
                if intent == 'activate_automation':
                    return self._start_automation_flow(user, board, message, state)
                # FC-based intents
                if intent in self._FC_INTENT_META:
                    return self._start_fc_flow(user, board, message, state, intent)
            else:
                # Different action intent — warn the user
                flow_name = {
                    'collecting_task': 'creating a task',
                    'collecting_board': 'creating a board',
                    'collecting_automation': 'setting up an automation',
                    'collecting_message': 'sending a message',
                    'collecting_time_entry': 'logging time',
                    'collecting_event': 'scheduling an event',
                    'collecting_retrospective': 'creating a retrospective',
                    'collecting_task_update': 'updating a task',
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
            # Distinguish template-based vs FC-based automation flows.
            # FC flow stores 'awaiting_board' or 'history'; template flow stores 'step'.
            cd = state.collected_data or {}
            if cd.get('awaiting_board') or cd.get('history') or cd.get('_fc_function'):
                return self._continue_fc_flow(user, board, message, state)
            return self._continue_automation_flow(user, board, message, state)

        # FC-based modes
        if state.mode in self._FC_NEW_MODES:
            return self._continue_fc_flow(user, board, message, state)

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
            pending = state.pending_action
            data = state.collected_data

            # Try to detect which specific field the user wants to change
            if pending == 'create_task':
                if any(f in msg_lower for f in ['name', 'title', 'called']):
                    data['step'] = 0
                    data.pop('title', None)
                    state.mode = 'collecting_task'
                    state.collected_data = data
                    state.save()
                    return "OK. **What should the task be called?**"
                if any(f in msg_lower for f in ['due', 'date', 'deadline']):
                    data['step'] = 1
                    state.mode = 'collecting_task'
                    state.collected_data = data
                    state.save()
                    return "OK. **What due date?** (e.g. 'next Friday' or 'skip')"
                if any(f in msg_lower for f in ['assign', 'assignee', 'person', 'member']):
                    data['step'] = 2
                    state.mode = 'collecting_task'
                    state.collected_data = data
                    state.save()
                    return "OK. **Who should this be assigned to?** (Type a name or 'skip')"
                if any(f in msg_lower for f in ['priority']):
                    # Extract new priority inline: "change priority to high"
                    new_p = None
                    for p in ('low', 'medium', 'high', 'urgent'):
                        if p in msg_lower:
                            new_p = p
                            break
                    if new_p:
                        data['priority'] = new_p
                        state.collected_data = data
                        state.mode = 'awaiting_confirmation'
                        state.save()
                        return self._format_task_confirmation(data)
                    # Ask for priority without restarting
                    data['_awaiting_priority_change'] = True
                    state.mode = 'collecting_task'
                    state.collected_data = data
                    state.save()
                    return (
                        "What priority would you like? "
                        "Options: **Low**, **Medium**, **High**, or **Urgent**."
                    )
                # Fallback: restart from beginning
                data['step'] = 0
                data.pop('title', None)
                state.mode = 'collecting_task'
                state.collected_data = data
                state.save()
                return "OK, let's start over. **What should the task be called?**"
            elif pending == 'create_board':
                if any(f in msg_lower for f in ['name', 'title', 'called']):
                    data['step'] = 0
                    data.pop('name', None)
                    state.mode = 'collecting_board'
                    state.collected_data = data
                    state.save()
                    return "OK. **What should the board be called?**"
                if any(f in msg_lower for f in ['desc', 'description']):
                    data['step'] = 1
                    state.mode = 'collecting_board'
                    state.collected_data = data
                    state.save()
                    return "OK. **What description would you like?** (or say 'skip')"
                # Fallback: restart from beginning
                data['step'] = 0
                data.pop('name', None)
                state.mode = 'collecting_board'
                state.collected_data = data
                state.save()
                return "OK, let's start over. **What should the board be called?**"
            elif pending == 'activate_automation':
                state.mode = 'collecting_automation'
                data['step'] = 0
                state.collected_data = data
                state.save()
                return (
                    "OK, which automation would you prefer?\n\n"
                    "1. Mark overdue tasks as Urgent\n"
                    "2. Notify creator when task is completed\n"
                    "3. Alert assignee 2 days before deadline"
                )
            elif pending in (
                'send_message', 'log_time', 'schedule_event',
                'create_retrospective', 'create_custom_automation',
                'create_scheduled_automation', 'update_task',
            ):
                # FC-based actions: restart the FC flow with the change request
                intent = self._pending_to_intent(pending)
                meta = self._FC_INTENT_META.get(intent, {})
                mode = meta.get('mode', 'normal')
                state.mode = mode
                state.collected_data = {
                    'history': [f"User: {message}"],
                }
                if data.get('board_id'):
                    state.collected_data['board_id'] = data['board_id']
                    state.collected_data['board_name'] = data.get('board_name', '')
                state.save()
                return self._continue_fc_flow(user, board, message, state)

        # Before falling back, check if the user is starting a completely
        # different action (e.g. "Tell Sam the meeting was moved to 3 PM"
        # while confirming a task-create).
        if len(message.strip()) > 15:
            from ai_assistant.utils.ai_clients import GeminiClient
            try:
                client = GeminiClient()
            except Exception:
                client = None
            ai_cls = classify_intent_with_ai(message, gemini_client=client)
            new_intent = ai_cls.get('intent')
            if new_intent and new_intent not in (
                'conversation', 'confirm_action', 'cancel_action'
            ):
                # Abandon the pending action and start the new flow
                state.reset()
                if new_intent == 'create_task':
                    return self._start_task_flow(user, board, message, state)
                if new_intent == 'create_board':
                    return self._start_board_flow(user, message, state)
                if new_intent == 'activate_automation':
                    return self._start_automation_flow(user, board, message, state)
                if new_intent in self._FC_INTENT_META:
                    return self._start_fc_flow(user, board, message, state, new_intent)

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

        # ── Final RBAC gate before executing any write ───────────────
        # Resolve the board if we don't have it yet (from collected_data)
        exec_board = board
        if exec_board is None and data.get('board_id'):
            from kanban.models import Board
            try:
                exec_board = Board.objects.get(id=data['board_id'])
            except Board.DoesNotExist:
                pass

        from ai_assistant.utils.rbac_utils import check_spectra_action_permission
        allowed, denial = check_spectra_action_permission(user, exec_board, pending)
        if not allowed:
            state.reset()
            return denial

        if pending == 'create_task':
            return self._execute_task_creation(user, board, state, data)
        elif pending == 'create_board':
            return self._execute_board_creation(user, state, data)
        elif pending == 'activate_automation':
            return self._execute_automation(user, board, state, data)
        elif pending in (
            'send_message', 'log_time', 'schedule_event',
            'create_retrospective', 'create_custom_automation',
            'create_scheduled_automation', 'update_task',
        ):
            return self._execute_fc_action(user, board, state, data)
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

        # Persist the board for future context
        self._remember_board(state, board)

        # Check for compound action before resetting
        second_action = self._extract_second_action(data)

        state.reset()

        if result['success']:
            task = result['task']
            url = result['url']

            # Remember this artifact for cross-session context
            self._remember_artifact(user, 'task', {
                'name': task.title, 'id': task.id,
                'board': board.name, 'board_id': board.id,
            })

            # Let the user know the task lives in demo workspace
            demo_note = ''
            if getattr(self, '_is_demo_mode', False):
                demo_note = (
                    "\n\n📌 This task was created inside **Demo Workspace** "
                    "so you can experiment freely."
                )

            # Proactive insight: workload check for assignee
            insight = ''
            if task.assigned_to:
                try:
                    from kanban.models import Task as TaskModel
                    open_count = TaskModel.objects.filter(
                        assigned_to=task.assigned_to,
                        column__board=board,
                        is_archived=False,
                    ).exclude(
                        column__position=board.columns.count() - 1,
                    ).count()
                    if open_count > 5:
                        name = task.assigned_to.get_full_name() or task.assigned_to.username
                        insight = (
                            f"\n\n💡 **Heads up:** {name} currently has "
                            f"**{open_count} open tasks** on this board."
                        )
                except Exception:
                    pass

            return (
                f"✅ **Task created successfully!**\n\n"
                f"📋 **{task.title}** has been added to **{board.name}** "
                f"in the **{task.column.name}** column.\n\n"
                f"[View task]({url}){demo_note}{insight}"
                + (f"\n\n💬 I also noticed you wanted to **{second_action}** — just say the word!" if second_action else '')
            )
        else:
            return (
                f"Something went wrong while creating that task. Please try again, "
                f"or create it manually from the board.\n\n"
                f"The error was: {result['error']}"
            )

    # ── Execute: Board ────────────────────────────────────────────────

    def _execute_board_creation(self, user, state, data):
        is_demo = getattr(self, '_is_demo_mode', False)
        create_data = {
            'name': data.get('name', 'Untitled Board'),
            'description': data.get('description', ''),
        }

        result = action_service.create_board(user, create_data, is_demo_mode=is_demo)

        state.reset()

        if result['success']:
            board_obj = result['board']
            url = result['url']

            # Remember this artifact
            self._remember_artifact(user, 'board', {
                'name': board_obj.name, 'id': board_obj.id,
            })

            env_note = ''
            if is_demo:
                env_note = (
                    "\n\n📌 This board was created inside **Demo Workspace** "
                    "so you can experiment freely. It won't appear in your "
                    "personal workspace."
                )

            return (
                f"✅ **Board created successfully!**\n\n"
                f"🗂️ **{board_obj.name}** is ready with columns: "
                f"To Do → In Progress → Done.\n\n"
                f"[Open board]({url}){env_note}"
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

    # ── Execute: FC-based actions ─────────────────────────────────────

    def _execute_fc_action(self, user, board, state, data):
        """Execute any FC-based action by delegating to action_service."""
        from kanban.models import Board

        pending = state.pending_action

        # Resolve board from stored data if not provided
        if board is None and data.get('board_id'):
            try:
                board = Board.objects.get(id=data['board_id'])
            except Board.DoesNotExist:
                state.reset()
                return "The board no longer exists. Please try again."

        if board is None and pending not in ('schedule_event',):
            state.reset()
            return (
                "I need a board for this action. "
                "Please select a board from the dropdown above and try again."
            )

        # Dispatch to the appropriate action_service method
        method_map = {
            'send_message': 'send_message',
            'log_time': 'log_time_entry',
            'schedule_event': 'schedule_event',
            'create_retrospective': 'create_retrospective',
            'create_custom_automation': 'create_custom_automation',
            'create_scheduled_automation': 'create_scheduled_automation',
            'update_task': 'update_task',
            # Living Commitment Protocols
            'get_commitment_status': 'get_commitment_status',
            'list_at_risk_commitments': 'list_at_risk_commitments',
            'place_commitment_bet': 'place_commitment_bet',
        }

        method_name = method_map.get(pending)
        if not method_name or not hasattr(action_service, method_name):
            state.reset()
            return "I'm not sure how to execute that action. Let's start over."

        method = getattr(action_service, method_name)
        result = method(user, board, data)

        if result.get('success'):
            # Persist the board for future interactions
            if board:
                self._remember_board(state, board)
            msg = result.get('message', '✅ Done!')

            # Check for compound action: did the original message contain
            # a second action clause after "and then", "then", "also"?
            second_action = self._extract_second_action(data)
            if second_action:
                msg += f"\n\n💬 I also noticed you wanted to **{second_action}** — just say the word and I'll help with that next!"

            state.reset()
            return msg

        # ── Task disambiguation — don't reset state, ask user to pick ──
        if result.get('disambiguation_needed'):
            candidates = result['candidates']  # list of {'id', 'title'}
            data['awaiting_task_disambiguation'] = True
            data['task_candidates'] = candidates
            # Keep pending_action intact; switch to FC collecting mode so
            # the next message routes through _continue_fc_flow
            fc_mode_map = {
                'log_time': 'collecting_time_entry',
                'send_message': 'collecting_message',
            }
            state.mode = fc_mode_map.get(pending, 'collecting_time_entry')
            state.collected_data = data
            state.save()
            names_list = '\n'.join(
                f'{i+1}. **{c["title"]}**' for i, c in enumerate(candidates)
            )
            return (
                f"I found multiple tasks that could match. Which one did you mean?\n\n"
                f"{names_list}\n\n"
                "Just type the number or the task name."
            )

        state.reset()
        error = result.get('error', 'Unknown error')
        # Surface a friendlier message for common resolvable errors
        if pending == 'send_message' and 'Could not find' in error:
            return f"❌ {error}\n\nTry again with one of the names listed, or say **cancel** to stop."
        return f"Something went wrong: {error}. Please try again."

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
            f"📁 **Board:** {board_name or 'Current board'}\n\n"
            "Type **confirm** to activate this automation, or say **cancel**."
        )
