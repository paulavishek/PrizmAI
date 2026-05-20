"""
Spectra Verified Data Fetchers (VDFs)

Centralized data access layer for Spectra's context-building pipeline.
Every context method in chatbot_service.py must call these functions
instead of writing inline ORM queries. This ensures:

1. Single source of truth for task status (always task.column.name, never progress-based)
2. Correct milestone completion (dual condition: milestone_status OR done-column)
3. Correct priority rendering (always get_priority_display())
4. Board-scoped queries (no cross-board leakage for board-specific answers)
5. Correct dependency direction (reverse M2M for blocking counts)

Created: April 12, 2026 — Spectra Accuracy Overhaul v1.1
"""

import logging
from datetime import date

from django.db.models import Count, F, Q
from django.utils import timezone

logger = logging.getLogger(__name__)

# Column names that indicate a task is complete (lowercase comparison always)
DONE_COLUMN_NAMES = frozenset({
    'done', 'completed', 'complete', 'closed', 'finished', 'resolved'
})


def _is_done_column(column_name):
    """Check if a column name indicates completion."""
    return column_name.lower().strip() in DONE_COLUMN_NAMES


def fetch_task_dict(task):
    """
    Convert a Task ORM object into a normalized Spectra-safe dict.

    Caller MUST use .select_related('column', 'assigned_to') before passing
    the task in. Dependencies and labels should be prefetched if needed.

    ── N+1 WARNING (Custom Fields) ────────────────────────────────────────
    This function reads `task.custom_field_values` to inject user-defined
    custom-field data into the Spectra Task Dict. Every queryset that calls
    `fetch_task_dict` MUST add:

        prefetch_related(
            'custom_field_values__field',
            'custom_field_values__selected_options',
        )

    Otherwise a board with N tasks triggers up to 3N extra DB queries
    (one per task for the value rows, plus one each for the field FK and
    the selected_options M2M). On a 100-task board that's ~300 unnecessary
    hits every time Spectra answers a question. `fetch_board_tasks` below
    already includes this prefetch — new callers must do the same.

    Returns a dict — the canonical "Spectra Task Dict" contract.
    """
    today = timezone.now().date()

    # Column name — the LIVE source of truth for task status
    col_name = task.column.name if task.column_id else 'Unknown'

    # Completion: dual condition — neither alone is sufficient
    #   1. Column name indicates done, OR
    #   2. Milestone with milestone_status='completed'
    in_done_column = _is_done_column(col_name)
    is_milestone_completed = (
        task.item_type != 'task' and task.milestone_status == 'completed'
    )
    is_complete = in_done_column or is_milestone_completed

    # Priority: always use Django's built-in choice display
    priority_label = task.get_priority_display()

    # Assignee
    if task.assigned_to_id:
        display_name = task.assigned_to.get_full_name()
        assigned_to_display = display_name if display_name.strip() else task.assigned_to.username
        assigned_to_username = task.assigned_to.username
    else:
        assigned_to_display = 'Unassigned'
        assigned_to_username = None

    # Due date and overdue check
    due_date_val = task.due_date
    if due_date_val and hasattr(due_date_val, 'date'):
        due_date_date = due_date_val.date()
    elif due_date_val:
        due_date_date = due_date_val
    else:
        due_date_date = None

    is_overdue = bool(
        due_date_date and due_date_date < today and not is_complete
    )
    overdue_days = (today - due_date_date).days if is_overdue else 0

    # Parent task title (requires select_related('parent_task'))
    parent_task_title = task.parent_task.title if task.parent_task_id and hasattr(task, 'parent_task') and task.parent_task else None

    # Dependency titles (requires prefetch_related('dependencies'))
    try:
        dependency_titles = [d.title for d in task.dependencies.all()] if hasattr(task, 'dependencies') else []
    except Exception:
        dependency_titles = []

    # Subtask count (requires prefetch_related('subtasks'))
    try:
        subtask_count = task.subtasks.count() if hasattr(task, 'subtasks') else 0
    except Exception:
        subtask_count = 0

    # Comment count
    try:
        comment_count = task.comments.count() if hasattr(task, 'comments') else 0
    except Exception:
        comment_count = 0

    # Custom fields — honors per-field `exclude_from_ai` flag.
    # Returns {} cheaply for tasks without custom-field values.
    try:
        from kanban.custom_field_serializers import serialize_for_ai
        custom_fields = serialize_for_ai(task)
    except Exception:
        custom_fields = {}

    return {
        'id': task.id,
        'board_id': task.column.board_id if task.column_id else None,
        'title': task.title,
        'column_name': col_name,
        'is_complete': is_complete,
        'in_done_column': in_done_column,
        'item_type': task.item_type,
        'milestone_status': task.milestone_status,
        'priority_label': priority_label,
        'priority_value': task.priority,   # raw string: 'low', 'medium', 'high', 'urgent'
        'assigned_to_username': assigned_to_username,
        'assigned_to_display': assigned_to_display,
        'due_date': due_date_val,
        'due_date_date': due_date_date,
        'is_overdue': is_overdue,
        'overdue_days': overdue_days,
        'progress': task.progress,
        'description': task.description or '',
        'comment_count': comment_count,
        'parent_task_id': task.parent_task_id,
        'parent_task_title': parent_task_title,
        'dependency_titles': dependency_titles,
        'subtask_count': subtask_count,
        'risk_level': task.risk_level,
        'ai_risk_score': task.ai_risk_score,
        'updated_at': task.updated_at if hasattr(task, 'updated_at') else None,
        'custom_fields': custom_fields,
    }


