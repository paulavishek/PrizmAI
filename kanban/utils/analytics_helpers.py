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

METRIC_CONFIG = {
    'task_velocity': {
        'label': 'Task Velocity',
        'icon': 'fas fa-tachometer-alt',
        'color': 'info',
        'description': 'Number of tasks completed in the last 7 days.',
    },
    'overdue_count': {
        'label': 'Overdue Tasks',
        'icon': 'fas fa-exclamation-triangle',
        'color': 'danger',
        'modal_target': '#overdueModal',
        'description': 'Tasks that are past their due date and not yet completed.',
    },
    'blocked_count': {
        'label': 'Blocked / At-Risk',
        'icon': 'fas fa-ban',
        'color': 'warning',
        'description': 'Urgent tasks (any progress) or high-priority tasks with 0% progress that may need attention.',
    },
    'completion_rate_by_column': {
        'label': 'Column Completion',
        'icon': 'fas fa-columns',
        'color': 'primary',
        'description': 'Task completion rate across each board column.',
    },
    'workload_distribution': {
        'label': 'Active Contributors',
        'icon': 'fas fa-users',
        'color': 'success',
        'description': 'Distribution of active tasks among team members.',
    },
    'tasks_by_phase': {
        'label': 'Tasks by Phase',
        'icon': 'fas fa-layer-group',
        'color': 'primary',
        'description': 'How tasks are distributed across project phases.',
    },
    'deadline_adherence_rate': {
        'label': 'Deadline Adherence',
        'icon': 'fas fa-calendar-check',
        'color': 'success',
        'description': 'Percentage of tasks completed on or before their deadline.',
    },
    'content_output_rate': {
        'label': 'Content Output',
        'icon': 'fas fa-file-alt',
        'color': 'info',
        'description': 'Number of tasks completed this week.',
    },
    'tasks_in_review': {
        'label': 'In Review',
        'icon': 'fas fa-search',
        'color': 'warning',
        'description': 'Tasks currently in review columns awaiting approval.',
    },
    'milestone_completion_pct': {
        'label': 'Milestone Completion',
        'icon': 'fas fa-flag-checkered',
        'color': 'success',
        'description': 'Overall percentage of completed milestones.',
    },
    'process_completion_rate': {
        'label': 'Process Completion',
        'icon': 'fas fa-cogs',
        'color': 'info',
        'description': 'Rate of task completion in the last 30 days.',
    },
    'avg_cycle_time_days': {
        'label': 'Avg Cycle Time',
        'icon': 'fas fa-clock',
        'color': 'warning',
        'description': 'Average number of days from task creation to completion.',
    },
    'on_time_rate': {
        'label': 'On-Time Rate',
        'icon': 'fas fa-check-double',
        'color': 'success',
        'description': 'Percentage of tasks completed before their deadline.',
    },
}


def _format_metric_value(key, value):
    """Convert complex dict metric values to simple display strings."""
    if not isinstance(value, dict):
        return value
    if key == 'completion_rate_by_column':
        if not value:
            return 'N/A'
        # Show average completion rate across columns
        rates = []
        for v in value.values():
            try:
                rates.append(int(v.replace('%', '')))
            except (ValueError, AttributeError):
                pass
        avg_rate = int(sum(rates) / len(rates)) if rates else 0
        return f"{avg_rate}% avg"
    if key == 'workload_distribution':
        if not value:
            return '0 active'
        return f"{len(value)} contributors"
    if key == 'tasks_by_phase':
        if not value:
            return '0 phases'
        total = sum(value.values())
        return f"{total} across {len(value)} phases"
    return str(len(value))


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


