"""
Organizational Memory Context Provider — surfaces the knowledge graph
(MemoryNode + MemoryConnection) so Spectra can answer "have we seen this
before?" / "similar past projects" without inventing precedents.

RBAC: memory nodes are scoped via their board FK. Cross-board reach is limited
to the user's accessible boards (get_accessible_boards_for_spectra), which is
membership/workspace-scoped — not organization-scoped. A node on a board the
user cannot access is never surfaced.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class MemoryContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Organizational Memory'
    FEATURE_TAGS = [
        'memory', 'organizational memory', 'lesson', 'similar past',
        'knowledge graph', 'learned', 'precedent', 'have we seen', 'before',
        'past project', 'history', 'decision log', 'memory node',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_memory_summary
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_memory_summary(board, accessible)
        if data is None or data['total'] == 0:
            return ''
        type_parts = ', '.join(
            f'{c} {t}' for t, c in list(data['by_type'].items())[:4]
        )
        return (
            f'🧠 **Org Memory:** {data["total"]} captured nodes — {type_parts}. '
            f'Latest: "{data["latest_title"]}".\n'
            if data.get('latest_title')
            else f'🧠 **Org Memory:** {data["total"]} captured nodes — {type_parts}.\n'
        )

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_memory_detail
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_memory_detail(board, accessible, query=query)
        if data is None or not data['nodes']:
            return None

        scope = board.name if board else 'all your boards'
        ctx = f'**🧠 Organizational Memory — {scope}** ({data["total"]} nodes)\n\n'

        if data['by_type']:
            ctx += '**By Type:**\n'
            for t, c in data['by_type'].items():
                ctx += f'  - {t}: {c}\n'
            ctx += '\n'

        ctx += '**Most relevant / recent nodes:**\n'
        for n in data['nodes'][:10]:
            ctx += (
                f'- [{n["type"]}] {n["title"]} '
                f'(importance {n["importance"]:.2f}, {n["when"]})'
            )
            if n.get('board_name'):
                ctx += f' — {n["board_name"]}'
            ctx += '\n'
            if n.get('excerpt'):
                ctx += f'    {n["excerpt"]}\n'

        if data.get('connections'):
            ctx += '\n**Notable connections:**\n'
            for c in data['connections'][:5]:
                ctx += f'- "{c["from"]}" --[{c["type"]}]--> "{c["to"]}"\n'

        return ctx


registry.register(MemoryContextProvider())
