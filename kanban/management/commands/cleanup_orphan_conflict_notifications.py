"""
Management Command: Cleanup Orphan Conflict Notifications
=========================================================
Removes conflict notifications (and affected-user links) for users who do not
have access to the conflict's board, enforcing the same board-level RBAC used
everywhere else in the app (``kanban.simple_access.can_access_board``).

This repairs historical data created before the RBAC guard was added to
``ConflictDetection.ensure_notifications()`` — e.g. a task assigned to a
non-member produced a notification on a board the recipient could not access.

Usage:
    python manage.py cleanup_orphan_conflict_notifications            # apply
    python manage.py cleanup_orphan_conflict_notifications --dry-run  # report only
"""
from django.core.management.base import BaseCommand

from kanban.conflict_models import ConflictDetection, ConflictNotification
from kanban.simple_access import can_access_board


class Command(BaseCommand):
    help = "Delete conflict notifications / affected-user links for users without board access"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report what would be removed without modifying the database',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        mode = 'DRY-RUN' if dry_run else 'APPLY'
        self.stdout.write(self.style.NOTICE(f'Scanning conflict notifications ({mode})...'))

        # Cache board-access decisions per (user_id, board_id) to avoid
        # repeated membership lookups across many notifications.
        access_cache = {}

        def has_access(user, board):
            key = (user.id, board.id)
            if key not in access_cache:
                access_cache[key] = can_access_board(user, board)
            return access_cache[key]

        # 1. Orphan notifications: recipient can't access the conflict's board.
        orphan_notif_ids = []
        notif_qs = ConflictNotification.objects.select_related('user', 'conflict', 'conflict__board')
        for notif in notif_qs.iterator():
            board = notif.conflict.board
            if board is None or not has_access(notif.user, board):
                orphan_notif_ids.append(notif.id)
                self.stdout.write(
                    f'  [orphan notif] id={notif.id} user={notif.user.username} '
                    f'board={getattr(board, "id", None)} ({getattr(board, "name", "?")}) '
                    f'conflict={notif.conflict_id}'
                )

        # 2. Orphan affected_users links: affected user can't access the board.
        stripped_links = 0
        for conflict in ConflictDetection.objects.select_related('board').prefetch_related('affected_users'):
            board = conflict.board
            if board is None:
                continue
            bad_users = [u for u in conflict.affected_users.all() if not has_access(u, board)]
            if bad_users:
                stripped_links += len(bad_users)
                names = ', '.join(u.username for u in bad_users)
                self.stdout.write(
                    f'  [orphan affected_user] conflict={conflict.id} '
                    f'board={board.id} removing: {names}'
                )
                if not dry_run:
                    conflict.affected_users.remove(*bad_users)

        # Apply notification deletions.
        if not dry_run and orphan_notif_ids:
            ConflictNotification.objects.filter(id__in=orphan_notif_ids).delete()

        verb = 'Would remove' if dry_run else 'Removed'
        self.stdout.write(self.style.SUCCESS(
            f'\n{verb} {len(orphan_notif_ids)} orphan notification(s) and '
            f'{stripped_links} orphan affected-user link(s).'
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run only — no changes were made.'))
