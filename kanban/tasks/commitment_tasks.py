"""
Celery tasks for Living Commitment Protocols.

- run_commitment_decay_all   : batch-apply confidence decay (every 4 h)
- reset_weekly_tokens        : refill UserCredibilityScore tokens (Monday)
- auto_detect_signals_for_board : triggered by kanban/signals.py on Task saves
- generate_ai_reasoning_task : async Gemini explanation write-back
"""
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='kanban.run_commitment_decay_all', max_retries=2)
def run_commitment_decay_all(self):
    """
    Apply Bayesian confidence decay to every active/at_risk CommitmentProtocol.
    Processes in chunks of 50 to avoid memory spikes.
    """
    from kanban.commitment_models import CommitmentProtocol
    from kanban.commitment_service import CommitmentService

    qs = CommitmentProtocol.objects.filter(
        status__in=['active', 'at_risk']
    ).select_related('board')

    processed = 0
    errors = 0

    # Iterate without loading all at once
    for protocol in qs.iterator(chunk_size=50):
        try:
            CommitmentService.calculate_decay(protocol)
            processed += 1
        except Exception as exc:
            logger.error(
                "Decay failed for CommitmentProtocol %s: %s",
                protocol.pk, exc, exc_info=True
            )
            errors += 1

    logger.info(
        "run_commitment_decay_all: processed=%d errors=%d",
        processed, errors
    )
    return {'processed': processed, 'errors': errors}


@shared_task(bind=True, name='kanban.reset_weekly_tokens', max_retries=2)
def reset_weekly_tokens(self):
    """
    Refill UserCredibilityScore tokens every Monday.
    Resets tokens_remaining to max_tokens and stamps tokens_reset_date.
    """
    from kanban.commitment_models import UserCredibilityScore

    today = timezone.now().date()
    updated = UserCredibilityScore.objects.all().update(
        tokens_remaining=10,
        tokens_reset_date=today,
    )
    logger.info("reset_weekly_tokens: updated %d credibility scores", updated)
    return {'updated': updated}


@shared_task(bind=True, name='kanban.auto_detect_signals_for_board', max_retries=2)
def auto_detect_signals_for_board(self, board_id):
    """
    Scan recent board activity for auto-detectable confidence signals.
    Called by kanban/signals.py after Task saves/deletes.
    """
    from kanban.models import Board
    from kanban.commitment_service import CommitmentService

    try:
        board = Board.objects.get(pk=board_id)
    except Board.DoesNotExist:
        logger.warning("auto_detect_signals_for_board: Board %s not found", board_id)
        return {'status': 'board_not_found'}

    try:
        signals_created = CommitmentService.detect_auto_signals(board)
        return {'status': 'ok', 'signals_created': signals_created}
    except Exception as exc:
        logger.error(
            "auto_detect_signals_for_board failed for board %s: %s",
            board_id, exc, exc_info=True
        )
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, name='kanban.generate_ai_reasoning_task', max_retries=1)
def generate_ai_reasoning_task(self, protocol_id):
    """
    Call Gemini to produce a plain-English explanation of the current
    confidence trend and write it back to CommitmentProtocol.ai_reasoning.
    """
    from kanban.commitment_models import CommitmentProtocol
    from kanban.commitment_service import CommitmentService

    try:
        reasoning = CommitmentService.generate_ai_reasoning(protocol_id)
        CommitmentProtocol.objects.filter(pk=protocol_id).update(ai_reasoning=reasoning)
        return {'status': 'ok', 'protocol_id': protocol_id}
    except CommitmentProtocol.DoesNotExist:
        logger.warning("generate_ai_reasoning_task: protocol %s not found", protocol_id)
        return {'status': 'not_found'}
    except Exception as exc:
        logger.error(
            "generate_ai_reasoning_task failed for protocol %s: %s",
            protocol_id, exc, exc_info=True
        )
        raise self.retry(exc=exc, countdown=120)
