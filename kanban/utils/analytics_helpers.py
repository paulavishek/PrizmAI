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
        'label': 'High-Priority / At-Risk',
        'icon': 'fas fa-exclamation-circle',
        'color': 'warning',
        'description': 'Urgent tasks (any progress) or high-priority tasks with 0% progress that may need attention. These are not necessarily blocked — there is no dependency/blocked state in the data.',
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

        # High-priority / at-risk count: urgent tasks, plus high-priority tasks
        # with 0% progress. NOTE: this is a priority-based attention signal, NOT
        # a true "blocked" state — the data has no dependency/blocked field.
        blocked_qs = tasks.filter(
            Q(priority='urgent') | Q(priority='high', progress=0)
        ).exclude(progress=100).select_related('column', 'assigned_to')
        metrics['blocked_count'] = blocked_qs.count()
        task_details['blocked_count'] = list(
            blocked_qs.values('id', 'title', 'priority', 'column__name', 'assigned_to__username')[:20]
        )
        explanations['blocked_count'] = (
            f"High-priority / at-risk tasks: urgent priority, or high priority with 0% progress. "
            f"Found {blocked_qs.count()} task(s) that may need attention "
            f"(not necessarily blocked)."
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
# Per-type chart data computation helpers
# ---------------------------------------------------------------------------

def get_cycle_time_distribution(board):
    """Bucket completed tasks by cycle time (created_at to completed_at / updated_at)."""
    from kanban.models import Task
    tasks = Task.objects.filter(
        column__board=board, item_type='task', progress=100
    ).exclude(created_at__isnull=True)
    buckets = [
        {'name': '1 day',      'count': 0},
        {'name': '2-3 days',   'count': 0},
        {'name': '4-7 days',   'count': 0},
        {'name': '1-2 weeks',  'count': 0},
        {'name': '2+ weeks',   'count': 0},
    ]
    for t in tasks:
        end = t.completed_at or t.updated_at
        if not end:
            continue
        days = max(0, (end - t.created_at).days)
        if days <= 1:
            buckets[0]['count'] += 1
        elif days <= 3:
            buckets[1]['count'] += 1
        elif days <= 7:
            buckets[2]['count'] += 1
        elif days <= 14:
            buckets[3]['count'] += 1
        else:
            buckets[4]['count'] += 1
    return buckets


def get_weekly_completion_trend(board, weeks=8):
    """Return completed-task counts grouped by week for the last N weeks."""
    from kanban.models import Task
    cutoff = timezone.now() - timedelta(weeks=weeks)
    qs = Task.objects.filter(
        column__board=board, item_type='task', progress=100,
        updated_at__gte=cutoff,
    ).values('updated_at__date').annotate(count=Count('id')).order_by('updated_at__date')

    # Map each completed date to its Monday (week start)
    week_map = {}
    for row in qs:
        d = row['updated_at__date']
        if d is None:
            continue
        monday = d - timedelta(days=d.weekday())
        week_map[monday] = week_map.get(monday, 0) + row['count']

    start = (timezone.now() - timedelta(weeks=weeks)).date()
    start -= timedelta(days=start.weekday())  # align to Monday
    result = []
    for i in range(weeks):
        d = start + timedelta(weeks=i)
        label = f"Wk {d.strftime('%b')} {d.day}"
        result.append({'date': label, 'count': week_map.get(d, 0)})
    return result


# Expanded keyword sets for label/title classification
_BUG_KEYWORDS = ('bug', 'fix', 'defect', 'issue', 'error', 'crash', 'regression', 'hotfix')
_FEATURE_KEYWORDS = ('feature', 'story', 'enhancement', 'improvement', 'epic', 'new', 'add', 'implement')


def _classify_text(text):
    """Return 'bug', 'feature', or 'chore' based on keyword matching against lowercased text."""
    t = text.lower()
    if any(kw in t for kw in _BUG_KEYWORDS):
        return 'bug'
    if any(kw in t for kw in _FEATURE_KEYWORDS):
        return 'feature'
    return 'chore'


def get_label_type_breakdown(board):
    """Classify tasks by label keywords into Bug / Feature / Chore categories.

    Priority order:
    1. If the task has labels → classify from joined label names.
    2. If the task has no labels → infer from task title.

    Returns None only when the board has no tasks at all.
    Includes 'title_inferred': True when any tasks were classified from titles.
    """
    from kanban.models import Task
    tasks = list(
        Task.objects.filter(column__board=board, item_type='task')
        .prefetch_related('labels')
        .only('id', 'title')
    )
    if not tasks:
        return None

    bug_count = feature_count = chore_count = 0
    title_inferred = False

    for t in tasks:
        labels = [lbl.name.lower() for lbl in t.labels.all()]
        if labels:
            joined = ' '.join(labels)
            cat = _classify_text(joined)
        else:
            # Title-based inference fallback
            cat = _classify_text(t.title or '')
            title_inferred = True
        if cat == 'bug':
            bug_count += 1
        elif cat == 'feature':
            feature_count += 1
        else:
            chore_count += 1

    return [
        {'name': 'Bug / Fix',     'count': bug_count,     'color': 'rgba(220, 53, 69, 0.8)',  'title_inferred': title_inferred},
        {'name': 'Feature',       'count': feature_count, 'color': 'rgba(54, 162, 235, 0.8)', 'title_inferred': title_inferred},
        {'name': 'Chore / Other', 'count': chore_count,   'color': 'rgba(108, 117, 125, 0.8)','title_inferred': title_inferred},
    ]


def get_backlog_age_distribution(board):
    """Bucket tasks in the To-Do/Backlog column by age since creation."""
    from kanban.models import Task, Column
    today = timezone.now().date()
    # Find To-Do/Backlog column by name; fall back to lowest-position column
    todo_col = (
        Column.objects.filter(board=board)
        .filter(Q(name__icontains='to do') | Q(name__icontains='todo') | Q(name__icontains='backlog'))
        .order_by('position')
        .first()
    )
    if not todo_col:
        todo_col = Column.objects.filter(board=board).order_by('position').first()
    buckets = [
        {'name': '< 1 week',  'count': 0, 'intensity': 1},
        {'name': '1-2 weeks', 'count': 0, 'intensity': 2},
        {'name': '2-4 weeks', 'count': 0, 'intensity': 3},
        {'name': '> 1 month', 'count': 0, 'intensity': 4},
    ]
    if not todo_col:
        return buckets
    for t in Task.objects.filter(column=todo_col, item_type='task'):
        age = (today - t.created_at.date()).days
        if age < 7:
            buckets[0]['count'] += 1
        elif age < 14:
            buckets[1]['count'] += 1
        elif age < 28:
            buckets[2]['count'] += 1
        else:
            buckets[3]['count'] += 1
    return buckets


def get_stage_transition_funnel(board):
    """Return task counts per column in board position order (pipeline funnel view)."""
    from kanban.models import Task, Column
    columns = Column.objects.filter(board=board).order_by('position')
    tasks = Task.objects.filter(column__board=board, item_type='task')
    return [
        {'name': col.name, 'count': tasks.filter(column=col).count(), 'position': col.position}
        for col in columns
    ]


def get_on_time_vs_late_weekly(board, weeks=8):
    """Return on-time vs late completed-task counts per week for the last N weeks.
    Returns None if fewer than 3 completed tasks have due dates (JS falls back to trend)."""
    from kanban.models import Task
    cutoff = timezone.now() - timedelta(weeks=weeks)
    completed = Task.objects.filter(
        column__board=board, item_type='task', progress=100,
        updated_at__gte=cutoff, due_date__isnull=False,
    )
    if completed.count() < 3:
        return None

    week_map = {}
    for t in completed:
        # Bucket by updated_at (spread across the full window) but judge on-time
        # vs late by the REAL completion date vs the deadline — updated_at can be
        # bumped by any later edit and is not a reliable completion signal.
        d = t.updated_at.date()
        monday = d - timedelta(days=d.weekday())
        if monday not in week_map:
            week_map[monday] = {'on_time': 0, 'late': 0}
        completed_on = (t.completed_at or t.updated_at).date()
        if completed_on <= t.due_date.date():
            week_map[monday]['on_time'] += 1
        else:
            week_map[monday]['late'] += 1

    start = (timezone.now() - timedelta(weeks=weeks)).date()
    start -= timedelta(days=start.weekday())
    result = []
    for i in range(weeks):
        d = start + timedelta(weeks=i)
        label = f"Wk {d.strftime('%b')} {d.day}"
        wd = week_map.get(d, {'on_time': 0, 'late': 0})
        result.append({'date': label, 'on_time': wd['on_time'], 'late': wd['late']})
    return result


def _column_weight(name):
    """Return a relative weight for a column based on its typical workflow role."""
    n = name.lower()
    if any(kw in n for kw in ('to do', 'todo', 'backlog')):
        return 2.5
    if any(kw in n for kw in ('in progress', 'doing', 'active')):
        return 2.0
    if any(kw in n for kw in ('review', 'testing', 'qa', 'approval')):
        return 1.0
    if any(kw in n for kw in ('done', 'complete', 'closed', 'finished')):
        return 0.5
    return 1.0  # default


def get_estimated_time_per_stage(board):
    """Estimate average days per stage using a weighted distribution of the board's
    overall average cycle time.  Columns get weights based on typical workflow role
    so the bars are meaningfully different lengths even without task-column history.
    No task-column history is tracked; this is always an approximation."""
    from kanban.models import Task, Column
    columns = list(Column.objects.filter(board=board).order_by('position'))
    if not columns:
        return []
    completed = Task.objects.filter(
        column__board=board, item_type='task', progress=100,
    )
    cycle_times = []
    for t in completed[:100]:
        end = t.completed_at or t.updated_at
        if end and t.created_at:
            cycle_times.append(max(0, (end - t.created_at).days))
    avg_total = sum(cycle_times) / len(cycle_times) if cycle_times else 0

    weights = [_column_weight(col.name) for col in columns]
    total_weight = sum(weights) or 1
    return [
        {
            'name': col.name,
            'avg_days': round(avg_total * (weights[i] / total_weight), 1),
            'estimated': True,
        }
        for i, col in enumerate(columns)
    ]


def get_promoted_chart_data(board):
    """Compute all type-specific chart datasets for a board.
    Returns a dict keyed by data_key string; values are list/None."""
    project_type = board.project_type
    if not project_type:
        return {}
    data = {}
    if project_type == 'product_tech':
        data['cycle_time_distribution'] = get_cycle_time_distribution(board)
        data['weekly_completion']        = get_weekly_completion_trend(board)
        data['label_type_breakdown']     = get_label_type_breakdown(board)
        data['backlog_age']              = get_backlog_age_distribution(board)
    elif project_type == 'marketing_campaign':
        data['weekly_completion']  = get_weekly_completion_trend(board)
        data['stage_funnel']       = get_stage_transition_funnel(board)
    elif project_type == 'operations':
        data['on_time_vs_late'] = get_on_time_vs_late_weekly(board)
        data['stage_time']      = get_estimated_time_per_stage(board)
    return data


# ---------------------------------------------------------------------------
# Chart configurations by project type
# ---------------------------------------------------------------------------

PROMOTED_CHARTS = {
    'product_tech': [
        {
            'id': 'cycleTimeChart',
            'title': 'Cycle Time Distribution',
            'type': 'bar',
            'data_key': 'cycle_time_distribution',
            'label_field': 'name',
            'value_field': 'count',
            'color': 'rgba(54, 162, 235, 0.8)',
            'border_color': 'rgba(54, 162, 235, 1)',
        },
        {
            'id': 'deployFreqChart',
            'title': 'Deployment / Completion Frequency',
            'type': 'bar',
            'data_key': 'weekly_completion',
            'label_field': 'date',
            'value_field': 'count',
            'color': 'rgba(32, 201, 151, 0.8)',
            'border_color': 'rgba(32, 201, 151, 1)',
        },
        {
            'id': 'labelBreakdownChart',
            'title': 'Bug vs Feature vs Chore Breakdown',
            'type': 'doughnut',
            'data_key': 'label_type_breakdown',
            'label_field': 'name',
            'value_field': 'count',
            'use_item_colors': True,
        },
        {
            'id': 'backlogAgeChart',
            'title': 'Task Age in Backlog',
            'type': 'bar',
            'data_key': 'backlog_age',
            'label_field': 'name',
            'value_field': 'count',
            'amber_gradient': True,
        },
    ],
    'marketing_campaign': [
        {
            'id': 'phaseChart',
            'title': 'Tasks by Phase / Column',
            'type': 'bar',
            'data_key': 'tasks_by_column',
            'label_field': 'name',
            'value_field': 'count',
            'color': 'rgba(153, 102, 255, 0.8)',
            'border_color': 'rgba(153, 102, 255, 1)',
            'index_axis': 'y',
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
            'id': 'weeklyOutputChart',
            'title': 'Content Delivered per Week',
            'type': 'bar',
            'data_key': 'weekly_completion',
            'label_field': 'date',
            'value_field': 'count',
            'color': 'rgba(255, 99, 132, 0.8)',
            'border_color': 'rgba(255, 99, 132, 1)',
        },
        {
            'id': 'funnelChart',
            'title': 'Stage Transition Funnel',
            'type': 'bar',
            'data_key': 'stage_funnel',
            'label_field': 'name',
            'value_field': 'count',
            'color': 'rgba(153, 102, 255, 0.8)',
            'border_color': 'rgba(153, 102, 255, 1)',
            'index_axis': 'y',
        },
    ],
    'operations': [
        {
            'id': 'columnChart',
            'title': 'Process Stage Distribution',
            'type': 'bar',
            'data_key': 'tasks_by_column',
            'label_field': 'name',
            'value_field': 'count',
            'color': 'rgba(54, 162, 235, 0.8)',
            'border_color': 'rgba(54, 162, 235, 1)',
        },
        {
            'id': 'onTimeLateChart',
            'title': 'On-Time vs Late Completion (Last 8 Weeks)',
            'type': 'bar',
            'data_key': 'on_time_vs_late',
            'label_field': 'date',
            'value_field': 'count',
            'stacked_series': True,
        },
        {
            'id': 'stageTimeChart',
            'title': 'SLA / Cycle Time by Stage',
            'type': 'bar',
            'data_key': 'stage_time',
            'label_field': 'name',
            'value_field': 'avg_days',
            'color': 'rgba(255, 193, 7, 0.8)',
            'border_color': 'rgba(255, 193, 7, 1)',
            'index_axis': 'y',
            'estimated_label': True,
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

    Results are additionally scoped to the record's own workspace (when set) so a
    portfolio aggregation can never pull in a board from a different workspace —
    defence-in-depth against demo/real bleed-through.
    """
    from kanban.models import Board

    if record_type == 'goal':
        qs = Board.objects.filter(strategy__mission__organization_goal=record)
    elif record_type == 'mission':
        qs = Board.objects.filter(strategy__mission=record)
    elif record_type == 'strategy':
        qs = Board.objects.filter(strategy=record)
    else:
        return Board.objects.none()

    # Scope to the record's workspace when it has one (legacy records may not).
    workspace_id = getattr(record, 'workspace_id', None)
    if workspace_id is not None:
        qs = qs.filter(workspace_id=workspace_id)
    return qs


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
