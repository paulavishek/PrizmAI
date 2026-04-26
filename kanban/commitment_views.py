"""
Living Commitment Protocol Views - DEPRECATED

The standalone commitment feature has been decomposed:
- Confidence scoring -> Triple Constraint Dashboard (auto-computed)
- Signal log -> Unified ProjectSignal model
- AI renegotiation -> AI Coach (suggestion type: confidence_drop)
- Prediction market -> Removed

This module now only provides redirect views for backwards compatibility.
"""
import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages

from kanban.models import Board

logger = logging.getLogger(__name__)


@login_required
def commitment_redirect(request, board_id, **kwargs):
    """
    Backwards-compatible redirect: sends users to the Triple Constraint
    Dashboard where project confidence is now displayed.
    """
    board = get_object_or_404(Board, id=board_id)
    messages.info(
        request,
        'Commitment Protocols have been integrated into the Triple Constraint '
        'Dashboard. Your project confidence score is now computed automatically.'
    )
    return redirect('triple_constraint_dashboard', board_id=board.id)