"""
Ephemeral Sandbox tasks — Phase 7 of RBAC implementation.

Sandbox lifecycle:
  Hour  0:  Created.  User gets full Owner access.
  Hour 22:  Warning notification sent (warning_sent = True).
  Hour 24:  Celery deletes all sandbox boards + DemoSandbox record.
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


def _send_sandbox_expiry_warning(sandbox):
    """Mark the sandbox as warned. The in-app banner is rendered based on warning_sent flag."""
    logger.info(
        f"Sandbox expiry warning for user {sandbox.user.username}: "
        f"expires at {sandbox.expires_at}"
    )


def _delete_sandbox(sandbox):
    """Delete all sandbox-copy boards owned by this user. Never touches official demo boards."""
    from kanban.models import Board, BoardMembership, DemoSandbox

    sandbox_boards = Board.objects.filter(
        owner=sandbox.user,
        is_sandbox_copy=True,
        is_official_demo_board=False,   # safety: never delete template boards
        is_seed_demo_data=False,        # safety: never delete seed data
    )

    if sandbox.saved_board_id:
        # Exclude the board the user chose to save
        sandbox_boards = sandbox_boards.exclude(pk=sandbox.saved_board_id)

    deleted_count = sandbox_boards.count()
    sandbox_boards.delete()
    logger.info(f"Sandbox cleanup: deleted {deleted_count} boards for user {sandbox.user.username}")


@shared_task(name='kanban.cleanup_expired_sandboxes')
def cleanup_expired_sandboxes():
    """
    Hourly task: send warnings for sandboxes expiring within 2 hours,
    then delete all fully expired sandboxes.
    """
    from kanban.models import DemoSandbox
    now = timezone.now()

    # Send expiry warnings for sandboxes expiring within 2 hours
    warning_soon = DemoSandbox.objects.filter(
        expires_at__lte=now + timedelta(hours=2),
        expires_at__gt=now,
        warning_sent=False,
    )
    warned = 0
    for sandbox in warning_soon:
        _send_sandbox_expiry_warning(sandbox)
        sandbox.warning_sent = True
        sandbox.save(update_fields=['warning_sent'])
        warned += 1

    # Delete expired sandboxes
    expired = DemoSandbox.objects.filter(expires_at__lte=now)
    deleted = 0
    for sandbox in expired:
        try:
            from kanban.sandbox_views import _restore_demo_task_assignments, _leave_demo_org
            _restore_demo_task_assignments(sandbox)
            _delete_sandbox(sandbox)
            _leave_demo_org(sandbox.user)
            # Also exit demo mode on their profile
            try:
                profile = sandbox.user.profile
                profile.is_viewing_demo = False
                profile.save(update_fields=['is_viewing_demo'])
            except Exception:
                pass
            sandbox.delete()
            deleted += 1
        except Exception as e:
            logger.error(f"Error deleting sandbox for {sandbox.user.username}: {e}")

    return {'warnings_sent': warned, 'sandboxes_deleted': deleted}
