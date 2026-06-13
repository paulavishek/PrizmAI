from django.core.management.base import BaseCommand
from kanban.models import Board, TaskLabel


class Command(BaseCommand):
    help = (
        "Removes Lean Six Sigma labels (category='lean') from boards. "
        "Lean Six Sigma is an operations/manufacturing methodology that is "
        "unfamiliar to most software teams, so these are no longer seeded by "
        "default. This cleans up boards that still carry the old LSS labels."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--board_id', type=int,
            help='Only clean this board (default: all boards).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Report what would be deleted without deleting anything.',
        )

    def handle(self, *args, **options):
        labels = TaskLabel.objects.filter(category='lean')

        if options['board_id']:
            boards = Board.objects.filter(id=options['board_id'])
            if not boards.exists():
                self.stdout.write(
                    self.style.ERROR(f"Board with ID {options['board_id']} not found")
                )
                return
            labels = labels.filter(board_id=options['board_id'])

        # Snapshot for reporting before we mutate anything.
        rows = list(labels.values('board_id', 'name'))
        affected_boards = {r['board_id'] for r in rows}

        if not rows:
            self.stdout.write(self.style.SUCCESS('No Lean Six Sigma labels found. Nothing to do.'))
            return

        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(
                    f"[DRY RUN] Would remove {len(rows)} Lean Six Sigma labels "
                    f"from {len(affected_boards)} board(s)."
                )
            )
            for r in rows:
                self.stdout.write(f"  board {r['board_id']}: {r['name']}")
            return

        deleted, _ = labels.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Removed {deleted} Lean Six Sigma label(s) "
                f"from {len(affected_boards)} board(s)."
            )
        )
