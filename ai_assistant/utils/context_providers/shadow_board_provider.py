"""
Shadow Board Context Provider — surfaces ShadowBranch / BranchSnapshot data
from ``kanban.shadow_models``.

Previously Spectra had no provider for this feature. When a user asked
"are there any shadow board branches?", Spectra answered "I can only see
Demo Workspace data" — a non-answer caused by the missing provider.
The ``'shadow board'`` tag on risk_provider was vestigial; this provider
takes over that responsibility.
"""

import logging

from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class ShadowBoardContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Shadow Board Branches'
    FEATURE_TAGS = [
        'shadow board', 'shadow branch', 'shadow branches', 'parallel branch',
        'parallel universe', 'feasibility score', 'what-if branch',
        'what if branch', 'branch snapshot', 'alternative timeline',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        if not board:
            return ''

        try:
            from kanban.shadow_models import ShadowBranch
        except ImportError:
            return ''

        branches = ShadowBranch.objects.filter(board=board)
        total = branches.count()
        if total == 0:
            return '🌓 **Shadow Branches:** none.\n'

        active = branches.filter(status='active').count()
        committed = branches.filter(status='committed').count()
        line = f'🌓 **Shadow Branches:** {total} ({active} active'
        if committed:
            line += f', {committed} committed'
        line += ')'
        return line + '\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        if not board:
            return None

        try:
            from kanban.shadow_models import ShadowBranch
        except ImportError:
            return None

        branches = (
            ShadowBranch.objects.filter(board=board)
            .select_related('created_by', 'source_scenario')
            .order_by('-is_starred', '-created_at')
        )
        if not branches.exists():
            return f'**🌓 Shadow Branches — {board.name}:** none created.\n'

        ctx = f'**🌓 Shadow Branches — {board.name}** ({branches.count()})\n'
        for b in branches[:10]:
            star = '⭐ ' if b.is_starred else ''
            snap = b.get_latest_snapshot()
            score = snap.feasibility_score if snap else None
            proj_date = (
                snap.projected_completion_date.isoformat()
                if snap and snap.projected_completion_date else 'n/a'
            )
            ctx += (
                f'  • {star}{b.name} [{b.get_status_display()}]\n'
                f'    Feasibility: {score if score is not None else "—"} / 100'
                f' — projected completion: {proj_date}\n'
            )
            if snap and snap.gemini_recommendation:
                ctx += f'    AI: {snap.gemini_recommendation[:160]}\n'
            if b.description:
                ctx += f'    {b.description[:140]}\n'

        return ctx


registry.register(ShadowBoardContextProvider())
