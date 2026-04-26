import django, os, json
os.environ['DJANGO_SETTINGS_MODULE'] = 'kanban_board.settings'
django.setup()

from kanban.coach_models import CoachingSuggestion, PMMetrics

# Get suggestions for board 44 (Software Development)
suggestions = CoachingSuggestion.objects.filter(board_id=44, status='active').order_by('-created_at')
print(f"Total active suggestions: {suggestions.count()}")
print("=" * 80)

for s in suggestions:
    print(f"ID={s.id} | Type={s.suggestion_type} | Severity={s.severity}")
    print(f"  Title: {s.title}")
    print(f"  Message: {s.message[:150]}")
    print(f"  Confidence: {s.confidence_score} | Method: {s.generation_method}")
    print(f"  Created: {s.created_at}")
    if s.recommended_actions:
        actions = json.loads(s.recommended_actions) if isinstance(s.recommended_actions, str) else s.recommended_actions
        print(f"  Actions ({len(actions)}):")
        for a in actions:
            if isinstance(a, dict):
                title = a.get('action', a.get('title', str(a)[:80]))
                print(f"    - {title}")
            else:
                print(f"    - {str(a)[:80]}")
    if s.expected_impact:
        print(f"  Impact: {s.expected_impact[:150]}")
    if s.reasoning:
        print(f"  Reasoning: {s.reasoning[:150]}")
    print()

# Check metrics
print("=" * 80)
print("PM Metrics for board 44:")
metrics = PMMetrics.objects.filter(board_id=44).order_by('-period_end').first()
if metrics:
    print(f"  Suggestions received: {metrics.suggestions_received}")
    print(f"  Suggestions acted on: {metrics.suggestions_acted_on}")
    print(f"  Coaching effectiveness: {metrics.coaching_effectiveness_score}")
    print(f"  Period: {metrics.period_start} to {metrics.period_end}")
else:
    print("  No metrics found")
