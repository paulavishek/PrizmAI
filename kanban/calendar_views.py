"""
Unified cross-board calendar views for PrizmAI.

Provides:
- unified_calendar          — renders the full-page calendar
- unified_calendar_events_api — JSON feed for FullCalendar (tasks + events)
- calendar_create_task      — AJAX: create a task from the calendar
- calendar_create_event     — AJAX: create a CalendarEvent from the calendar
- calendar_get_board_columns — AJAX: return columns for a board (for task modal)
- calendar_event_detail     — view/edit a CalendarEvent
- calendar_event_delete     — delete a CalendarEvent
"""

import json
import logging
import zoneinfo
from datetime import datetime, timedelta
from django.conf import settings

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET

from django.db.models import Max

from .models import Board, Column, Task, TaskActivity, CalendarEvent
from .decorators import demo_write_guard

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_boards(user):
    """Return boards visible to the user, respecting demo/real workspace mode."""
    from kanban.utils.demo_protection import get_user_boards
    return get_user_boards(user).order_by('name')


def _teammate_boards(user, base_boards):
    """Boards whose membership decides who the user shares "Team can see I'm busy"
    visibility with.

    In a real workspace this is just the boards the user owns/belongs to
    (``base_boards``).  In DEMO mode every user — the real prospect *and* each
    demo persona — owns a *separate* sandbox copy of the same template board, and
    ``get_user_boards()`` only returns boards the user OWNS.  That makes the
    teammate relationship asymmetric: a persona is a member of the real user's
    sandbox board but never counts the real user as a teammate, so the real
    user's team-visible blocks never reach the persona.  To keep the promise
    symmetric we widen to every sandbox board the user is a *member* of, not just
    the ones they own.  Real users still never see other real users (a real user
    is not a member of another real user's sandbox board); only the shared
    persona accounts gain visibility into active demo prospects' busy blocks,
    which is demo-only data.
    """
    profile = getattr(user, 'profile', None)
    if getattr(profile, 'is_viewing_demo', False):
        from kanban.models import Board
        return Board.objects.filter(
            Q(owner=user) | Q(memberships__user=user),
            is_sandbox_copy=True,
        ).distinct()
    return base_boards


def _create_notification(recipient, sender, notification_type, text, action_url=None):
    """Safely create a messaging.Notification, swallowing any import/save errors."""
    try:
        from messaging.models import Notification
        Notification.objects.create(
            recipient=recipient,
            sender=sender,
            notification_type=notification_type,
            text=text,
            action_url=action_url,
        )
    except Exception as exc:
        logger.warning("Failed to create notification: %s", exc)


def _priority_color(priority):
    return {
        'urgent': '#dc3545',
        'high':   '#fd7e14',
        'medium': '#0d6efd',
        'low':    '#198754',
    }.get(priority, '#6c757d')


# ---------------------------------------------------------------------------
# Assignee colour palette — completely distinct from priority colours
# Avoids: #dc3545 red, #fd7e14 orange, #0d6efd blue, #198754 green, #6c757d grey
# ---------------------------------------------------------------------------
_ASSIGNEE_PALETTE = [
    '#7c3aed',  # violet
    '#db2777',  # hot pink
    '#0891b2',  # teal
    '#ca8a04',  # golden yellow
    '#c026d3',  # fuchsia
    '#0f766e',  # dark teal
    '#b45309',  # amber brown
    '#4338ca',  # indigo
    '#be185d',  # deep rose
    '#0369a1',  # steel blue
]
_UNASSIGNED_COLOR = '#9ca3af'  # neutral grey for unassigned tasks


def _assignee_color(user_id):
    """Return a deterministic, palette-based colour for a given user_id."""
    if user_id is None:
        return _UNASSIGNED_COLOR
    return _ASSIGNEE_PALETTE[user_id % len(_ASSIGNEE_PALETTE)]


# Characters that are safe in JSON but break (or escape) an inline <script>:
#   <, >, &  → a title like "</script>" would terminate the tag and dump the
#             rest of the script onto the page (also a stored-XSS vector).
#   U+2028/U+2029 → line separators, historically invalid in JS string literals.
# Mirrors Django's own ``json_script`` escaping so user-supplied board/task names
# can be embedded with ``|safe`` without breaking the page.
_JSON_SCRIPT_ESCAPES = {
    ord('<'): '\\u003C',
    ord('>'): '\\u003E',
    ord('&'): '\\u0026',
    0x2028: '\\u2028',
    0x2029: '\\u2029',
}


