#!/usr/bin/env python
"""Find tasks without phase assignments and potential milestones"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Board

# Get demo boards
demo_boards = Board.objects.filter(is_official_demo_board=True)

print("Checking all tasks in demo boards...\n")

for board in demo_boards:
    print(f"Board: {board.name}")
    tasks = Task.objects.filter(column__board=board)
    print(f"  Total tasks: {tasks.count()}")
    
    # Tasks with no phase
    no_phase = tasks.filter(phase__isnull=True)
    if no_phase.exists():
        print(f"  Tasks with no phase: {no_phase.count()}")
        for task in no_phase[:10]:
            print(f"    - ID: {task.id}, Title: {task.title}, Start: {task.start_date}, Due: {task.due_date}")
    
    # Tasks with each phase
    for phase_num in [1, 2, 3]:
        phase_tasks = tasks.filter(phase=phase_num)
        if phase_tasks.exists():
            print(f"  Phase {phase_num}: {phase_tasks.count()} tasks")
    
    # Look for milestone-like tasks (any title with milestone keywords)
    milestone_like = tasks.filter(
        title__iregex=r'.*(complete|launch|milestone|kickoff|ready|approved|signed|delivery).*'
    )
    if milestone_like.exists():
        print(f"\n  Milestone-like tasks ({milestone_like.count()}):")
        for task in milestone_like:
            print(f"    - ID: {task.id}, Phase: {task.phase}, Title: {task.title}")
    
    print()
