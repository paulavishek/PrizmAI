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

from django.db.models import Count, Q
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
        .prefetch_related('dependencies', 'labels', 'subtasks')
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