def _json_for_script(obj):
    """``json.dumps`` an object, escaped for safe embedding inside a <script> tag."""
    return json.dumps(obj).translate(_JSON_SCRIPT_ESCAPES)


def _event_workspace_scope(user):
    """A ``Q`` limiting CalendarEvents to the user's current workspace mode.

    CalendarEvent has no workspace field, so the only reliable anchor is the
    event's board: demo events live on sandbox (or template) boards, real events
    on real boards.  Without this, the "my own events" visibility clause
    (``created_by=user``) would surface a user's *demo* events in their real
    workspace and vice-versa.  Board-less events have no workspace anchor, so
    they are treated as personal/real and never shown inside demo mode.
    """
    profile = getattr(user, 'profile', None)
    if getattr(profile, 'is_viewing_demo', False):
        return Q(board__is_sandbox_copy=True) | Q(board__is_official_demo_board=True)
    return (
        Q(board__isnull=True) |
        Q(board__is_sandbox_copy=False, board__is_official_demo_board=False)
    )


# ---------------------------------------------------------------------------
# Main calendar page
# ---------------------------------------------------------------------------

@login_required
def unified_calendar(request):
    boards = _user_boards(request.user)

    # Build a list of board dicts for the JS board-selector in the "create task"
    # modal — and the per-board member ids so the Teammates filter can be scoped
    # to whichever board the user has selected (the chips filter the calendar to a
    # single board; the teammate list should follow).
    from collections import defaultdict
    board_member_map = defaultdict(set)
    for bid, uid in User.objects.filter(
        board_memberships__board__in=boards
    ).values_list('board_memberships__board_id', 'id'):
        board_member_map[bid].add(uid)

    boards_data = []
    for b in boards:
        columns = list(b.columns.order_by('position').values('id', 'name'))
        members = board_member_map[b.id]
        if b.created_by_id:  # owner is always a member of their own board
            members = members | {b.created_by_id}
        boards_data.append({
            'id': b.id, 'name': b.name, 'columns': columns,
            'members': sorted(members),
        })

    # Gather all board members across user's boards for participant typeahead
    participant_qs = User.objects.filter(
        Q(board_memberships__board__in=boards) | Q(created_boards__in=boards)
    ).exclude(id=request.user.id).distinct().order_by('username')
    participants_data = [
        {'id': u.id, 'username': u.username,
         'display': u.get_full_name() or u.username}
        for u in participant_qs
    ]

    # Teammates list with assigned colours (for filter chips & availability mode)
    # Current user is listed first so they can filter their own tasks too
    _me_display = request.user.get_full_name() or request.user.username
    teammates_data = [
        {
            'id': request.user.id,
            'username': request.user.username,
            'display': f'{_me_display} (You)',
            'color': _assignee_color(request.user.id),
        }
    ] + [
        {
            'id': u.id,
            'username': u.username,
            'display': u.get_full_name() or u.username,
            'color': _assignee_color(u.id),
        }
        for u in participant_qs
    ]

    # Quick stats (current calendar month)
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    import calendar as _cal
    _, last_day = _cal.monthrange(now.year, now.month)
    month_end = now.replace(day=last_day, hour=23, minute=59, second=59)

    user_tasks_qs = Task.objects.filter(
        column__board__in=boards,
        item_type='task',
        due_date__isnull=False,
    ).distinct()

    total_tasks = user_tasks_qs.count()
    overdue_count = user_tasks_qs.filter(
        due_date__lt=now, progress__lt=100
    ).count()
    events_this_month = CalendarEvent.objects.filter(
        Q(created_by=request.user) | Q(participants=request.user),
        start_datetime__range=(month_start, month_end),
    ).filter(_event_workspace_scope(request.user)).distinct().count()

    # Build a flat task list for the "linked task" dropdown in the event form
    _all_tasks = []
    for _t in Task.objects.filter(
        column__board__in=boards, item_type='task',
    ).select_related('column__board').order_by('column__board__name', 'title'):
        _all_tasks.append({'id': _t.id, 'title': _t.title, 'board_name': _t.column.board.name})

    # Optional pre-filter: ?board=<id> scopes the calendar to a single board
    # (used by each board's "Calendar" tab so it lands here pre-scoped).
    active_board_ids = []
    _board_param = request.GET.get('board')
    if _board_param and _board_param.isdigit():
        if boards.filter(id=int(_board_param)).exists():
            active_board_ids = [_board_param]

    context = {
        'boards': boards,
        'active_board_ids_json': _json_for_script(active_board_ids),
        'boards_json': _json_for_script(boards_data),
        'participants_json': _json_for_script(participants_data),
        'teammates_json': _json_for_script(teammates_data),
        'total_tasks': total_tasks,
        'overdue_count': overdue_count,
        'events_this_month': events_this_month,
        'current_month': now.strftime('%B %Y'),
        'all_tasks_json': _json_for_script(_all_tasks),
    }
    return render(request, 'kanban/unified_calendar.html', context)


