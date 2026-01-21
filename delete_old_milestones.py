#!/usr/bin/env python
"""Delete old milestone records from the database"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task

# Find and delete tasks with milestone-like names
milestone_keywords = ['milestone', 'kickoff', 'complete launch']

tasks_to_delete = Task.objects.filter(
    title__icontains='milestone'
) | Task.objects.filter(
    title__icontains='kickoff'
) | Task.objects.filter(
    title__icontains='foundation complete'
) | Task.objects.filter(
    title__icontains='project launch'
)

tasks_to_delete = tasks_to_delete.distinct()

if tasks_to_delete.exists():
    print(f"Found {tasks_to_delete.count()} old milestone records to delete:")
    for task in tasks_to_delete:
        print(f"  - ID: {task.id}, Title: {task.title}, Board: {task.column.board.name}")
    
    confirm = input("\nDelete these tasks? (yes/no): ")
    if confirm.lower() == 'yes':
        count = tasks_to_delete.count()
        tasks_to_delete.delete()
        print(f"\nDeleted {count} old milestone records!")
    else:
        print("\nCancelled - no tasks deleted")
else:
    print("No old milestone records found to delete")
