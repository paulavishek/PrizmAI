"""
Risk Context Provider — risk analysis, dependencies, stakeholders, critical tasks.
"""

import logging
from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class RiskContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Risk & Dependencies'
    FEATURE_TAGS = [
        'risk', 'risks', 'critical', 'blocker', 'blockers', 'blocked',
        'dependency', 'dependencies', 'depends', 'blocking',
        'stakeholder', 'stakeholders', 'high risk', 'risk score',
        'mitigation', 'what if', 'shadow board', 'pre-mortem',
        'stress test', 'scenario',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        if not board:
            return ''

        from ai_assistant.utils.spectra_data_fetchers import (
            fetch_board_tasks,
            fetch_dependency_graph,
        )

        tasks = fetch_board_tasks(board, filters={'item_type': 'task', 'is_complete': False})
        high_risk = sum(
            1 for t in tasks
            if t.get('risk_level') in ('high', 'critical')
            or (t.get('ai_risk_score') and t['ai_risk_score'] >= 70)
        )

        graph = fetch_dependency_graph(board)
        blocked = sum(1 for v in graph.values() if v['blocked_by'] and not v['is_complete'])

        parts = []
        if high_risk:
            parts.append(f'{high_risk} high-risk')
        if blocked:
            parts.append(f'{blocked} blocked')
        if not parts:
            return '⚠️ **Risk:** No high-risk or blocked tasks.\n'

        return f'⚠️ **Risk:** {", ".join(parts)} task(s).\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        if not board:
            return None

        from ai_assistant.utils.spectra_data_fetchers import (
            fetch_board_tasks,
            fetch_dependency_graph,
        )

        tasks = fetch_board_tasks(board, filters={'item_type': 'task', 'is_complete': False})
        graph = fetch_dependency_graph(board)

        ctx = f'**⚠️ Risk & Dependency Analysis — {board.name}:**\n'

        # High-risk tasks
        high_risk_tasks = [
            t for t in tasks
            if t.get('risk_level') in ('high', 'critical')
            or (t.get('ai_risk_score') and t['ai_risk_score'] >= 70)
        ]
        if high_risk_tasks:
            ctx += f'\n**🔴 High-Risk Tasks ({len(high_risk_tasks)}):**\n'
            for t in sorted(high_risk_tasks, key=lambda x: x.get('ai_risk_score', 0), reverse=True)[:15]:
                ctx += f'  • {t["title"]} — Risk: {t["risk_level"]} (Score: {t.get("ai_risk_score", "N/A")})\n'
                ctx += f'    Status: {t["column_name"]}, Assigned: {t["assigned_to_display"]}\n'
                if t['is_overdue']:
                    ctx += f'    ⚠️ OVERDUE by {t["overdue_days"]} days\n'

        # Blocked tasks
        blocked_tasks = [
            (tid, v) for tid, v in graph.items()
            if v['blocked_by'] and not v['is_complete']
        ]
        if blocked_tasks:
            ctx += f'\n**🚧 Blocked Tasks ({len(blocked_tasks)}):**\n'
            for tid, v in blocked_tasks[:10]:
                blockers = ', '.join(b['title'] for b in v['blocked_by'])
                ctx += f'  • {v["title"]} — blocked by: {blockers}\n'

        # Critical chain (tasks that block the most)
        critical_chain = sorted(
            graph.items(),
            key=lambda x: x[1]['blocking_count'],
            reverse=True,
        )[:5]
        critical_chain = [(tid, v) for tid, v in critical_chain if v['blocking_count'] > 0]
        if critical_chain:
            ctx += '\n**🔗 Critical Chain (most blocking):**\n'
            for tid, v in critical_chain:
                blocked_names = ', '.join(b['title'] for b in v['blocking'][:3])
                ctx += f'  • {v["title"]} blocks {v["blocking_count"]} task(s): {blocked_names}\n'

        # Stakeholders
        try:
            from kanban.stakeholder_models import ProjectStakeholder
            stakeholders = ProjectStakeholder.objects.filter(board=board)
            if stakeholders.exists():
                ctx += f'\n**👥 Stakeholders ({stakeholders.count()}):**\n'
                for s in stakeholders[:10]:
                    ctx += f'  • {s.name} ({s.role})'
                    if hasattr(s, 'influence_level'):
                        ctx += f' — Influence: {s.influence_level}'
                    ctx += '\n'
        except (ImportError, Exception):
            pass

        return ctx


registry.register(RiskContextProvider())