# ---------------------------------------------------------------------------
# JSON events feed — consumed by FullCalendar
# ---------------------------------------------------------------------------

@login_required
@require_GET
def unified_calendar_events_api(request):
    """
    Returns a JSON array of FullCalendar-compatible events.
    Accepts optional ?start=YYYY-MM-DD&end=YYYY-MM-DD query params.
    Also accepts ?boards=1,2,3 to filter by board ids.
    """
    boards = _user_boards(request.user)

    # Optional board filter
    board_filter = request.GET.get('boards', '')
    if board_filter:
        try:
            board_ids = [int(x) for x in board_filter.split(',') if x.strip()]
            boards = boards.filter(id__in=board_ids)
        except ValueError:
            pass

    # Date range from FullCalendar
    start_str = request.GET.get('start')
    end_str = request.GET.get('end')

    task_qs = Task.objects.filter(
        column__board__in=boards,
        item_type='task',
        due_date__isnull=False,
    ).select_related('column', 'column__board', 'assigned_to').distinct()

    # Collect board member IDs (not including self) for the teammate-status event
    # query — these are the people whose team-visible "busy" blocks the viewer is
    # allowed to see.
    #
    # In a real workspace, teammates = members of the boards the viewer owns or
    # belongs to (the `boards` queryset already reflects this).
    #
    # In DEMO mode this is widened to keep the "Team can see I'm busy" promise
    # symmetric across separate sandbox copies — see _teammate_boards().
    teammate_boards = _teammate_boards(request.user, boards)

    board_member_ids = list(
        User.objects.filter(
            Q(board_memberships__board__in=teammate_boards) | Q(created_boards__in=teammate_boards)
        ).exclude(id=request.user.id).values_list('id', flat=True)
    )

    event_qs = CalendarEvent.objects.filter(
        # My own events — all types, all visibility
        Q(created_by=request.user) |
        # Events I'm invited to, team-visible only
        Q(participants=request.user, visibility='team') |
        # Teammate events shared as team-visible.  A team-visible MEETING shows
        # other teammates a sanitized "busy" block (see title sanitization below)
        # so the "Team can see I'm busy" promise holds for the default event type.
        Q(
            created_by__in=board_member_ids,
            event_type__in=['out_of_office', 'busy_block', 'team_event', 'meeting'],
            visibility='team',
        )
    ).select_related('board', 'linked_task', 'created_by').prefetch_related('participants').distinct()

    # Demo / real workspace isolation — task scoping already separates the two
    # via `boards`, but events bypassed that (they're matched by created_by /
    # participant / teammate, not board).  See _event_workspace_scope().
    event_qs = event_qs.filter(_event_workspace_scope(request.user))

    if start_str and end_str:
        try:
            # FullCalendar sends ISO strings like "2026-02-01T00:00:00"
            range_start = datetime.fromisoformat(start_str.rstrip('Z'))
            range_end = datetime.fromisoformat(end_str.rstrip('Z'))
            task_qs = task_qs.filter(
                # Include tasks whose [start_date..due_date] overlaps [range_start..range_end]
                Q(due_date__date__gte=range_start.date()) &
                Q(
                    Q(start_date__lte=range_end.date()) |
                    Q(start_date__isnull=True, due_date__date__lte=range_end.date())
                )
            )
            event_qs = event_qs.filter(
                start_datetime__date__lte=range_end.date(),
                end_datetime__date__gte=range_start.date(),
            )
        except (ValueError, AttributeError):
            pass

    events = []

    # --- Tasks — split into "mine" (priority colour) vs "teammate" (assignee colour) ---
    for task in task_qs:
        # Determine layer
        is_mine = (
            (task.assigned_to_id is not None and task.assigned_to_id == request.user.id) or
            (task.assigned_to_id is None and task.created_by_id == request.user.id)
        )
        if is_mine:
            layer = 'mine'
            color = _assignee_color(task.assigned_to_id)
        else:
            layer = 'teammate'
            color = _assignee_color(task.assigned_to_id)

        assignee_name = None
        if task.assigned_to:
            assignee_name = task.assigned_to.get_full_name() or task.assigned_to.username

        # Multi-day bar: use start_date→due_date span (same as board_calendar)
        due = task.due_date
        due_date_obj = due.date() if hasattr(due, 'date') else due
        due_str = due_date_obj.isoformat()

        if task.start_date:
            start_str_task = task.start_date.isoformat()
        else:
            start_str_task = due_str

        # FullCalendar exclusive end — add 1 day
        end_str_task = (due_date_obj + timedelta(days=1)).isoformat()

        events.append({
            'id': f'task-{task.id}',
            'title': task.title,
            'start': start_str_task,
            'end': end_str_task,
            'url': f'/tasks/{task.id}/',
            'color': color,
            'source': 'task',
            'extendedProps': {
                'source': 'task',
                'layer': layer,
                'board': task.column.board.name,
                'board_id': task.column.board_id,
                'column': task.column.name,
                'priority': task.get_priority_display(),
                'progress': task.progress,
                'assignee': task.assigned_to.username if task.assigned_to else None,
                'assignee_id': task.assigned_to_id,
                'assignee_name': assignee_name,
                'assignee_color': color,
                'due_date_str': due_str,
                'start_date_str': task.start_date.isoformat() if task.start_date else None,
            },
        })

    # --- Calendar Events ---
    for ev in event_qs:
        is_mine = (ev.created_by_id == request.user.id)
        # Participants who are invited to an event should see full details, not the
        # sanitized teammate_status view.
        is_invited = not is_mine and any(p.id == request.user.id for p in ev.participants.all())
        layer = 'event' if (is_mine or is_invited) else 'teammate_status'

        # Use explicit astimezone() — bypasses Django's thread-local timezone
        # which is unreliable under Daphne/ASGI thread-pool execution.
        _srv_tz = zoneinfo.ZoneInfo(settings.TIME_ZONE)
        if ev.is_all_day:
            local_start = ev.start_datetime.astimezone(_srv_tz)
            local_end   = ev.end_datetime.astimezone(_srv_tz)
            start_str_fc = local_start.strftime('%Y-%m-%d')
            # FullCalendar all-day end is EXCLUSIVE, so advance by 1 day so that
            # the user's chosen end date is actually the last visible day.
            end_str_fc      = (local_end.date() + timedelta(days=1)).isoformat()
            ev_end_date_str = local_end.strftime('%Y-%m-%d')  # inclusive last calendar day
        else:
            start_str_fc    = ev.start_datetime.isoformat()
            end_str_fc      = ev.end_datetime.isoformat()
            ev_end_date_str = ev.end_datetime.astimezone(_srv_tz).strftime('%Y-%m-%d')

        linked_task_title = ev.linked_task.title if ev.linked_task else None

        # Sanitize title for teammate events — protect personal details
        if is_mine or is_invited:
            fc_title = ev.title
        else:
            owner_name = ev.created_by.get_full_name() or ev.created_by.username
            if ev.event_type == 'out_of_office':
                fc_title = f"{owner_name} — Out of Office"
            elif ev.event_type == 'busy_block':
                fc_title = (
                    f"{owner_name} — busy ({linked_task_title})"
                    if linked_task_title
                    else f"{owner_name} — busy"
                )
            elif ev.event_type == 'meeting':
                # "Team can see I'm busy" — show the block, hide the reason (title).
                fc_title = f"{owner_name} — busy"
            else:  # team_event — show actual title
                fc_title = ev.title

        # A sanitized "busy"/OOO block (teammate_status) must not leak the reason
        # in the JSON payload either — the title is already redacted above, so
        # blank out notes, location and participants for non-team_event blocks.
        # (team_event is intentionally fully shared.)
        sanitized = (layer == 'teammate_status') and ev.event_type != 'team_event'
        participant_names = [] if sanitized else [p.username for p in ev.participants.all()]
        events.append({
            'id': f'event-{ev.id}',
            'title': fc_title,
            'start': start_str_fc,
            'end': end_str_fc,
            'allDay': ev.is_all_day,
            'color': ev.get_event_type_color(),
            'source': 'event',
            'extendedProps': {
                'source': 'event',
                'layer': layer,
                'event_id': ev.id,
                'event_type': ev.get_event_type_display(),
                'event_type_key': ev.event_type,
                'visibility': ev.visibility,
                'is_mine': is_mine,
                'description': '' if sanitized else (ev.description or ''),
                'location': '' if sanitized else (ev.location or ''),
                'board': ev.board.name if ev.board else '',
                'participants': participant_names,
                'created_by': ev.created_by.username,
                'creator_id': ev.created_by_id,
                'linked_task_title': linked_task_title,
                'linked_task_id': ev.linked_task_id,
                'end_date_str': ev_end_date_str,
            },
        })

    return JsonResponse(events, safe=False)


