"""
Integrations Context Provider — connected third-party services (GitHub, etc.).

Surfaces connection STATUS only (board, repo name, last activity). NEVER
exposes secrets like webhook_secret or access tokens.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class IntegrationsContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Integrations'
    FEATURE_TAGS = [
        'integration', 'integrations', 'github', 'sync', 'repo',
        'repository', 'pull request', 'pr', 'linked', 'third party',
        'connector', 'webhook source', 'connected',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_integrations_summary
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_integrations_summary(board, accessible)
        if data is None or data['total'] == 0:
            return ''
        names = ', '.join(data['active_repos'][:3])
        more = f' (+{data["total"] - 3} more)' if data['total'] > 3 else ''
        return (
            f'🔗 **Integrations:** {data["active"]} active / {data["total"]} total. '
            f'Connected repos: {names}{more}.\n'
        )

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_integrations_detail
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_integrations_detail(board, accessible)
        if data is None or not data['integrations']:
            return None

        scope = board.name if board else 'all your boards'
        ctx = f'**🔗 Integrations — {scope}**\n\n'
        for i in data['integrations']:
            status = '✅ active' if i['is_active'] else '⛔ disabled'
            ctx += (
                f'- **GitHub: {i["repo"]}** → board "{i["board_name"]}" '
                f'({status}, set up {i["created_at"]})'
            )
            if i.get('in_review_column'):
                ctx += f' — PRs route to "{i["in_review_column"]}"'
            ctx += '\n'
        ctx += '\n_Note: Spectra never displays webhook secrets or access tokens._\n'
        return ctx


registry.register(IntegrationsContextProvider())
