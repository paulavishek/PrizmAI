"""
Management command to test resource leveling setup
"""
from django.core.management.base import BaseCommand
from kanban.models import Board
from kanban.resource_leveling import ResourceLevelingService


class Command(BaseCommand):
    help = 'Test resource leveling setup and generate initial data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--board-id',
            type=int,
            help='Board ID to test (defaults to first board)',
        )

    def handle(self, *args, **options):
        board_id = options.get('board_id')
        
        if board_id:
            try:
                board = Board.objects.get(id=board_id)
            except Board.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Board {board_id} not found'))
                return
        else:
            board = Board.objects.first()
            if not board:
                self.stdout.write(self.style.ERROR('No boards found'))
                return
        
        self.stdout.write(f'Testing resource leveling for board: {board.name}')
        
        # Initialize service
        service = ResourceLevelingService(board.organization)
        
        # Update profiles
        self.stdout.write('Updating performance profiles...')
        result = service.update_all_profiles(board)
        self.stdout.write(self.style.SUCCESS(
            f"Updated {result['updated']} of {result['total_members']} profiles"
        ))
        
        # Get workload report
        self.stdout.write('\nGenerating workload report...')
        report = service.get_team_workload_report(board)
        
        self.stdout.write(f"Team size: {report['team_size']}")
        self.stdout.write(f"Bottlenecks: {len(report['bottlenecks'])}")
        self.stdout.write(f"Underutilized: {len(report['underutilized'])}")
        
        if report['members']:
            self.stdout.write('\nTeam Members:')
            for member in report['members']:
                status_icon = {
                    'overloaded': '🔴',
                    'balanced': '🟢',
                    'underutilized': '🔵'
                }.get(member['status'], '⚪')
                self.stdout.write(
                    f"  {status_icon} {member['name']}: "
                    f"{member['utilization']:.0f}% "
                    f"({member['active_tasks']} tasks)"
                )
        
        # Get suggestions
        self.stdout.write('\nGenerating suggestions...')
        suggestions = service.get_board_optimization_suggestions(board, limit=5)
        
        if suggestions:
            self.stdout.write(self.style.SUCCESS(f'Found {len(suggestions)} suggestions:'))
            for i, s in enumerate(suggestions, 1):
                self.stdout.write(
                    f"\n{i}. {s.task.title}"
                    f"\n   From: {s.current_assignee.username if s.current_assignee else 'unassigned'}"
                    f"\n   To: {s.suggested_assignee.username}"
                    f"\n   Savings: {s.time_savings_percentage:.0f}%"
                    f"\n   Confidence: {s.confidence_score:.0f}%"
                    f"\n   Reason: {s.reasoning}"
                )
        else:
            self.stdout.write(self.style.WARNING('No optimization suggestions found'))
            self.stdout.write('This means your team is well balanced!')
        
        self.stdout.write('\n' + self.style.SUCCESS('✓ Resource leveling is working!'))
        self.stdout.write(f'\nVisit: http://localhost:8000/boards/{board.id}/')