# ---------------------------------------------------------------------------
# Create Task from calendar (AJAX POST)
# ---------------------------------------------------------------------------

@login_required
@require_POST
@demo_write_guard
def calendar_create_task(request):
    try:
        data = json.loads(request.body)
    except (ValueError, KeyError):
        data = request.POST.dict()

    title = (data.get('title') or '').strip()
    if not title:
        return JsonResponse({'success': False, 'error': 'Title is required.'}, status=400)

    board_id = data.get('board_id')
    if not board_id:
        return JsonResponse({'success': False, 'error': 'Board is required.'}, status=400)

    # Verify the user has access to this board
    boards = _user_boards(request.user)
    board = boards.filter(id=board_id).first()
    if not board:
        return JsonResponse({'success': False, 'error': 'Board not found or access denied.'}, status=404)

    # Determine column
    column_id = data.get('column_id')
    if column_id:
        column = Column.objects.filter(id=column_id, board=board).first()
    else:
        column = board.columns.order_by('position').first()
    if not column:
        return JsonResponse({'success': False, 'error': 'No column found for the selected board.'}, status=400)

    # Due date
    due_date_str = data.get('due_date', '')
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.fromisoformat(due_date_str)
            if timezone.is_naive(due_date):
                due_date = timezone.make_aware(due_date)
        except ValueError:
            pass

    # Start date
    start_date_str = data.get('start_date', '')
    start_date = None
    if start_date_str:
        try:
            from datetime import date as date_type
            start_date = date_type.fromisoformat(start_date_str)
        except ValueError:
            pass

    # Assignee — validate board membership
    assignee_id = data.get('assignee_id')
    assignee = None
    if assignee_id:
        try:
            assignee = User.objects.filter(
                Q(board_memberships__board=board) | Q(id=board.created_by_id),
                id=assignee_id
            ).first()
        except (ValueError, TypeError):
            pass

    # Priority
    priority = data.get('priority', 'medium')
    if priority not in ('low', 'medium', 'high', 'urgent'):
        priority = 'medium'

    # Position — end of column
    last_pos = column.tasks.aggregate(max_pos=Max('position'))['max_pos']
    position = (last_pos or 0) + 1

    task = Task.objects.create(
        title=title,
        column=column,
        position=position,
        due_date=due_date,
        start_date=start_date,
        assigned_to=assignee,
        priority=priority,
        created_by=request.user,
        item_type='task',
    )

    # Activity log
    TaskActivity.objects.create(
        task=task,
        user=request.user,
        activity_type='created',
        description=f'Task created via Unified Calendar by {request.user.username}',
    )

    # Notify assignee (if different from creator)
    if assignee and assignee != request.user:
        from django.urls import reverse
        task_url = reverse('task_detail', args=[task.id])
        _create_notification(
            recipient=assignee,
            sender=request.user,
            notification_type='TASK_ASSIGNED_CAL',
            text=(
                f'{request.user.get_full_name() or request.user.username} assigned you a new task '
                f'"{task.title}" on board "{board.name}" via the Calendar.'
            ),
            action_url=task_url,
        )

    return JsonResponse({
        'success': True,
        'task_id': task.id,
        'event': {
            'id': f'task-{task.id}',
            'title': task.title,
            'start': task.due_date.strftime('%Y-%m-%d') if task.due_date else None,
            'url': f'/tasks/{task.id}/',
            'color': _priority_color(task.priority),
            'source': 'task',
            'extendedProps': {
                'source': 'task',
                'board': board.name,
                'board_id': board.id,
                'column': column.name,
                'priority': task.get_priority_display(),
                'progress': task.progress,
                'assignee': assignee.username if assignee else None,
            },
        },
    })


