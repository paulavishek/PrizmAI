"""
Management command to bulk-classify existing boards into project type profiles.
Sends each unclassified board to Gemini for analysis.

Usage:
    python manage.py classify_boards
    python manage.py classify_boards --organization 3
    python manage.py classify_boards --dry-run
    python manage.py classify_boards --reclassify   # include already-classified boards
"""
import time

from django.core.management.base import BaseCommand

from accounts.models import Organization
from kanban.models import Board
from kanban.utils.ai_utils import classify_board_project_type


class Command(BaseCommand):
    help = 'Classify existing boards into project type profiles using Gemini AI'

    def add_arguments(self, parser):
        parser.add_argument(
            '--organization',
            type=int,
            help='Only process boards belonging to this organization ID',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List boards that would be classified without calling Gemini',
        )
        parser.add_argument(
            '--reclassify',
            action='store_true',
            help='Re-classify boards that already have a project_type (skips confirmed)',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.0,
            help='Seconds to wait between API calls (default: 1.0)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        reclassify = options['reclassify']
        delay = options['delay']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no API calls will be made'))

        boards = Board.objects.filter(is_active=True)

        if options['organization']:
            org = Organization.objects.filter(id=options['organization']).first()
            if not org:
                self.stdout.write(self.style.ERROR(
                    f'Organization {options["organization"]} not found'))
                return
            boards = boards.filter(organization=org)

        if reclassify:
            # Include already-classified but skip user-confirmed
            boards = boards.exclude(project_type_confirmed=True)
        else:
            # Only unclassified boards
            boards = boards.filter(project_type__isnull=True)

        total = boards.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No boards to classify.'))
            return

        self.stdout.write(f'Found {total} board(s) to classify.')

        success = 0
        failed = 0

        for i, board in enumerate(boards.iterator(), 1):
            self.stdout.write(f'  [{i}/{total}] {board.name} (id={board.id}) ... ', ending='')
            if dry_run:
                self.stdout.write(self.style.NOTICE('SKIP (dry-run)'))
                continue

            try:
                result = classify_board_project_type(board)
                board.project_type = result['project_type']
                board.project_type_confidence = result.get('confidence', 0)
                board.project_type_confirmed = False
                board.save(update_fields=[
                    'project_type', 'project_type_confidence',
                    'project_type_confirmed',
                ])
                self.stdout.write(self.style.SUCCESS(
                    f'{result["project_type"]} ({result.get("confidence", 0):.0%})'))
                success += 1
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'FAILED — {exc}'))
                failed += 1

            if i < total and delay > 0:
                time.sleep(delay)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done. {success} classified, {failed} failed, {total - success - failed} skipped.'))