def fetch_board_tasks(board, filters=None):
    """
    Fetch ALL tasks for a board as normalized Spectra dicts.

    Always scoped to a single board. Never cross-board.

    Optional filters dict keys:
        column_name     — exact column name (case-insensitive)
        assigned_to_username — exact username string
        item_type       — 'task', 'milestone', 'epic'
        exclude_item_type — item_type to exclude (e.g. 'task' to get milestones+epics)
        is_overdue      — True to keep only overdue items
        priority_value  — min priority level ('high' keeps high+urgent)
        is_complete     — True/False to filter by completion
    """
    from kanban.models import Task

    qs = (
        Task.objects
        .filter(column__board=board)
        .select_related('column', 'assigned_to', 'parent_task')
        .prefetch_related(
            'dependencies', 'labels', 'subtasks',
            # Custom fields — see fetch_task_dict's N+1 warning above.
            'custom_field_values__field',
            'custom_field_values__selected_options',
        )
        .order_by('column__position', 'position')
    )

    task_dicts = [fetch_task_dict(t) for t in qs]

    if not filters:
        return task_dicts

    # Apply filters on the normalized dicts
    if 'item_type' in filters:
        task_dicts = [t for t in task_dicts if t['item_type'] == filters['item_type']]

    if 'exclude_item_type' in filters:
        task_dicts = [t for t in task_dicts if t['item_type'] != filters['exclude_item_type']]

    if 'column_name' in filters:
        target = filters['column_name'].lower().strip()
        task_dicts = [t for t in task_dicts if t['column_name'].lower().strip() == target]

    if 'assigned_to_username' in filters:
        task_dicts = [
            t for t in task_dicts
            if t['assigned_to_username'] == filters['assigned_to_username']
        ]

    if 'is_overdue' in filters:
        task_dicts = [t for t in task_dicts if t['is_overdue'] == filters['is_overdue']]

    if 'is_complete' in filters:
        task_dicts = [t for t in task_dicts if t['is_complete'] == filters['is_complete']]

    if 'priority_value' in filters:
        priority_order = {'low': 0, 'medium': 1, 'high': 2, 'urgent': 3}
        min_level = priority_order.get(filters['priority_value'], 0)
        task_dicts = [
            t for t in task_dicts
            if priority_order.get(t['priority_value'], 0) >= min_level
        ]

    return task_dicts


def fetch_milestones(board):
    """
    Fetch all milestone/epic items for a board with correct live status.

    Completion uses dual condition:
      - milestone_status == 'completed', OR
      - column name is in DONE_COLUMN_NAMES
    Neither alone is sufficient.

    Returns list of task dicts sorted by due_date.
    """
    all_items = fetch_board_tasks(board, filters={'exclude_item_type': 'task'})
    return sorted(
        all_items,
        key=lambda t: (t['due_date_date'] is None, t['due_date_date'] or date.max)
    )


def fetch_column_distribution(board):
    """
    Return task count per column, using live column FK (never progress-based).

    Returns OrderedDict-like list of tuples: [(column_name, count), ...]
    ordered by column position.
    Only counts item_type='task' (excludes milestones/epics).
    """
    from kanban.models import Task

    results = (
        Task.objects
        .filter(column__board=board, item_type='task')
        .values('column__name', 'column__position')
        .annotate(count=Count('id'))
        .order_by('column__position')
    )
    return [(row['column__name'], row['count']) for row in results]


