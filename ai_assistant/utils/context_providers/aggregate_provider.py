"""
Cross-Board Aggregate Context Provider — dashboard-level summaries.

Provides aggregate data across ALL user-accessible boards, perfect for
dashboard-level questions like "How many total tasks do I have?"
"""

import logging
from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class AggregateContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Cross-Board Aggregate'
    FEATURE_TAGS = [
        'all boards', 'across all', 'total', 'overall', 'summary',
        'dashboard', 'how many boards', 'my boards', 'all projects',
        'everything', 'whole', 'aggregate', 'overview',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        """Always provide a cross-board summary."""
        accessible = self._get_accessible_boards(user, is_demo_mode)
        board_count = accessible.count()

        if board_count == 0:
            return '🏠 **Dashboard:** No boards available.\n'

        from kanban.models import Task
        total_tasks = Task.objects.filter(
            column__board__in=accessible, item_type='task'
        ).count()
        done_tasks = Task.objects.filter(
            column__board__in=accessible, item_type='task',
        ).select_related('column')

        # Count done using column name (VDF-consistent logic)
        from ai_assistant.utils.spectra_data_fetchers import DONE_COLUMN_NAMES
        done_count = 0
        overdue_count = 0
        from django.utils import timezone
        today = timezone.now().date()
        for t in done_tasks.only('column__name', 'due_date', 'progress'):
            col = t.column.name.lower().strip() if t.column_id else ''
            if col in DONE_COLUMN_NAMES:
                done_count += 1
            elif t.due_date:
                due = t.due_date.date() if hasattr(t.due_date, 'date') else t.due_date
                if due < today:
                    overdue_count += 1

        pct = round(done_count / total_tasks * 100, 1) if total_tasks else 0

        return (
            f'🏠 **Dashboard:** {board_count} board(s), {total_tasks} total tasks, '
            f'{done_count} done ({pct}%), {overdue_count} overdue.\n'
        )

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        accessible = self._get_accessible_boards(user, is_demo_mode)

        if not accessible.exists():
            return '**🏠 Dashboard Overview:** No boards.\n'

        from kanban.models import Task
        from ai_assistant.utils.spectra_data_fetchers import (
            fetch_column_distribution,
            DONE_COLUMN_NAMES,
        )
        from django.utils import timezone
        today = timezone.now().date()

        ctx = f'**🏠 Dashboard Overview ({accessible.count()} boards):**\n'

        grand_total = 0
        grand_done = 0
        grand_overdue = 0

        for b in accessible[:15]:
            col_dist = fetch_column_distribution(b)
            total = sum(c for _, c in col_dist)
            done = sum(c for name, c in col_dist if name.lower().strip() in DONE_COLUMN_NAMES)

            # Overdue count
            overdue = Task.objects.filter(
                column__board=b, item_type='task',
                due_date__lt=today,
            ).exclude(
                column__name__in=['Done', 'Completed', 'Complete', 'Closed', 'Finished', 'Resolved']
            ).count()

            grand_total += total
            grand_done += done
            grand_overdue += overdue

            pct = round(done / total * 100, 1) if total else 0
            overdue_str = f', ⚠️ {overdue} overdue' if overdue else ''
            ctx += f'  • **{b.name}**: {total} tasks, {done} done ({pct}%){overdue_str}\n'

            # Column breakdown
            col_parts = [f'{name}: {cnt}' for name, cnt in col_dist]
            if col_parts:
                ctx += f'    {" | ".join(col_parts)}\n'

        # Totals
        grand_pct = round(grand_done / grand_total * 100, 1) if grand_total else 0
        ctx += (
            f'\n**Totals:** {grand_total} tasks, {grand_done} done ({grand_pct}%), '
            f'{grand_overdue} overdue.\n'
        )

        return ctx


registry.register(AggregateContextProvider())
