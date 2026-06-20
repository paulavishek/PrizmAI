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
import re
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
    now = timezone.now()
    today = now.date()

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

    # Overdue check — match the dashboard's logic in kanban/views.py:224 which
    # uses ``due_date__lt=timezone.now()`` (datetime comparison). A task whose
    # due_date is "today" with a 00:00 timestamp shows as overdue any time after
    # midnight, which is what the dashboard counts. Without this, Spectra
    # under-counted overdue tasks by excluding everything due today.
    if due_date_val and not hasattr(due_date_val, 'date'):
        # Pure date object — compare against today
        is_overdue = bool(due_date_val < today and not is_complete)
    else:
        is_overdue = bool(due_date_val and due_date_val < now and not is_complete)
    overdue_days = (today - due_date_date).days if (is_overdue and due_date_date) else 0

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

    # Checklist items (requires prefetch_related('checklist_items')). Uses
    # .all() on the prefetched relation — no extra query. Spectra was
    # previously blind to checklists and would say "no checklist exists" for
    # tasks that have one.
    try:
        checklist = [
            {'title': c.title, 'is_completed': c.is_completed}
            for c in task.checklist_items.all()
        ]
    except Exception:
        checklist = []

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
        'checklist': checklist,
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
            'checklist_items',
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
        "Marcus Chen": {
            "username": "marcus.chen",
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

    # Custom field DEFINITIONS are workspace-scoped by design — all boards in
    # the same workspace share the same field schema. This is intentional and
    # not an RBAC leak: a workspace member sees field names/types for the
    # whole workspace, but individual field VALUES on tasks are board-scoped
    # below in fetch_custom_fields_detail (which uses task__column__board=board).
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

    latest_autopsy_obj = None
    try:
        from kanban.scope_autopsy_models import ScopeAutopsyReport
        latest_autopsy_obj = (
            ScopeAutopsyReport.objects.filter(board=board, status='complete')
            .order_by('-created_at').first()
        )
    except Exception:
        latest_autopsy_obj = None

    return {
        'active_alerts': active_qs.count(),
        'critical_alerts': active_qs.filter(severity='critical').count(),
        'scope_change_pct': scope_pct,
        'latest_autopsy': (
            {
                'created_at': latest_autopsy_obj.created_at.strftime('%Y-%m-%d'),
                'growth_pct': latest_autopsy_obj.total_scope_growth_percentage,
                'delay_days': latest_autopsy_obj.total_delay_days,
            }
            if latest_autopsy_obj else None
        ),
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

    autopsies = []
    try:
        from kanban.scope_autopsy_models import ScopeAutopsyReport
        for ap in (
            ScopeAutopsyReport.objects.filter(board=board)
            .order_by('-created_at')[:5]
        ):
            top_events = []
            for ev in ap.timeline_events.order_by('-net_task_change', 'event_date')[:3]:
                top_events.append({
                    'event_date': ev.event_date.strftime('%Y-%m-%d'),
                    'title': ev.title,
                    'net_task_change': ev.net_task_change,
                })
            autopsies.append({
                'created_at': ap.created_at.strftime('%Y-%m-%d %H:%M'),
                'status': ap.get_status_display(),
                'baseline_task_count': ap.baseline_task_count,
                'final_task_count': ap.final_task_count,
                'total_scope_growth_percentage': ap.total_scope_growth_percentage,
                'total_delay_days': ap.total_delay_days,
                'total_budget_impact': str(ap.total_budget_impact),
                'ai_summary': ap.ai_summary or '',
                'top_events': top_events,
            })
    except Exception:
        autopsies = []

    return {
        'latest_snapshot': serialize_snapshot(latest),
        'baseline': serialize_snapshot(baseline),
        'alerts': alerts,
        'autopsies': autopsies,
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


# ────────────────────────────────────────────────────────────────────────
# Phase 2 v2 fetchers — Activity, Coach, Memory, Status Report,
# Integrations, Comments, Files, Skill Development, Briefs.
# Every fetcher takes an `accessible` queryset (the user's accessible
# boards) for cross-board scoping; `board` (single board) takes
# precedence when set.
# ────────────────────────────────────────────────────────────────────────


def _humanize_dt(dt):
    """Compact 'when' label used across the new providers."""
    if not dt:
        return ''
    try:
        delta = timezone.now() - dt
        if delta.days >= 30:
            return dt.strftime('%Y-%m-%d')
        if delta.days >= 1:
            return f'{delta.days}d ago'
        hours = delta.seconds // 3600
        if hours >= 1:
            return f'{hours}h ago'
        minutes = max(1, delta.seconds // 60)
        return f'{minutes}m ago'
    except Exception:
        try:
            return dt.strftime('%Y-%m-%d')
        except Exception:
            return ''


# ── Activity ───────────────────────────────────────────────────────────

def fetch_activity_summary(board, accessible_boards):
    """Counts + latest TaskActivity event. Board or accessible_boards required."""
    try:
        from kanban.models import TaskActivity
    except Exception:
        return None
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=7)

    qs = TaskActivity.objects.filter(created_at__gte=cutoff).select_related(
        'task', 'user', 'task__column'
    )
    if board:
        qs = qs.filter(task__column__board=board)
    else:
        if accessible_boards is None:
            return None
        qs = qs.filter(task__column__board__in=accessible_boards)

    total = qs.count()
    latest_obj = qs.order_by('-created_at').first()
    latest = None
    if latest_obj:
        actor = latest_obj.user.get_full_name() or latest_obj.user.username
        latest = {
            'actor': actor,
            'action': latest_obj.get_activity_type_display().lower(),
            'task_title': latest_obj.task.title,
            'when': _humanize_dt(latest_obj.created_at),
        }
    return {'total': total, 'latest': latest}


def fetch_activity_detail(board, accessible_boards, limit=25):
    """Most-recent TaskActivity events in last 30 days."""
    try:
        from kanban.models import TaskActivity
    except Exception:
        return None
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=30)

    qs = TaskActivity.objects.filter(created_at__gte=cutoff).select_related(
        'task', 'user', 'task__column'
    )
    if board:
        qs = qs.filter(task__column__board=board)
    else:
        if accessible_boards is None:
            return None
        qs = qs.filter(task__column__board__in=accessible_boards)

    qs = qs.order_by('-created_at')
    total = qs.count()
    events = []
    for ev in qs[:limit]:
        actor = ev.user.get_full_name() or ev.user.username
        events.append({
            'when': _humanize_dt(ev.created_at),
            'actor': actor,
            'action': ev.get_activity_type_display().lower(),
            'task_title': ev.task.title,
            'description': (ev.description or '').strip(),
        })
    truncated = max(0, total - limit)
    return {'events': events, 'truncated': truncated}


# ── AI Coach ───────────────────────────────────────────────────────────

def fetch_coach_summary(board, user, accessible_boards):
    """Open suggestions + most-recent PM metric snapshot for the user."""
    try:
        from kanban.coach_models import CoachingSuggestion, PMMetrics
    except Exception:
        return None

    sugg = CoachingSuggestion.objects.filter(status='active')
    if board:
        sugg = sugg.filter(board=board)
    elif accessible_boards is not None:
        sugg = sugg.filter(board__in=accessible_boards)
    else:
        return None

    open_count = sugg.count()
    high_sev = sugg.filter(severity__in=['high', 'critical']).count()
    top = sugg.order_by('-severity', '-created_at').first()
    top_suggestion = None
    if top:
        top_suggestion = {'title': top.title, 'severity': top.severity}

    top_metric = None
    if user and getattr(user, 'is_authenticated', False):
        m_qs = PMMetrics.objects.filter(pm_user=user)
        if board:
            m_qs = m_qs.filter(board=board)
        elif accessible_boards is not None:
            m_qs = m_qs.filter(board__in=accessible_boards)
        m = m_qs.order_by('-period_end').first()
        if m:
            top_metric = {
                'velocity_trend': m.velocity_trend,
                'deadline_hit_rate': float(m.deadline_hit_rate),
            }

    return {
        'open_count': open_count,
        'high_severity': high_sev,
        'top_suggestion': top_suggestion,
        'top_metric': top_metric,
    }


def fetch_coach_detail(board, user, accessible_boards):
    """Detail: list open suggestions + recent PM metrics + active insights."""
    try:
        from kanban.coach_models import (
            CoachingSuggestion, PMMetrics, CoachingInsight,
        )
    except Exception:
        return None

    sugg_qs = CoachingSuggestion.objects.filter(
        status__in=['active', 'acknowledged']
    ).select_related('board', 'task')
    if board:
        sugg_qs = sugg_qs.filter(board=board)
    elif accessible_boards is not None:
        sugg_qs = sugg_qs.filter(board__in=accessible_boards)
    else:
        return None
    sugg_qs = sugg_qs.order_by('-severity', '-created_at')

    suggestions = []
    for s in sugg_qs[:15]:
        suggestions.append({
            'title': s.title,
            'type': s.get_suggestion_type_display(),
            'severity': s.severity,
            'status': s.status,
            'message': s.message,
            'created_at': s.created_at.strftime('%Y-%m-%d'),
        })

    metrics = []
    if user and getattr(user, 'is_authenticated', False):
        m_qs = PMMetrics.objects.filter(pm_user=user)
        if board:
            m_qs = m_qs.filter(board=board)
        elif accessible_boards is not None:
            m_qs = m_qs.filter(board__in=accessible_boards)
        for m in m_qs.order_by('-period_end')[:3]:
            metrics.append({
                'period': f'{m.period_start} → {m.period_end}',
                'velocity_trend': m.velocity_trend,
                'deadline_hit_rate': float(m.deadline_hit_rate),
                'risk_mitigation_success_rate': float(m.risk_mitigation_success_rate),
                'coaching_effectiveness_score': float(m.coaching_effectiveness_score),
            })

    insights = []
    for i in CoachingInsight.objects.filter(is_active=True).order_by(
        '-confidence_score', '-sample_size'
    )[:5]:
        insights.append({
            'title': i.title,
            'confidence': float(i.confidence_score),
        })

    return {
        'suggestions': suggestions,
        'metrics': metrics,
        'insights': insights,
    }


# ── Organizational Memory ──────────────────────────────────────────────

def fetch_memory_summary(board, accessible_boards, organization):
    """Memory node counts + latest title."""
    try:
        from knowledge_graph.models import MemoryNode
    except Exception:
        return None

    if board:
        qs = MemoryNode.objects.filter(board=board)
    elif accessible_boards is not None:
        qs = MemoryNode.objects.filter(board__in=accessible_boards)
    else:
        return None

    total = qs.count()
    if total == 0:
        return {'total': 0, 'by_type': {}, 'latest_title': None}

    by_type = {}
    for row in qs.values('node_type').annotate(c=Count('id')).order_by('-c'):
        by_type[row['node_type']] = row['c']

    latest = qs.order_by('-created_at').first()
    return {
        'total': total,
        'by_type': by_type,
        'latest_title': latest.title if latest else None,
    }


def fetch_memory_detail(board, accessible_boards, organization, query=''):
    """Top relevant nodes + recent connections. Lightweight keyword filter."""
    try:
        from knowledge_graph.models import MemoryNode, MemoryConnection
    except Exception:
        return None

    if board:
        qs = MemoryNode.objects.filter(board=board)
    elif accessible_boards is not None:
        qs = MemoryNode.objects.filter(board__in=accessible_boards)
    else:
        return None

    qs = qs.select_related('board')

    # Light keyword filter (tags + title + content) if query has signal
    if query:
        terms = [t for t in re.findall(r'\w+', query.lower()) if len(t) >= 3]
        if terms:
            f = Q()
            for t in terms[:8]:
                f |= Q(title__icontains=t) | Q(content__icontains=t)
            qs_filtered = qs.filter(f)
            if qs_filtered.exists():
                qs = qs_filtered

    total = MemoryNode.objects.filter(
        board=board if board else None,
    ).count() if board else qs.count()

    by_type = {}
    for row in qs.values('node_type').annotate(c=Count('id')).order_by('-c'):
        by_type[row['node_type']] = row['c']

    nodes = []
    for n in qs.order_by('-importance_score', '-created_at')[:10]:
        # 500 chars so enriched memories are usable in chat, not just one-liners.
        excerpt = (n.content or '')[:500]
        if len(n.content or '') > 500:
            excerpt += '…'
        nodes.append({
            'type': n.get_node_type_display(),
            'title': n.title,
            'importance': float(n.importance_score),
            'when': _humanize_dt(n.created_at),
            'board_name': n.board.name if n.board else None,
            'excerpt': excerpt,
        })

    # Connections among the surfaced nodes only
    surfaced_ids = {
        n.id for n in qs.order_by('-importance_score', '-created_at')[:20]
    }
    connections = []
    if surfaced_ids:
        for c in MemoryConnection.objects.filter(
            from_node_id__in=surfaced_ids, to_node_id__in=surfaced_ids,
        ).select_related('from_node', 'to_node')[:10]:
            connections.append({
                'from': c.from_node.title,
                'to': c.to_node.title,
                'type': c.get_connection_type_display(),
            })

    return {
        'total': total,
        'by_type': by_type,
        'nodes': nodes,
        'connections': connections,
    }


# ── Status Reports ─────────────────────────────────────────────────────

def fetch_status_report_summary(board, accessible_boards):
    """Count + latest status report."""
    try:
        from kanban.models import BoardStatusReport
    except Exception:
        return None

    qs = BoardStatusReport.objects.select_related('board')
    if board:
        qs = qs.filter(board=board)
    elif accessible_boards is not None:
        qs = qs.filter(board__in=accessible_boards)
    else:
        return None

    total = qs.count()
    if total == 0:
        return {'total': 0, 'latest': None}

    latest = qs.order_by('-created_at').first()
    return {
        'total': total,
        'latest': {
            'created_at': latest.created_at.strftime('%Y-%m-%d'),
            'rag': latest.rag_status,
            'board_name': latest.board.name,
        },
    }


def fetch_status_report_detail(board, accessible_boards, limit=5):
    try:
        from kanban.models import BoardStatusReport
    except Exception:
        return None

    qs = BoardStatusReport.objects.select_related('board').order_by('-created_at')
    if board:
        qs = qs.filter(board=board)
    elif accessible_boards is not None:
        qs = qs.filter(board__in=accessible_boards)
    else:
        return None

    reports = []
    for r in qs[:limit]:
        text = (r.report_text or '').strip()
        excerpt = text[:600] + ('…' if len(text) > 600 else '')
        reports.append({
            'board_name': r.board.name,
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M'),
            'rag': r.rag_status,
            'rag_reasoning': r.rag_reasoning or '',
            'confidence': float(r.confidence_score),
            'text_excerpt': excerpt,
            'key_drivers': list(r.key_data_drivers or []),
        })
    return {'reports': reports}


# ── Integrations ───────────────────────────────────────────────────────

def fetch_integrations_summary(board, accessible_boards):
    try:
        from integrations.models import GitHubIntegration
    except Exception:
        return None

    qs = GitHubIntegration.objects.select_related('board')
    if board:
        qs = qs.filter(board=board)
    elif accessible_boards is not None:
        qs = qs.filter(board__in=accessible_boards)
    else:
        return None

    total = qs.count()
    if total == 0:
        return {'total': 0, 'active': 0, 'active_repos': []}

    active = qs.filter(is_active=True).count()
    active_repos = list(
        qs.filter(is_active=True).values_list('repo_full_name', flat=True)[:5]
    )
    return {'total': total, 'active': active, 'active_repos': active_repos}


def fetch_integrations_detail(board, accessible_boards):
    try:
        from integrations.models import GitHubIntegration
    except Exception:
        return None

    qs = GitHubIntegration.objects.select_related('board', 'in_review_column')
    if board:
        qs = qs.filter(board=board)
    elif accessible_boards is not None:
        qs = qs.filter(board__in=accessible_boards)
    else:
        return None

    integrations = []
    for g in qs.order_by('-updated_at')[:15]:
        # Never expose webhook_secret.
        integrations.append({
            'repo': g.repo_full_name,
            'board_name': g.board.name,
            'is_active': g.is_active,
            'created_at': g.created_at.strftime('%Y-%m-%d'),
            'in_review_column': g.in_review_column.name if g.in_review_column else None,
        })
    return {'integrations': integrations}


# ── Comments ───────────────────────────────────────────────────────────

def fetch_comments_summary(board, accessible_boards):
    try:
        from kanban.models import Comment
        from messaging.models import TaskThreadComment
    except Exception:
        return None
    from datetime import timedelta
    cutoff_7d = timezone.now() - timedelta(days=7)

    c_qs = Comment.objects.select_related('task__column')
    t_qs = TaskThreadComment.objects.select_related('task__column')
    if board:
        c_qs = c_qs.filter(task__column__board=board)
        t_qs = t_qs.filter(task__column__board=board)
    elif accessible_boards is not None:
        c_qs = c_qs.filter(task__column__board__in=accessible_boards)
        t_qs = t_qs.filter(task__column__board__in=accessible_boards)
    else:
        return None

    classic = c_qs.count()
    thread = t_qs.count()
    if classic == 0 and thread == 0:
        return {'total': 0, 'thread_count': 0, 'classic_count': 0, 'recent_7d': 0}

    recent_7d = (
        c_qs.filter(created_at__gte=cutoff_7d).count()
        + t_qs.filter(created_at__gte=cutoff_7d).count()
    )
    return {
        'total': classic + thread,
        'thread_count': thread,
        'classic_count': classic,
        'recent_7d': recent_7d,
    }


def fetch_comments_detail(board, accessible_boards, limit=15):
    try:
        from kanban.models import Comment
        from messaging.models import TaskThreadComment
    except Exception:
        return None

    c_qs = Comment.objects.select_related('user', 'task', 'task__column')
    t_qs = TaskThreadComment.objects.select_related('author', 'task', 'task__column')
    if board:
        c_qs = c_qs.filter(task__column__board=board)
        t_qs = t_qs.filter(task__column__board=board)
    elif accessible_boards is not None:
        c_qs = c_qs.filter(task__column__board__in=accessible_boards)
        t_qs = t_qs.filter(task__column__board__in=accessible_boards)
    else:
        return None

    merged = []
    for c in c_qs.order_by('-created_at')[:limit]:
        author = c.user.get_full_name() or c.user.username
        merged.append((c.created_at, {
            'kind': 'classic',
            'author': author,
            'task_title': c.task.title,
            'when': _humanize_dt(c.created_at),
            'content_excerpt': (c.content or '')[:200],
        }))
    for t in t_qs.order_by('-created_at')[:limit]:
        author = t.author.get_full_name() or t.author.username
        merged.append((t.created_at, {
            'kind': 'thread',
            'author': author,
            'task_title': t.task.title,
            'when': _humanize_dt(t.created_at),
            'content_excerpt': (t.content or '')[:200],
        }))
    merged.sort(key=lambda row: row[0], reverse=True)
    return {'comments': [row[1] for row in merged[:limit]]}


# ── Files & Attachments ────────────────────────────────────────────────

def fetch_files_summary(board, accessible_boards):
    try:
        from kanban.models import TaskFile
        from messaging.models import FileAttachment
    except Exception:
        return None

    tf = TaskFile.objects.filter(deleted_at__isnull=True)
    fa = FileAttachment.objects.filter(deleted_at__isnull=True)
    if board:
        tf = tf.filter(task__column__board=board)
        fa = fa.filter(chat_room__board=board)
    elif accessible_boards is not None:
        tf = tf.filter(task__column__board__in=accessible_boards)
        fa = fa.filter(chat_room__board__in=accessible_boards)
    else:
        return None

    task_count = tf.count()
    chat_count = fa.count()
    if task_count == 0 and chat_count == 0:
        return {'total': 0, 'task_files': 0, 'chat_files': 0, 'total_size_bytes': 0}

    total_size = (
        sum(tf.values_list('file_size', flat=True))
        + sum(fa.values_list('file_size', flat=True))
    )
    return {
        'total': task_count + chat_count,
        'task_files': task_count,
        'chat_files': chat_count,
        'total_size_bytes': total_size,
    }


def fetch_files_detail(board, accessible_boards, limit=15):
    try:
        from kanban.models import TaskFile
        from messaging.models import FileAttachment
    except Exception:
        return None

    tf = TaskFile.objects.filter(deleted_at__isnull=True).select_related(
        'uploaded_by', 'task'
    )
    fa = FileAttachment.objects.filter(deleted_at__isnull=True).select_related(
        'uploaded_by', 'chat_room'
    )
    if board:
        tf = tf.filter(task__column__board=board)
        fa = fa.filter(chat_room__board=board)
    elif accessible_boards is not None:
        tf = tf.filter(task__column__board__in=accessible_boards)
        fa = fa.filter(chat_room__board__in=accessible_boards)
    else:
        return None

    merged = []
    by_type = {}
    for f in tf.order_by('-uploaded_at')[:limit]:
        uploader = f.uploaded_by.get_full_name() or f.uploaded_by.username
        by_type[f.file_type] = by_type.get(f.file_type, 0) + 1
        merged.append((f.uploaded_at, {
            'filename': f.filename,
            'type': f.file_type,
            'size': f.file_size,
            'uploaded_by': uploader,
            'when': _humanize_dt(f.uploaded_at),
            'attached_to': f'task "{f.task.title}"',
            'ai_summary': (f.ai_summary or '').strip(),
        }))
    for f in fa.order_by('-uploaded_at')[:limit]:
        uploader = f.uploaded_by.get_full_name() or f.uploaded_by.username
        by_type[f.file_type] = by_type.get(f.file_type, 0) + 1
        merged.append((f.uploaded_at, {
            'filename': f.filename,
            'type': f.file_type,
            'size': f.file_size,
            'uploaded_by': uploader,
            'when': _humanize_dt(f.uploaded_at),
            'attached_to': f'chat room "{f.chat_room.name}"',
            'ai_summary': (f.ai_summary or '').strip(),
        }))
    merged.sort(key=lambda row: row[0], reverse=True)
    return {
        'files': [row[1] for row in merged[:limit]],
        'by_type': dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
    }


# ── Skill Development ──────────────────────────────────────────────────

def fetch_skill_dev_summary(board, accessible_boards):
    try:
        from kanban.models import SkillDevelopmentPlan, SkillGap
    except Exception:
        return None

    plans = SkillDevelopmentPlan.objects.exclude(status__in=['completed', 'cancelled'])
    gaps = SkillGap.objects.exclude(status__in=['resolved', 'accepted'])
    if board:
        plans = plans.filter(board=board)
        gaps = gaps.filter(board=board)
    elif accessible_boards is not None:
        plans = plans.filter(board__in=accessible_boards)
        gaps = gaps.filter(board__in=accessible_boards)
    else:
        return None

    active_plans = plans.count()
    open_gaps = gaps.count()
    critical = gaps.filter(severity__in=['high', 'critical']).count()
    return {
        'active_plans': active_plans,
        'open_gaps': open_gaps,
        'critical_gaps': critical,
    }


def fetch_skill_dev_detail(board, accessible_boards):
    try:
        from kanban.models import SkillDevelopmentPlan, SkillGap, TeamSkillProfile
    except Exception:
        return None

    plans_qs = SkillDevelopmentPlan.objects.exclude(
        status__in=['cancelled']
    ).select_related('board')
    gaps_qs = SkillGap.objects.exclude(
        status__in=['accepted']
    ).select_related('board')
    profiles_qs = TeamSkillProfile.objects.select_related('board')
    if board:
        plans_qs = plans_qs.filter(board=board)
        gaps_qs = gaps_qs.filter(board=board)
        profiles_qs = profiles_qs.filter(board=board)
    elif accessible_boards is not None:
        plans_qs = plans_qs.filter(board__in=accessible_boards)
        gaps_qs = gaps_qs.filter(board__in=accessible_boards)
        profiles_qs = profiles_qs.filter(board__in=accessible_boards)
    else:
        return None

    plans = []
    for p in plans_qs.order_by('-target_completion_date')[:10]:
        plans.append({
            'title': p.title,
            'plan_type': p.get_plan_type_display(),
            'target_skill': p.target_skill,
            'target_proficiency': p.target_proficiency,
            'status': p.get_status_display(),
            'target_date': p.target_completion_date.strftime('%Y-%m-%d') if p.target_completion_date else None,
        })

    gaps = []
    for g in gaps_qs.order_by('-severity', '-identified_at')[:10]:
        gaps.append({
            'skill_name': g.skill_name,
            'proficiency': g.proficiency_level,
            'gap_count': g.gap_count,
            'required_count': g.required_count,
            'severity': g.severity,
            'status': g.status,
        })

    profiles = []
    for prof in profiles_qs[:5]:
        try:
            util = float(prof.utilization_percentage)
        except Exception:
            util = 0.0
        profiles.append({
            'board_name': prof.board.name,
            'skill_count': len(prof.available_skills),
            'utilization_percentage': util,
        })

    return {'plans': plans, 'gaps': gaps, 'profiles': profiles}


# ── Briefs (SavedBrief) ────────────────────────────────────────────────

def fetch_briefs_summary(board, user, accessible_boards):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    try:
        from kanban.prizmbrief_models import SavedBrief
    except Exception:
        return None

    qs = SavedBrief.objects.filter(user=user)
    if board:
        qs = qs.filter(board=board)
    elif accessible_boards is not None:
        qs = qs.filter(board__in=accessible_boards)
    else:
        return None

    total = qs.count()
    if total == 0:
        return {'total': 0, 'latest': None}

    latest = qs.order_by('-created_at').first()
    return {
        'total': total,
        'latest': {
            'name': latest.name,
            'when': _humanize_dt(latest.created_at),
        },
    }


def fetch_briefs_detail(board, user, accessible_boards):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    try:
        from kanban.prizmbrief_models import SavedBrief
    except Exception:
        return None

    qs = SavedBrief.objects.filter(user=user).select_related('board')
    if board:
        qs = qs.filter(board=board)
    elif accessible_boards is not None:
        qs = qs.filter(board__in=accessible_boards)
    else:
        return None

    briefs = []
    for b in qs.order_by('-created_at')[:10]:
        slides = b.slides_json or []
        briefs.append({
            'name': b.name,
            'audience_label': b.audience_label or b.audience,
            'purpose_label': b.purpose_label or b.purpose,
            'mode_label': b.mode_label or b.mode,
            'slide_count': len(slides) if isinstance(slides, list) else 0,
            'when': _humanize_dt(b.created_at),
            'board_name': b.board.name if not board else None,
        })
    return {'briefs': briefs}
