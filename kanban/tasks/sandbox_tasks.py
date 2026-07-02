"""
Sandbox tasks — persistent personal demo system.

The sandbox persists as long as the user's account. No timer, no expiry.
This module provides helper functions for sandbox board cleanup (used by
the reset flow and purge operations).
"""
import logging

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)

# Reclaim a sandbox after this many days of inactivity (no demo entry / reset /
# re-provision). Override with settings.STALE_SANDBOX_DAYS.
DEFAULT_STALE_SANDBOX_DAYS = 90


@shared_task(name='kanban.cleanup_stale_sandboxes')
def cleanup_stale_sandboxes(stale_days=None):
    """Garbage-collect demo sandboxes for users who stopped using the demo.

    A sandbox is "stale" when it hasn't been accessed (entered / reset /
    re-provisioned) for ``stale_days`` days — measured by last_accessed_at,
    falling back to created_at for legacy rows. Each stale sandbox is removed
    with the same comprehensive purge used by Reset Demo (which also deletes the
    DemoSandbox row itself), so no orphaned rows accumulate. This is the fix for
    unbounded storage growth from abandoned demos in production.
    """
    from django.conf import settings
    from kanban.models import DemoSandbox
    from kanban.sandbox_views import _purge_existing_sandbox

    if stale_days is None:
        stale_days = getattr(settings, 'STALE_SANDBOX_DAYS', DEFAULT_STALE_SANDBOX_DAYS)
    cutoff = timezone.now() - timezone.timedelta(days=stale_days)

    # last_accessed_at is NULL on legacy rows — fall back to created_at.
    stale = DemoSandbox.objects.filter(
        Q(last_accessed_at__lt=cutoff)
        | Q(last_accessed_at__isnull=True, created_at__lt=cutoff)
    ).select_related('user')

    reclaimed = 0
    errors = 0
    for sandbox in list(stale):
        user = sandbox.user
        try:
            _purge_existing_sandbox(user)  # also deletes the DemoSandbox row
            reclaimed += 1
        except Exception:
            errors += 1
            logger.exception("cleanup_stale_sandboxes: purge failed for user %s", getattr(user, 'id', None))

    logger.info(
        "cleanup_stale_sandboxes: reclaimed %s stale sandbox(es) (>%s days idle), %s error(s)",
        reclaimed, stale_days, errors,
    )
    return {'reclaimed': reclaimed, 'errors': errors, 'stale_days': stale_days}


def _delete_sandbox(sandbox):
    """Delete all sandbox-copy boards owned by this user. Never touches official demo boards."""
    from kanban.models import Board

    sandbox_boards = Board.objects.filter(
        owner=sandbox.user,
        is_sandbox_copy=True,
        is_official_demo_board=False,   # safety: never delete template boards
        is_seed_demo_data=False,        # safety: never delete seed data
    )

    deleted_count = sandbox_boards.count()
    sandbox_boards.delete()
    logger.info(f"Sandbox cleanup: deleted {deleted_count} boards for user {sandbox.user.username}")
