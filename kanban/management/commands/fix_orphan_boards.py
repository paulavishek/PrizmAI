"""
One-time cleanup for boards with no workspace.

Boards created before the Workspace model existed (or seeded by an old demo
command) carry ``workspace=None``. These bleed across the workspace switcher
because they have no home - including the test users' personal "Software
Development" copies that were causing Spectra to answer from the wrong board.

For each orphan: assign to the owner's primary non-demo workspace if one
exists, otherwise report and skip. Use ``--delete-skipped`` to remove
unassignable boards.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from kanban.models import Board, Workspace


class Command(BaseCommand):
    help = 'Assign workspace to boards where workspace is null.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would change without writing.',
        )
        parser.add_argument(
            '--delete-skipped',
            action='store_true',
            help='Delete orphan boards whose owner has no eligible workspace.',
        )

    def handle(self, *args, **opts):
        dry_run = opts['dry_run']
        delete_skipped = opts['delete_skipped']

        orphans = Board.objects.filter(workspace__isnull=True).select_related('owner')
        self.stdout.write(f'Found {orphans.count()} orphan board(s).')

        assigned = 0
        skipped = 0
        deleted = 0

        for board in orphans:
            owner = board.owner
            ws = None
            if owner is not None:
                ws = (
                    Workspace.objects.filter(
                        memberships__user=owner,
                        is_demo=False,
                        is_active=True,
                    )
                    .order_by('created_at')
                    .first()
                )

            if ws is None:
                owner_label = owner.username if owner else '<no owner>'
                self.stdout.write(self.style.WARNING(
                    f'  SKIP id={board.id} name={board.name!r} owner={owner_label} '
                    f'- no eligible non-demo workspace'
                ))
                if delete_skipped and not dry_run:
                    board.delete()
                    deleted += 1
                else:
                    skipped += 1
                continue

            self.stdout.write(
                f'  ASSIGN id={board.id} name={board.name!r} -> {ws.name}'
            )
            if not dry_run:
                with transaction.atomic():
                    board.workspace = ws
                    board.save(update_fields=['workspace'])
            assigned += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. assigned={assigned} skipped={skipped} deleted={deleted}'
            + (' (dry-run)' if dry_run else '')
        ))
