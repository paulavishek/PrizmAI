"""
Sandbox tasks — persistent personal demo system.

The sandbox persists as long as the user's account. No timer, no expiry.
This module provides helper functions for sandbox board cleanup (used by
the reset flow and purge operations).
"""
import logging

logger = logging.getLogger(__name__)


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
