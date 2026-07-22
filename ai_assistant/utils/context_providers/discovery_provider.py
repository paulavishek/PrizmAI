"""
Discovery Context Provider — DiscoveryIdea backlog (org-scoped).

DiscoveryIdea is organization-scoped (not board-scoped), so this provider
works at the user's organization level. It surfaces the idea funnel:
new / under_review / approved counts, AI scoring quadrants, and the most
recent ideas. Promoted ideas link to a board via IdeaPromotion.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class DiscoveryContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Discovery Ideas'
    FEATURE_TAGS = [
        'idea', 'ideas', 'discovery', 'backlog idea', 'promote', 'promoted',
        'opportunity', 'opportunities', 'product idea', 'feature request',
        'inbox', 'validation', 'quick win', 'strategic bet',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        if not board:
            # Cross-board / org-level view still works
            pass

        from ai_assistant.utils.spectra_data_fetchers import fetch_discovery_summary

        ws = self._get_user_workspace(user)
        if not ws:
            return ''
        data = fetch_discovery_summary(ws)
        if data is None or data['total'] == 0:
            return ''

        stage_parts = [
            f'{cnt} {label}' for label, cnt in data['by_stage'].items() if cnt
        ]
        lines = [f'💡 **Discovery Ideas:** {data["total"]} total — {", ".join(stage_parts)}']
        if data['promoted']:
            lines.append(f'  Promoted to tasks: {data["promoted"]}')
        return '\n'.join(lines) + '\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_discovery_detail

        ws = self._get_user_workspace(user)
        if not ws:
            return None
        data = fetch_discovery_detail(ws)
        if data is None or data['total'] == 0:
            return None

        ctx = f'**💡 Discovery Ideas — {ws.name}** ({data["total"]} total)\n'

        if data['by_stage']:
            ctx += '\n**By Stage:**\n'
            for label, cnt in data['by_stage'].items():
                ctx += f'  - {label}: {cnt}\n'

        if data['by_quadrant']:
            ctx += '\n**AI Scoring Quadrants:**\n'
            for label, cnt in data['by_quadrant'].items():
                ctx += f'  - {label}: {cnt}\n'

        if data['recent']:
            ctx += f'\n**Recent ({len(data["recent"])}):**\n'
            for idea in data['recent'][:12]:
                score = ''
                if idea['ai_score_impact'] is not None:
                    score = (
                        f' — impact {idea["ai_score_impact"]}/100, '
                        f'effort {idea["ai_score_effort"]}/100'
                    )
                ctx += (
                    f'  - [{idea["stage"]}] {idea["title"]}{score}\n'
                )
                if idea['ai_score_recommendation']:
                    ctx += f'    AI: {idea["ai_score_recommendation"][:200]}\n'

        return ctx


registry.register(DiscoveryContextProvider())
