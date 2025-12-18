#!/usr/bin/env python
"""
Fix action_taken values in existing suggestions
Change 'implemented' to 'accepted' to match model choices
"""
from kanban.coach_models import CoachingSuggestion, CoachingFeedback

print("\n" + "="*80)
print("FIXING ACTION_TAKEN VALUES")
print("="*80)

# Fix CoachingSuggestion records
suggestions_fixed = 0
suggestions = CoachingSuggestion.objects.filter(action_taken='implemented')
for suggestion in suggestions:
    print(f"Fixing Suggestion #{suggestion.id}: {suggestion.title}")
    print(f"  Old action_taken: {suggestion.action_taken}")
    suggestion.action_taken = 'accepted'
    suggestion.save()
    print(f"  New action_taken: {suggestion.action_taken}")
    suggestions_fixed += 1

# Fix CoachingFeedback records
feedback_fixed = 0
feedbacks = CoachingFeedback.objects.filter(action_taken='implemented')
for feedback in feedbacks:
    print(f"\nFixing Feedback for Suggestion #{feedback.suggestion.id}")
    print(f"  Old action_taken: {feedback.action_taken}")
    feedback.action_taken = 'accepted'
    feedback.save()
    print(f"  New action_taken: {feedback.action_taken}")
    feedback_fixed += 1

print(f"\n{'='*80}")
print(f"SUMMARY")
print(f"{'='*80}")
print(f"Fixed {suggestions_fixed} CoachingSuggestion records")
print(f"Fixed {feedback_fixed} CoachingFeedback records")

# Verify the fix
from kanban.models import Board
board = Board.objects.get(id=18)
suggestions = CoachingSuggestion.objects.filter(board=board)
total = suggestions.count()
acted_on = suggestions.filter(
    action_taken__in=['accepted', 'partially', 'modified']
).count()

print(f"\nVerification for Software Project board:")
print(f"  Total suggestions: {total}")
print(f"  Acted on: {acted_on}")
print(f"  Action Rate: {(acted_on/total*100):.1f}%")

print("\nDone!")
