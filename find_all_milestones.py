#!/usr/bin/env python
"""Find all old milestone records across all phases"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Board

# Get demo boards
demo_boards = Board.objects.filter(is_official_demo_board=True)

print("Checking for all old milestone records...\n")

for board in demo_boards:
    print(f"Board: {board.name}")
    tasks = Task.objects.filter(column__board=board)
    
    # Check each phase
    for phase_num in [1, 2, 3]:
        phase_tasks = tasks.filter(phase=phase_num)
        print(f"\n  Phase {phase_num}: {phase_tasks.count()} total tasks")
        
        # Look for tasks with typical milestone indicators
        # Often milestones have very short titles or end with "Complete", "Launch", etc.
        suspicious = []
        for task in phase_tasks:
            # Check for milestone-like patterns
            title_lower = task.title.lower()
            if any(word in title_lower for word in ['complete', 'launch', 'milestone', 'kickoff', 'ready', 'approved', 'signed']):
                suspicious.append(task)
            # Or tasks without start_date
            elif task.start_date is None and task.due_date is not None:
                suspicious.append(task)
        
        if suspicious:
            print(f"    Found {len(suspicious)} potential milestones:")
            for task in suspicious:
                print(f"      - ID: {task.id}, Title: {task.title}")
                print(f"        Start: {task.start_date}, Due: {task.due_date}")
    print()
