#!/usr/bin/env python
"""Delete all old milestone records across all phases"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task

# Find tasks with milestone-like titles
# These are typical milestone names from the old demo data
milestone_tasks = Task.objects.filter(
    title__iregex=r'.*(kickoff|foundation complete|mvp.*complete|beta ready|strategy approved|planning complete|assets ready|launch preparation|production launch|campaign launch).*'
)

milestone_tasks = milestone_tasks.distinct()

if milestone_tasks.exists():
    print(f"Found {milestone_tasks.count()} old milestone records to delete:\n")
    for task in milestone_tasks:
        print(f"  - ID: {task.id}, Board: {task.column.board.name}, Phase: {task.phase}")
        print(f"    Title: {task.title}")
    
    confirm = input("\nDelete these tasks? (yes/no): ")
    if confirm.lower() == 'yes':
        count = milestone_tasks.count()
        milestone_tasks.delete()
        print(f"\nDeleted {count} old milestone records!")
    else:
        print("\nCancelled - no tasks deleted")
else:
    print("No old milestone records found to delete")
