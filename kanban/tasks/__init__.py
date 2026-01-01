"""
Celery tasks for the kanban app.
Import all tasks here to ensure they are registered with Celery.
"""
from kanban.tasks.conflict_tasks import (
    detect_conflicts_task,
    generate_resolution_suggestions_task,
    notify_conflict_users_task,
    cleanup_resolved_conflicts_task,
    detect_board_conflicts_task,
)

from kanban.tasks.demo_tasks import (
    cleanup_expired_demo_sessions,
    send_demo_expiry_warning,
    refresh_demo_dates_task,
)

__all__ = [
    # Conflict tasks
    'detect_conflicts_task',
    'generate_resolution_suggestions_task',
    'notify_conflict_users_task',
    'cleanup_resolved_conflicts_task',
    'detect_board_conflicts_task',
    # Demo tasks
    'cleanup_expired_demo_sessions',
    'send_demo_expiry_warning',
    'refresh_demo_dates_task',
]
