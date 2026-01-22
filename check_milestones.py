#!/usr/bin/env python
"""Check for Milestone records in demo boards"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Board, Milestone

# Get demo boards
demo_boards = Board.objects.filter(is_official_demo_board=True)

print("Checking tasks and milestones in demo boards...\n")

for board in demo_boards:
    print(f"Board: {board.name}")
    
    # Count tasks
    tasks = Task.objects.filter(column__board=board)
    print(f"  Tasks: {tasks.count()}")
    
    # Count milestones
    milestones = Milestone.objects.filter(board=board)
    print(f"  Milestones: {milestones.count()}")
    
    if milestones.exists():
        print(f"\n  Milestone details:")
        for ms in milestones:
            print(f"    - ID: {ms.id}, Title: {ms.title}")
            print(f"      Target Date: {ms.target_date}, Type: {ms.milestone_type}")
            print(f"      Completed: {ms.is_completed}")
            # Check related tasks
            related_tasks_count = ms.related_tasks.count()
            print(f"      Related Tasks: {related_tasks_count}")
    
    print()
