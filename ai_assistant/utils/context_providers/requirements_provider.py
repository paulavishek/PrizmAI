"""
Requirements Context Provider — board requirements, status mix, task coverage.

Closes the gap where `requirements.Requirement` was only reachable through
disabled function-call tools. Now Spectra always sees how many requirements
exist, how many are uncovered by tasks, and the top risks.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class RequirementsContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Requirements'
    FEATURE_TAGS = [
        'requirement', 'requirements', 'spec', 'specs', 'specification',
        'acceptance', 'acceptance criteria', 'coverage', 'traceability',
        'functional', 'non-functional', 'in review', 'approved',
        'implemented', 'verified', 'req-',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        if not board:
            return ''

        from ai_assistant.utils.spectra_data_fetchers import fetch_requirements_summary

        data = fetch_requirements_summary(board)
        if data is None:
            return ''  # requirements app not installed / unavailable
        total = data['total']
        if total == 0:
            return '📑 **Requirements:** 0 defined.\n'

        status_parts = [
            f'{cnt} {label}' for label, cnt in data['by_status'].items() if cnt
        ]
        covered_pct = data['covered_pct']
        lines = [
            f'📑 **Requirements:** {total} total — {", ".join(status_parts) or "no status data"}'
        ]
        lines.append(f'  Task coverage: {covered_pct}% ({data["covered"]}/{total} linked to tasks)')
        if data['uncovered']:
            lines.append(f'  ⚠️ Uncovered: {data["uncovered"]}')
        return '\n'.join(lines) + '\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        if not board:
            return None

        from ai_assistant.utils.spectra_data_fetchers import fetch_requirements_detail

        data = fetch_requirements_detail(board)
        if data is None:
            return None
        if data['total'] == 0:
            return f'**📑 Requirements — {board.name}:** none defined.\n'

        ctx = f'**📑 Requirements — {board.name}** ({data["total"]} total)\n'

        if data['by_status']:
            ctx += '\n**By Status:**\n'
            for label, cnt in data['by_status'].items():
                ctx += f'  - {label}: {cnt}\n'

        if data['by_priority']:
            ctx += '\n**By Priority:**\n'
            for label, cnt in data['by_priority'].items():
                ctx += f'  - {label}: {cnt}\n'

        ctx += (
            f'\n**Coverage:** {data["covered"]}/{data["total"]} '
            f'({data["covered_pct"]}%) linked to at least one task\n'
        )

        if data['uncovered_items']:
            ctx += f'\n**⚠️ Uncovered Requirements ({len(data["uncovered_items"])}):**\n'
            for r in data['uncovered_items'][:10]:
                ctx += f'  - {r["identifier"]} {r["title"]} [{r["status_label"]}, {r["priority_label"]}]\n'

        if data['recent']:
            ctx += f'\n**Recently Updated ({len(data["recent"])}):**\n'
            for r in data['recent'][:8]:
                task_n = r['linked_task_count']
                ctx += (
                    f'  - {r["identifier"]} {r["title"]} '
                    f'[{r["status_label"]}, {r["priority_label"]}, {task_n} linked task(s)]\n'
                )

        return ctx


registry.register(RequirementsContextProvider())
