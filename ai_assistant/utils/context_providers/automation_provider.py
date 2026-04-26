"""
Automation Context Provider — board automations and scheduled rules.

NEW provider — automation data was previously invisible to Spectra Q&A.
"""

import logging
from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class AutomationContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Automations'
    FEATURE_TAGS = [
        'automation', 'automations', 'trigger', 'rule', 'rules',
        'webhook', 'webhooks', 'scheduled', 'automated', 'auto',
        'when', 'if then', 'action', 'cron', 'recurring',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        try:
            from kanban.automation_models import BoardAutomation
        except ImportError:
            return ''

        if board:
            autos = BoardAutomation.objects.filter(board=board)
        else:
            accessible = self._get_accessible_boards(user, is_demo_mode)
            autos = BoardAutomation.objects.filter(board__in=accessible)

        total = autos.count()
        active = autos.filter(is_active=True).count()
        if total == 0:
            return '⚡ **Automations:** None configured.\n'

        return f'⚡ **Automations:** {active} active / {total} total.\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        try:
            from kanban.automation_models import BoardAutomation
        except ImportError:
            return ''

        if board:
            autos = BoardAutomation.objects.filter(board=board)
        else:
            accessible = self._get_accessible_boards(user, is_demo_mode)
            autos = BoardAutomation.objects.filter(board__in=accessible)

        if not autos.exists():
            return '**⚡ Automations:** None configured.\n'

        ctx = f'**⚡ Automations ({autos.count()}):**\n'

        for auto in autos.order_by('-is_active', '-last_run_at')[:15]:
            status = '🟢 Active' if auto.is_active else '⭕ Inactive'
            ctx += f'  • {auto.name} [{status}]\n'
            ctx += f'    Trigger: {auto.trigger_type}'
            if auto.trigger_value:
                ctx += f' ({auto.trigger_value})'
            ctx += '\n'
            ctx += f'    Action: {auto.action_type}'
            if auto.action_value:
                ctx += f' ({auto.action_value})'
            ctx += '\n'
            if auto.run_count:
                ctx += f'    Runs: {auto.run_count}'
                if auto.last_run_at:
                    ctx += f', Last: {auto.last_run_at.strftime("%b %d, %I:%M %p")}'
                ctx += '\n'
            if hasattr(auto, 'created_by') and auto.created_by:
                name = auto.created_by.get_full_name() or auto.created_by.username
                ctx += f'    Created by: {name}\n'

        return ctx


registry.register(AutomationContextProvider())