# ---------------------------------------------------------------------------
# Create CalendarEvent from calendar (AJAX POST)
# ---------------------------------------------------------------------------

@login_required
@require_POST
@demo_write_guard
def calendar_create_event(request):
    try:
        data = json.loads(request.body)
    except (ValueError, KeyError):
        data = request.POST.dict()

    title = (data.get('title') or '').strip()
    if not title:
        return JsonResponse({'success': False, 'error': 'Title is required.'}, status=400)

    start_str = data.get('start_datetime', '')
    end_str = data.get('end_datetime', '')
    is_all_day = bool(data.get('is_all_day', False))

    if not start_str or not end_str:
        return JsonResponse({'success': False, 'error': 'Start and end datetime are required.'}, status=400)

    try:
        if is_all_day:
            # For all-day events, store as UTC midnight of the chosen date.
            # This makes the date completely timezone-independent:
            # ev.start_datetime.date() always equals the chosen calendar date.
            import datetime as _dt_mod
            start_date = _dt_mod.date.fromisoformat(start_str.split('T')[0])
            end_date   = _dt_mod.date.fromisoformat(end_str.split('T')[0])
            start_dt = datetime(start_date.year, start_date.month, start_date.day,
                                tzinfo=_dt_mod.timezone.utc)
            end_dt   = datetime(end_date.year, end_date.month, end_date.day,
                                tzinfo=_dt_mod.timezone.utc)
        else:
            start_dt = datetime.fromisoformat(start_str)
            end_dt = datetime.fromisoformat(end_str)
            if timezone.is_naive(start_dt):
                start_dt = timezone.make_aware(start_dt)
            if timezone.is_naive(end_dt):
                end_dt = timezone.make_aware(end_dt)
    except ValueError as exc:
        return JsonResponse({'success': False, 'error': f'Invalid datetime: {exc}'}, status=400)

    if end_dt < start_dt:
        return JsonResponse({'success': False, 'error': 'End must be after start.'}, status=400)

    event_type = data.get('event_type', 'meeting')
    if event_type not in ('meeting', 'out_of_office', 'busy_block', 'team_event'):
        event_type = 'meeting'

    # Visibility field
    visibility = data.get('visibility', 'team')
    if visibility not in ('team', 'private'):
        visibility = 'team'

    description = data.get('description', '').strip()
    location = data.get('location', '').strip()

    # Optional board association
    board = None
    board_id = data.get('board_id')
    if board_id:
        board = _user_boards(request.user).filter(id=board_id).first()

    # Optional linked task (for busy_block context)
    linked_task = None
    linked_task_id = data.get('linked_task_id')
    if linked_task_id:
        try:
            linked_task = Task.objects.filter(
                id=int(linked_task_id),
                column__board__in=_user_boards(request.user),
            ).first()
        except (ValueError, TypeError):
            pass

    event = CalendarEvent.objects.create(
        title=title,
        description=description or None,
        event_type=event_type,
        visibility=visibility,
        start_datetime=start_dt,
        end_datetime=end_dt,
        is_all_day=is_all_day,
        location=location or None,
        board=board,
        linked_task=linked_task,
        created_by=request.user,
    )

    # Participants — only relevant for Meeting and Team Event
    SOLO_TYPES = ('out_of_office', 'busy_block')
    participant_ids = [] if event_type in SOLO_TYPES else data.get('participant_ids', [])
    if isinstance(participant_ids, str):
        try:
            participant_ids = json.loads(participant_ids)
        except ValueError:
            participant_ids = []

    notified_participants = []
    if participant_ids:
        participants = User.objects.filter(id__in=participant_ids).exclude(id=request.user.id)
        event.participants.set(participants)
        notified_participants = list(participants)

    # Notify each participant
    board_context = f' (Board: {board.name})' if board else ''
    for participant in notified_participants:
        _create_notification(
            recipient=participant,
            sender=request.user,
            notification_type='EVENT_INVITED',
            text=(
                f'{request.user.get_full_name() or request.user.username} invited you to '
                f'"{event.title}" on {event.start_datetime.strftime("%b %d, %Y")}{board_context}.'
            ),
            action_url=f'/calendar/events/{event.id}/',
        )

    # Build FullCalendar event object for immediate rendering
    if is_all_day:
        # All-day events are now stored as UTC midnight, so .date() gives the correct calendar date.
        fc_start = event.start_datetime.date().isoformat()
        fc_end = (event.end_datetime.date() + timedelta(days=1)).isoformat()
    else:
        fc_start = event.start_datetime.isoformat()
        fc_end = event.end_datetime.isoformat()

    return JsonResponse({
        'success': True,
        'event_id': event.id,
        'event': {
            'id': f'event-{event.id}',
            'title': event.title,
            'start': fc_start,
            'end': fc_end,
            'allDay': is_all_day,
            'url': f'/calendar/events/{event.id}/',
            'color': event.get_event_type_color(),
            'source': 'event',
            'extendedProps': {
                'source': 'event',
                'layer': 'event',
                'event_id': event.id,
                'event_type': event.get_event_type_display(),
                'event_type_key': event.event_type,
                'visibility': event.visibility,
                'is_mine': True,
                'description': event.description or '',
                'location': event.location or '',
                'board': board.name if board else '',
                'participants': [u.username for u in notified_participants],
                'participant_ids': [u.id for u in notified_participants],
                'created_by': request.user.username,
                'created_by_id': request.user.id,
                'linked_task_title': linked_task.title if linked_task else None,
                'linked_task_id': linked_task.id if linked_task else None,
            },
        },
    })


