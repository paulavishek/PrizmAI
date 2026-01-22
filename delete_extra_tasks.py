#!/usr/bin/env python
"""Delete extra milestone-like tasks that should not be in the demo boards"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task

# IDs of tasks to delete (the extra milestone-like tasks)
task_ids_to_delete = [
    # Marketing Campaign extras
    4512,  # Content Review (Phase 2)
    4525,  # Campaign Completion (Phase 3)
    
    # Bug Tracking extras
    4536,  # Critical Bugs Fixed (Phase 1)
    4537,  # Security Audit Passed (Phase 1)
    4548,  # High Priority Fixed (Phase 2)
    4549,  # Performance Targets Met (Phase 2)
    4560,  # All Bugs Resolved (Phase 3)
    4561,  # QA Sign-off (Phase 3)
]

print("Extra milestone-like tasks to delete:\n")
print("="*80)

tasks_to_delete = Task.objects.filter(id__in=task_ids_to_delete)

if not tasks_to_delete.exists():
    print("No tasks found with these IDs!")
else:
    for task in tasks_to_delete:
        print(f"ID: {task.id:4d} | Board: {task.column.board.name:25s} | Phase: {task.phase} | Title: {task.title}")

    print(f"\nTotal: {tasks_to_delete.count()} tasks")
    print("="*80)
    
    confirm = input("\nDelete these tasks? (yes/no): ")
    if confirm.lower() == 'yes':
        count = tasks_to_delete.count()
        tasks_to_delete.delete()
        print(f"\n✓ Deleted {count} extra tasks!")
        print("\nVerifying counts:")
        from kanban.models import Board
        demo_boards = Board.objects.filter(is_official_demo_board=True).order_by('name')
        for board in demo_boards:
            task_count = Task.objects.filter(column__board=board).count()
            print(f"  {board.name}: {task_count} tasks")
    else:
        print("\nCancelled - no tasks deleted")
