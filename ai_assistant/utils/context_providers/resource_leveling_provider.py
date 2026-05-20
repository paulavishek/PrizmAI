"""
Resource Leveling Context Provider — capacity alerts, demand forecasts,
workload-distribution recommendations.

Surfaces TeamCapacityAlert, ResourceDemandForecast, and
WorkloadDistributionRecommendation so Spectra can answer "is anyone
overloaded?" / "how do I rebalance?" from real data instead of guessing.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class ResourceLevelingContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Resource Leveling'
    FEATURE_TAGS = [
        'workload', 'capacity', 'overload', 'overloaded', 'rebalance',
        'leveling', 'allocation', 'utilization', 'over-utilized',
        'demand', 'forecast', 'reassign', 'redistribute', 'bandwidth',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        if not board:
            return ''

        from ai_assistant.utils.spectra_data_fetchers import fetch_resource_leveling_summary

        data = fetch_resource_leveling_summary(board)
        if data is None:
            return ''

        parts = []
        if data['active_alerts']:
            parts.append(f'{data["active_alerts"]} active capacity alert(s)')
        if data['critical_alerts']:
            parts.append(f'{data["critical_alerts"]} critical')
        if data['pending_recommendations']:
            parts.append(f'{data["pending_recommendations"]} pending recommendation(s)')
        if data['overloaded_forecasts']:
            parts.append(f'{data["overloaded_forecasts"]} forecast(s) over capacity')

        if not parts:
            return '⚖️ **Resource Leveling:** no active alerts.\n'
        return '⚖️ **Resource Leveling:** ' + ', '.join(parts) + '.\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        if not board:
            return None

        from ai_assistant.utils.spectra_data_fetchers import fetch_resource_leveling_detail

        data = fetch_resource_leveling_detail(board)
        if data is None:
            return None

        ctx = f'**⚖️ Resource Leveling — {board.name}**\n'

        if data['alerts']:
            ctx += f'\n**Capacity Alerts ({len(data["alerts"])}):**\n'
            for a in data['alerts'][:10]:
                ctx += (
                    f'  - [{a["alert_level"]}] {a["resource_name"]} at {a["workload_percentage"]}%'
                    f' — {a["status"]} ({a["alert_type"]})\n'
                )
                if a['message']:
                    ctx += f'    {a["message"][:200]}\n'
        else:
            ctx += '\nNo active capacity alerts.\n'

        if data['recommendations']:
            ctx += f'\n**Distribution Recommendations ({len(data["recommendations"])}):**\n'
            for r in data['recommendations'][:10]:
                ctx += (
                    f'  - [P{r["priority"]}/{r["status"]}] {r["recommendation_type"]}: '
                    f'{r["title"]} (~{r["expected_savings_hours"]}h saved, '
                    f'confidence {r["confidence_score"]})\n'
                )
                if r['description']:
                    ctx += f'    {r["description"][:200]}\n'

        if data['forecasts']:
            ctx += f'\n**Demand Forecasts (latest {len(data["forecasts"])}):**\n'
            for f in data['forecasts'][:8]:
                overload_flag = ' ⚠️ OVER CAPACITY' if f['is_overloaded'] else ''
                ctx += (
                    f'  - {f["resource_name"]} ({f["period_start"]} → {f["period_end"]}): '
                    f'{f["predicted_workload_hours"]}h needed / '
                    f'{f["available_capacity_hours"]}h available '
                    f'({f["utilization_percentage"]}%){overload_flag}\n'
                )

        return ctx


registry.register(ResourceLevelingContextProvider())
