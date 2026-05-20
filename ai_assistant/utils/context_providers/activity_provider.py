"""
Activity Context Provider — recent TaskActivity feed per board.

Surfaces the "what changed?" / "who did what?" feed so Spectra can answer
questions like "show me recent activity" without hallucinating.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class ActivityContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Activity'
    FEATURE_TAGS = [
        'activity', 'recent', 'recently', 'history', 'changed', 'updated',
        'who did', 'what happened', 'audit', 'change log', 'recent activity',
        'last week', 'today', 'yesterday', 'moved', 'created', 'modified',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_activity_summary
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_activity_summary(board, accessible)
        if data is None or data['total'] == 0:
            return ''
        latest = data['latest']
        if latest:
            return (
                f'🕓 **Activity:** {data["total"]} events in last 7 days. '
                f'Latest: {latest["actor"]} {latest["action"]} '
                f'"{latest["task_title"][:40]}" '
                f'{latest["when"]}.\n'
            )
        return f'🕓 **Activity:** {data["total"]} events in last 7 days.\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_activity_detail
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_activity_detail(board, accessible)
        if data is None or not data['events']:
            return None
        scope = board.name if board else 'all your boards'
        ctx = f'**🕓 Recent Activity — {scope}** (last 30 days)\n\n'
        for e in data['events']:
            ctx += (
                f'- {e["when"]} — **{e["actor"]}** {e["action"]} '
                f'`{e["task_title"]}`'
            )
            if e.get('description'):
                ctx += f' — {e["description"][:120]}'
            ctx += '\n'
        if data.get('truncated'):
            ctx += f'\n_…and {data["truncated"]} more events not shown._\n'
        return ctx


registry.register(ActivityContextProvider())
