"""Re-sync per-user demo sandbox copies' Organizational Memory to the curated set.

Each demo user gets a per-user ``is_sandbox_copy=True`` clone of the official
"Software Development" demo board. The clone copies the curated ~29 memories, but
before live auto-capture was gated for demo boards, signals and daily Celery tasks
kept minting extra MemoryNodes on these copies (older copies drifted to 43-47).

This one-time (idempotent) command restores every existing sandbox copy to exactly
the template's curated set: it deletes each copy's MemoryNodes (MemoryConnections
cascade) and re-clones from the clean template via the same helper used during
provisioning (``kanban.sandbox_views._clone_board_memories``). Safe to re-run.

    python manage.py resync_demo_sandbox_memories [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from kanban.models import Board
from kanban.sandbox_views import _clone_board_memories
from knowledge_graph.models import MemoryNode


class Command(BaseCommand):
    help = "Restore demo sandbox copies' Organizational Memory to the curated template set."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change without modifying the database.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        template = Board.objects.filter(
            is_official_demo_board=True, name='Software Development',
        ).first()
        if not template:
            self.stderr.write(self.style.ERROR(
                'Official "Software Development" demo board not found - nothing to sync.'
            ))
            return

        template_count = MemoryNode.objects.filter(board=template).count()
        self.stdout.write(self.style.NOTICE(
            f'Template board {template.pk} has {template_count} curated memories.'
        ))

        copies = Board.objects.filter(is_sandbox_copy=True).order_by('id')
        if not copies:
            self.stdout.write('No sandbox copies found.')
            return

        total_removed = 0
        for board in copies:
            before = MemoryNode.objects.filter(board=board).count()
            if dry_run:
                self.stdout.write(
                    f'  [dry-run] board {board.pk} (owner={board.owner_id}): '
                    f'{before} -> {template_count}'
                )
                continue
            with transaction.atomic():
                deleted, _ = MemoryNode.objects.filter(board=board).delete()
                _clone_board_memories(template, board)
            after = MemoryNode.objects.filter(board=board).count()
            total_removed += max(before - after, 0)
            self.stdout.write(self.style.SUCCESS(
                f'  board {board.pk} (owner={board.owner_id}): {before} -> {after}'
            ))

        if dry_run:
            self.stdout.write(self.style.NOTICE('Dry run complete - no changes made.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nRe-synced {copies.count()} sandbox copies; '
                f'removed {total_removed} drifted memories.'
            ))
