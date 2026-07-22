"""
Budget Context Provider — project budget, task costs, ROI, scope.
"""

import logging
from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class BudgetContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Budget & ROI'
    FEATURE_TAGS = [
        'budget', 'cost', 'costs', 'roi', 'return on investment',
        'spending', 'allocated', 'actual cost', 'estimated cost',
        'scope', 'scope baseline', 'scope creep', 'hours',
        'hourly rate', 'task cost', 'project budget',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        try:
            from kanban.budget_models import ProjectBudget
        except ImportError:
            return ''

        if board:
            budget = ProjectBudget.objects.filter(board=board).first()
        else:
            accessible = self._get_accessible_boards(user, is_demo_mode)
            budgets = ProjectBudget.objects.filter(board__in=accessible)
            total_allocated = sum(b.allocated_budget or 0 for b in budgets)
            if not budgets.exists():
                return '💰 **Budget:** No budgets configured.\n'
            return f'💰 **Budget:** {budgets.count()} board(s) with budgets, ${total_allocated:,.0f} total allocated.\n'

        if not budget:
            return '💰 **Budget:** Not configured for this board.\n'

        allocated = budget.allocated_budget or 0
        # Calculate spent from task costs
        try:
            from kanban.budget_models import TaskCost
            spent = sum(
                tc.actual_cost or 0
                for tc in TaskCost.objects.filter(task__column__board=board)
            )
        except Exception:
            spent = 0

        pct = round(spent / allocated * 100, 1) if allocated else 0
        return f'💰 **Budget:** ${spent:,.0f} / ${allocated:,.0f} spent ({pct}%).\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        try:
            from kanban.budget_models import ProjectBudget, TaskCost
        except ImportError:
            return ''

        if not board:
            return self._get_cross_board_budget(user, is_demo_mode)

        budget = ProjectBudget.objects.filter(board=board).first()
        if not budget:
            return f'**💰 Budget — {board.name}:** Not configured.\n'

        ctx = f'**💰 Budget & ROI — {board.name}:**\n'
        ctx += f'  Allocated Budget: ${budget.allocated_budget or 0:,.0f} ({budget.currency})\n'
        if budget.allocated_hours:
            ctx += f'  Allocated Hours: {budget.allocated_hours}\n'
        ctx += f'  Warning Threshold: {budget.warning_threshold}%\n'
        ctx += f'  Critical Threshold: {budget.critical_threshold}%\n'

        # Task costs
        task_costs = TaskCost.objects.filter(
            task__column__board=board
        ).select_related('task')

        total_estimated = sum(tc.estimated_cost or 0 for tc in task_costs)
        total_actual = sum(tc.actual_cost or 0 for tc in task_costs)

        ctx += f'\n  Estimated Total: ${total_estimated:,.0f}\n'
        ctx += f'  Actual Spent: ${total_actual:,.0f}\n'

        if budget.allocated_budget and budget.allocated_budget > 0:
            remaining = budget.allocated_budget - total_actual
            pct_used = round(total_actual / budget.allocated_budget * 100, 1)
            ctx += f'  Remaining: ${remaining:,.0f} ({pct_used}% used)\n'
            if pct_used >= budget.critical_threshold:
                ctx += f'  🔴 CRITICAL: Budget usage at {pct_used}%!\n'
            elif pct_used >= budget.warning_threshold:
                ctx += f'  🟡 WARNING: Budget usage at {pct_used}%\n'

        # Top costs by task
        costly = task_costs.order_by('-actual_cost')[:10]
        if costly:
            ctx += '\n**Top Costs by Task:**\n'
            for tc in costly:
                ctx += (
                    f'  • {tc.task.title}: '
                    f'${tc.actual_cost or 0:,.0f} actual / '
                    f'${tc.estimated_cost or 0:,.0f} estimated\n'
                )

        # Budget recommendations
        try:
            from kanban.budget_models import BudgetRecommendation
            recs = BudgetRecommendation.objects.filter(
                budget=budget
            ).order_by('-created_at')[:5]
            if recs:
                ctx += '\n**AI Budget Recommendations:**\n'
                for r in recs:
                    ctx += f'  • {r.recommendation[:150]}\n'
        except (ImportError, Exception):
            pass

        return ctx

    def _get_cross_board_budget(self, user, is_demo_mode):
        from kanban.budget_models import ProjectBudget
        accessible = self._get_accessible_boards(user, is_demo_mode)
        budgets = ProjectBudget.objects.filter(board__in=accessible).select_related('board')

        if not budgets.exists():
            return '**💰 Budget:** No budgets configured.\n'

        ctx = f'**💰 Budget Overview ({budgets.count()} boards):**\n'
        for b in budgets:
            ctx += f'  • {b.board.name}: ${b.allocated_budget or 0:,.0f} allocated\n'
        return ctx


registry.register(BudgetContextProvider())
