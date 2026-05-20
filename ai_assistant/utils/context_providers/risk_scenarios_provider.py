"""
Risk Scenarios Context Provider — Pre-Mortem, Stress Test, What-If.

The existing `Risk & Dependencies` provider lists open risks and blockers but
does not surface PreMortemAnalysis, StressTestSession/ImmunityScore, or
WhatIfScenario. This provider owns those three scenario-based features.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class RiskScenariosContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Risk Scenarios'
    FEATURE_TAGS = [
        'pre-mortem', 'premortem', 'pre mortem', 'failure scenario',
        'stress test', 'red team', 'immunity', 'antifragile', 'fragile',
        'resilient', 'vaccine', 'what if', 'what-if', 'whatif', 'scenario',
        'simulation', 'attack', 'fail mode',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        if not board:
            return ''

        from ai_assistant.utils.spectra_data_fetchers import fetch_risk_scenarios_summary

        data = fetch_risk_scenarios_summary(board)
        if data is None:
            return ''

        parts = []
        if data['premortem_count']:
            parts.append(f'{data["premortem_count"]} pre-mortem(s)')
            if data['latest_premortem_risk']:
                parts[-1] += f' (latest: {data["latest_premortem_risk"]})'
        if data['stress_test_count']:
            parts.append(f'{data["stress_test_count"]} stress test(s)')
            if data['latest_immunity_score'] is not None:
                parts[-1] += (
                    f' (latest immunity: {data["latest_immunity_score"]}'
                    f' / {data["latest_immunity_band"]})'
                )
        if data['whatif_count']:
            parts.append(f'{data["whatif_count"]} what-if scenario(s)')
        if not parts:
            return ''  # quiet if nothing exists
        return '🧪 **Risk Scenarios:** ' + ', '.join(parts) + '.\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        if not board:
            return None

        from ai_assistant.utils.spectra_data_fetchers import fetch_risk_scenarios_detail

        data = fetch_risk_scenarios_detail(board)
        if data is None:
            return None
        if (
            not data['premortems']
            and not data['stress_tests']
            and not data['whatifs']
        ):
            return None

        ctx = f'**🧪 Risk Scenarios — {board.name}**\n'

        if data['premortems']:
            ctx += f'\n**Pre-Mortem Analyses ({len(data["premortems"])}):**\n'
            for pm in data['premortems'][:5]:
                ctx += (
                    f'  - {pm["created_at"]} — overall risk: {pm["overall_risk_level"]}'
                    f', {pm["scenario_count"]} scenario(s), {pm["acknowledged_count"]} acknowledged\n'
                )
                for scen in pm['top_scenarios'][:3]:
                    ctx += f'    • {scen}\n'

        if data['stress_tests']:
            ctx += f'\n**Stress Tests ({len(data["stress_tests"])}):**\n'
            for st in data['stress_tests'][:5]:
                immunity = ''
                if st['immunity_overall'] is not None:
                    immunity = f' — immunity {st["immunity_overall"]} ({st["immunity_band"]})'
                ctx += (
                    f'  - {st["created_at"]}{immunity}, '
                    f'{st["scenarios_unaddressed"]} unaddressed, '
                    f'{st["vaccines_applied"]} vaccine(s) applied\n'
                )
                for scen in st['top_scenarios'][:3]:
                    ctx += f'    • {scen}\n'

        if data['whatifs']:
            ctx += f'\n**What-If Scenarios ({len(data["whatifs"])}):**\n'
            for w in data['whatifs'][:6]:
                star = '⭐ ' if w['is_starred'] else ''
                ctx += (
                    f'  - {star}{w["name"]} [{w["scenario_type"]}] — {w["created_at"]}\n'
                )

        return ctx


registry.register(RiskScenariosContextProvider())
