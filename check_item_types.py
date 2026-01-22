#!/usr/bin/env python
"""Check item_type field for all tasks in demo boards"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Board

# Get demo boards
demo_boards = Board.objects.filter(is_official_demo_board=True)

print("Checking item_type field for all tasks in demo boards...\n")

for board in demo_boards:
    print(f"Board: {board.name}")
    tasks = Task.objects.filter(column__board=board)
    
    # Count by item_type
    total = tasks.count()
    actual_tasks = tasks.filter(item_type='task').count()
    milestones = tasks.filter(item_type='milestone').count()
    other = total - actual_tasks - milestones
    
    print(f"  Total items: {total}")
    print(f"  Tasks (item_type='task'): {actual_tasks}")
    print(f"  Milestones (item_type='milestone'): {milestones}")
    if other > 0:
        print(f"  Other/Unknown: {other}")
    
    # List all milestones if any
    if milestones > 0:
        print(f"\n  Milestone items found:")
        milestone_items = tasks.filter(item_type='milestone')
        for item in milestone_items:
            print(f"    - ID: {item.id}, Phase: {item.phase}, Title: {item.title}")
    
    print()
