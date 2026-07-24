"""One-time fix for the Requirement identifier auto-generation bug.

``Requirement.save()`` used to derive the next identifier from
``Max('id')`` (the global auto-increment primary key across every board)
instead of a per-board sequence. Every board's *first* requirement was
created directly with an explicit ``REQ-001`` identifier, but every
requirement after that fell through to the buggy auto-generation and
picked up the *global* max id, producing boards with identifiers like
REQ-001, REQ-18910, REQ-18911, ... REQ-18923 instead of a clean REQ-001
through REQ-015 sequence.

This command renumbers each board's requirements sequentially (ordered by
creation date, keeping their relative order intact) now that
``Requirement.save()`` has been fixed to compute the next number from
existing per-board identifiers. Idempotent and safe to re-run.

Run ``--dry-run`` first to preview the changes.
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Renumber Requirement identifiers sequentially per board (fixes the global-id auto-generation bug).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change without writing to the database.',
        )

    def handle(self, *args, **options):
        from requirements.models import Requirement

        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be written.\n'))

        board_ids = sorted(set(Requirement.objects.values_list('board_id', flat=True)))
        total_fixed = 0

        with transaction.atomic():
            for board_id in board_ids:
                reqs = list(
                    Requirement.objects.filter(board_id=board_id).order_by('created_at', 'id')
                )
                changes = []
                for i, req in enumerate(reqs, start=1):
                    expected = f"REQ-{i:03d}"
                    if req.identifier != expected:
                        changes.append((req, req.identifier, expected))

                if not changes:
                    continue

                self.stdout.write(f'Board {board_id}: {len(changes)} identifier(s) to fix')
                for req, old, new in changes:
                    self.stdout.write(f'  {old} -> {new} ("{req.title[:50]}")')
                    if not dry_run:
                        # Bypass Requirement.save()'s auto-generation and history
                        # tracking — this is a pure relabelling, not a status change.
                        Requirement.objects.filter(pk=req.pk).update(identifier=new)
                total_fixed += len(changes)

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Identifiers {"would be " if dry_run else ""}fixed: {total_fixed}.'
        ))
