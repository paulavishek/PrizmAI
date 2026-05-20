"""
Scope Context Provider — scope-change snapshots and scope-creep alerts.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class ScopeContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Scope'
    FEATURE_TAGS = [
        'scope', 'creep', 'scope creep', 'baseline', 'change request',
        'scope change', 'scope autopsy', 'autopsy', 'snapshot',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        if not board:
            return ''

        from ai_assistant.utils.spectra_data_fetchers import fetch_scope_summary

        data = fetch_scope_summary(board)
        if data is None:
            return ''

        parts = []
        if data['active_alerts']:
            parts.append(f'{data["active_alerts"]} open alert(s)')
        if data['critical_alerts']:
            parts.append(f'{data["critical_alerts"]} critical')
        if data['scope_change_pct'] is not None:
            parts.append(f'{data["scope_change_pct"]:+.1f}% vs baseline')

        autopsy = data.get('latest_autopsy')
        if autopsy:
            parts.append(
                f'last autopsy {autopsy["created_at"]} '
                f'(+{autopsy["growth_pct"]:.1f}% growth, '
                f'{autopsy["delay_days"]}d delay)'
            )

        if not parts:
            return '📐 **Scope:** stable, no open alerts.\n'
        return '📐 **Scope:** ' + ', '.join(parts) + '.\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        if not board:
            return None

        from ai_assistant.utils.spectra_data_fetchers import fetch_scope_detail

        data = fetch_scope_detail(board)
        if data is None:
            return None

        ctx = f'**📐 Scope Analysis — {board.name}**\n'

        if data['latest_snapshot']:
            s = data['latest_snapshot']
            ctx += (
                f'\n**Latest Snapshot ({s["snapshot_date"]}, {s["snapshot_type"]}):**\n'
                f'  - Total tasks: {s["total_tasks"]} '
                f'(todo={s["todo_tasks"]}, in_progress={s["in_progress_tasks"]}, done={s["completed_tasks"]})\n'
                f'  - High priority: {s["high_priority_tasks"]}, urgent: {s["urgent_priority_tasks"]}\n'
                f'  - Complexity points: {s["total_complexity_points"]} (avg {s["avg_complexity"]:.2f})\n'
            )
            if s['scope_change_percentage'] is not None:
                ctx += f'  - Scope change vs baseline: {s["scope_change_percentage"]:+.1f}%\n'
            if s['complexity_change_percentage'] is not None:
                ctx += f'  - Complexity change vs baseline: {s["complexity_change_percentage"]:+.1f}%\n'
            if s['predicted_delay_days']:
                ctx += f'  - ⚠️ Predicted delay: {s["predicted_delay_days"]} day(s)\n'

        if data['baseline']:
            b = data['baseline']
            ctx += (
                f'\n**Baseline ({b["snapshot_date"]}):** '
                f'{b["total_tasks"]} tasks, {b["total_complexity_points"]} complexity pts\n'
            )

        if data['alerts']:
            ctx += f'\n**Open Alerts ({len(data["alerts"])}):**\n'
            for a in data['alerts'][:10]:
                ctx += (
                    f'  - [{a["severity"]}/{a["status"]}] +{a["scope_increase_percentage"]:.1f}% scope,'
                    f' +{a["tasks_added"]} tasks (detected {a["detected_at"]})\n'
                )
                if a['ai_summary']:
                    ctx += f'    {a["ai_summary"][:200]}\n'

        if data.get('autopsies'):
            ctx += f'\n**Scope Autopsies ({len(data["autopsies"])}):**\n'
            for ap in data['autopsies'][:5]:
                ctx += (
                    f'  - {ap["created_at"]} [{ap["status"]}]: '
                    f'{ap["baseline_task_count"]} → {ap["final_task_count"]} tasks '
                    f'(+{ap["total_scope_growth_percentage"]:.1f}%), '
                    f'{ap["total_delay_days"]}d delay, '
                    f'${ap["total_budget_impact"]} impact\n'
                )
                if ap.get('ai_summary'):
                    ctx += f'    {ap["ai_summary"][:240]}\n'
                if ap.get('top_events'):
                    ctx += '    Top events:\n'
                    for ev in ap['top_events'][:3]:
                        ctx += (
                            f'      • {ev["event_date"]} — {ev["title"]} '
                            f'(net +{ev["net_task_change"]})\n'
                        )

        return ctx


registry.register(ScopeContextProvider())
