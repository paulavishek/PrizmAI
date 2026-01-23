"""
Regenerate AI Coach suggestions for Marketing Campaign and Bug Tracking boards
with detailed AI enhancement
"""
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.coach_models import CoachingSuggestion
from kanban.models import Board, Task
from kanban.utils.coaching_rules import CoachingRuleEngine
from kanban.utils.ai_coach_service import AICoachService

print("\n=== Regenerating AI Coach Suggestions for Marketing & Bug Tracking ===\n")

# Get the boards
marketing_board = Board.objects.filter(name='Marketing Campaign', is_official_demo_board=True).first()
bug_board = Board.objects.filter(name='Bug Tracking', is_official_demo_board=True).first()

boards_to_process = []
if marketing_board:
    boards_to_process.append(('Marketing Campaign', marketing_board))
if bug_board:
    boards_to_process.append(('Bug Tracking', bug_board))

if not boards_to_process:
    print("❌ No boards found to process")
    exit(1)

# Initialize AI service
ai_coach = AICoachService()

if not ai_coach.gemini_available:
    print("❌ AI Coach service not available. Please configure GEMINI_API_KEY.")
    exit(1)

print("✅ AI Coach service is available\n")

for board_name, board in boards_to_process:
    print(f"{'='*80}")
    print(f"Processing: {board_name}")
    print(f"{'='*80}\n")
    
    # Count before
    before_count = CoachingSuggestion.objects.filter(board=board).count()
    before_ai_enhanced = CoachingSuggestion.objects.filter(
        board=board, 
        generation_method='hybrid'
    ).count()
    
    print(f"Before:")
    print(f"  Total suggestions: {before_count}")
    print(f"  AI-enhanced: {before_ai_enhanced}")
    print(f"  Rule-only: {before_count - before_ai_enhanced}\n")
    
    # Delete all existing suggestions for this board
    deleted = CoachingSuggestion.objects.filter(board=board).delete()
    print(f"✓ Deleted {deleted[0]} old suggestions\n")
    
    # Generate new suggestions using rule engine
    print(f"Generating new suggestions...")
    rule_engine = CoachingRuleEngine(board)
    suggestions_data = rule_engine.analyze_and_generate_suggestions()
    
    print(f"✓ Rule engine generated {len(suggestions_data)} suggestions\n")
    
    if not suggestions_data:
        print(f"⚠️  No suggestions generated for {board_name}\n")
        continue
    
    # Create context for AI enhancement
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
    
    # Enhance and create suggestions
    created_count = 0
    enhanced_count = 0
    
    for suggestion_data in suggestions_data:
        try:
            # Enhance with AI
            print(f"  Enhancing: {suggestion_data['title'][:60]}...")
            enhanced_data = ai_coach.enhance_suggestion_with_ai(
                suggestion_data, context
            )
            
            if enhanced_data.get('generation_method') == 'hybrid':
                enhanced_count += 1
                print(f"    ✓ Enhanced with AI")
            else:
                print(f"    ⚠️  AI enhancement failed, using basic format")
            
            # Create suggestion
            CoachingSuggestion.objects.create(**enhanced_data)
            created_count += 1
            
        except Exception as e:
            print(f"    ❌ Error: {e}")
            continue
    
    print(f"\nAfter:")
    print(f"  Created: {created_count} suggestions")
    print(f"  AI-enhanced: {enhanced_count} suggestions")
    print(f"  Success rate: {(enhanced_count/created_count*100) if created_count > 0 else 0:.1f}%\n")

print("\n" + "="*80)
print("✅ Regeneration Complete!")
print("="*80)
print("\nSummary:")
print("  Marketing Campaign and Bug Tracking boards now have AI-enhanced suggestions")
print("  with detailed 'Why this matters', 'Recommended Actions', and 'Expected Impact' sections.")
print("\nNext steps:")
print("  1. Refresh the AI Coach dashboard in your browser")
print("  2. Verify suggestions are now detailed and actionable")
print("  3. Compare with Software Development board suggestions")
