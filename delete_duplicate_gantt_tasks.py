"""
Delete duplicate tasks from Software Project board
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task

# IDs of duplicate tasks to delete (the older ones without dependencies)
duplicate_task_ids = [1776, 1780]  

print("Deleting duplicate tasks...")
for task_id in duplicate_task_ids:
    try:
        task = Task.objects.get(id=task_id)
        print(f"  Deleting: {task.title} (ID: {task.id}, Date: {task.start_date})")
        task.delete()
    except Task.DoesNotExist:
        print(f"  Task {task_id} not found")

print("\n✅ Duplicates removed!")
