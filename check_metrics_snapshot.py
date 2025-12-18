#!/usr/bin/env python
"""
Check what's in the metrics_snapshot field
"""
from kanban.coach_models import CoachingSuggestion

suggestions = CoachingSuggestion.objects.filter(id__in=[3, 4, 5])

print("\n" + "="*80)
print("METRICS SNAPSHOT DATA")
print("="*80)

for suggestion in suggestions:
    print(f"\nSuggestion #{suggestion.id}: {suggestion.title}")
    print(f"  metrics_snapshot: {suggestion.metrics_snapshot}")
    print(f"  Type: {type(suggestion.metrics_snapshot)}")
    if suggestion.metrics_snapshot:
        print(f"  Items: {suggestion.metrics_snapshot.items()}")
    else:
        print("  NO DATA - metrics_snapshot is empty or None")

print("\n" + "="*80)
