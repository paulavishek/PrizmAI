"""
Coach Context Provider — AI Coach suggestions, insights, and PM metrics.

Closes the gap where the AI Coach feature was invisible to Spectra. Users
asking "what does the coach suggest?" or "where am I improving?" now get
grounded data instead of generic platitudes.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class CoachContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'AI Coach'
    FEATURE_TAGS = [
        'coach', 'coaching', 'suggestion', 'suggestions', 'insight',
        'insights', 'pm metric', 'pm metrics', 'recommend', 'recommendation',
        'improve', 'mentor', 'advice', 'guidance', 'effectiveness',
        'velocity trend', 'deadline hit rate',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_coach_summary
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_coach_summary(board, user, accessible)
        if data is None:
            return ''
        if data['open_count'] == 0 and not data.get('top_metric'):
            return ''
        lines = [f'🎯 **AI Coach:** {data["open_count"]} active suggestions']
        if data.get('high_severity'):
            lines[-1] += f' ({data["high_severity"]} high/critical)'
        if data.get('top_suggestion'):
            lines.append(f'  Top: "{data["top_suggestion"]["title"]}"')
        if data.get('top_metric'):
            m = data['top_metric']
            lines.append(
                f'  Last period: velocity {m["velocity_trend"]}, '
                f'deadline hit rate {m["deadline_hit_rate"]}%'
            )
        return '\n'.join(lines) + '\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_coach_detail
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_coach_detail(board, user, accessible)
        if data is None:
            return None
        if not data['suggestions'] and not data['insights'] and not data['metrics']:
            return None

        scope = board.name if board else 'all your boards'
        ctx = f'**🎯 AI Coach — {scope}**\n\n'

        if data['suggestions']:
            ctx += f'**Open Suggestions ({len(data["suggestions"])}):**\n'
            for s in data['suggestions'][:10]:
                ctx += (
                    f'- [{s["severity"].upper()}] {s["title"]} — {s["type"]} '
                    f'(created {s["created_at"]})\n'
                )
                if s.get('message'):
                    ctx += f'    {s["message"][:200]}\n'

        if data['metrics']:
            ctx += '\n**Recent PM Metrics:**\n'
            for m in data['metrics'][:3]:
                ctx += (
                    f'- {m["period"]}: velocity {m["velocity_trend"]}, '
                    f'deadline hit {m["deadline_hit_rate"]}%, '
                    f'risk mitigation {m["risk_mitigation_success_rate"]}%, '
                    f'effectiveness {m["coaching_effectiveness_score"]}\n'
                )

        if data['insights']:
            ctx += '\n**Active Insights:**\n'
            for i in data['insights'][:5]:
                ctx += f'- {i["title"]} (confidence {i["confidence"]:.2f})\n'

        return ctx


registry.register(CoachContextProvider())
