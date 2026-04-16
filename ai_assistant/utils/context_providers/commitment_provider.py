"""
Commitment Protocol Context Provider — confidence scores, bets, signals.

NEW provider — commitment data was previously invisible to Spectra Q&A.
"""

import logging
from .base import BaseContextProvider
from . import registry

logger = logging.getLogger(__name__)


class CommitmentContextProvider(BaseContextProvider):
    PROVIDER_NAME = 'Commitments'
    FEATURE_TAGS = [
        'commitment', 'commitments', 'confidence', 'protocol',
        'bet', 'bets', 'prediction', 'delivery confidence',
        'signal', 'negotiation', 'credibility', 'at risk',
        'commitment protocol', 'will we deliver',
    ]

    def _get_summary_impl(self, board, user, is_demo_mode=False):
        try:
            from kanban.commitment_models import CommitmentProtocol
        except ImportError:
            return ''

        if board:
            commitments = CommitmentProtocol.objects.filter(board=board)
        else:
            accessible = self._get_accessible_boards(user, is_demo_mode)
            commitments = CommitmentProtocol.objects.filter(board__in=accessible)

        total = commitments.count()
        if total == 0:
            return '🤝 **Commitments:** None active.\n'

        at_risk = commitments.filter(current_confidence__lt=70).count()
        avg_conf = commitments.values_list('current_confidence', flat=True)
        avg = sum(avg_conf) / len(avg_conf) if avg_conf else 0

        risk_str = f', ⚠️ {at_risk} at risk (<70%)' if at_risk else ''
        return f'🤝 **Commitments:** {total} active, avg confidence: {avg:.0f}%{risk_str}\n'

    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        try:
            from kanban.commitment_models import CommitmentProtocol, ConfidenceSignal
        except ImportError:
            return ''

        if board:
            commitments = CommitmentProtocol.objects.filter(board=board)
        else:
            accessible = self._get_accessible_boards(user, is_demo_mode)
            commitments = CommitmentProtocol.objects.filter(board__in=accessible)

        if not commitments.exists():
            return '**🤝 Commitment Protocol:** No commitments.\n'

        ctx = f'**🤝 Commitment Protocol ({commitments.count()}):**\n'

        for c in commitments.order_by('current_confidence')[:10]:
            risk_icon = '🔴' if c.current_confidence < 50 else ('🟡' if c.current_confidence < 70 else '🟢')
            ctx += f'\n  {risk_icon} **{c.title}** — Confidence: {c.current_confidence}%\n'
            ctx += f'    Status: {c.status}, Target: {c.target_date}\n'
            if c.description:
                ctx += f'    {c.description[:150]}\n'
            if c.ai_reasoning:
                ctx += f'    AI Assessment: {c.ai_reasoning[:150]}\n'

            # Latest signals
            try:
                signals = ConfidenceSignal.objects.filter(
                    commitment=c
                ).order_by('-created_at')[:3]
                if signals:
                    ctx += '    Recent signals:\n'
                    for s in signals:
                        ctx += f'      • {s.signal_type}: {s.description[:80]} ({s.created_at.strftime("%b %d")})\n'
            except Exception:
                pass

        return ctx


registry.register(CommitmentContextProvider())