def fetch_dependency_graph(board):
    """
    Return a complete dependency map for a board.

    Returns dict keyed by task ID:
    {
        task_id: {
            'title': str,
            'column_name': str,
            'is_complete': bool,
            'assigned_to_display': str,
            'priority_label': str,
            'blocking': [{'id': int, 'title': str}, ...],  # tasks THIS task blocks
            'blocked_by': [{'id': int, 'title': str}, ...], # tasks blocking THIS task
            'blocking_count': int,
        }
    }

    Blocking direction:
      task.dependencies.all() = tasks THIS task depends on (forward / "blocked by")
      Task.objects.filter(dependencies=task) = tasks that depend on THIS task (reverse / "blocks")
    """
    from kanban.models import Task

    tasks = (
        Task.objects
        .filter(column__board=board, item_type='task')
        .select_related('column', 'assigned_to')
        .prefetch_related('dependencies')
    )

    # Build forward dependency map from prefetched data
    forward_deps = {}  # task_id -> list of task_ids it depends on
    task_lookup = {}
    for task in tasks:
        task_lookup[task.id] = task
        forward_deps[task.id] = [dep.id for dep in task.dependencies.all()]

    # Build reverse map: for each task, which other tasks depend on it?
    reverse_deps = {tid: [] for tid in task_lookup}
    for tid, dep_ids in forward_deps.items():
        for dep_id in dep_ids:
            if dep_id in reverse_deps:
                reverse_deps[dep_id].append(tid)

    graph = {}
    for tid, task in task_lookup.items():
        col_name = task.column.name if task.column_id else 'Unknown'
        is_complete = _is_done_column(col_name)

        assignee = 'Unassigned'
        if task.assigned_to_id:
            name = task.assigned_to.get_full_name()
            assignee = name if name.strip() else task.assigned_to.username

        # Blocking: tasks that list THIS task as a dependency (reverse)
        blocking = [
            {'id': btid, 'title': task_lookup[btid].title}
            for btid in reverse_deps.get(tid, [])
            if btid in task_lookup
        ]

        # Blocked by: tasks THIS task depends on (forward)
        blocked_by = [
            {'id': did, 'title': task_lookup[did].title}
            for did in forward_deps.get(tid, [])
            if did in task_lookup
        ]

        graph[tid] = {
            'title': task.title,
            'column_name': col_name,
            'is_complete': is_complete,
            'assigned_to_display': assignee,
            'priority_label': task.get_priority_display(),
            'blocking': blocking,
            'blocked_by': blocked_by,
            'blocking_count': len(blocking),
        }

    return graph


def fetch_assignee_workload(board):
    """
    Return task distribution grouped by assignee for a SINGLE board.

    Returns dict keyed by display name:
    {
        "Sam Rivera": {
            "username": "sam_rivera_demo",
            "tasks": [task_dict, ...],   # ALL tasks, not just top-5
            "count": int,
            "overdue_count": int,
            "column_breakdown": {"To Do": 3, "In Progress": 2, ...},
        }
    }
    """
    all_tasks = fetch_board_tasks(board, filters={'item_type': 'task'})
    workload = {}

    for task in all_tasks:
        key = task['assigned_to_display']
        if key not in workload:
            workload[key] = {
                'username': task['assigned_to_username'],
                'display_name': key,
                'tasks': [],
                'task_titles': [],
                'task_count': 0,
                'count': 0,          # alias
                'overdue_count': 0,
                'column_breakdown': {},
            }
        entry = workload[key]
        entry['tasks'].append(task)
        entry['task_titles'].append(task['title'])
        entry['task_count'] += 1
        entry['count'] += 1
        if task['is_overdue']:
            entry['overdue_count'] += 1
        col = task['column_name']
        entry['column_breakdown'][col] = entry['column_breakdown'].get(col, 0) + 1

    # Sort by count descending
    return dict(sorted(workload.items(), key=lambda x: -x[1]['count']))


def fetch_overdue_tasks(board):
    """Shortcut: fetch only overdue, non-complete tasks for a board."""
    return fetch_board_tasks(board, filters={'item_type': 'task', 'is_overdue': True})


def fetch_tasks_for_user_on_board(board, username):
    """Fetch all tasks assigned to a specific user on a single board."""
    return fetch_board_tasks(
        board,
        filters={'item_type': 'task', 'assigned_to_username': username}
    )


