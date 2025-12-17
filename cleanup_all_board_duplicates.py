"""
Clean up duplicate tasks across all demo boards
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task

# Duplicates to delete (older versions without proper dependencies)
# Based on the analysis, we keep the ones with better dates or dependencies

duplicates_to_delete = [
    # Bug Tracking duplicates
    1800,  # Fix bug in table (Nov 30 - older)
    1802,  # Optimize authentication performance (Dec 10 - older)
    
    # Marketing Campaign duplicates  
    1823,  # Fix bug in login (Nov 18 - older)
    1826,  # Refactor analytics module (Nov 3 - oldest)
]

print("Cleaning up duplicate tasks across all boards...")
print("=" * 80)

deleted_count = 0
for task_id in duplicates_to_delete:
    try:
        task = Task.objects.get(id=task_id)
        board_name = task.column.board.name
        print(f"\n📋 {board_name}")
        print(f"   Deleting: {task.title} (ID: {task.id})")
        print(f"   Date: {task.start_date} → {task.due_date.date() if task.due_date else 'None'}")
        print(f"   Dependencies: {task.dependencies.count()}")
        task.delete()
        deleted_count += 1
    except Task.DoesNotExist:
        print(f"\n⚠️  Task {task_id} not found (may have been deleted already)")

print("\n" + "=" * 80)
print(f"✅ Removed {deleted_count} duplicate tasks!")
print("\nRun fix_gantt_demo_data again to add dependencies to remaining tasks.")
