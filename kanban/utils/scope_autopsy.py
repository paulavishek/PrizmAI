"""
Scope Autopsy Data Collection Utilities

Gathers scope change events from multiple sources and calculates
baseline/cost impact for forensic analysis.
"""
import logging
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger(__name__)


def calculate_baseline(board):
    """
    Determine the original scope baseline for a board.

    Priority:
    1. Use board.baseline_task_count / board.baseline_set_date if set
    2. Fall back to task count 24 hours after board creation

    Returns dict: {'task_count': int, 'baseline_date': datetime}
    """
    from kanban.models import Task

    # If an explicit baseline exists on the board, use it
    if board.baseline_task_count and board.baseline_set_date:
        return {
            'task_count': board.baseline_task_count,
            'baseline_date': board.baseline_set_date,
        }

    # Fall back: count tasks that existed 24h after board creation
    cutoff = board.created_at + timedelta(hours=24)
    count = Task.objects.filter(
        column__board=board,
        created_at__lte=cutoff,
    ).count()

    return {
        'task_count': max(count, 1),  # avoid zero-division later
        'baseline_date': cutoff,
    }


def collect_scope_history(board):
    """
    Collect all scope change events for a board in chronological order.

    Gathers from four sources:
    1. ScopeCreepAlert records
    2. Task creation after baseline
    3. Resolved conflicts that affected tasks
    4. Meeting transcripts that created tasks

    Returns a list of event dicts sorted by date.
    """
    from kanban.models import Task, ScopeCreepAlert, MeetingTranscript
    from kanban.conflict_models import ConflictDetection

    baseline = calculate_baseline(board)
    baseline_date = baseline['baseline_date']
    now = timezone.now()
    events = []

    # ── SOURCE 1: Scope Creep Alerts ────────────────────────────────────
    try:
        alerts = ScopeCreepAlert.objects.filter(
            board=board, detected_at__lte=now
        ).order_by('detected_at')
        for alert in alerts:
            events.append({
                'date': alert.detected_at,
                'title': f"Scope creep alert ({alert.get_severity_display()})",
                'description': alert.ai_summary or f"Scope increased {alert.scope_increase_percentage:.1f}%",
                'source_type': 'scope_alert',
                'source_object_type': 'ScopeCreepAlert',
                'source_object_id': alert.pk,
                'tasks_added': alert.tasks_added or 0,
                'tasks_removed': 0,
                'added_by_id': None,
                'added_by_name': '',
            })
    except Exception:
        logger.warning("Error collecting scope alerts for board %s", board.pk, exc_info=True)

    # ── SOURCE 2: Task creation after baseline ──────────────────────────
    try:
        post_baseline_tasks = (
            Task.objects.filter(
                column__board=board,
                created_at__gt=baseline_date,
                created_at__lte=now,
            )
            .select_related('created_by')
            .order_by('created_at')
        )

        # Group tasks added on the same calendar day by the same user
        daily_groups = defaultdict(list)
        for task in post_baseline_tasks:
            key = (task.created_at.date(), getattr(task.created_by, 'pk', None))
            daily_groups[key].append(task)

        for (day, user_id), tasks in daily_groups.items():
            creator = tasks[0].created_by
            creator_name = ''
            if creator:
                creator_name = creator.get_full_name() or creator.username

            task_titles = ', '.join(t.title[:40] for t in tasks[:5])
            if len(tasks) > 5:
                task_titles += f' (+{len(tasks) - 5} more)'

            events.append({
                'date': timezone.make_aware(
                    timezone.datetime.combine(day, timezone.datetime.min.time())
                ) if timezone.is_naive(
                    timezone.datetime.combine(day, timezone.datetime.min.time())
                ) else timezone.datetime.combine(day, timezone.datetime.min.time()),
                'title': f"{len(tasks)} task{'s' if len(tasks) != 1 else ''} added by {creator_name or 'Unknown'}",
                'description': task_titles,
                'source_type': 'task_added',
                'source_object_type': 'Task',
                'source_object_id': tasks[0].pk,
                'tasks_added': len(tasks),
                'tasks_removed': 0,
                'added_by_id': user_id,
                'added_by_name': creator_name,
            })
    except Exception:
        logger.warning("Error collecting task history for board %s", board.pk, exc_info=True)

    # ── SOURCE 3: Resolved conflicts ────────────────────────────────────
    try:
        conflicts = ConflictDetection.objects.filter(
            board=board,
            status__in=['resolved', 'auto_resolved'],            resolved_at__lte=now,        ).order_by('resolved_at')

        for conflict in conflicts:
            task_count = conflict.tasks.count()
            if task_count == 0:
                continue
            events.append({
                'date': conflict.resolved_at or conflict.detected_at,
                'title': f"Conflict resolved: {conflict.title[:80]}",
                'description': conflict.description[:200] if conflict.description else '',
                'source_type': 'conflict',
                'source_object_type': 'ConflictDetection',
                'source_object_id': conflict.pk,
                'tasks_added': task_count,
                'tasks_removed': 0,
                'added_by_id': None,
                'added_by_name': '',
            })
    except Exception:
        logger.warning("Error collecting conflicts for board %s", board.pk, exc_info=True)

    # ── SOURCE 4: Meeting transcript imports ────────────────────────────
    try:
        transcripts = MeetingTranscript.objects.filter(
            board=board,
            processing_status='completed',
            tasks_created_count__gt=0,            created_at__lte=now,        ).order_by('created_at')

        for transcript in transcripts:
            events.append({
                'date': transcript.created_at,
                'title': f"Meeting import: {transcript.title[:80]}",
                'description': (
                    f"{transcript.tasks_created_count} tasks created from "
                    f"{transcript.get_meeting_type_display()} on {transcript.meeting_date}"
                ),
                'source_type': 'meeting',
                'source_object_type': 'MeetingTranscript',
                'source_object_id': transcript.pk,
                'tasks_added': transcript.tasks_created_count,
                'tasks_removed': 0,
                'added_by_id': transcript.created_by_id,
                'added_by_name': (
                    transcript.created_by.get_full_name() or transcript.created_by.username
                ) if transcript.created_by else '',
            })
    except Exception:
        logger.warning("Error collecting meeting transcripts for board %s", board.pk, exc_info=True)

    # ── De-duplicate and sort ───────────────────────────────────────────
    # Remove alert-sourced events whose task counts overlap with task_added events
    # on the same day (alerts are derivative of task additions).
    alert_events = [e for e in events if e['source_type'] == 'scope_alert']
    non_alert_events = [e for e in events if e['source_type'] != 'scope_alert']
    task_event_dates = {e['date'].date() for e in non_alert_events if e['source_type'] == 'task_added'}

    filtered_alerts = [
        a for a in alert_events
        if a['date'].date() not in task_event_dates
    ]
    events = non_alert_events + filtered_alerts

    # Mark major events
    for event in events:
        event['net_task_change'] = event['tasks_added'] - event['tasks_removed']
        event['is_major_event'] = event['net_task_change'] >= 3

    return sorted(events, key=lambda x: x['date'])