def get_promoted_metrics(board, raw=False):
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
    task_details = {}   # key -> list of task dicts for modal display
    explanations = {}   # key -> human-readable explanation string

    if project_type == 'product_tech':
        # Task velocity: tasks completed in last 7 days
        completed_last_week = tasks.filter(progress=100, updated_at__gte=seven_days_ago).count()
        metrics['task_velocity'] = f"{completed_last_week} tasks/week"

        # Overdue count
        overdue = tasks.filter(
            due_date__isnull=False, due_date__date__lt=today
        ).exclude(progress=100).count()
        metrics['overdue_count'] = overdue

        # Blocked / high-risk count (all urgent tasks, plus high-priority with 0% progress)
        blocked_qs = tasks.filter(
            Q(priority='urgent') | Q(priority='high', progress=0)
        ).exclude(progress=100).select_related('column', 'assigned_to')
        metrics['blocked_count'] = blocked_qs.count()
        task_details['blocked_count'] = list(
            blocked_qs.values('id', 'title', 'priority', 'column__name', 'assigned_to__username')[:20]
        )
        explanations['blocked_count'] = (
            f"Tasks that are urgent priority, or high priority with 0% progress. "
            f"Found {blocked_qs.count()} task(s) that may need immediate attention."
        )

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
        explanations['completion_rate_by_column'] = (
            "Shows what percentage of tasks in each column have reached 100% progress. "
            "Columns like 'Done' are expected to be 100% while active columns will be lower. "
            "This helps identify columns where tasks are stalling."
        )

        # Workload distribution — show ALL users with tasks on the board
        workload = list(
            tasks.values('assigned_to__username')
            .annotate(
                count=Count('id'),
                active_count=Count('id', filter=Q(progress__lt=100)),
            )
            .order_by('-count')
        )
        metrics['workload_distribution'] = {
            (w['assigned_to__username'] or 'Unassigned'): f"{w['active_count']} active / {w['count']} total"
            for w in workload
        }
        explanations['workload_distribution'] = (
            f"All team members with tasks on this board. "
            f"Shows active (incomplete) and total task counts per contributor."
        )

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
        # Simpler calculation: completed tasks that were not overdue at completion
        completed_with_due = with_due.filter(progress=100).count()
        overdue_completed = with_due.filter(
            progress=100, due_date__date__lt=F('updated_at__date')
        ).count()
        on_time_completed = completed_with_due - overdue_completed
        adherence_pct = int(on_time_completed / total_with_due * 100) if total_with_due > 0 else 0
        metrics['deadline_adherence_rate'] = f"{adherence_pct}%" if total_with_due > 0 else "N/A"
        explanations['deadline_adherence_rate'] = (
            f"Percentage of tasks with deadlines that were completed on time. "
            f"{on_time_completed} of {total_with_due} tasks with due dates were finished before their deadline. "
            f"{overdue_completed} task(s) were completed late."
        )

        # Content output rate (tasks completed this week)
        content_done = tasks.filter(progress=100, updated_at__gte=seven_days_ago).count()
        metrics['content_output_rate'] = f"{content_done} tasks/week"

        # Tasks currently in review columns (heuristic: columns with 'review' in name)
        review_cols = columns.filter(name__icontains='review')
        if review_cols.exists():
            review_tasks_qs = tasks.filter(column__in=review_cols).exclude(
                progress=100
            ).select_related('column', 'assigned_to')
            review_count = review_tasks_qs.count()
            metrics['tasks_in_review'] = review_count
            task_details['tasks_in_review'] = list(
                review_tasks_qs.values(
                    'id', 'title', 'priority', 'column__name', 'assigned_to__username'
                )[:20]
            )
            explanations['tasks_in_review'] = (
                f"Tasks sitting in columns containing 'review' in their name. "
                f"Found {review_count} task(s) awaiting review/approval."
            )
        else:
            # No review column on this board
            metrics['tasks_in_review'] = "N/A"
            explanations['tasks_in_review'] = (
                "No column with 'review' in its name was found on this board. "
                "Add a column like 'In Review' or 'Review' to track tasks awaiting approval."
            )

        # Milestone completion percentage — only count actual milestone items
        milestone_qs = Task.objects.filter(column__board=board, item_type='milestone')
        total_milestones = milestone_qs.count()
        completed_milestones = milestone_qs.filter(
            Q(milestone_status='completed') | Q(progress=100)
        ).count()
        if total_milestones > 0:
            milestone_pct = int(completed_milestones / total_milestones * 100)
            metrics['milestone_completion_pct'] = f"{milestone_pct}%"
            explanations['milestone_completion_pct'] = (
                f"{completed_milestones} of {total_milestones} milestones are completed. "
                f"This tracks progress through the project's key milestone markers."
            )
            task_details['milestone_completion_pct'] = list(
                milestone_qs.values(
                    'id', 'title', 'milestone_status', 'column__name', 'assigned_to__username', 'progress'
                )[:20]
            )
        else:
            metrics['milestone_completion_pct'] = "N/A"
            explanations['milestone_completion_pct'] = (
                "No milestone items found on this board. "
                "Add items with the 'Milestone' type to track key project checkpoints."
            )

    elif project_type == 'operations':
        # Process completion rate (completed / created in last 30 days)
        created_30d = tasks.filter(created_at__gte=thirty_days_ago).count()
        completed_30d = tasks.filter(progress=100, updated_at__gte=thirty_days_ago).count()
        process_pct = int(completed_30d / created_30d * 100) if created_30d > 0 else 0
        metrics['process_completion_rate'] = f"{process_pct}%" if created_30d > 0 else "N/A"
        explanations['process_completion_rate'] = (
            f"Ratio of completed tasks to newly created tasks in the last 30 days. "
            f"{completed_30d} completed out of {created_30d} created. "
            f"A rate above 100% means the team is clearing backlog faster than new work arrives."
        )

        # Workload distribution — show ALL users with tasks on the board
        workload = list(
            tasks.values('assigned_to__username')
            .annotate(
                count=Count('id'),
                active_count=Count('id', filter=Q(progress__lt=100)),
            )
            .order_by('-count')
        )
        metrics['workload_distribution'] = {
            (w['assigned_to__username'] or 'Unassigned'): f"{w['active_count']} active / {w['count']} total"
            for w in workload
        }
        explanations['workload_distribution'] = (
            f"All team members with tasks on this board. "
            f"Shows active (incomplete) and total task counts per contributor."
        )

        # Average cycle time (creation → completion, in days)
        completed_tasks_qs = tasks.filter(progress=100, updated_at__isnull=False)
        if completed_tasks_qs.exists():
            cycle_times = []
            for t in completed_tasks_qs[:100]:  # cap for perf
                delta = (t.updated_at - t.created_at).total_seconds()
                cycle_times.append(max(0, delta / 86400))  # convert to days, floor at 0
            avg_days = sum(cycle_times) / len(cycle_times) if cycle_times else 0
            metrics['avg_cycle_time_days'] = f"{avg_days:.1f} days"
            explanations['avg_cycle_time_days'] = (
                f"Average time from task creation to completion across "
                f"{len(cycle_times)} completed task(s). "
                f"Shorter cycle times indicate faster throughput."
            )
        else:
            metrics['avg_cycle_time_days'] = "N/A"
            explanations['avg_cycle_time_days'] = "No completed tasks to measure cycle time."

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
        on_time_pct = int(on_time / total_done_with_due * 100) if total_done_with_due > 0 else 0
        metrics['on_time_rate'] = f"{on_time_pct}%" if total_done_with_due > 0 else "N/A"
        explanations['on_time_rate'] = (
            f"Percentage of completed tasks that were finished before their due date. "
            f"{on_time} of {total_done_with_due} completed tasks with deadlines were on time. "
            f"{overdue_at_completion} task(s) were completed after their deadline."
        )

    if raw:
        return metrics

    # Convert raw metrics dict to a list of rich dicts for the template
    metric_keys = PROMOTED_METRICS.get(project_type, list(metrics.keys()))
    result = []
    for key in metric_keys:
        if key in metrics:
            raw_value = metrics[key]
            config = METRIC_CONFIG.get(key, {})
            entry = {
                'key': key,
                'label': config.get('label', key.replace('_', ' ').title()),
                'value': _format_metric_value(key, raw_value),
                'icon': config.get('icon', 'fas fa-chart-bar'),
                'color': config.get('color', 'primary'),
                'description': config.get('description', ''),
                'modal_target': config.get('modal_target', ''),
                'explanation': explanations.get(key, ''),
            }
            if isinstance(raw_value, dict):
                entry['detail_items'] = [
                    {'name': k, 'value': v} for k, v in raw_value.items()
                ]
            # Add task details for metrics that have them
            if key in task_details and task_details[key]:
                entry['task_details'] = [
                    {
                        'id': t['id'],
                        'title': t['title'],
                        'priority': t.get('priority', ''),
                        'column_name': t.get('column__name', ''),
                        'assigned_to': t.get('assigned_to__username') or 'Unassigned',
                    }
                    for t in task_details[key]
                ]
            result.append(entry)
    return result


