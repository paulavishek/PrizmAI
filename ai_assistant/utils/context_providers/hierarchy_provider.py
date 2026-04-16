"""
Hierarchy Context Provider — Goals, Missions, Strategies, Board linkage.

Covers the Hierarchy Navigator feature visible on the dashboard.
"""

import logging
from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class HierarchyContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Hierarchy'
    FEATURE_TAGS = [
        'goal', 'goals', 'mission', 'missions', 'strategy', 'strategies',
        'hierarchy', 'organization goal', 'org goal', 'objective', 'vision',
        'target metric', 'okr', 'key result', 'alignment', 'strategic',
        'hierarchy navigator', 'linked boards', 'goal progress',
        'mission progress', 'on track', 'off track',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        try:
            from kanban.models import OrganizationGoal, Mission, Strategy
        except ImportError:
            return ''

        if board and board.strategy_id:
            strategy = board.strategy
            mission = strategy.mission if strategy else None
            goal = mission.organization_goal if mission else None
            crumbs = []
            if goal:
                crumbs.append(f'Goal: {goal.name}')
            if mission:
                crumbs.append(f'Mission: {mission.name}')
            if strategy:
                crumbs.append(f'Strategy: {strategy.name}')
            return f'🏗️ **Hierarchy:** {" → ".join(crumbs)} → {board.name}\n'

        # Cross-board / dashboard: summarize all goals
        accessible_boards = self._get_accessible_boards(user, is_demo_mode)
        strategy_ids = accessible_boards.filter(
            strategy__isnull=False
        ).values_list('strategy_id', flat=True).distinct()

        if not strategy_ids:
            return '🏗️ **Hierarchy:** No goals/missions linked to your boards.\n'

        goals = OrganizationGoal.objects.filter(
            missions__strategies__id__in=strategy_ids
        ).distinct()[:5]
        if not goals:
            return ''
        names = [g.name for g in goals]
        return f'🏗️ **Hierarchy:** {len(goals)} goal(s): {", ".join(names)}\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        try:
            from kanban.models import OrganizationGoal, Mission, Strategy
        except ImportError:
            return ''

        # Collect strategy IDs from accessible boards + the active board
        accessible_boards = self._get_accessible_boards(user, is_demo_mode)
        strategy_ids = set(accessible_boards.filter(
            strategy__isnull=False
        ).values_list('strategy_id', flat=True).distinct())

        # Include the active board's strategy even if _get_accessible_boards
        # doesn't return it (e.g. official demo board for sandbox users)
        if board and board.strategy_id:
            strategy_ids.add(board.strategy_id)

        if not strategy_ids:
            return '**🏗️ Hierarchy Navigator:** No goals/missions linked.\n'

        strategies = Strategy.objects.filter(
            id__in=strategy_ids
        ).select_related('mission', 'mission__organization_goal')

        # Build goal → mission → strategy → boards tree
        goal_tree = {}
        for strat in strategies:
            mission = strat.mission
            goal = mission.organization_goal if mission else None
            goal_key = goal.id if goal else 0
            if goal_key not in goal_tree:
                goal_tree[goal_key] = {
                    'goal': goal,
                    'missions': {},
                }
            if mission:
                m_key = mission.id
                if m_key not in goal_tree[goal_key]['missions']:
                    goal_tree[goal_key]['missions'][m_key] = {
                        'mission': mission,
                        'strategies': [],
                    }
                goal_tree[goal_key]['missions'][m_key]['strategies'].append(strat)

        ctx = '**🏗️ Hierarchy Navigator:**\n'
        for gdata in goal_tree.values():
            goal = gdata['goal']
            if goal:
                status = getattr(goal, 'status', 'active')
                ctx += f'\n🏆 **GOAL: {goal.name}** ({status})\n'
                if getattr(goal, 'target_metric', None):
                    ctx += f'  Target: {goal.target_metric}\n'
                if getattr(goal, 'description', ''):
                    ctx += f'  Context: {goal.description[:200]}\n'

            for mdata in gdata['missions'].values():
                mission = mdata['mission']
                ctx += f'  🎯 **Mission: {mission.name}** (Status: {mission.status})\n'
                if getattr(mission, 'description', ''):
                    ctx += f'    Problem: {mission.description[:200]}\n'

                for strat in mdata['strategies']:
                    ctx += f'    💡 Strategy: {strat.name} (Status: {strat.status})\n'
                    # Boards linked to this strategy
                    linked_boards = accessible_boards.filter(strategy=strat)
                    for b in linked_boards[:5]:
                        from kanban.models import Task
                        t_count = Task.objects.filter(
                            column__board=b, item_type='task'
                        ).count()
                        ctx += f'      📌 Board: {b.name} ({t_count} tasks)\n'

        return ctx


registry.register(HierarchyContextProvider())
