"""
Management command to clean up orphaned Strategy records.

An "orphaned" strategy is one that is not reachable from any active workspace
and is not part of the official demo seed data — i.e. it was created before
workspace FKs were enforced, or was left behind by incomplete provisioning runs.

Specifically, a strategy is considered orphaned when ALL of the following hold:
  1. strategy.workspace_id is NULL          — not bound to any workspace
  2. strategy.is_seed_demo_data is False    — not official seed/demo data
  3. strategy.mission.workspace_id is NULL  — parent mission also unbound
  4. strategy.mission.is_demo is False      — mission not flagged as demo
  5. strategy.mission.is_seed_demo_data is False

Run with --dry-run first to preview what would be deleted:

    python manage.py clean_orphaned_strategies --dry-run

Then run without it to actually delete:

    python manage.py clean_orphaned_strategies
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from kanban.models import Strategy


class Command(BaseCommand):
    help = (
        "Delete Strategy records that are not associated with any workspace "
        "and are not official demo/seed data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without making any changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN — no changes will be made.\n")
            )

        orphaned_qs = (
            Strategy.objects.filter(
                workspace__isnull=True,
                is_seed_demo_data=False,
                mission__workspace__isnull=True,
                mission__is_demo=False,
                mission__is_seed_demo_data=False,
            )
            .select_related("mission")
            .order_by("mission__name", "name")
        )

        count = orphaned_qs.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No orphaned strategies found."))
            return

        self.stdout.write(
            self.style.WARNING(f"Found {count} orphaned strateg{'y' if count == 1 else 'ies'}:\n")
        )

        for strategy in orphaned_qs:
            mission_name = strategy.mission.name if strategy.mission_id else "(no mission)"
            linked_boards = strategy.boards.count()
            self.stdout.write(
                f"  [{strategy.pk}] {strategy.name!r}  "
                f"(mission: {mission_name!r}, "
                f"linked boards: {linked_boards}, "
                f"created_by: {strategy.created_by_id})"
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{count} strateg{'y' if count == 1 else 'ies'} would be deleted "
                    "(re-run without --dry-run to apply)."
                )
            )
            return

        # Confirm before deleting
        self.stdout.write("")
        confirm = input(
            f"Delete {count} orphaned strateg{'y' if count == 1 else 'ies'}? "
            "Linked boards will have their strategy FK set to NULL. [yes/no]: "
        ).strip().lower()

        if confirm != "yes":
            self.stdout.write(self.style.WARNING("Aborted — no changes made."))
            return

        with transaction.atomic():
            deleted_count, _ = orphaned_qs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted_count} orphaned "
                f"strateg{'y' if deleted_count == 1 else 'ies'}."
            )
        )