# ── Feature-specific fetchers added April 2026 ─────────────────────────────
# Each new context provider has a fetcher here so ORM access stays in one
# place. All fetchers return None when the underlying app/model is not
# importable (graceful degradation — the provider sees a None and returns
# an empty string).


def fetch_requirements_summary(board):
    """Return high-level requirements stats for a board, or None."""
    try:
        from requirements.models import Requirement
    except Exception:
        return None

    qs = Requirement.objects.filter(board=board)
    total = qs.count()
    if total == 0:
        return {
            'total': 0,
            'by_status': {},
            'covered': 0,
            'uncovered': 0,
            'covered_pct': 0,
        }

    by_status = {}
    status_labels = dict(Requirement.STATUS_CHOICES)
    for row in qs.values('status').annotate(c=Count('id')):
        by_status[status_labels.get(row['status'], row['status'])] = row['c']

    covered = qs.annotate(task_n=Count('linked_tasks')).filter(task_n__gt=0).count()
    uncovered = total - covered
    covered_pct = round((covered / total) * 100, 1) if total else 0

    return {
        'total': total,
        'by_status': by_status,
        'covered': covered,
        'uncovered': uncovered,
        'covered_pct': covered_pct,
    }


def fetch_requirements_detail(board, uncovered_limit=15, recent_limit=15):
    """Return per-requirement detail for a board, or None."""
    try:
        from requirements.models import Requirement
    except Exception:
        return None

    qs = Requirement.objects.filter(board=board).prefetch_related('linked_tasks')
    total = qs.count()
    if total == 0:
        return {
            'total': 0, 'by_status': {}, 'by_priority': {},
            'covered': 0, 'uncovered': 0, 'covered_pct': 0,
            'uncovered_items': [], 'recent': [],
        }

    status_labels = dict(Requirement.STATUS_CHOICES)
    priority_labels = dict(Requirement.PRIORITY_CHOICES)

    by_status = {}
    for row in qs.values('status').annotate(c=Count('id')):
        by_status[status_labels.get(row['status'], row['status'])] = row['c']

    by_priority = {}
    for row in qs.values('priority').annotate(c=Count('id')):
        by_priority[priority_labels.get(row['priority'], row['priority'])] = row['c']

    annotated = qs.annotate(task_n=Count('linked_tasks'))
    covered = annotated.filter(task_n__gt=0).count()
    uncovered = total - covered
    covered_pct = round((covered / total) * 100, 1) if total else 0

    uncovered_items = []
    for r in annotated.filter(task_n=0).order_by('-priority', 'identifier')[:uncovered_limit]:
        uncovered_items.append({
            'identifier': r.identifier,
            'title': r.title,
            'status_label': status_labels.get(r.status, r.status),
            'priority_label': priority_labels.get(r.priority, r.priority),
        })

    recent = []
    for r in annotated.order_by('-updated_at')[:recent_limit]:
        recent.append({
            'identifier': r.identifier,
            'title': r.title,
            'status_label': status_labels.get(r.status, r.status),
            'priority_label': priority_labels.get(r.priority, r.priority),
            'linked_task_count': r.task_n,
        })

    return {
        'total': total,
        'by_status': by_status,
        'by_priority': by_priority,
        'covered': covered,
        'uncovered': uncovered,
        'covered_pct': covered_pct,
        'uncovered_items': uncovered_items,
        'recent': recent,
    }


def fetch_stakeholders_summary(board):
    """Return summary stakeholder stats for a board, or None."""
    try:
        from kanban.stakeholder_models import ProjectStakeholder
    except Exception:
        return None

    qs = ProjectStakeholder.objects.filter(board=board, is_active=True)
    total = qs.count()
    if total == 0:
        return {'total': 0, 'quadrants': {}, 'engagement_gap_count': 0}

    quadrants = {}
    engagement_gap_count = 0
    for s in qs:
        q = s.get_quadrant()
        quadrants[q] = quadrants.get(q, 0) + 1
        if s.get_engagement_gap() > 0:
            engagement_gap_count += 1

    return {
        'total': total,
        'quadrants': quadrants,
        'engagement_gap_count': engagement_gap_count,
    }


