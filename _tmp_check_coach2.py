import django, os, json
os.environ['DJANGO_SETTINGS_MODULE'] = 'kanban_board.settings'
django.setup()

from kanban.coach_models import CoachingSuggestion, CoachingFeedback
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg

start_date = timezone.now() - timedelta(days=30)

# All suggestions in last 30 days
all_suggestions = CoachingSuggestion.objects.filter(board_id=44, created_at__gte=start_date)
print(f"Total suggestions (30d): {all_suggestions.count()}")
print(f"Active: {all_suggestions.filter(status='active').count()}")
print(f"Acknowledged: {all_suggestions.filter(status='acknowledged').count()}")
print(f"Resolved: {all_suggestions.filter(status='resolved').count()}")
print(f"Dismissed: {all_suggestions.filter(status='dismissed').count()}")
print(f"Expired: {all_suggestions.filter(status='expired').count()}")

# Feedback counts
with_feedback = all_suggestions.filter(was_helpful__isnull=False)
print(f"\nWith feedback: {with_feedback.count()}")
helpful = all_suggestions.filter(was_helpful=True)
print(f"Helpful: {helpful.count()}")
acted_on = all_suggestions.filter(action_taken__in=['accepted', 'partially', 'modified'])
print(f"Acted on: {acted_on.count()}")

# Detailed feedback entries
feedbacks = CoachingFeedback.objects.filter(suggestion__board_id=44)
print(f"\nFeedback entries: {feedbacks.count()}")
for f in feedbacks:
    print(f"  Suggestion {f.suggestion_id}: helpful={f.was_helpful}, relevance={f.relevance_score}, action={f.action_taken}")

# Calculate rates
total = all_suggestions.count()
action_rate = (acted_on.count() / total * 100) if total > 0 else 0
feedback_count = with_feedback.count()
helpful_rate = (helpful.count() / feedback_count * 100) if feedback_count > 0 else 0
avg_relevance = feedbacks.aggregate(Avg('relevance_score'))['relevance_score__avg'] or 0

effectiveness = (helpful_rate * 0.4) + (action_rate * 0.4) + (avg_relevance / 5 * 100 * 0.2)
print(f"\nCalculated metrics:")
print(f"  Action rate: {action_rate:.1f}%")
print(f"  Helpful rate: {helpful_rate:.1f}%")
print(f"  Avg relevance: {avg_relevance}")
print(f"  Effectiveness: {effectiveness:.1f}%")

# Check for duplicate suggestions
print("\n\nDUPLICATE CHECK:")
from collections import Counter
titles = list(all_suggestions.filter(status='active').values_list('title', flat=True))
for title, count in Counter(titles).items():
    if count > 1:
        dupes = all_suggestions.filter(title=title, status='active')
        print(f"  DUPLICATE: '{title}' x{count}")
        for d in dupes:
            print(f"    ID={d.id}, created={d.created_at}")
