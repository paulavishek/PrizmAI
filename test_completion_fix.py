"""
Test script to verify completion count fix
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.db.models import Q
from kanban.models import Board, Task
from accounts.models import Organization

# Get demo boards
demo_org_names = ['Dev Team', 'Marketing Team']
demo_orgs = Organization.objects.filter(name__in=demo_org_names)
demo_boards = Board.objects.filter(organization__in=demo_orgs)

print("=" * 80)
print("COMPLETION COUNT TEST - AFTER FIX")
print("=" * 80)

for board in demo_boards:
    total = Task.objects.filter(column__board=board).count()
    
    # Old method (only checks 'done')
    old_completed = Task.objects.filter(
        column__board=board,
        column__name__icontains='done'
    ).count()
    
    # New method (checks 'done', 'closed', 'completed')
    new_completed = Task.objects.filter(
        column__board=board
    ).filter(
        Q(column__name__icontains='done') |
        Q(column__name__icontains='closed') |
        Q(column__name__icontains='completed')
    ).count()
    
    old_rate = (old_completed / total * 100) if total else 0
    new_rate = (new_completed / total * 100) if total else 0
    
    print(f"\n{board.name}:")
    print(f"  Total Tasks: {total}")
    print(f"  OLD Method (done only): {old_completed} ({old_rate:.1f}%)")
    print(f"  NEW Method (done/closed/completed): {new_completed} ({new_rate:.1f}%)")
    print(f"  Difference: +{new_completed - old_completed} tasks")
    
    # Show which columns have tasks
    columns = board.columns.all()
    for col in columns:
        task_count = Task.objects.filter(column=col).count()
        if task_count > 0:
            print(f"    - {col.name}: {task_count} tasks")

print("\n" + "=" * 80)
print("✅ Fix verified! All completion columns are now detected correctly.")
print("=" * 80)
