import django, os, json
os.environ['DJANGO_SETTINGS_MODULE'] = 'kanban_board.settings'
django.setup()

from kanban.coach_models import CoachingSuggestion, CoachingFeedback, CoachingInsight
from kanban.utils.feedback_learning import FeedbackLearningSystem
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Avg
from django.contrib.auth import get_user_model

User = get_user_model()
board_id = 44

# Simulate what the analytics view does for 30 days
days = 30
start_date = timezone.now() - timedelta(days=days)

suggestions = CoachingSuggestion.objects.filter(board_id=board_id, created_at__gte=start_date)

total = suggestions.count()
print(f"Total suggestions (30d): {total}")

by_type = suggestions.values('suggestion_type').annotate(count=Count('id')).order_by('-count')
print("\nBy type:")
for bt in by_type:
    print(f"  {bt['suggestion_type']}: {bt['count']}")

by_severity = suggestions.values('severity').annotate(count=Count('id'))
print("\nBy severity:")
for bs in by_severity:
    print(f"  {bs['severity']}: {bs['count']}")

by_status = suggestions.values('status').annotate(count=Count('id'))
print("\nBy status:")
for bst in by_status:
    print(f"  {bst['status']}: {bst['count']}")

helpful_count = suggestions.filter(was_helpful=True).count()
acted_on = suggestions.filter(action_taken__in=['accepted', 'partially', 'modified']).count()
print(f"\nHelpful: {helpful_count}")
print(f"Acted on: {acted_on}")

# Calculate effectiveness using the same system as the view
# Need to find any user that accessed this board
user = User.objects.first()
learning_system = FeedbackLearningSystem()
effectiveness = learning_system.calculate_pm_coaching_effectiveness(
    suggestions.first().board, user, days
)
print(f"\nEffectiveness metrics:")
for k, v in effectiveness.items():
    print(f"  {k}: {v}")

# Check insights
insights = CoachingInsight.objects.filter(is_active=True).order_by('-confidence_score')[:10]
print(f"\nActive insights: {insights.count()}")
for i in insights:
    print(f"  {i.insight_type}: observed={i.observation_count}, conf={i.confidence_score}")
