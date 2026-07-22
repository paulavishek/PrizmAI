"""
Decisions Context Provider — decision items from the decision center.
"""

import logging
from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class DecisionsContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Decisions'
    FEATURE_TAGS = [
        'decision', 'decisions', 'decision log', 'decided',
        'choice', 'options', 'decision center', 'approval',
        'pending decision', 'decision item',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        try:
            from decision_center.models import DecisionItem
        except ImportError:
            return ''

        if board:
            items = DecisionItem.objects.filter(board=board)
        else:
            accessible = self._get_accessible_boards(user, is_demo_mode)
            items = DecisionItem.objects.filter(board__in=accessible)

        total = items.count()
        if total == 0:
            return '⚖️ **Decisions:** No decision items.\n'

        pending = items.filter(item_type='pending').count()
        return (
            f'⚖️ **Decisions:** {total} item(s)'
            + (f', {pending} pending' if pending else '')
            + '.\n'
        )

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        try:
            from decision_center.models import DecisionItem
        except ImportError:
            return ''

        if board:
            items = DecisionItem.objects.filter(board=board)
        else:
            accessible = self._get_accessible_boards(user, is_demo_mode)
            items = DecisionItem.objects.filter(board__in=accessible)

        if not items.exists():
            return '**⚖️ Decisions:** No items.\n'

        ctx = f'**⚖️ Decision Center ({items.count()} items):**\n'

        for item in items.order_by('-created_at')[:20]:
            priority = getattr(item, 'priority_level', 'normal')
            status = getattr(item, 'item_type', 'unknown')
            ctx += f'  • [{status.upper()}] {item.title} (Priority: {priority})\n'
            if hasattr(item, 'description') and item.description:
                ctx += f'    {item.description[:100]}\n'

        return ctx


registry.register(DecisionsContextProvider())
