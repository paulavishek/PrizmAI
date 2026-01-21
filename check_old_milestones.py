#!/usr/bin/env python
"""Check for old milestone records in the database"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Board

# Get demo boards
demo_boards = Board.objects.filter(is_official_demo_board=True)

print("Checking for old milestone records...\n")

for board in demo_boards:
    print(f"Board: {board.name}")
    tasks = Task.objects.filter(column__board=board)
    
    # Look for tasks with milestone-like names or tasks without start dates
    milestone_candidates = tasks.filter(
        title__icontains='milestone'
    ) | tasks.filter(
        title__icontains='kickoff'
    ) | tasks.filter(
        title__icontains='complete',
        start_date__isnull=True
    ) | tasks.filter(
        title__icontains='launch',
        start_date__isnull=True
    )
    
    milestone_candidates = milestone_candidates.distinct()
    
    if milestone_candidates.exists():
        print(f"  Found {milestone_candidates.count()} potential old milestone records:")
        for task in milestone_candidates:
            print(f"    - ID: {task.id}, Title: {task.title}")
            print(f"      Start: {task.start_date}, Due: {task.due_date}")
    else:
        print("  No old milestones found")
    print()

# Also check for any tasks without start dates across all boards
tasks_without_start = Task.objects.filter(
    start_date__isnull=True,
    due_date__isnull=False
)

if tasks_without_start.exists():
    print(f"\nFound {tasks_without_start.count()} tasks with due_date but no start_date:")
    for task in tasks_without_start[:20]:
        print(f"  - ID: {task.id}, Board: {task.column.board.name}, Title: {task.title}")
