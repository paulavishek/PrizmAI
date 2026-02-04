"""
Check for duplicate action items
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.retrospective_models import RetrospectiveActionItem
from django.db.models import Count

# Find duplicate action items (same retrospective + same title)
duplicates = RetrospectiveActionItem.objects.values(
    'retrospective_id', 'title'
).annotate(
    count=Count('id')
).filter(count__gt=1).order_by('-count')

print(f'Found {len(duplicates)} duplicate groups:\n')

for dup in duplicates:
    print(f"{dup['count']} copies of \"{dup['title']}\" in retrospective {dup['retrospective_id']}")
    
    # Get the actual items
    items = RetrospectiveActionItem.objects.filter(
        retrospective_id=dup['retrospective_id'],
        title=dup['title']
    ).order_by('id')
    
    print(f"  IDs: {[item.id for item in items]}")
    print(f"  Board: {items[0].board.name}")
    print(f"  Assigned to: {items[0].assigned_to}")
    print()