def estimate_cost_impact(events, board):
    """
    For each event, estimate delay and budget impact.

    Delay: tasks_added * avg_task_duration (defaults to 2 days/task)
    Budget: tasks_added * (total_budget / total_tasks) if budget exists
    """
    from kanban.models import Task

    total_tasks = Task.objects.filter(column__board=board).count() or 1

    # Try to get average task duration from completed tasks
    completed = Task.objects.filter(
        column__board=board,
        completed_at__isnull=False,
        start_date__isnull=False,
    )
    avg_duration_days = 2  # default
    if completed.exists():
        durations = []
        for t in completed[:50]:
            delta = (t.completed_at.date() - t.start_date).days
            if delta > 0:
                durations.append(delta)
        if durations:
            avg_duration_days = sum(durations) / len(durations)

    # Try to get per-task budget
    per_task_budget = Decimal('0')
    try:
        budget = board.budget
        if budget and budget.allocated_budget and total_tasks > 0:
            per_task_budget = budget.allocated_budget / total_tasks
    except Exception:
        pass

    for event in events:
        tasks = event.get('tasks_added', 0)
        event['estimated_delay_days'] = round(tasks * avg_duration_days)
        event['estimated_budget_impact'] = float(per_task_budget * tasks)

    return events


def has_scope_change_history(board):
    """Quick check: does the board have any scope change events?"""
    from kanban.models import Task, ScopeCreepAlert

    # Check for scope creep alerts
    if ScopeCreepAlert.objects.filter(board=board).exists():
        return True

    # Check if tasks were added after baseline
    baseline = calculate_baseline(board)
    post_baseline = Task.objects.filter(
        column__board=board,
        created_at__gt=baseline['baseline_date'],
    ).exists()

    return post_baseline
