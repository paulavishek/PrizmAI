"""
Generate and save coaching suggestions to the database
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board
from kanban.coach_models import CoachingSuggestion
from kanban.utils.coaching_rules import CoachingRuleEngine
from kanban.utils.ai_coach_service import AICoachService
from kanban.utils.feedback_learning import FeedbackLearningSystem

print("=" * 80)
print("GENERATING AND SAVING COACHING SUGGESTIONS")
print("=" * 80)

# Get demo boards
demo_boards = Board.objects.filter(
    name__in=['Software Project', 'Bug Tracking', 'Marketing Campaign'],
    organization__name__in=['Dev Team', 'Marketing Team']
)

if not demo_boards.exists():
    print("\n❌ No demo boards found!")
    exit(1)

# Initialize AI coach and learning system
ai_coach = AICoachService()
learning_system = FeedbackLearningSystem()

total_created = 0

for board in demo_boards:
    print(f"\n{'='*80}")
    print(f"BOARD: {board.name}")
    print(f"{'='*80}")
    
    # Delete old suggestions to start fresh
    old_count = CoachingSuggestion.objects.filter(board=board).count()
    if old_count > 0:
        print(f"   Deleting {old_count} old suggestion(s)...")
        CoachingSuggestion.objects.filter(board=board).delete()
    
    # Run rule engine
    rule_engine = CoachingRuleEngine(board)
    suggestions_data = rule_engine.analyze_and_generate_suggestions()
    
    print(f"   Generated {len(suggestions_data)} suggestion(s) from rule engine")
    
    # Create board context for AI enhancement
    from kanban.models import Task
    context = {
        'board_name': board.name,
        'team_size': board.members.count(),
        'active_tasks': Task.objects.filter(
            column__board=board, 
            progress__isnull=False, 
            progress__lt=100
        ).count(),
        'project_phase': 'active',
    }
    
    created_count = 0
    for suggestion_data in suggestions_data:
        # Check if should generate based on learning
        should_generate = learning_system.should_generate_suggestion(
            suggestion_data['suggestion_type'],
            board,
            float(suggestion_data['confidence_score'])
        )
        
        if not should_generate:
            print(f"   ⊘ Skipped {suggestion_data['suggestion_type']} (learning system)")
            continue
        
        # Adjust confidence based on learning
        adjusted_confidence = learning_system.get_adjusted_confidence(
            suggestion_data['suggestion_type'],
            float(suggestion_data['confidence_score']),
            board
        )
        suggestion_data['confidence_score'] = adjusted_confidence
        
        # Enhance with AI (if available)
        try:
            suggestion_data = ai_coach.enhance_suggestion_with_ai(
                suggestion_data, context
            )
        except Exception as e:
            print(f"   ⚠️ AI enhancement failed: {e}")
            # Continue with rule-based suggestion
        
        # Create suggestion
        suggestion = CoachingSuggestion.objects.create(**suggestion_data)
        created_count += 1
        total_created += 1
        
        print(f"   ✓ Created: {suggestion.suggestion_type} - {suggestion.title}")
        print(f"      Severity: {suggestion.severity}, Confidence: {suggestion.confidence_score}")
    
    print(f"\n   Total created for this board: {created_count}")

print(f"\n{'='*80}")
print(f"COMPLETE! Created {total_created} coaching suggestions across all boards")
print(f"{'='*80}")
print("\n✅ Suggestions are now visible in the AI Coach dashboard!")
print("   Go to any demo board → AI Coach tab to see them")
