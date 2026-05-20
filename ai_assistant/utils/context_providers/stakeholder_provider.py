"""
Stakeholder Context Provider — project stakeholders, RACI, engagement gaps.

Gives Spectra ground truth for "who are the stakeholders on this board?",
"who is the approver/owner?", and engagement gap analysis. The existing
risk_provider only mentioned name + influence as a side-block; this provider
covers the model fully and handles task-level involvement (RACI).
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class StakeholderContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Stakeholders'
    FEATURE_TAGS = [
        'stakeholder', 'stakeholders', 'raci', 'sponsor', 'approver',
        'decision maker', 'decider', 'influence', 'engagement',
        'power interest', 'quadrant', 'inform', 'consult', 'collaborate',
        'empower',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        if not board:
            return ''

        from ai_assistant.utils.spectra_data_fetchers import fetch_stakeholders_summary

        data = fetch_stakeholders_summary(board)
        if data is None:
            return ''
        total = data['total']
        if total == 0:
            return '👥 **Stakeholders:** none recorded.\n'

        lines = [f'👥 **Stakeholders:** {total} active']
        quad_parts = [f'{cnt} {label}' for label, cnt in data['quadrants'].items() if cnt]
        if quad_parts:
            lines.append(f'  Quadrants: {", ".join(quad_parts)}')
        if data['engagement_gap_count']:
            lines.append(
                f'  ⚠️ {data["engagement_gap_count"]} with engagement gap (current < desired)'
            )
        return '\n'.join(lines) + '\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        if not board:
            return None

        from ai_assistant.utils.spectra_data_fetchers import fetch_stakeholders_detail

        data = fetch_stakeholders_detail(board)
        if data is None:
            return None
        if data['total'] == 0:
            return f'**👥 Stakeholders — {board.name}:** none recorded.\n'

        ctx = f'**👥 Stakeholders — {board.name}** ({data["total"]} active)\n'

        if data['stakeholders']:
            ctx += '\n**Roster:**\n'
            for s in data['stakeholders']:
                line = (
                    f'  - {s["name"]} ({s["role"]})'
                    f' — Influence: {s["influence_level"]}, Interest: {s["interest_level"]},'
                    f' Engagement: {s["current_engagement"]}→{s["desired_engagement"]}'
                    f' [{s["quadrant"]}]'
                )
                if s['email']:
                    line += f' <{s["email"]}>'
                ctx += line + '\n'

        if data['raci']:
            ctx += '\n**RACI (task-level involvement):**\n'
            for involvement_type, items in data['raci'].items():
                if not items:
                    continue
                ctx += f'  {involvement_type}:\n'
                for it in items[:8]:
                    ctx += f'    • {it["stakeholder_name"]} on "{it["task_title"]}" ({it["engagement_status"]})\n'

        if data['engagement_gaps']:
            ctx += '\n**⚠️ Engagement Gaps (desired > current):**\n'
            for g in data['engagement_gaps'][:10]:
                ctx += (
                    f'  - {g["name"]}: {g["current_engagement"]} → '
                    f'{g["desired_engagement"]} (gap {g["gap"]})\n'
                )

        return ctx


registry.register(StakeholderContextProvider())
