"""
Django management command to train priority classification models
"""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from kanban.models import Board
from kanban.priority_models import PriorityDecision
from ai_assistant.utils.priority_service import PriorityModelTrainer


class Command(BaseCommand):
    help = 'Train priority classification models for boards with sufficient data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--board-id',
            type=int,
            help='Train model for specific board ID'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Train models for all boards with sufficient data'
        )
        parser.add_argument(
            '--min-samples',
            type=int,
            default=20,
            help='Minimum number of training samples required (default: 20)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force training even with low sample count'
        )
    
    def handle(self, *args, **options):
        board_id = options.get('board_id')
        train_all = options.get('all')
        min_samples = options.get('min_samples', 20)
        force = options.get('force', False)
        
        if not board_id and not train_all:
            raise CommandError('Please specify --board-id or --all')
        
        if board_id:
            # Train specific board
            try:
                board = Board.objects.get(pk=board_id)
                self._train_board_model(board, min_samples, force)
            except Board.DoesNotExist:
                raise CommandError(f'Board with ID {board_id} does not exist')
        
        elif train_all:
            # Train all boards with sufficient data
            self._train_all_boards(min_samples, force)
    
    def _train_board_model(self, board, min_samples, force):
        """Train model for a single board"""
        self.stdout.write(f'\nTraining priority model for board: {board.name} (ID: {board.id})')
        
        # Check decision count
        decision_count = PriorityDecision.objects.filter(board=board).count()
        self.stdout.write(f'  Available training samples: {decision_count}')
        
        if decision_count < min_samples and not force:
            self.stdout.write(
                self.style.WARNING(
                    f'  Skipping: Need at least {min_samples} samples (use --force to override)'
                )
            )
            return False
        
        # Train model
        trainer = PriorityModelTrainer(board)
        
        try:
            result = trainer.train_model(min_samples=min_samples if not force else 1)
            
            if not result['success']:
                self.stdout.write(
                    self.style.ERROR(f"  Failed: {result.get('error', 'Unknown error')}")
                )
                return False
            
            # Display results
            self.stdout.write(self.style.SUCCESS(f"  ✓ Model v{result['model_version']} trained successfully!"))
            self.stdout.write(f"    Accuracy: {result['accuracy']:.2%}")
            self.stdout.write(f"    Training samples: {result['training_samples']}")
            self.stdout.write(f"    Test samples: {result['test_samples']}")
            
            # Display per-class metrics
            self.stdout.write('\n    Per-class metrics:')
            for priority_class in result['classes']:
                precision = result['precision'].get(priority_class, 0)
                recall = result['recall'].get(priority_class, 0)
                f1 = result['f1_scores'].get(priority_class, 0)
                self.stdout.write(
                    f"      {priority_class:8s}: P={precision:.2%} R={recall:.2%} F1={f1:.2%}"
                )
            
            # Display top features
            self.stdout.write('\n    Top influential features:')
            sorted_features = sorted(
                result['feature_importance'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            for feature, importance in sorted_features:
                self.stdout.write(f"      {feature:25s}: {importance:.3f}")
            
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"  Error during training: {str(e)}")
            )
            return False
    
    def _train_all_boards(self, min_samples, force):
        """Train models for all eligible boards"""
        self.stdout.write(self.style.NOTICE('\nTraining priority models for all eligible boards...'))
        
        # Get boards with sufficient decision data
        boards_with_data = PriorityDecision.objects.values('board').annotate(
            decision_count=Count('id')
        ).filter(decision_count__gte=min_samples if not force else 1)
        
        board_ids = [item['board'] for item in boards_with_data]
        boards = Board.objects.filter(id__in=board_ids)
        
        self.stdout.write(f'Found {boards.count()} boards with sufficient data\n')
        
        if boards.count() == 0:
            self.stdout.write(
                self.style.WARNING(
                    f'No boards have at least {min_samples} priority decisions yet.'
                )
            )
            self.stdout.write('Users need to make more priority decisions before models can be trained.')
            return
        
        # Train each board
        success_count = 0
        for board in boards:
            if self._train_board_model(board, min_samples, force):
                success_count += 1
        
        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Successfully trained {success_count} of {boards.count()} models'
            )
        )
