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
    refresh_demo_dates_task,
)

from kanban.tasks.automation_tasks import (
    run_due_date_approaching_automations,
    run_scheduled_automation,
)

from kanban.tasks.time_tracking_tasks import (
    send_time_tracking_reminders,
    detect_time_anomalies,
    send_weekly_time_summary,
)

from kanban.tasks.ai_summary_tasks import (
    generate_board_summary_task,
    generate_strategy_summary_task,
    generate_mission_summary_task,
    generate_daily_executive_briefing,
)

from kanban.tasks.onboarding_tasks import (
    generate_workspace_from_goal_task,
)

__all__ = [
    # Conflict tasks
    'detect_conflicts_task',
    'generate_resolution_suggestions_task',
    'notify_conflict_users_task',
    'cleanup_resolved_conflicts_task',
    'detect_board_conflicts_task',
    # Demo tasks
    'refresh_demo_dates_task',
    # Automation tasks
    'run_due_date_approaching_automations',
    # Time tracking tasks
    'send_time_tracking_reminders',
    'detect_time_anomalies',
    'send_weekly_time_summary',
    # AI summary tasks
    'generate_board_summary_task',
    'generate_strategy_summary_task',
    'generate_mission_summary_task',
    'generate_daily_executive_briefing',
    # Onboarding tasks
    'generate_workspace_from_goal_task',
]
