"""
Utility functions for the AI-powered onboarding flow.

commit_onboarding_workspace() is the main entry-point — it takes a
OnboardingWorkspacePreview and materialises the full Goal → Mission →
Strategy → Board → Column → Task hierarchy inside a single transaction.
"""
import logging
from datetime import datetime

from django.db import transaction

logger = logging.getLogger(__name__)

# Maps AI-generated priority labels to the model's PRIORITY_CHOICES values
_PRIORITY_MAP = {
    'critical': 'urgent',   # Model uses 'urgent' not 'critical'
    'high': 'high',
    'medium': 'medium',
    'low': 'low',
}

# Model only supports 'task' and 'milestone' for item_type
_ITEM_TYPE_MAP = {
    'task': 'task',
    'bug': 'task',       # Fallback: bugs → tasks
    'feature': 'task',   # Fallback: features → tasks
    'story': 'task',     # Fallback: stories → tasks
    'milestone': 'milestone',
}


def commit_onboarding_workspace(user, preview):
    """
    Materialise the AI-generated workspace hierarchy into real DB objects.

    Uses ``preview.edited_data`` if present, otherwise ``preview.generated_data``.

    All objects are created inside a single ``transaction.atomic()`` so either
    everything succeeds or nothing is written.

    Returns the created OrganizationGoal instance.
    """
    from kanban.models import (
        OrganizationGoal,
        Mission,
        Strategy,
        Board,
        Column,
        Task,
    )

    data = preview.edited_data if preview.edited_data else preview.generated_data

    if not data or 'goal' not in data or 'missions' not in data:
        raise ValueError("Preview data is missing required 'goal' or 'missions' keys.")

    goal_data = data['goal']
    missions_data = data.get('missions', [])

    # Parse target_date
    target_date = None
    td_raw = goal_data.get('target_date', '')
    if td_raw:
        try:
            target_date = datetime.strptime(td_raw, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            logger.warning(f"Could not parse target_date '{td_raw}', leaving null")

    org = getattr(user, 'profile', None) and user.profile.organization

    with transaction.atomic():
        # ── Organization Goal ──────────────────────────────────────────
        org_goal = OrganizationGoal.objects.create(
            name=goal_data.get('name', 'My Organization Goal')[:200],
            description=goal_data.get('description', ''),
            target_metric=goal_data.get('target_metric', '')[:100] if goal_data.get('target_metric') else '',
            target_date=target_date,
            status='active',
            organization=org,
            created_by=user,
        )
        logger.info(f"Created OrganizationGoal #{org_goal.pk} for {user.username}")

        # ── Missions ───────────────────────────────────────────────────
        for m_data in missions_data:
            mission = Mission.objects.create(
                name=m_data.get('name', 'Mission')[:200],
                description=m_data.get('description', ''),
                status='active',
                organization_goal=org_goal,
                created_by=user,
            )

            # ── Strategies ─────────────────────────────────────────────
            for s_data in m_data.get('strategies', []):
                strategy = Strategy.objects.create(
                    name=s_data.get('name', 'Strategy')[:200],
                    description=s_data.get('description', ''),
                    status='active',
                    mission=mission,
                    created_by=user,
                )

                # ── Boards ─────────────────────────────────────────────
                for b_data in s_data.get('boards', []):
                    board = Board.objects.create(
                        name=b_data.get('name', 'Board')[:100],
                        description=b_data.get('description', ''),
                        strategy=strategy,
                        organization=org,
                        created_by=user,
                    )
                    board.members.add(user)

                    # ── Columns ────────────────────────────────────────
                    columns_names = b_data.get('columns', ['To Do', 'In Progress', 'Done'])
                    # Ensure first column is always "To Do"
                    if not columns_names or columns_names[0] != 'To Do':
                        columns_names = ['To Do'] + [c for c in columns_names if c != 'To Do']

                    col_objects = {}
                    for pos, col_name in enumerate(columns_names):
                        col = Column.objects.create(
                            name=col_name[:100],
                            board=board,
                            position=pos,
                        )
                        col_objects[col_name] = col

                    # ── Tasks (placed in the first column) ─────────────
                    first_col = col_objects.get('To Do') or col_objects.get(columns_names[0])
                    for t_idx, t_data in enumerate(b_data.get('tasks', [])):
                        raw_priority = (t_data.get('priority', 'medium') or 'medium').lower()
                        priority = _PRIORITY_MAP.get(raw_priority, 'medium')

                        raw_type = (t_data.get('item_type', 'task') or 'task').lower()
                        item_type = _ITEM_TYPE_MAP.get(raw_type, 'task')

                        Task.objects.create(
                            title=t_data.get('title', 'New Task')[:200],
                            description=t_data.get('description', ''),
                            column=first_col,
                            position=t_idx,
                            priority=priority,
                            item_type=item_type,
                            created_by=user,
                        )

        # ── Finalise preview + profile ─────────────────────────────────
        preview.status = 'committed'
        preview.save(update_fields=['status', 'updated_at'])

        profile = user.profile
        profile.onboarding_status = 'completed'
        profile.save(update_fields=['onboarding_status'])

    logger.info(f"Onboarding workspace committed for {user.username} (Goal #{org_goal.pk})")
    return org_goal
