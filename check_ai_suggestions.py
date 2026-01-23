"""
Check AI Coach suggestions in database
"""
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.coach_models import CoachingSuggestion
from django.db.models import Count

print("\n=== Generation Methods Count ===")
methods = CoachingSuggestion.objects.values('generation_method').annotate(count=Count('id'))
for m in methods:
    print(f"{m['generation_method']:15} : {m['count']}")

print("\n=== Software Development Board Suggestions ===")
suggestions = CoachingSuggestion.objects.filter(
    board__name='Software Development'
).order_by('-created_at').values(
    'title', 'generation_method', 'ai_model_used', 'reasoning'
)[:10]

for s in suggestions:
    print(f"\nTitle: {s['title']}")
    print(f"  Method: {s['generation_method']}")
    print(f"  AI Model: {s['ai_model_used']}")
    print(f"  Has Reasoning: {'Yes' if s['reasoning'] else 'No'}")
    if s['reasoning']:
        print(f"  Reasoning length: {len(s['reasoning'])} chars")
