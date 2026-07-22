"""
Skill Development Context Provider — SkillDevelopmentPlan, SkillGap,
TeamSkillProfile.

Spectra can now answer "any active training plans?" / "what skills are we
developing?" / "what's the team's skill inventory?" with real data.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class SkillDevContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Skill Development'
    FEATURE_TAGS = [
        'skill', 'skills', 'training', 'development plan', 'learning',
        'competency', 'growth', 'gap', 'skill gap', 'upskill', 'cross-train',
        'mentorship', 'hiring plan', 'skill inventory', 'capability',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_skill_dev_summary
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_skill_dev_summary(board, accessible)
        if data is None:
            return ''
        if data['active_plans'] == 0 and data['open_gaps'] == 0:
            return ''
        bits = []
        if data['active_plans']:
            bits.append(f'{data["active_plans"]} active dev plans')
        if data['open_gaps']:
            bits.append(f'{data["open_gaps"]} open skill gaps')
            if data.get('critical_gaps'):
                bits[-1] += f' ({data["critical_gaps"]} critical)'
        return f'🎓 **Skill Development:** {", ".join(bits)}.\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        from ai_assistant.utils.spectra_data_fetchers import fetch_skill_dev_detail
        accessible = self._get_accessible_boards(user, is_demo_mode) if not board else None
        data = fetch_skill_dev_detail(board, accessible)
        if data is None:
            return None
        if not data['plans'] and not data['gaps'] and not data['profiles']:
            return None

        scope = board.name if board else 'all your boards'
        ctx = f'**🎓 Skill Development — {scope}**\n\n'

        if data['gaps']:
            ctx += f'**Skill Gaps ({len(data["gaps"])}):**\n'
            for g in data['gaps'][:8]:
                ctx += (
                    f'- {g["skill_name"]} ({g["proficiency"]}) — '
                    f'gap {g["gap_count"]} / {g["required_count"]}, '
                    f'severity **{g["severity"]}**, status {g["status"]}\n'
                )
            ctx += '\n'

        if data['plans']:
            ctx += f'**Development Plans ({len(data["plans"])}):**\n'
            for p in data['plans'][:8]:
                ctx += (
                    f'- {p["title"]} ({p["plan_type"]}) → {p["target_skill"]} '
                    f'to {p["target_proficiency"]}, status {p["status"]}'
                )
                if p.get('target_date'):
                    ctx += f', due {p["target_date"]}'
                ctx += '\n'
            ctx += '\n'

        if data['profiles']:
            ctx += '**Team Skill Profile:**\n'
            for prof in data['profiles'][:3]:
                ctx += (
                    f'- {prof["board_name"]}: {prof["skill_count"]} skills, '
                    f'utilization {prof["utilization_percentage"]:.0f}%\n'
                )

        return ctx


registry.register(SkillDevContextProvider())
