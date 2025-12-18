"""
Check coaching suggestions and feedback data to debug metrics
"""
import os
import sys
import django

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PrizmAI.settings')
django.setup()

from kanban.coach_models import CoachingSuggestion, CoachingFeedback
from kanban.models import Board

# Get demo boards
boards = Board.objects.filter(id__in=[18, 19, 20])

print("\n" + "="*80)
print("COACHING SUGGESTIONS AND FEEDBACK STATUS")
print("="*80)

for board in boards:
    print(f"\n{'='*80}")
    print(f"BOARD: {board.name} (ID: {board.id})")
    print(f"{'='*80}")
    
    suggestions = CoachingSuggestion.objects.filter(board=board)
    
    print(f"\nTotal Suggestions: {suggestions.count()}")
    
    for suggestion in suggestions:
        print(f"\n  Suggestion ID: {suggestion.id}")
        print(f"  Title: {suggestion.title}")
        print(f"  Type: {suggestion.suggestion_type}")
        print(f"  Status: {suggestion.status}")
        print(f"  was_helpful: {suggestion.was_helpful}")
        print(f"  action_taken: {suggestion.action_taken}")
        
        # Get feedback entries
        feedbacks = CoachingFeedback.objects.filter(suggestion=suggestion)
        print(f"  Feedback Entries: {feedbacks.count()}")
        
        for feedback in feedbacks:
            print(f"    - User: {feedback.user.username}")
            print(f"      Was Helpful: {feedback.was_helpful}")
            print(f"      Action Taken: {feedback.action_taken}")
            print(f"      Feedback Text: {feedback.feedback_text[:50] if feedback.feedback_text else 'None'}...")
            print(f"      Created: {feedback.created_at}")

# Calculate metrics manually
print(f"\n{'='*80}")
print("MANUAL METRICS CALCULATION")
print(f"{'='*80}")

for board in boards:
    print(f"\nBoard: {board.name}")
    suggestions = CoachingSuggestion.objects.filter(board=board)
    total = suggestions.count()
    
    with_helpful = suggestions.filter(was_helpful__isnull=False).count()
    helpful_true = suggestions.filter(was_helpful=True).count()
    
    acted_on = suggestions.filter(
        action_taken__in=['accepted', 'partially', 'modified']
    ).count()
    
    print(f"  Total Suggestions: {total}")
    print(f"  With was_helpful set: {with_helpful}")
    print(f"  was_helpful=True: {helpful_true}")
    print(f"  Acted On (accepted/partially/modified): {acted_on}")
    
    if total > 0:
        helpful_rate = (helpful_true / with_helpful * 100) if with_helpful > 0 else 0
        action_rate = (acted_on / total * 100)
        print(f"  Helpful Rate: {helpful_rate:.1f}%")
        print(f"  Action Rate: {action_rate:.1f}%")

print("\n" + "="*80)
