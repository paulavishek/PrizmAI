#!/usr/bin/env python
"""List all tasks in Marketing Campaign and Bug Tracking boards to identify extras"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Board

# Get the two problem boards
marketing = Board.objects.filter(name='Marketing Campaign', is_official_demo_board=True).first()
bug_tracking = Board.objects.filter(name='Bug Tracking', is_official_demo_board=True).first()

if marketing:
    print(f"Marketing Campaign Board - {Task.objects.filter(column__board=marketing).count()} tasks\n")
    print("="*80)
    
    # Group by phase
    for phase_num in [1, 2, 3]:
        phase_tasks = Task.objects.filter(column__board=marketing, phase=f'Phase {phase_num}').order_by('position')
        print(f"\nPhase {phase_num}: {phase_tasks.count()} tasks")
        for i, task in enumerate(phase_tasks, 1):
            print(f"  {i}. ID:{task.id:4d} | {task.title[:60]}")
    
    # Check for tasks without phase
    no_phase = Task.objects.filter(column__board=marketing, phase__isnull=True)
    if no_phase.exists():
        print(f"\n\nNo Phase: {no_phase.count()} tasks")
        for task in no_phase:
            print(f"  ID:{task.id:4d} | {task.title}")

print("\n\n" + "="*80)
print("="*80)

if bug_tracking:
    print(f"\nBug Tracking Board - {Task.objects.filter(column__board=bug_tracking).count()} tasks\n")
    print("="*80)
    
    # Group by phase
    for phase_num in [1, 2, 3]:
        phase_tasks = Task.objects.filter(column__board=bug_tracking, phase=f'Phase {phase_num}').order_by('position')
        print(f"\nPhase {phase_num}: {phase_tasks.count()} tasks")
        for i, task in enumerate(phase_tasks, 1):
            print(f"  {i}. ID:{task.id:4d} | {task.title[:60]}")
    
    # Check for tasks without phase
    no_phase = Task.objects.filter(column__board=bug_tracking, phase__isnull=True)
    if no_phase.exists():
        print(f"\n\nNo Phase: {no_phase.count()} tasks")
        for task in no_phase:
            print(f"  ID:{task.id:4d} | {task.title}")