def fetch_stakeholders_detail(board, roster_limit=15, raci_limit=8):
    """Return detailed stakeholder info for a board, or None."""
    try:
        from kanban.stakeholder_models import (
            ProjectStakeholder,
            StakeholderTaskInvolvement,
        )
    except Exception:
        return None

    qs = ProjectStakeholder.objects.filter(board=board, is_active=True).order_by('name')
    total = qs.count()
    if total == 0:
        return {'total': 0, 'stakeholders': [], 'raci': {}, 'engagement_gaps': []}

    stakeholders = []
    engagement_gaps = []
    for s in qs[:roster_limit]:
        stakeholders.append({
            'name': s.name,
            'role': s.role,
            'email': s.email or '',
            'influence_level': s.influence_level,
            'interest_level': s.interest_level,
            'current_engagement': s.current_engagement,
            'desired_engagement': s.desired_engagement,
            'quadrant': s.get_quadrant(),
        })
        gap = s.get_engagement_gap()
        if gap > 0:
            engagement_gaps.append({
                'name': s.name,
                'current_engagement': s.current_engagement,
                'desired_engagement': s.desired_engagement,
                'gap': gap,
            })

    raci = {}
    involvements = (
        StakeholderTaskInvolvement.objects
        .filter(stakeholder__board=board, stakeholder__is_active=True)
        .select_related('stakeholder', 'task')
        .order_by('-last_engagement')
    )
    for inv in involvements:
        bucket = inv.get_involvement_type_display()
        raci.setdefault(bucket, []).append({
            'stakeholder_name': inv.stakeholder.name,
            'task_title': inv.task.title,
            'engagement_status': inv.get_engagement_status_display(),
        })
    # cap each bucket
    raci = {k: v[:raci_limit] for k, v in raci.items()}

    return {
        'total': total,
        'stakeholders': stakeholders,
        'raci': raci,
        'engagement_gaps': engagement_gaps,
    }


def fetch_custom_fields_summary(board):
    """Return summary of custom fields for the board's workspace, or None."""
    try:
        from kanban.custom_field_models import CustomFieldDefinition
    except Exception:
        return None

    workspace_id = getattr(board, 'workspace_id', None)
    if not workspace_id:
        return {'total': 0, 'names': [], 'excluded_from_ai': 0}

    all_active = CustomFieldDefinition.objects.filter(
        workspace_id=workspace_id, is_active=True, applies_to_tasks=True,
    )
    visible = all_active.filter(exclude_from_ai=False).order_by('position', 'name')
    excluded_count = all_active.filter(exclude_from_ai=True).count()
    names = [f.name for f in visible]

    return {
        'total': len(names),
        'names': names,
        'excluded_from_ai': excluded_count,
    }


def fetch_custom_fields_detail(board, value_sample_limit=20):
    """Return schema + sampled values for custom fields on this board, or None."""
    try:
        from kanban.custom_field_models import (
            CustomFieldDefinition,
            TaskCustomFieldValue,
        )
    except Exception:
        return None

    workspace_id = getattr(board, 'workspace_id', None)
    if not workspace_id:
        return None

    visible = (
        CustomFieldDefinition.objects
        .filter(
            workspace_id=workspace_id,
            is_active=True,
            applies_to_tasks=True,
            exclude_from_ai=False,
        )
        .prefetch_related('options')
        .order_by('position', 'name')
    )
    fields = []
    for f in visible:
        fields.append({
            'name': f.name,
            'field_type': f.get_field_type_display(),
            'is_required': f.is_required,
            'options': [o.value for o in f.options.all()] if f.supports_options else [],
        })

    excluded_count = CustomFieldDefinition.objects.filter(
        workspace_id=workspace_id, is_active=True,
        applies_to_tasks=True, exclude_from_ai=True,
    ).count()

    value_samples = []
    if fields:
        vals = (
            TaskCustomFieldValue.objects
            .filter(
                task__column__board=board,
                field__exclude_from_ai=False,
                field__is_active=True,
            )
            .select_related('task', 'field')
            .prefetch_related('selected_options')
            .order_by('-updated_at')[:value_sample_limit]
        )
        for v in vals:
            display = v.display_value()
            if not display:
                continue
            value_samples.append({
                'task_title': v.task.title,
                'field_name': v.field.name,
                'display_value': display,
            })

    return {
        'total': len(fields),
        'fields': fields,
        'excluded_from_ai': excluded_count,
        'value_samples': value_samples,
    }


