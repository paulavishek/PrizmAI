"""
Management command to generate coaching suggestions
Run this periodically to keep suggestions fresh
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from kanban.models import Board
from kanban.coach_models import CoachingSuggestion
from kanban.utils.coaching_rules import CoachingRuleEngine
from kanban.utils.ai_coach_service import AICoachService
from kanban.utils.feedback_learning import FeedbackLearningSystem
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate AI coaching suggestions for boards'

    def add_arguments(self, parser):
        parser.add_argument(
            '--board-id',
            type=int,
            help='Generate suggestions for specific board only',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force generation even if recent suggestions exist',
        )
        parser.add_argument(
            '--ai-enhance',
            action='store_true',
            default=True,
            help='Use AI to enhance suggestions (default: True)',
        )

    def handle(self, *args, **options):
        board_id = options.get('board_id')
        force = options.get('force', False)
        use_ai = options.get('ai_enhance', True)
        
        # Get boards to process
        if board_id:
            boards = Board.objects.filter(id=board_id)
            if not boards.exists():
                self.stdout.write(
                    self.style.ERROR(f"Board {board_id} not found")
                )
                return
        else:
            # Get active boards (has tasks, updated recently)
            boards = Board.objects.filter(
                columns__tasks__isnull=False,
                columns__tasks__updated_at__gte=timezone.now() - timedelta(days=30)
            ).distinct()
        
        self.stdout.write(f"Processing {boards.count()} board(s)...")
        
        # Initialize services
        ai_coach = AICoachService() if use_ai else None
        learning_system = FeedbackLearningSystem()
        
        total_generated = 0
        total_skipped = 0
        boards_processed = 0
        
        for board in boards:
            self.stdout.write(f"\n📊 Analyzing: {board.name}")
            
            # Check if we recently generated for this board
            if not force:
                recent_generation = CoachingSuggestion.objects.filter(
                    board=board,
                    created_at__gte=timezone.now() - timedelta(hours=6)
                ).exists()
                
                if recent_generation:
                    self.stdout.write(
                        self.style.WARNING(
                            "  ⏭️  Skipped (generated within last 6 hours)"
                        )
                    )
                    continue
            
            # Run rule engine
            try:
                rule_engine = CoachingRuleEngine(board)
                suggestions_data = rule_engine.analyze_and_generate_suggestions()
                
                if not suggestions_data:
                    self.stdout.write(
                        self.style.SUCCESS("  ✅ No issues detected - board looks good!")
                    )
                    boards_processed += 1
                    continue
                
                # Build context for AI
                from kanban.models import Task
                context = {
                    'board_name': board.name,
                    'team_size': board.members.count(),
                    'active_tasks': Task.objects.filter(
                        column__board=board,
                        progress__lt=100
                    ).count(),
                    'project_phase': 'active',
                }
                
                board_generated = 0
                board_skipped = 0
                
                for suggestion_data in suggestions_data:
                    # Check if should generate based on learning
                    should_generate = learning_system.should_generate_suggestion(
                        suggestion_data['suggestion_type'],
                        board,
                        float(suggestion_data['confidence_score'])
                    )
                    
                    if not should_generate:
                        board_skipped += 1
                        continue
                    
                    # Adjust confidence based on learning
                    adjusted_confidence = learning_system.get_adjusted_confidence(
                        suggestion_data['suggestion_type'],
                        float(suggestion_data['confidence_score']),
                        board
                    )
                    suggestion_data['confidence_score'] = adjusted_confidence
                    
                    # AI enhancement
                    if ai_coach and use_ai:
                        try:
                            suggestion_data = ai_coach.enhance_suggestion_with_ai(
                                suggestion_data, context
                            )
                        except Exception as e:
                            logger.error(f"AI enhancement failed: {e}")
                            # Continue with rule-based suggestion
                    
                    # Check for duplicate (same type, active, created recently)
                    duplicate = CoachingSuggestion.objects.filter(
                        board=board,
                        suggestion_type=suggestion_data['suggestion_type'],
                        status__in=['active', 'acknowledged'],
                        created_at__gte=timezone.now() - timedelta(days=3)
                    ).exists()
                    
                    if duplicate and not force:
                        board_skipped += 1
                        continue
                    
                    # Create suggestion
                    CoachingSuggestion.objects.create(**suggestion_data)
                    board_generated += 1
                
                total_generated += board_generated
                total_skipped += board_skipped
                boards_processed += 1
                
                # Summary for this board
                severity_counts = {}
                for s in suggestions_data:
                    severity = s['severity']
                    severity_counts[severity] = severity_counts.get(severity, 0) + 1
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✅ Generated {board_generated} suggestions "
                        f"(skipped {board_skipped})"
                    )
                )
                
                if severity_counts:
                    severity_str = ", ".join([
                        f"{k}: {v}" for k, v in severity_counts.items()
                    ])
                    self.stdout.write(f"     {severity_str}")
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  ❌ Error: {str(e)}")
                )
                logger.error(f"Error processing board {board.id}: {e}")
                continue
        
        # Final summary
        self.stdout.write("\n" + "="*50)
        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Complete! Processed {boards_processed} boards"
            )
        )
        self.stdout.write(f"   Generated: {total_generated} suggestions")
        self.stdout.write(f"   Skipped: {total_skipped} duplicates/learned")
        
        if total_generated > 0:
            self.stdout.write(
                "\n💡 Tip: View suggestions at /board/{board_id}/coach/"
            )
