"""
Cemetery / Exit Protocol Context Provider — project health, hospice, cemetery.

NEW provider — exit protocol data was previously invisible to Spectra Q&A.
"""

import logging
from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class CemeteryContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Project Cemetery'
    FEATURE_TAGS = [
        'cemetery', 'hospice', 'exit protocol', 'project health',
        'killed', 'archived', 'wind down', 'sunset', 'retired',
        'organ transplant', 'transplant', 'health signal',
        'project cemetery', 'dead project',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        try:
            from exit_protocol.models import CemeteryEntry, HospiceSession
        except ImportError:
            return ''

        accessible = self._get_accessible_boards(user, is_demo_mode)

        cemetery_count = CemeteryEntry.objects.filter(
            board__in=accessible
        ).count()

        hospice_count = HospiceSession.objects.filter(
            board__in=accessible, status='active'
        ).count()

        if cemetery_count == 0 and hospice_count == 0:
            return '🪦 **Project Cemetery:** No projects in hospice or cemetery.\n'

        parts = []
        if hospice_count:
            parts.append(f'{hospice_count} in hospice')
        if cemetery_count:
            parts.append(f'{cemetery_count} in cemetery')
        return f'🪦 **Project Cemetery:** {", ".join(parts)}.\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        try:
            from exit_protocol.models import (
                CemeteryEntry, HospiceSession,
                ProjectHealthSignal, ProjectOrgan,
            )
        except ImportError:
            return ''

        accessible = self._get_accessible_boards(user, is_demo_mode)
        ctx = '**🪦 Project Cemetery & Exit Protocol:**\n'

        # Health signals for current board
        if board:
            signals = ProjectHealthSignal.objects.filter(
                board=board
            ).order_by('-recorded_at')[:5]
            if signals:
                ctx += f'\n**Health Signals ({board.name}):**\n'
                for s in signals:
                    risk_icon = '🔴' if s.hospice_risk_score >= 70 else ('🟡' if s.hospice_risk_score >= 40 else '🟢')
                    ctx += (
                        f'  {risk_icon} {s.recorded_at.strftime("%b %d")}: '
                        f'Risk Score {s.hospice_risk_score}/100\n'
                    )
                    ctx += f'    Velocity decline: {s.velocity_decline_pct}%, '
                    ctx += f'Budget spent: {s.budget_spent_pct}%, '
                    ctx += f'Tasks complete: {s.tasks_complete_pct}%\n'

        # Hospice sessions
        hospice = HospiceSession.objects.filter(
            board__in=accessible
        ).select_related('board').order_by('-started_at')[:5]
        if hospice:
            ctx += f'\n**Hospice Sessions ({hospice.count()}):**\n'
            for h in hospice:
                ctx += f'  • {h.board.name} [{h.status}] — Started: {h.started_at.strftime("%b %d, %Y")}\n'

        # Cemetery entries
        cemetery = CemeteryEntry.objects.filter(
            board__in=accessible
        ).select_related('board').order_by('-archived_at')[:5]
        if cemetery:
            ctx += f'\n**Cemetery ({cemetery.count()}):**\n'
            for c in cemetery:
                ctx += f'  • {c.board.name} — Archived: {c.archived_at.strftime("%b %d, %Y")}\n'
                if hasattr(c, 'reason') and c.reason:
                    ctx += f'    Reason: {c.reason[:100]}\n'

        # Organ transplants (reusable components)
        try:
            organs = ProjectOrgan.objects.filter(
                board__in=accessible
            ).select_related('board')[:5]
            if organs:
                ctx += f'\n**Reusable Components ({organs.count()}):**\n'
                for o in organs:
                    ctx += f'  • {o.name} from {o.board.name}'
                    if hasattr(o, 'organ_type'):
                        ctx += f' [{o.organ_type}]'
                    ctx += '\n'
        except Exception:
            pass

        return ctx


registry.register(CemeteryContextProvider())