# ---------------------------------------------------------------------------
# Chart configurations by project type
# ---------------------------------------------------------------------------

PROMOTED_CHARTS = {
    'product_tech': [
        {
            'id': 'columnChart',
            'title': 'Tasks by Column',
            'type': 'bar',
            'data_key': 'tasks_by_column',
            'label_field': 'name',
            'value_field': 'count',
            'color': 'rgba(54, 162, 235, 0.8)',
            'border_color': 'rgba(54, 162, 235, 1)',
        },
        {
            'id': 'priorityChart',
            'title': 'Tasks by Priority',
            'type': 'doughnut',
            'data_key': 'tasks_by_priority',
            'label_field': 'priority',
            'value_field': 'count',
            'use_priority_colors': True,
        },
        {
            'id': 'userChart',
            'title': 'Workload Distribution',
            'type': 'bar',
            'data_key': 'tasks_by_user',
            'label_field': 'username',
            'value_field': 'count',
            'color': 'rgba(75, 192, 192, 0.8)',
            'border_color': 'rgba(75, 192, 192, 1)',
            'index_axis': 'y',
        },
        {
            'id': 'velocityChart',
            'title': 'Completion Velocity (Last 30 Days)',
            'type': 'line',
            'data_key': 'completed_tasks',
            'label_field': 'date',
            'value_field': 'count',
            'color': 'rgba(40, 167, 69, 0.8)',
            'border_color': 'rgba(40, 167, 69, 1)',
            'fill': True,
        },
    ],
    'marketing_campaign': [
        {
            'id': 'phaseChart',
            'title': 'Tasks by Phase',
            'type': 'bar',
            'data_key': 'tasks_by_column',
            'label_field': 'name',
            'value_field': 'count',
            'color': 'rgba(153, 102, 255, 0.8)',
            'border_color': 'rgba(153, 102, 255, 1)',
        },
        {
            'id': 'priorityChart',
            'title': 'Content Priority Mix',
            'type': 'doughnut',
            'data_key': 'tasks_by_priority',
            'label_field': 'priority',
            'value_field': 'count',
            'use_priority_colors': True,
        },
        {
            'id': 'userChart',
            'title': 'Team Output Distribution',
            'type': 'bar',
            'data_key': 'tasks_by_user',
            'label_field': 'username',
            'value_field': 'count',
            'color': 'rgba(255, 159, 64, 0.8)',
            'border_color': 'rgba(255, 159, 64, 1)',
            'index_axis': 'y',
        },
        {
            'id': 'deadlineChart',
            'title': 'Content Delivery Trend',
            'type': 'line',
            'data_key': 'completed_tasks',
            'label_field': 'date',
            'value_field': 'count',
            'color': 'rgba(40, 167, 69, 0.8)',
            'border_color': 'rgba(40, 167, 69, 1)',
            'fill': True,
        },
    ],
    'operations': [
        {
            'id': 'columnChart',
            'title': 'Process Stages',
            'type': 'bar',
            'data_key': 'tasks_by_column',
            'label_field': 'name',
            'value_field': 'count',
            'color': 'rgba(54, 162, 235, 0.8)',
            'border_color': 'rgba(54, 162, 235, 1)',
        },
        {
            'id': 'userChart',
            'title': 'Workload Distribution',
            'type': 'bar',
            'data_key': 'tasks_by_user',
            'label_field': 'username',
            'value_field': 'count',
            'color': 'rgba(75, 192, 192, 0.8)',
            'border_color': 'rgba(75, 192, 192, 1)',
            'index_axis': 'y',
        },
        {
            'id': 'leanChart',
            'title': 'Lean Six Sigma Analysis',
            'type': 'doughnut',
            'data_key': 'tasks_by_lean_category',
            'label_field': 'name',
            'value_field': 'count',
            'use_item_colors': True,
        },
        {
            'id': 'cycleChart',
            'title': 'Completion Trend',
            'type': 'line',
            'data_key': 'completed_tasks',
            'label_field': 'date',
            'value_field': 'count',
            'color': 'rgba(40, 167, 69, 0.8)',
            'border_color': 'rgba(40, 167, 69, 1)',
            'fill': True,
        },
    ],
}


def get_promoted_charts(board):
    """
    Return the chart configuration list for the board's project type.
    Returns None if the board has no confirmed project type.
    """
    project_type = board.project_type
    if not project_type or project_type not in PROMOTED_CHARTS:
        return None
    return PROMOTED_CHARTS[project_type]


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
            board_metrics = get_promoted_metrics(b, raw=True)
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