# ---------------------------------------------------------------------------
# Helper: Get columns for a board (used by task-creation modal)
# ---------------------------------------------------------------------------

@login_required
@require_GET
def calendar_get_board_columns(request, board_id):
    boards = _user_boards(request.user)
    board = get_object_or_404(boards, id=board_id)
    columns = list(board.columns.order_by('position').values('id', 'name'))

    # Also return board members for the assignee dropdown
    members = list(
        User.objects.filter(
            Q(board_memberships__board=board) | Q(created_boards=board)
        ).distinct().values('id', 'username')
    )
    for m in members:
        user_obj = User.objects.get(id=m['id'])
        m['display'] = user_obj.get_full_name() or user_obj.username

    return JsonResponse({'columns': columns, 'members': members})


# ---------------------------------------------------------------------------
# CalendarEvent detail & delete
# ---------------------------------------------------------------------------

def _calendar_back_url(request, event):
    """Resolve where the "Back to Calendar" link should point.

    The same event detail page is reachable from both the unified "My Calendar"
    (/calendar/) and a board calendar (/boards/<id>/calendar/).  A board-linked
    event must not always bounce back to the board calendar — it should return
    the user to whichever calendar they came from.  Resolution order:

      1. Explicit ?from= marker ('unified' or 'board') set on the originating link.
      2. The HTTP referer, if it points at one of our calendar pages.
      3. Fallback: board calendar when board-linked, otherwise unified.
    """
    origin = request.GET.get('from')
    if origin == 'unified':
        return '/calendar/'
    if origin == 'board' and event.board_id:
        return f'/boards/{event.board_id}/calendar/'

    referer = request.META.get('HTTP_REFERER', '')
    if referer:
        from urllib.parse import urlparse
        path = urlparse(referer).path
        if path == '/calendar/':
            return '/calendar/'
        if path.startswith('/boards/') and path.endswith('/calendar/'):
            return path

    if event.board_id:
        return f'/boards/{event.board_id}/calendar/'
    return '/calendar/'


