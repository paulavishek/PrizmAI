"""
Sweep orphaned rows left behind by demo-sandbox board deletions.

Background
----------
When a sandbox board is deleted (Reset Demo, or the stale-sandbox GC), a
``post_delete`` handler (``record_project_signal_on_task_delete``) can insert a
fresh ``ProjectSignal`` row for a task that is being removed *during* the same
cascade. Those rows are born after Django's collector already chose what to
delete, so they reference a board/task that no longer exists. On SQLite (dev)
FK checks are disabled for the bulk delete, so the DB doesn't reject them — they
accumulate and eventually make ``PRAGMA foreign_key_check`` (and migrations)
fail. ``_purge_existing_sandbox`` already does a post-cascade sweep, but this
command is a standalone, idempotent safety net you can run at any time — in
particular right before/after migrating the dev SQLite DB to PostgreSQL on
Google Cloud, where such orphans would otherwise raise IntegrityErrors.

It deletes:
  * ProjectSignal / ProjectConfidenceScore whose ``board`` no longer exists
  * TaskActivity whose ``task`` no longer exists

All targets reference their parent via a CASCADE FK, so under normal FK
enforcement (PostgreSQL) there should be nothing to delete — a clean run is the
expected, healthy outcome.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Delete orphaned ProjectSignal/ProjectConfidenceScore/TaskActivity rows whose parent board/task was deleted.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report counts without deleting anything.',
        )

    def handle(self, *args, **options):
        from kanban.models import Board, Task, TaskActivity
        from kanban.project_signals_models import ProjectSignal, ProjectConfidenceScore

        dry_run = options['dry_run']

        board_ids = Board.objects.values_list('id', flat=True)
        task_ids = Task.objects.values_list('id', flat=True)

        targets = [
            ('ProjectSignal (board missing)',
             ProjectSignal.objects.exclude(board_id__in=board_ids)),
            ('ProjectConfidenceScore (board missing)',
             ProjectConfidenceScore.objects.exclude(board_id__in=board_ids)),
            ('TaskActivity (task missing)',
             TaskActivity.objects.exclude(task_id__in=task_ids)),
        ]

        total = 0
        for label, qs in targets:
            count = qs.count()
            total += count
            if count == 0:
                self.stdout.write(f'  {label}: 0 (clean)')
                continue
            if dry_run:
                self.stdout.write(self.style.WARNING(f'  {label}: {count} orphaned (would delete)'))
            else:
                qs.delete()
                self.stdout.write(self.style.SUCCESS(f'  {label}: deleted {count}'))

        if total == 0:
            self.stdout.write(self.style.SUCCESS('No orphaned sandbox rows found — database is clean.'))
        elif dry_run:
            self.stdout.write(self.style.WARNING(f'Total orphaned rows: {total} (dry run — nothing deleted).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Swept {total} orphaned rows.'))