def fetch_resource_leveling_summary(board):
    """Return summary capacity/leveling stats for a board, or None."""
    try:
        from kanban.models import (
            TeamCapacityAlert,
            WorkloadDistributionRecommendation,
            ResourceDemandForecast,
        )
    except Exception:
        return None

    active_alerts_qs = TeamCapacityAlert.objects.filter(board=board, status='active')
    pending_rec_count = WorkloadDistributionRecommendation.objects.filter(
        board=board, status='pending'
    ).count()
    overloaded = ResourceDemandForecast.objects.filter(
        board=board,
        predicted_workload_hours__gt=F('available_capacity_hours'),
    ).count()

    return {
        'active_alerts': active_alerts_qs.count(),
        'critical_alerts': active_alerts_qs.filter(alert_level='critical').count(),
        'pending_recommendations': pending_rec_count,
        'overloaded_forecasts': overloaded,
    }


def fetch_resource_leveling_detail(board, limit=10):
    """Return detailed capacity alerts + recommendations for a board, or None."""
    try:
        from kanban.models import (
            TeamCapacityAlert,
            WorkloadDistributionRecommendation,
            ResourceDemandForecast,
        )
    except Exception:
        return None

    alerts = []
    for a in (
        TeamCapacityAlert.objects.filter(board=board)
        .exclude(status='resolved')
        .select_related('resource_user')
        .order_by('-created_at')[:limit]
    ):
        resource_name = a.resource_user.username if a.resource_user else 'Team'
        alerts.append({
            'alert_type': a.get_alert_type_display(),
            'alert_level': a.get_alert_level_display(),
            'status': a.get_status_display(),
            'resource_name': resource_name,
            'workload_percentage': a.workload_percentage,
            'message': a.message or '',
        })

    recommendations = []
    for r in (
        WorkloadDistributionRecommendation.objects.filter(board=board)
        .exclude(status='rejected')
        .order_by('-priority', '-created_at')[:limit]
    ):
        recommendations.append({
            'recommendation_type': r.get_recommendation_type_display(),
            'priority': r.priority,
            'status': r.get_status_display(),
            'title': r.title,
            'description': r.description or '',
            'expected_savings_hours': float(r.expected_capacity_savings_hours),
            'confidence_score': float(r.confidence_score),
        })

    forecasts = []
    for f in (
        ResourceDemandForecast.objects.filter(board=board)
        .select_related('resource_user')
        .order_by('-forecast_date')[:limit]
    ):
        resource_name = (
            f.resource_user.username if f.resource_user else f.resource_role
        )
        forecasts.append({
            'resource_name': resource_name,
            'period_start': str(f.period_start),
            'period_end': str(f.period_end),
            'predicted_workload_hours': float(f.predicted_workload_hours),
            'available_capacity_hours': float(f.available_capacity_hours),
            'utilization_percentage': round(float(f.utilization_percentage), 1),
            'is_overloaded': f.is_overloaded,
        })

    return {
        'alerts': alerts,
        'recommendations': recommendations,
        'forecasts': forecasts,
    }


def fetch_scope_summary(board):
    """Return summary scope stats for a board, or None."""
    try:
        from kanban.models import ScopeChangeSnapshot, ScopeCreepAlert
    except Exception:
        return None

    active_qs = ScopeCreepAlert.objects.filter(board=board, status='active')
    latest = ScopeChangeSnapshot.objects.filter(board=board).order_by('-snapshot_date').first()
    scope_pct = latest.scope_change_percentage if latest else None

    return {
        'active_alerts': active_qs.count(),
        'critical_alerts': active_qs.filter(severity='critical').count(),
        'scope_change_pct': scope_pct,
    }


def fetch_scope_detail(board, alert_limit=10):
    """Return detailed scope info for a board, or None."""
    try:
        from kanban.models import ScopeChangeSnapshot, ScopeCreepAlert
    except Exception:
        return None

    latest = (
        ScopeChangeSnapshot.objects.filter(board=board)
        .order_by('-snapshot_date').first()
    )
    baseline = ScopeChangeSnapshot.objects.filter(board=board, is_baseline=True).first()

    def serialize_snapshot(s):
        if not s:
            return None
        return {
            'snapshot_date': s.snapshot_date.strftime('%Y-%m-%d %H:%M'),
            'snapshot_type': s.get_snapshot_type_display(),
            'total_tasks': s.total_tasks,
            'total_complexity_points': s.total_complexity_points,
            'avg_complexity': s.avg_complexity,
            'high_priority_tasks': s.high_priority_tasks,
            'urgent_priority_tasks': s.urgent_priority_tasks,
            'todo_tasks': s.todo_tasks,
            'in_progress_tasks': s.in_progress_tasks,
            'completed_tasks': s.completed_tasks,
            'scope_change_percentage': s.scope_change_percentage,
            'complexity_change_percentage': s.complexity_change_percentage,
            'predicted_delay_days': s.predicted_delay_days,
        }

    alerts = []
    for a in (
        ScopeCreepAlert.objects.filter(board=board)
        .exclude(status__in=['resolved', 'dismissed'])
        .order_by('-detected_at')[:alert_limit]
    ):
        alerts.append({
            'severity': a.get_severity_display(),
            'status': a.get_status_display(),
            'scope_increase_percentage': a.scope_increase_percentage,
            'tasks_added': a.tasks_added,
            'detected_at': a.detected_at.strftime('%Y-%m-%d'),
            'ai_summary': a.ai_summary or '',
        })

    return {
        'latest_snapshot': serialize_snapshot(latest),
        'baseline': serialize_snapshot(baseline),
        'alerts': alerts,
    }


