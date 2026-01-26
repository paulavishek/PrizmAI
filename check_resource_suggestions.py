#!/usr/bin/env python
"""
Check and clean up resource leveling suggestions
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db.models import Q
from kanban.models import Board, Organization
from kanban.resource_leveling_models import ResourceLevelingSuggestion

User = get_user_model()

print("="*70)
print("CHECKING AI RESOURCE OPTIMIZATION SUGGESTIONS")
print("="*70)

# Get demo organization
demo_org = Organization.objects.filter(name='Demo - Acme Corporation').first()
if not demo_org:
    print("❌ Demo organization not found")
    exit(1)

# Get demo boards
demo_boards = Board.objects.filter(organization=demo_org, is_official_demo_board=True)

# Get demo_admin_solo
demo_admin = User.objects.filter(username='demo_admin_solo').first()

if demo_admin:
    print(f"\n🔍 Checking for suggestions involving demo_admin_solo...")
    
    # Check suggestions where demo_admin is suggested assignee
    suggestions_to_demo_admin = ResourceLevelingSuggestion.objects.filter(
        task__column__board__in=demo_boards,
        suggested_assignee=demo_admin
    )
    
    # Check suggestions where demo_admin is current assignee
    suggestions_from_demo_admin = ResourceLevelingSuggestion.objects.filter(
        task__column__board__in=demo_boards,
        current_assignee=demo_admin
    )
    
    total_bad_suggestions = suggestions_to_demo_admin.count() + suggestions_from_demo_admin.count()
    
    if total_bad_suggestions > 0:
        print(f"\n⚠️  Found {total_bad_suggestions} suggestions involving demo_admin_solo:")
        print(f"   - Suggesting TO demo_admin_solo: {suggestions_to_demo_admin.count()}")
        print(f"   - Suggesting FROM demo_admin_solo: {suggestions_from_demo_admin.count()}")
        
        print(f"\n🗑️  Deleting these suggestions...")
        deleted_count = ResourceLevelingSuggestion.objects.filter(
            task__column__board__in=demo_boards
        ).filter(
            Q(suggested_assignee=demo_admin) | Q(current_assignee=demo_admin)
        ).delete()[0]
        
        print(f"   ✅ Deleted {deleted_count} suggestions")
    else:
        print("   ✅ No suggestions involving demo_admin_solo found")
else:
    print("\n✅ demo_admin_solo user not found (already removed)")

# Check all suggestions for demo boards
print(f"\n📊 Current AI suggestions for demo boards:")

for board in demo_boards:
    suggestions = ResourceLevelingSuggestion.objects.filter(
        task__column__board=board
    ).select_related('suggested_assignee', 'current_assignee', 'task')
    
    print(f"\n{board.name}:")
    if suggestions.exists():
        for sug in suggestions[:5]:  # Show first 5
            from_user = sug.current_assignee.get_full_name() if sug.current_assignee else "unassigned"
            to_user = sug.suggested_assignee.get_full_name()
            print(f"  - Move '{sug.task.title[:40]}...' from {from_user} to {to_user}")
    else:
        print(f"  No suggestions currently")

print("\n" + "="*70)
print("✅ AI SUGGESTIONS CHECK COMPLETE")
print("="*70)
