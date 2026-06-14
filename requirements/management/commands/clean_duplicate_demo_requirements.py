"""One-time cleanup for inflated demo requirement → goal/strategy links.

Two independent fixes, both idempotent and safe to re-run:

1. Collapse genuine duplicate Requirement records that share the same
   (board, title): keep the lowest-id survivor, migrate every linked_goals /
   linked_strategies / linked_tasks relation onto it, then delete the dupes.
   (Defensive — current demo data has none, but a future bug could create some.)

2. Unlink sandbox-copy requirements from the shared org-scoped Goals and
   Strategies. Those objects are singletons shared across all demo sandboxes,
   and the Goal/Strategy detail views aggregate linked_requirements across
   every board with no workspace filter — so each sandbox copy inflates a
   Goal's requirement count by one. Only the canonical template-board
   requirements should carry goal/strategy links. The sandbox Requirement
   records themselves are kept (each demo board still needs its own
   requirements list); only the cross-board goal/strategy links are removed.

Run ``--dry-run`` first to preview the changes.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count


class Command(BaseCommand):
    help = 'Remove duplicate demo requirements and unlink sandbox copies from shared goals/strategies.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would change without writing to the database.',
        )

    def handle(self, *args, **options):
        from kanban.models import Board
        from requirements.models import Requirement

        dry_run = options['dry_run']
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be written.\n'))

        with transaction.atomic():
            collapsed = self._collapse_title_board_duplicates(Requirement, dry_run)
            unlinked = self._unlink_sandbox_requirements(Board, Requirement, dry_run)
            if dry_run:
                # Roll back any speculative writes (there shouldn't be any, but
                # be safe if a future edit forgets a guard).
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Duplicate records {"would be " if dry_run else ""}removed: {collapsed}. '
            f'Sandbox requirements {"would be " if dry_run else ""}unlinked from goals/strategies: {unlinked}.'
        ))

    # ──────────────────────────────────────────────────────────────────
    def _collapse_title_board_duplicates(self, Requirement, dry_run):
        """Keep lowest-id record per (board, title); migrate links; delete rest."""
        dup_keys = (
            Requirement.objects.values('board_id', 'title')
            .annotate(n=Count('id')).filter(n__gt=1)
        )
        deleted = 0
        for key in dup_keys:
            records = list(
                Requirement.objects
                .filter(board_id=key['board_id'], title=key['title'])
                .order_by('id')
            )
            survivor, dupes = records[0], records[1:]
            self.stdout.write(
                f'  [{survivor.board_id}] "{survivor.title}": keep #{survivor.id}, '
                f'collapse {[d.id for d in dupes]}'
            )
            if not dry_run:
                for dupe in dupes:
                    survivor.linked_goals.add(*dupe.linked_goals.all())
                    survivor.linked_strategies.add(*dupe.linked_strategies.all())
                    survivor.linked_tasks.add(*dupe.linked_tasks.all())
                    dupe.delete()
            deleted += len(dupes)
        if not deleted:
            self.stdout.write('  No (board, title) duplicates found.')
        return deleted

    # ──────────────────────────────────────────────────────────────────
    def _unlink_sandbox_requirements(self, Board, Requirement, dry_run):
        """Clear linked_goals / linked_strategies on all sandbox-copy reqs."""
        sandbox_board_ids = list(
            Board.objects.filter(is_sandbox_copy=True).values_list('id', flat=True)
        )
        qs = Requirement.objects.filter(board_id__in=sandbox_board_ids).filter(
            # Only those that actually carry goal/strategy links.
            id__in=(
                Requirement.objects.filter(board_id__in=sandbox_board_ids)
                .filter(linked_goals__isnull=False).values('id')
            )
        ) | Requirement.objects.filter(board_id__in=sandbox_board_ids).filter(
            id__in=(
                Requirement.objects.filter(board_id__in=sandbox_board_ids)
                .filter(linked_strategies__isnull=False).values('id')
            )
        )
        qs = qs.distinct()
        affected = qs.count()
        self.stdout.write(
            f'  Sandbox boards: {len(sandbox_board_ids)}; '
            f'requirements with goal/strategy links to clear: {affected}'
        )
        if not dry_run:
            for req in qs:
                req.linked_goals.clear()
                req.linked_strategies.clear()
        return affected
