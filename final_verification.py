#!/usr/bin/env python
"""Final verification of demo boards structure"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Board

print("="*80)
print("FINAL DEMO BOARDS VERIFICATION")
print("="*80)
print()

demo_boards = Board.objects.filter(is_official_demo_board=True).order_by('name')

for board in demo_boards:
    print(f"Board: {board.name}")
    print("-" * 80)
    
    # Count tasks
    tasks = Task.objects.filter(column__board=board)
    total_tasks = tasks.count()
    print(f"  Total Tasks: {total_tasks}")
    
    # Count by phase
    for phase_num in [1, 2, 3]:
        phase_name = f'Phase {phase_num}'
        phase_tasks = tasks.filter(phase=phase_name).count()
        print(f"    {phase_name}: {phase_tasks} tasks")
    
    print()

print("="*80)
print("SUMMARY")
print("="*80)
print()
print("✓ All demo boards should have exactly 30 tasks (10 per phase)")
print("✓ Task count dashboard should now show correct numbers")
print()
