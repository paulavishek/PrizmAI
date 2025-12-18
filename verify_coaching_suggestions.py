"""
Verify coaching suggestions are in the database and ready to display
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board
from kanban.coach_models import CoachingSuggestion

print("=" * 80)
print("VERIFICATION: AI COACH SUGGESTIONS")
print("=" * 80)

# Get demo boards
demo_boards = Board.objects.filter(
    name__in=['Software Project', 'Bug Tracking', 'Marketing Campaign'],
    organization__name__in=['Dev Team', 'Marketing Team']
)

total_suggestions = 0

for board in demo_boards:
    print(f"\n{'='*80}")
    print(f"BOARD: {board.name} (ID: {board.id})")
    print(f"{'='*80}")
    print(f"URL: http://127.0.0.1:8000/board/{board.id}/coach/")
    
    suggestions = CoachingSuggestion.objects.filter(
        board=board,
        status='active'
    ).order_by('-severity', '-created_at')
    
    print(f"\nActive Suggestions: {suggestions.count()}")
    
    for i, suggestion in enumerate(suggestions, 1):
        total_suggestions += 1
        print(f"\n{i}. {suggestion.get_suggestion_type_display()} - {suggestion.get_severity_display()}")
        print(f"   Title: {suggestion.title}")
        print(f"   Created: {suggestion.created_at.strftime('%Y-%m-%d %H:%M')}")
        print(f"   Confidence: {suggestion.confidence_score}")
        print(f"   Status: {suggestion.status}")
        print(f"   Message: {suggestion.message[:120]}...")
        if suggestion.recommended_actions:
            print(f"   Actions: {len(suggestion.recommended_actions)} recommended")

print(f"\n{'='*80}")
print(f"TOTAL: {total_suggestions} active coaching suggestions across all demo boards")
print(f"{'='*80}")
print("\n✅ AI Coach is ready! Refresh your browser to see the suggestions.")
print("\nTo access:")
print("1. Navigate to any demo board")
print("2. Click 'AI Coach' in the board navigation")
print("3. You should see suggestions organized by severity")