def fetch_risk_scenarios_summary(board):
    """Return summary counts for pre-mortems, stress tests, what-ifs, or None."""
    result = {
        'premortem_count': 0,
        'latest_premortem_risk': '',
        'stress_test_count': 0,
        'latest_immunity_score': None,
        'latest_immunity_band': '',
        'whatif_count': 0,
    }
    found_any = False

    try:
        from kanban.premortem_models import PreMortemAnalysis
        pm_qs = PreMortemAnalysis.objects.filter(board=board)
        result['premortem_count'] = pm_qs.count()
        latest_pm = pm_qs.order_by('-created_at').first()
        if latest_pm:
            result['latest_premortem_risk'] = latest_pm.overall_risk_level
        found_any = True
    except Exception:
        pass

    try:
        from kanban.stress_test_models import StressTestSession
        st_qs = StressTestSession.objects.filter(board=board)
        result['stress_test_count'] = st_qs.count()
        latest_st = (
            st_qs.select_related('immunity_score').order_by('-created_at').first()
        )
        if latest_st and hasattr(latest_st, 'immunity_score'):
            try:
                score = latest_st.immunity_score
                result['latest_immunity_score'] = score.overall
                result['latest_immunity_band'] = score.get_band()
            except Exception:
                pass
        found_any = True
    except Exception:
        pass

    try:
        from kanban.whatif_models import WhatIfScenario
        result['whatif_count'] = WhatIfScenario.objects.filter(board=board).count()
        found_any = True
    except Exception:
        pass

    return result if found_any else None


def fetch_risk_scenarios_detail(board, limit=5):
    """Return detailed risk scenarios for a board, or None."""
    result = {'premortems': [], 'stress_tests': [], 'whatifs': []}
    found_any = False

    try:
        from kanban.premortem_models import (
            PreMortemAnalysis,
            PreMortemScenarioAcknowledgment,
        )
        for pm in (
            PreMortemAnalysis.objects.filter(board=board)
            .order_by('-created_at')[:limit]
        ):
            scenarios_json = pm.analysis_json or {}
            scenarios = []
            raw_scenarios = scenarios_json.get('scenarios') if isinstance(scenarios_json, dict) else None
            if isinstance(raw_scenarios, list):
                for s in raw_scenarios[:5]:
                    if isinstance(s, dict):
                        title = s.get('title') or s.get('scenario') or s.get('name') or ''
                        if title:
                            scenarios.append(str(title)[:160])
            ack_count = PreMortemScenarioAcknowledgment.objects.filter(pre_mortem=pm).count()
            result['premortems'].append({
                'created_at': pm.created_at.strftime('%Y-%m-%d'),
                'overall_risk_level': pm.overall_risk_level,
                'scenario_count': len(raw_scenarios) if isinstance(raw_scenarios, list) else 0,
                'acknowledged_count': ack_count,
                'top_scenarios': scenarios,
            })
        found_any = True
    except Exception:
        pass

    try:
        from kanban.stress_test_models import StressTestSession
        for st in (
            StressTestSession.objects.filter(board=board)
            .select_related('immunity_score')
            .prefetch_related('scenarios', 'vaccines')
            .order_by('-created_at')[:limit]
        ):
            immunity_overall = None
            immunity_band = ''
            try:
                score = st.immunity_score
                immunity_overall = score.overall
                immunity_band = score.get_band()
            except Exception:
                pass
            top_scen = [
                f'#{s.scenario_number} {s.title} [{s.outcome}]'
                for s in st.scenarios.all()[:5]
            ]
            result['stress_tests'].append({
                'created_at': st.created_at.strftime('%Y-%m-%d'),
                'immunity_overall': immunity_overall,
                'immunity_band': immunity_band,
                'scenarios_unaddressed': st.scenarios_unaddressed_count,
                'vaccines_applied': st.vaccines_applied_count,
                'top_scenarios': top_scen,
            })
        found_any = True
    except Exception:
        pass

    try:
        from kanban.whatif_models import WhatIfScenario
        for w in WhatIfScenario.objects.filter(board=board).order_by('-created_at')[:limit + 1]:
            result['whatifs'].append({
                'name': w.name,
                'scenario_type': w.get_scenario_type_display(),
                'created_at': w.created_at.strftime('%Y-%m-%d'),
                'is_starred': w.is_starred,
            })
        found_any = True
    except Exception:
        pass

    return result if found_any else None


