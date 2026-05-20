"""
Status Report Context Provider — surfaces the latest BoardStatusReport so
Spectra can answer "what's our project status?" / "are we on track?" with
the actual generated report instead of inferring from raw data.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class StatusReportContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Status Report'
    FEATURE_TAGS = [
        'status', 'status report', 'on track', 'health', 'rag',
        'executive summary', 'sitrep', 'report', 'project status',
        'how are we doing', 'amber', 'green', 'red',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_status_report_summary
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_status_report_summary(board, accessible)
        if data is None or data['total'] == 0:
            return ''
        latest = data['latest']
        if latest:
            return (
                f'📊 **Status Report:** {data["total"]} on file. '
                f'Latest ({latest["created_at"]}): **{latest["rag"].upper()}** '
                f'on {latest["board_name"]}.\n'
            )
        return f'📊 **Status Report:** {data["total"]} on file.\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_status_report_detail
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_status_report_detail(board, accessible)
        if data is None or not data['reports']:
            return None

        scope = board.name if board else 'all your boards'
        ctx = f'**📊 Status Reports — {scope}**\n\n'
        for r in data['reports'][:5]:
            ctx += (
                f'**{r["board_name"]} — {r["created_at"]}** '
                f'(RAG: **{r["rag"].upper()}**, confidence {r["confidence"]:.2f})\n'
            )
            if r.get('rag_reasoning'):
                ctx += f'_Why this RAG:_ {r["rag_reasoning"][:300]}\n'
            if r.get('text_excerpt'):
                ctx += f'{r["text_excerpt"]}\n'
            if r.get('key_drivers'):
                ctx += f'_Key drivers:_ {", ".join(r["key_drivers"][:5])}\n'
            ctx += '\n'
        return ctx


registry.register(StatusReportContextProvider())
