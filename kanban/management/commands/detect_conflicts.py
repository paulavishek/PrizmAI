"""
Management command to detect conflicts in project boards.
Usage: python manage.py detect_conflicts [--board-id=X] [--with-ai]
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from kanban.models import Board
from kanban.conflict_models import ConflictDetection
from kanban.utils.conflict_detection import ConflictDetectionService, ConflictResolutionSuggester
from kanban.utils.ai_conflict_resolution import AIConflictResolutionEngine


class Command(BaseCommand):
    help = 'Detect conflicts in project boards (resource, schedule, dependency conflicts)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--board-id',
            type=int,
            help='Detect conflicts for a specific board ID',
        )
        parser.add_argument(
            '--with-ai',
            action='store_true',
            help='Generate AI-powered resolution suggestions',
        )
        parser.add_argument(
            '--all-boards',
            action='store_true',
            help='Detect conflicts across all boards',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing conflicts before detecting new ones',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting conflict detection...'))
        
        # Determine which boards to analyze
        board_id = options.get('board_id')
        all_boards = options.get('all_boards')
        with_ai = options.get('with_ai', False)
        clear_existing = options.get('clear', False)
        
        if board_id:
            # Detect for specific board
            try:
                board = Board.objects.get(id=board_id)
                if clear_existing:
                    deleted = ConflictDetection.objects.filter(board=board).delete()[0]
                    self.stdout.write(self.style.WARNING(f'Cleared {deleted} existing conflicts for board {board.name}'))
                self.detect_board_conflicts(board, with_ai)
            except Board.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Board with ID {board_id} not found'))
                return
        
        elif all_boards:
            # Detect for all boards
            boards = Board.objects.all()
            if clear_existing:
                deleted = ConflictDetection.objects.filter(board__in=boards).delete()[0]
                self.stdout.write(self.style.WARNING(f'Cleared {deleted} existing conflicts across all boards'))
            self.stdout.write(self.style.NOTICE(f'Analyzing {boards.count()} boards...'))
            
            total_conflicts = 0
            for board in boards:
                count = self.detect_board_conflicts(board, with_ai)
                total_conflicts += count
            
            self.stdout.write(self.style.SUCCESS(f'\nTotal conflicts detected across all boards: {total_conflicts}'))
        
        else:
            # Detect for active boards (default)
            from datetime import timedelta
            from django.utils import timezone
            
            thirty_days_ago = timezone.now() - timedelta(days=30)
            # Tasks are related to boards through columns, use correct relationship path
            boards = Board.objects.filter(
                columns__tasks__updated_at__gte=thirty_days_ago
            ).distinct()
            
            if clear_existing:
                deleted = ConflictDetection.objects.filter(board__in=boards).delete()[0]
                self.stdout.write(self.style.WARNING(f'Cleared {deleted} existing conflicts'))
            
            self.stdout.write(self.style.NOTICE(f'Analyzing {boards.count()} active boards...'))
            
            total_conflicts = 0
            for board in boards:
                count = self.detect_board_conflicts(board, with_ai)
                total_conflicts += count
            
            self.stdout.write(self.style.SUCCESS(f'\nTotal conflicts detected: {total_conflicts}'))
        
        self.stdout.write(self.style.SUCCESS('\nConflict detection completed!'))

    def detect_board_conflicts(self, board, with_ai=False):
        """Detect conflicts for a specific board and return count."""
        self.stdout.write(f'\n--- Analyzing board: {board.name} ---')
        
        # Run detection
        service = ConflictDetectionService(board=board)
        results = service.detect_all_conflicts()
        
        total_conflicts = results['total_conflicts']
        
        # Display summary
        self.stdout.write(f'  Conflicts found: {total_conflicts}')
        
        if total_conflicts > 0:
            self.stdout.write(f'    Resource conflicts: {results["by_type"]["resource"]}')
            self.stdout.write(f'    Schedule conflicts: {results["by_type"]["schedule"]}')
            self.stdout.write(f'    Dependency conflicts: {results["by_type"]["dependency"]}')
            
            self.stdout.write(f'  By severity:')
            self.stdout.write(f'    Critical: {results["by_severity"]["critical"]}')
            self.stdout.write(f'    High: {results["by_severity"]["high"]}')
            self.stdout.write(f'    Medium: {results["by_severity"]["medium"]}')
            self.stdout.write(f'    Low: {results["by_severity"]["low"]}')
            
            # Generate resolution suggestions
            self.stdout.write(f'\n  Generating resolution suggestions...')
            
            for conflict in results['conflicts']:
                self.stdout.write(f'    - {conflict.title} ({conflict.severity})')
                
                # Generate basic suggestions
                suggester = ConflictResolutionSuggester(conflict)
                basic_suggestions = suggester.generate_suggestions()
                
                self.stdout.write(f'      Generated {len(basic_suggestions)} basic resolutions')
                
                # Generate AI suggestions if requested
                if with_ai:
                    try:
                        ai_engine = AIConflictResolutionEngine()
                        ai_suggestions = ai_engine.generate_advanced_resolutions(conflict)
                        self.stdout.write(self.style.SUCCESS(
                            f'      Generated {len(ai_suggestions)} AI-powered resolutions'
                        ))
                        
                        # Enhance basic suggestions
                        if basic_suggestions:
                            enhanced = ai_engine.enhance_basic_suggestions(conflict, basic_suggestions)
                            self.stdout.write(self.style.SUCCESS(
                                f'      Enhanced {len(enhanced)} resolutions with AI insights'
                            ))
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(
                            f'      AI generation failed: {str(e)}'
                        ))
        
        return total_conflicts
