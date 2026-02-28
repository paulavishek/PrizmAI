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
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET

from django.db.models import Max

from .models import Board, Column, Task, TaskActivity, CalendarEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_boards(user):
    """Return all boards the user owns or is a member of (excluding official demo boards)."""
    return Board.objects.filter(
        Q(created_by=user) | Q(members=user)
    ).distinct().order_by('name')


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


# ---------------------------------------------------------------------------
# Main calendar page
# ---------------------------------------------------------------------------

@login_required
def unified_calendar(request):
    boards = _user_boards(request.user)

    # Build a list of board dicts for the JS board-selector in the "create task" modal
    boards_data = []
    for b in boards:
        columns = list(b.columns.order_by('position').values('id', 'name'))
        boards_data.append({'id': b.id, 'name': b.name, 'columns': columns})

    # Gather all board members across user's boards for participant typeahead
    participant_qs = User.objects.filter(
        Q(member_boards__in=boards) | Q(created_boards__in=boards)
    ).exclude(id=request.user.id).distinct().order_by('username')
    participants_data = [
        {'id': u.id, 'username': u.username,
         'display': u.get_full_name() or u.username}
        for u in participant_qs
    ]

    # Teammates list with assigned colours (for filter chips & availability mode)
    teammates_data = [
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
    ).distinct().count()

    # Build a flat task list for the "linked task" dropdown in the event form
    _all_tasks = []
    for _t in Task.objects.filter(
        column__board__in=boards, item_type='task',
    ).select_related('column__board').order_by('column__board__name', 'title'):
        _all_tasks.append({'id': _t.id, 'title': _t.title, 'board_name': _t.column.board.name})

    context = {
        'boards': boards,
        'boards_json': json.dumps(boards_data),
        'participants_json': json.dumps(participants_data),
        'teammates_json': json.dumps(teammates_data),
        'total_tasks': total_tasks,
        'overdue_count': overdue_count,
        'events_this_month': events_this_month,
        'current_month': now.strftime('%B %Y'),
        'all_tasks_json': json.dumps(_all_tasks),
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

    # Collect board member IDs (not including self) for teammate-status event query
    board_member_ids = list(
        User.objects.filter(
            Q(member_boards__in=boards) | Q(created_boards__in=boards)
        ).exclude(id=request.user.id).values_list('id', flat=True)
    )

    event_qs = CalendarEvent.objects.filter(
        # My own events — all types, all visibility
        Q(created_by=request.user) |
        # Events I'm invited to, team-visible only
        Q(participants=request.user, visibility='team') |
        # Teammate OOO / busy blocks / team events that they chose to share
        Q(
            created_by__in=board_member_ids,
            event_type__in=['out_of_office', 'busy_block', 'team_event'],
            visibility='team',
        )
    ).select_related('board', 'linked_task', 'created_by').prefetch_related('participants').distinct()

    if start_str and end_str:
        try:
            # FullCalendar sends ISO strings like "2026-02-01T00:00:00"
            range_start = datetime.fromisoformat(start_str.rstrip('Z'))
            range_end = datetime.fromisoformat(end_str.rstrip('Z'))
            task_qs = task_qs.filter(due_date__date__gte=range_start.date(),
                                      due_date__date__lte=range_end.date())
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
            color = _priority_color(task.priority)
        else:
            layer = 'teammate'
            color = _assignee_color(task.assigned_to_id)

        assignee_name = None
        if task.assigned_to:
            assignee_name = task.assigned_to.get_full_name() or task.assigned_to.username

        events.append({
            'id': f'task-{task.id}',
            'title': task.title,
            'start': task.due_date.strftime('%Y-%m-%d'),
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
                'assignee_color': color if layer == 'teammate' else None,
            },
        })

    # --- Calendar Events ---
    for ev in event_qs:
        is_mine = (ev.created_by_id == request.user.id)
        layer = 'event' if is_mine else 'teammate_status'

        if ev.is_all_day:
            start_str_fc = ev.start_datetime.strftime('%Y-%m-%d')
            end_str_fc = ev.end_datetime.strftime('%Y-%m-%d')
        else:
            start_str_fc = ev.start_datetime.isoformat()
            end_str_fc = ev.end_datetime.isoformat()

        linked_task_title = ev.linked_task.title if ev.linked_task else None

        # Sanitize title for teammate events — protect personal details
        if is_mine:
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
            else:  # team_event — show actual title
                fc_title = ev.title

        participant_names = [p.username for p in ev.participants.all()]
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
                'description': ev.description or '',
                'location': ev.location or '',
                'board': ev.board.name if ev.board else '',
                'participants': participant_names,
                'created_by': ev.created_by.username,
                'creator_id': ev.created_by_id,
                'linked_task_title': linked_task_title,
                'linked_task_id': ev.linked_task_id,
            },
        })

    return JsonResponse(events, safe=False)


# ---------------------------------------------------------------------------
# Create Task from calendar (AJAX POST)
# ---------------------------------------------------------------------------

@login_required
@require_POST
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

    # Assignee
    assignee_id = data.get('assignee_id')
    assignee = None
    if assignee_id:
        try:
            assignee = User.objects.get(id=assignee_id)
        except User.DoesNotExist:
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
        fc_start = event.start_datetime.strftime('%Y-%m-%d')
        fc_end = event.end_datetime.strftime('%Y-%m-%d')
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
                'created_by': request.user.username,
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
            Q(member_boards=board) | Q(created_boards=board)
        ).distinct().values('id', 'username')
    )
    for m in members:
        user_obj = User.objects.get(id=m['id'])
        m['display'] = user_obj.get_full_name() or user_obj.username

    return JsonResponse({'columns': columns, 'members': members})


# ---------------------------------------------------------------------------
# CalendarEvent detail & delete
# ---------------------------------------------------------------------------

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
        # Board members may view team-shared OOO/busy/team events
        shared_boards = _user_boards(request.user).filter(
            Q(created_by=event.created_by) | Q(members=event.created_by)
        )
        can_view = shared_boards.exists()
    if not can_view:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("You don't have access to this event.")

    context = {'event': event}
    return render(request, 'kanban/calendar_event_detail.html', context)


@login_required
@require_POST
def calendar_event_delete(request, event_id):
    """Delete a CalendarEvent (creator only)."""
    event = get_object_or_404(CalendarEvent, id=event_id, created_by=request.user)
    event.delete()
    return JsonResponse({'success': True})
