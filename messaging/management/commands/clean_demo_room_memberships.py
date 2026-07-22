"""
Management Command: Clean Demo Room Memberships
===============================================
Removes real (non-demo) users from ChatRoom.members for rooms that belong
to demo workspace boards or official demo boards.

This cleans up stale membership records left by the old auto-add logic that
ran before the RBAC fix was applied.

Usage:
    python manage.py clean_demo_room_memberships
    python manage.py clean_demo_room_memberships --dry-run
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from messaging.models import ChatRoom


class Command(BaseCommand):
    help = 'Remove real users from demo board chat room memberships (cleanup for RBAC fix)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be removed without making any changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes will be made\n'))

        # Identify demo/sandbox rooms via three flags:
        #   1. Board belongs to a demo workspace (workspace.is_demo=True)
        #   2. Board is the official demo board (is_official_demo_board=True)
        #   3. Board is a personal sandbox copy (is_sandbox_copy=True, workspace=None)
        demo_rooms = ChatRoom.objects.filter(
            Q(board__workspace__is_demo=True)
            | Q(board__is_official_demo_board=True)
            | Q(board__is_sandbox_copy=True)
        ).prefetch_related('members', 'members__profile').select_related('board')

        if not demo_rooms.exists():
            self.stdout.write(self.style.SUCCESS('No demo rooms found. Nothing to do.'))
            return

        total_removed = 0
        rooms_affected = 0

        for room in demo_rooms:
            # Real users are those whose UserProfile.is_demo_account is False.
            # Guard against users without a profile (shouldn't happen, but be safe).
            # The sandbox board OWNER is a real user but legitimately belongs to
            # their own sandbox rooms — never remove them, or their Messages
            # badge unread count breaks.
            board_owner_id = getattr(room.board, 'owner_id', None)
            real_members = [
                u for u in room.members.all()
                if not getattr(getattr(u, 'profile', None), 'is_demo_account', False)
                and u.id != board_owner_id
            ]

            if not real_members:
                continue

            rooms_affected += 1
            usernames = ', '.join(u.username for u in real_members)
            self.stdout.write(
                f'  Room "{room.name}" (board: {room.board.name}): '
                f'removing {len(real_members)} real user(s): {usernames}'
            )

            if not dry_run:
                room.members.remove(*real_members)

            total_removed += len(real_members)

        # Summary
        action = 'Would remove' if dry_run else 'Removed'
        style = self.style.WARNING if dry_run else self.style.SUCCESS
        self.stdout.write(
            style(
                f'\n{action} {total_removed} real user(s) from '
                f'{rooms_affected} demo room(s).'
            )
        )
