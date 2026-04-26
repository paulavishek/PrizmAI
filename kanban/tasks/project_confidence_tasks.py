"""
Celery tasks for Project Confidence scoring.

- compute_all_board_confidence: Compute confidence scores for all active boards (every 6 hours)
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='kanban.compute_all_board_confidence', max_retries=2)
def compute_all_board_confidence(self):
    """
    Compute a fresh ProjectConfidenceScore for every board that has at least
    one task. Runs every 6 hours via Celery beat.
    """
    from kanban.models import Board
    from kanban.project_confidence_service import ProjectConfidenceService

    boards = Board.objects.filter(
        columns__tasks__isnull=False,
    ).distinct()

    processed = 0
    errors = 0

    for board in boards.iterator(chunk_size=50):
        try:
            ProjectConfidenceService.compute_score(board)
            processed += 1
        except Exception as exc:
            logger.error(
                "Confidence computation failed for board %s: %s",
                board.pk, exc, exc_info=True,
            )
            errors += 1

    logger.info(
        "compute_all_board_confidence: processed=%d errors=%d",
        processed, errors,
    )
    return {'processed': processed, 'errors': errors}
