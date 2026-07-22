"""
Spectra signals:

1. Auto-embed ProjectKnowledgeBase rows on save (so semantic search has a
   vector to work with). Failures are logged but don't break the save.

2. Invalidate the per-board Spectra summary cache when board-level data
   changes (Task / Column / Board / AccessRequest / BoardStatusReport /
   TaskActivity / Notification). Cache busts fire only after the DB write
   commits via transaction.on_commit().
"""

import logging

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction

logger = logging.getLogger(__name__)


# ── ProjectKnowledgeBase: auto-embed on save ────────────────────────────


def _is_embedding_only_update(update_fields):
    """Skip re-embedding when the save only touched the embedding columns."""
    if not update_fields:
        return False
    return set(update_fields).issubset(
        {'embedding', 'embedding_model', 'embedding_updated_at'}
    )


@receiver(post_save, sender='ai_assistant.ProjectKnowledgeBase')
def auto_embed_kb_entry(sender, instance, created, update_fields=None, **kwargs):
    """Generate or refresh the embedding vector for a KB row."""
    # Avoid recursion when we save the embedding back to the row.
    if _is_embedding_only_update(update_fields):
        return
    if not getattr(instance, 'is_active', True):
        return

    def _do_embed():
        try:
            from ai_assistant.utils.ai_clients import embed_text, GEMINI_EMBEDDING_MODEL
            from django.utils import timezone

            text = f'{instance.title}\n\n{instance.content or ""}'.strip()
            if not text:
                return

            vec = embed_text(text, task_type='RETRIEVAL_DOCUMENT')
            if not vec:
                return

            # Refresh from DB before saving so we don't clobber concurrent edits.
            sender.objects.filter(pk=instance.pk).update(
                embedding=vec,
                embedding_model=GEMINI_EMBEDDING_MODEL,
                embedding_updated_at=timezone.now(),
            )
        except Exception as e:
            logger.warning(f'KB auto-embed failed for id={instance.pk}: {e}')

    transaction.on_commit(_do_embed)


# ── Spectra summary cache invalidation ──────────────────────────────────


def _invalidate_summaries_for_board(board_id):
    """Bust all cached summary blocks tied to this board."""
    try:
        from kanban_board.ai_cache import ai_cache_manager
    except Exception:
        return

    def _do_bust():
        try:
            # The summary cache helper keys are namespaced by operation;
            # invalidating the operation clears all (user, board, demo)
            # tuples for that board. Cheap and correct.
            ai_cache_manager.invalidate_operation(f'spectra_summaries_board_{board_id}')
            # Also bust cross-board (board=None) caches for ALL users — these
            # aggregate over multiple boards, so any board change taints them.
            ai_cache_manager.invalidate_operation('spectra_summaries_cross_board')
        except Exception as e:
            logger.debug(f'cache invalidation failed: {e}')

    transaction.on_commit(_do_bust)


def _board_id_from_obj(obj):
    """Best-effort extraction of board_id from a Task/Column/etc."""
    if obj is None:
        return None
    bid = getattr(obj, 'board_id', None)
    if bid:
        return bid
    column = getattr(obj, 'column', None)
    if column is not None:
        return getattr(column, 'board_id', None)
    task = getattr(obj, 'task', None)
    if task is not None:
        col = getattr(task, 'column', None)
        if col is not None:
            return getattr(col, 'board_id', None)
    return None


def _on_board_change(sender, instance, **kwargs):
    bid = _board_id_from_obj(instance)
    if bid:
        _invalidate_summaries_for_board(bid)


def register_cache_invalidators():
    """Wire the invalidator across board-affecting models. Idempotent."""
    try:
        from kanban.models import Task, Column, Board, TaskActivity
    except Exception:
        return

    # Task changes are the highest-frequency signal.
    post_save.connect(_on_board_change, sender=Task, weak=False, dispatch_uid='spectra_cache_task_save')
    post_delete.connect(_on_board_change, sender=Task, weak=False, dispatch_uid='spectra_cache_task_del')
    post_save.connect(_on_board_change, sender=Column, weak=False, dispatch_uid='spectra_cache_column_save')
    post_save.connect(_on_board_change, sender=Board, weak=False, dispatch_uid='spectra_cache_board_save')
    post_save.connect(_on_board_change, sender=TaskActivity, weak=False, dispatch_uid='spectra_cache_activity_save')

    # Optional models — bind only if installed.
    try:
        from kanban.access_request_models import AccessRequest
        post_save.connect(_on_board_change, sender=AccessRequest, weak=False, dispatch_uid='spectra_cache_access_save')
    except Exception:
        pass
    try:
        from kanban.models import BoardStatusReport
        post_save.connect(_on_board_change, sender=BoardStatusReport, weak=False, dispatch_uid='spectra_cache_statusreport_save')
    except Exception:
        pass
