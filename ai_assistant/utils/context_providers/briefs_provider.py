"""
Briefs Context Provider — SavedBrief (PrizmBrief AI-generated presentations).

RBAC note: SavedBrief is per-(user, board). Only the user who created a
brief sees it. Cross-board mode scopes to the user's saved briefs across
accessible boards.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class BriefsContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Briefs'
    FEATURE_TAGS = [
        'brief', 'briefs', 'prizmbrief', 'summary doc', 'saved brief',
        'memo', 'executive brief', 'presentation', 'slides',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_briefs_summary
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_briefs_summary(board, user, accessible)
        if data is None or data['total'] == 0:
            return ''
        latest = data.get('latest')
        if latest:
            return (
                f'📝 **Briefs:** {data["total"]} saved. '
                f'Latest: "{latest["name"]}" ({latest["when"]}).\n'
            )
        return f'📝 **Briefs:** {data["total"]} saved.\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_briefs_detail
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_briefs_detail(board, user, accessible)
        if data is None or not data['briefs']:
            return None

        scope = board.name if board else 'all your boards'
        ctx = f'**📝 Saved Briefs — {scope}**\n\n'
        for b in data['briefs'][:10]:
            ctx += (
                f'- "{b["name"]}" — {b["audience_label"]} / '
                f'{b["purpose_label"]} / {b["mode_label"]}, '
                f'{b["slide_count"]} slides, {b["when"]}'
            )
            if b.get('board_name'):
                ctx += f' (board: {b["board_name"]})'
            ctx += '\n'
        return ctx


registry.register(BriefsContextProvider())
