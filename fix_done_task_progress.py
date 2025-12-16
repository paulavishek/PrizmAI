"""
Script to update progress to 100% for all tasks in Done/Complete columns
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Column
from django.db import models

# Find all columns with "done" or "complete" in their name
done_columns = Column.objects.filter(
    models.Q(name__icontains='done') | models.Q(name__icontains='complete')
)

print(f"Found {done_columns.count()} Done/Complete columns:")
for col in done_columns:
    print(f"  - {col.name} (Board: {col.board.name})")

# Find all tasks in those columns with progress < 100%
tasks_to_update = Task.objects.filter(
    column__in=done_columns,
    progress__lt=100
)

print(f"\nFound {tasks_to_update.count()} tasks with progress < 100% in Done/Complete columns:")
for task in tasks_to_update:
    print(f"  - Task #{task.id}: {task.title} (Current progress: {task.progress}%)")
    print(f"    Column: {task.column.name}, Board: {task.column.board.name}")

# Update all tasks to 100% progress
if tasks_to_update.exists():
    confirm = input("\nUpdate all these tasks to 100% progress? (yes/no): ")
    if confirm.lower() == 'yes':
        updated_count = 0
        for task in tasks_to_update:
            task.progress = 100
            task.save()
            updated_count += 1
            print(f"  ✓ Updated Task #{task.id}: {task.title}")
        
        print(f"\n✅ Successfully updated {updated_count} tasks to 100% progress!")
    else:
        print("\n❌ Update cancelled.")
else:
    print("\n✅ All tasks in Done/Complete columns already have 100% progress!")
