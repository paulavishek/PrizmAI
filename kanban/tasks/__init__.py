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

from kanban.tasks.ai_learning_tasks import (
    refresh_pm_metrics_task,
    generate_coaching_suggestions_task,
    train_priority_models_task,
    analyze_feedback_text_task,
    aggregate_org_learning_task,
    run_ab_experiments_task,
)

from kanban.tasks.scope_autopsy_tasks import (
    generate_scope_autopsy,
)

from kanban.tasks.shadow_branch_tasks import (
    recalculate_branches_for_board,
)

from kanban.tasks.sandbox_tasks import (
    cleanup_expired_sandboxes,
)

from kanban.tasks.commitment_tasks import (
    run_commitment_decay_all,
    reset_weekly_tokens,
    auto_detect_signals_for_board,
    generate_ai_reasoning_task,
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
    # AI learning tasks
    'refresh_pm_metrics_task',
    'generate_coaching_suggestions_task',
    'train_priority_models_task',
    'analyze_feedback_text_task',
    'aggregate_org_learning_task',
    'run_ab_experiments_task',
    # Scope autopsy tasks
    'generate_scope_autopsy',
    # Shadow branch tasks
    'recalculate_branches_for_board',
    # Commitment protocol tasks
    'run_commitment_decay_all',
    'reset_weekly_tokens',
    'auto_detect_signals_for_board',
    'generate_ai_reasoning_task',
]