def fetch_discovery_summary(organization):
    """Return summary of org-scoped discovery ideas, or None."""
    try:
        from kanban.discovery_models import DiscoveryIdea, IDEA_STAGE_CHOICES
    except Exception:
        return None

    qs = DiscoveryIdea.objects.filter(organization=organization)
    total = qs.count()
    if total == 0:
        return {'total': 0, 'by_stage': {}, 'promoted': 0}

    stage_labels = dict(IDEA_STAGE_CHOICES)
    by_stage = {}
    for row in qs.values('stage').annotate(c=Count('id')):
        by_stage[stage_labels.get(row['stage'], row['stage'])] = row['c']

    promoted = qs.filter(promoted_at__isnull=False).count()

    return {'total': total, 'by_stage': by_stage, 'promoted': promoted}


def fetch_discovery_detail(organization, recent_limit=12):
    """Return detail of org-scoped discovery ideas, or None."""
    try:
        from kanban.discovery_models import DiscoveryIdea, IDEA_STAGE_CHOICES
    except Exception:
        return None

    qs = DiscoveryIdea.objects.filter(organization=organization)
    total = qs.count()
    if total == 0:
        return {'total': 0, 'by_stage': {}, 'by_quadrant': {}, 'recent': []}

    stage_labels = dict(IDEA_STAGE_CHOICES)
    by_stage = {}
    for row in qs.values('stage').annotate(c=Count('id')):
        by_stage[stage_labels.get(row['stage'], row['stage'])] = row['c']

    by_quadrant = {}
    for idea in qs:
        label = idea.quadrant_label
        if label:
            by_quadrant[label] = by_quadrant.get(label, 0) + 1

    recent = []
    for idea in qs.order_by('-created_at')[:recent_limit]:
        recent.append({
            'title': idea.title,
            'stage': idea.get_stage_display(),
            'ai_score_impact': idea.ai_score_impact,
            'ai_score_effort': idea.ai_score_effort,
            'ai_score_recommendation': idea.ai_score_recommendation or '',
        })

    return {
        'total': total,
        'by_stage': by_stage,
        'by_quadrant': by_quadrant,
        'recent': recent,
    }


def fetch_access_requests_summary(board, user):
    """Return summary of pending access requests visible to this user, or None."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    try:
        from kanban.access_request_models import AccessRequest
    except Exception:
        return None

    pending = AccessRequest.objects.filter(status='pending')
    if board:
        pending = pending.filter(board=board)
    as_owner = pending.filter(owner=user).count()
    as_requester = pending.filter(requester=user).count()
    total_pending = as_owner + as_requester
    return {
        'total_pending': total_pending,
        'pending_as_owner': as_owner,
        'pending_by_user': as_requester,
    }


def fetch_access_requests_detail(board, user):
    """Return per-request detail visible to this user, or None."""
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    try:
        from kanban.access_request_models import AccessRequest
    except Exception:
        return None

    base = (
        AccessRequest.objects.filter(status='pending')
        .select_related('requester', 'owner', 'board')
        .order_by('-created_at')
    )
    if board:
        base = base.filter(board=board)

    def fmt(r, role):
        requester_name = r.requester.get_full_name() or r.requester.username
        owner_name = r.owner.get_full_name() or r.owner.username
        return {
            'role': role,
            'requester_name': requester_name,
            'owner_name': owner_name,
            'board_name': r.board.name,
            'requested_role': r.requested_role,
            'trigger': r.get_trigger_display(),
            'message': r.message or '',
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M'),
        }

    as_owner = [fmt(r, 'owner') for r in base.filter(owner=user)[:15]]
    as_requester = [fmt(r, 'requester') for r in base.filter(requester=user)[:15]]
    return {'as_owner': as_owner, 'as_requester': as_requester}