@login_required
def calendar_event_detail(request, event_id):
    """Simple detail/edit page for a CalendarEvent."""
    event = get_object_or_404(
        CalendarEvent.objects.prefetch_related('participants'),
        id=event_id,
    )
    # Only creator or participants can view, OR board members for team-visible events
    can_view = (
        event.created_by == request.user or
        event.participants.filter(id=request.user.id).exists()
    )
    if not can_view and event.visibility == 'team':
        # Board members may view team-shared OOO/busy/team events.  Use the same
        # demo-aware teammate scope as the calendar feed so a block that is
        # visible on the grid is also openable (and vice-versa).
        shared_boards = _teammate_boards(
            request.user, _user_boards(request.user)
        ).filter(
            Q(created_by=event.created_by) | Q(memberships__user=event.created_by)
        )
        can_view = shared_boards.exists()
    if not can_view:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("You don't have access to this event.")

    # Determine back URL — respect where the user actually came from
    back_url = _calendar_back_url(request, event)

    # Pre-compute display dates using explicit timezone conversion (bypasses
    # Django's thread-local which is unreliable under Daphne/ASGI).
    import zoneinfo as _zi
    _srv_tz = _zi.ZoneInfo(settings.TIME_ZONE)
    if event.is_all_day:
        # All-day events: new ones stored as UTC midnight; old ones stored as
        # local midnight converted to UTC.  astimezone(server_tz) handles both.
        event_start_display = event.start_datetime.astimezone(_srv_tz).date()
        event_end_display   = event.end_datetime.astimezone(_srv_tz).date()
    else:
        event_start_display = event.start_datetime.astimezone(_srv_tz)
        event_end_display   = event.end_datetime.astimezone(_srv_tz)

    # If the viewer is neither the creator nor a participant, they are only here
    # via "Team can see I'm busy" visibility — show a sanitized busy/OOO block so
    # the reason (title, notes, location, participants) is not leaked.  Team
    # events are intentionally fully shared, so they are never sanitized.
    is_mine = event.created_by_id == request.user.id
    is_participant = event.participants.filter(id=request.user.id).exists()
    sanitized = (not is_mine) and (not is_participant) and event.event_type != 'team_event'
    owner_name = event.created_by.get_full_name() or event.created_by.username
    if sanitized:
        display_title = (
            f"{owner_name} — Out of Office"
            if event.event_type == 'out_of_office'
            else f"{owner_name} — busy"
        )
    else:
        display_title = event.title

    context = {
        'event': event,
        'back_url': back_url,
        'back_origin': 'unified' if back_url == '/calendar/' else 'board',
        'event_start_display': event_start_display,
        'event_end_display': event_end_display,
        'sanitized': sanitized,
        'display_title': display_title,
    }
    return render(request, 'kanban/calendar_event_detail.html', context)


