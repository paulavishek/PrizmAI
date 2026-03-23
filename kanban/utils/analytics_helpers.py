"""
Utility functions for Goal-Aware Analytics.

Calculates promoted metrics for each project type profile and
provides aggregation helpers for portfolio-level analytics.
"""
import logging
from datetime import timedelta

from django.db.models import Count, Avg, Q, F
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Metric definitions by project type
# ---------------------------------------------------------------------------

PROMOTED_METRICS = {
    'product_tech': [
        'task_velocity',
        'overdue_count',
        'blocked_count',
        'completion_rate_by_column',
        'workload_distribution',
    ],
    'marketing_campaign': [
        'tasks_by_phase',
        'deadline_adherence_rate',
        'content_output_rate',
        'tasks_in_review',
        'milestone_completion_pct',
    ],
    'operations': [
        'process_completion_rate',
        'workload_distribution',
        'avg_cycle_time_days',
        'overdue_count',
        'on_time_rate',
    ],
}


def get_promoted_metrics(board):
    """
    Calculate the promoted metrics for a board based on its project_type.

    Returns a dict of metric_name → value.
    Falls back to a generic set if project_type is not set.
    """
    from kanban.models import Task, Column, TaskActivity

    project_type = board.project_type or 'product_tech'
    today = timezone.now().date()
    seven_days_ago = timezone.now() - timedelta(days=7)
    thirty_days_ago = timezone.now() - timedelta(days=30)

    tasks = Task.objects.filter(column__board=board, item_type='task')
    total = tasks.count()

    metrics = {}

    if project_type == 'product_tech':
        # Task velocity: tasks completed in last 7 days
        completed_last_week = tasks.filter(progress=100, updated_at__gte=seven_days_ago).count()
        metrics['task_velocity'] = f"{completed_last_week} tasks/week"

        # Overdue count
        overdue = tasks.filter(
            due_date__isnull=False, due_date__date__lt=today
        ).exclude(progress=100).count()
        metrics['overdue_count'] = overdue

        # Blocked / high-risk count (priority=urgent or high with no progress)
        blocked = tasks.filter(
            Q(priority='urgent') | Q(priority='high', progress=0)
        ).exclude(progress=100).count()
        metrics['blocked_count'] = blocked

        # Task completion rate by column
        columns = Column.objects.filter(board=board).order_by('position')
        col_rates = {}
        for col in columns:
            col_tasks = tasks.filter(column=col)
            col_total = col_tasks.count()
            col_done = col_tasks.filter(progress=100).count()
            rate = int((col_done / col_total * 100)) if col_total > 0 else 0
            col_rates[col.name] = f"{rate}%"
        metrics['completion_rate_by_column'] = col_rates

        # Workload distribution
        workload = list(
            tasks.exclude(progress=100)
            .values('assigned_to__username')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
        metrics['workload_distribution'] = {
            (w['assigned_to__username'] or 'Unassigned'): w['count'] for w in workload
        }

    elif project_type == 'marketing_campaign':
        # Tasks by phase (column)
        columns = Column.objects.filter(board=board).order_by('position')
        phase_counts = {}
        for col in columns:
            phase_counts[col.name] = tasks.filter(column=col).count()
        metrics['tasks_by_phase'] = phase_counts

        # Deadline adherence rate
        with_due = tasks.filter(due_date__isnull=False)
        total_with_due = with_due.count()
        on_time = with_due.filter(
            Q(progress=100, due_date__date__gte=F('updated_at__date')) |
            Q(progress=100, due_date__date__gte=today)
        ).count()
        # Simpler calculation: completed tasks that were not overdue at completion
        completed_with_due = with_due.filter(progress=100).count()
        overdue_completed = with_due.filter(
            progress=100, due_date__date__lt=F('updated_at__date')
        ).count()
        on_time_completed = completed_with_due - overdue_completed
        metrics['deadline_adherence_rate'] = (
            f"{int(on_time_completed / total_with_due * 100)}%" if total_with_due > 0 else "N/A"
        )

        # Content output rate (tasks completed this week)
        content_done = tasks.filter(progress=100, updated_at__gte=seven_days_ago).count()
        metrics['content_output_rate'] = f"{content_done} tasks/week"

        # Tasks currently in review columns (heuristic: columns with 'review' in name)
        review_cols = columns.filter(name__icontains='review')
        review_count = tasks.filter(column__in=review_cols).exclude(progress=100).count()
        metrics['tasks_in_review'] = review_count

        # Milestone completion percentage
        completed = tasks.filter(progress=100).count()
        metrics['milestone_completion_pct'] = f"{int(completed / total * 100)}%" if total > 0 else "0%"

    elif project_type == 'operations':
        # Process completion rate (completed / created in last 30 days)
        created_30d = tasks.filter(created_at__gte=thirty_days_ago).count()
        completed_30d = tasks.filter(progress=100, updated_at__gte=thirty_days_ago).count()
        metrics['process_completion_rate'] = (
            f"{int(completed_30d / created_30d * 100)}%" if created_30d > 0 else "N/A"
        )

        # Workload distribution
        workload = list(
            tasks.exclude(progress=100)
            .values('assigned_to__username')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
        metrics['workload_distribution'] = {
            (w['assigned_to__username'] or 'Unassigned'): w['count'] for w in workload
        }

        # Average cycle time (creation → completion, in days)
        completed_tasks = tasks.filter(progress=100, updated_at__isnull=False)
        if completed_tasks.exists():
            total_days = sum(
                (t.updated_at - t.created_at).days for t in completed_tasks[:100]  # cap for perf
            )
            avg_days = total_days / completed_tasks[:100].count()
            metrics['avg_cycle_time_days'] = f"{avg_days:.1f} days"
        else:
            metrics['avg_cycle_time_days'] = "N/A"

        # Overdue count
        overdue = tasks.filter(
            due_date__isnull=False, due_date__date__lt=today
        ).exclude(progress=100).count()
        metrics['overdue_count'] = overdue

        # On-time rate
        with_due = tasks.filter(due_date__isnull=False, progress=100)
        total_done_with_due = with_due.count()
        overdue_at_completion = with_due.filter(due_date__date__lt=F('updated_at__date')).count()
        on_time = total_done_with_due - overdue_at_completion
        metrics['on_time_rate'] = (
            f"{int(on_time / total_done_with_due * 100)}%" if total_done_with_due > 0 else "N/A"
        )

    return metrics


def get_boards_for_record(record, record_type):
    """
    Return a queryset of all Board objects linked to a Goal, Mission, or Strategy
    by traversing the hierarchy downward.
    """
    from kanban.models import Board

    if record_type == 'goal':
        return Board.objects.filter(
            strategy__mission__organization_goal=record
        )
    elif record_type == 'mission':
        return Board.objects.filter(
            strategy__mission=record
        )
    elif record_type == 'strategy':
        return Board.objects.filter(strategy=record)
    return Board.objects.none()


def get_portfolio_analytics(record, record_type):
    """
    Aggregate promoted metrics across all boards linked to a strategic record,
    grouped by project type.

    Returns:
        {
            'groups': [ { type, label, board_count, metrics: { ... } }, ... ],
            'unclassified_count': int,
            'unclassified_board_ids': [int, ...],
        }
    """
    from kanban.models import Board

    boards = get_boards_for_record(record, record_type)

    unclassified = boards.filter(
        Q(project_type__isnull=True) | Q(project_type_confirmed=False, project_type__isnull=True)
    )
    unclassified_ids = list(unclassified.values_list('id', flat=True))

    classified = boards.filter(project_type__isnull=False)

    type_labels = dict(Board.PROJECT_TYPE_CHOICES)
    groups = []

    for ptype in ['product_tech', 'marketing_campaign', 'operations']:
        group_boards = classified.filter(project_type=ptype)
        if not group_boards.exists():
            continue

        # Aggregate metrics across boards of this type
        aggregated = {}
        for b in group_boards:
            board_metrics = get_promoted_metrics(b)
            for k, v in board_metrics.items():
                if isinstance(v, (int, float)):
                    aggregated[k] = aggregated.get(k, 0) + v
                elif isinstance(v, str) and v != 'N/A':
                    # Keep first value as representative for string metrics
                    if k not in aggregated:
                        aggregated[k] = v

        groups.append({
            'type': ptype,
            'label': type_labels.get(ptype, ptype),
            'board_count': group_boards.count(),
            'metrics': aggregated,
        })

    return {
        'groups': groups,
        'unclassified_count': len(unclassified_ids),
        'unclassified_board_ids': unclassified_ids,
    }
