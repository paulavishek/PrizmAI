# kanban/management/commands/calculate_stakeholder_metrics.py
"""
Management command to calculate engagement metrics for all boards
Usage: python manage.py calculate_stakeholder_metrics
"""

from django.core.management.base import BaseCommand
from kanban.models import Board
from kanban.stakeholder_utils import calculate_engagement_metrics


class Command(BaseCommand):
    help = 'Calculate engagement metrics for all stakeholders in all boards'

    def add_arguments(self, parser):
        parser.add_argument(
            '--board_id',
            type=int,
            help='Calculate metrics for a specific board ID',
        )

    def handle(self, *args, **options):
        if options['board_id']:
            # Calculate for specific board
            try:
                board = Board.objects.get(id=options['board_id'])
                success, message = self._calculate_for_board(board)
                if success:
                    self.stdout.write(
                        self.style.SUCCESS(f'[OK] {message}')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'[FAIL] {message}')
                    )
            except Board.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Board with ID {options["board_id"]} not found')
                )
        else:
            # Calculate for all boards
            boards = Board.objects.all()
            total = boards.count()
            success_count = 0
            
            self.stdout.write(f'Calculating metrics for {total} board(s)...')
            
            for board in boards:
                success, message = self._calculate_for_board(board)
                if success:
                    success_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'[OK] {board.name}: {message}')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'[FAIL] {board.name}: {message}')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(f'\n[OK] Completed: {success_count}/{total} boards processed successfully')
            )

    @staticmethod
    def _calculate_for_board(board):
        try:
            stakeholders = board.stakeholders.count()
            calculate_engagement_metrics(board)
            return True, f'Metrics calculated for {stakeholders} stakeholder(s)'
        except Exception as e:
            return False, str(e)