@login_required
@demo_write_guard
def calendar_event_edit(request, event_id):
    """Edit a CalendarEvent (creator only)."""
    event = get_object_or_404(CalendarEvent, id=event_id, created_by=request.user)

    # Determine back URL — respect where the user came from
    back_url = _calendar_back_url(request, event)

    # Build participants list (board members if board-linked, otherwise all users the creator shares boards with)
    if event.board:
        participant_qs = User.objects.filter(
            Q(board_memberships__board=event.board) | Q(created_boards=event.board)
        ).exclude(id=request.user.id).distinct().order_by('username')
    else:
        user_boards = Board.objects.filter(
            Q(memberships__user=request.user) | Q(created_by=request.user)
        )
        participant_qs = User.objects.filter(
            Q(board_memberships__board__in=user_boards) | Q(created_boards__in=user_boards)
        ).exclude(id=request.user.id).distinct().order_by('username')

    if request.method == 'POST':
        event.title = request.POST.get('title', '').strip() or event.title
        event.event_type = request.POST.get('event_type', event.event_type)
        event.description = request.POST.get('description', '').strip() or None
        event.location = request.POST.get('location', '').strip() or None
        event.visibility = request.POST.get('visibility', event.visibility)

        is_all_day = request.POST.get('is_all_day') == 'on'
        event.is_all_day = is_all_day

        try:
            start_str = request.POST.get('start_datetime', '')
            end_str = request.POST.get('end_datetime', '')
            if start_str:
                start_dt = datetime.fromisoformat(start_str)
                if timezone.is_naive(start_dt):
                    start_dt = timezone.make_aware(start_dt)
                event.start_datetime = start_dt
            if end_str:
                end_dt = datetime.fromisoformat(end_str)
                if timezone.is_naive(end_dt):
                    end_dt = timezone.make_aware(end_dt)
                event.end_datetime = end_dt
        except ValueError:
            pass

        event.save()

        # Update participants for non-solo types
        if event.event_type not in CalendarEvent.SOLO_TYPES:
            participant_ids = request.POST.getlist('participants')
            participants = User.objects.filter(id__in=participant_ids).exclude(id=request.user.id)
            event.participants.set(participants)
        else:
            event.participants.clear()

        from django.urls import reverse
        detail_url = reverse('calendar_event_detail', args=[event.id])
        if back_url == '/calendar/':
            detail_url += '?from=unified'
        return redirect(detail_url)

    context = {
        'event': event,
        'back_url': back_url,
        'back_origin': 'unified' if back_url == '/calendar/' else 'board',
        'participant_choices': participant_qs,
        'current_participant_ids': list(event.participants.values_list('id', flat=True)),
    }
    return render(request, 'kanban/calendar_event_edit.html', context)


@login_required
@require_POST
@demo_write_guard
def calendar_event_delete(request, event_id):
    """Delete a CalendarEvent (creator only)."""
    event = get_object_or_404(CalendarEvent, id=event_id, created_by=request.user)
    event.delete()
    return JsonResponse({'success': True})
