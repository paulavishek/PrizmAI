"""
Script to fix Gantt chart demo data for impressive visualization.
This spreads out task dates to avoid stacking and ensures proper dependencies.
"""

import os
import sys

# Add the project root to the path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')

import django
django.setup()

from datetime import datetime, timedelta
from django.utils import timezone
from kanban.models import Board, Task, Column, Organization

def fix_gantt_dates():
    """Fix task dates to create an impressive Gantt chart visualization."""
    
    print("=" * 70)
    print("🎨 Fixing Gantt Chart Dates for Impressive Visualization")
    print("=" * 70)
    
    try:
        org = Organization.objects.get(name='Demo - Acme Corporation')
    except Organization.DoesNotExist:
        print("❌ Demo - Acme Corporation not found!")
        return
    
    # Get all demo boards
    boards = Board.objects.filter(organization=org)
    
    for board in boards:
        print(f"\n📊 Processing Board: {board.name}")
        
        # Get all tasks with dates
        tasks = Task.objects.filter(
            column__board=board,
            start_date__isnull=False,
            due_date__isnull=False
        ).select_related('column').order_by('id')
        
        print(f"   Found {tasks.count()} tasks with dates")
        
        if tasks.count() == 0:
            print("   No tasks to update!")
            continue
        
        task_list = list(tasks)
        
        # Update dates for this board
        update_board_dates(board.name, task_list)
        
        # Fix dependencies
        fix_dependencies(board, task_list)
    
    print("\n" + "=" * 70)
    print("✅ All Gantt Chart Data Fixed Successfully!")
    print("=" * 70)


def update_board_dates(board_name, task_list):
    """Update task dates for a specific board."""
    
    base_date = timezone.now().date()
    total_tasks = len(task_list)
    
    print(f"\n📅 Updating {total_tasks} task dates...")
    
    # Different configurations for different boards
    if board_name == 'Software Development':
        phase_configs = [
            {'name': 'Foundation', 'start_offset': -42, 'task_gap': 3, 'duration_range': (4, 8)},
            {'name': 'Development', 'start_offset': -21, 'task_gap': 2, 'duration_range': (5, 14)},
            {'name': 'Testing', 'start_offset': 7, 'task_gap': 2, 'duration_range': (3, 7)},
            {'name': 'Deployment', 'start_offset': 28, 'task_gap': 3, 'duration_range': (4, 10)},
        ]
        phase_ratios = [0.25, 0.35, 0.25, 0.15]
    elif board_name == 'Bug Tracking':
        phase_configs = [
            {'name': 'Critical', 'start_offset': -21, 'task_gap': 2, 'duration_range': (2, 4)},
            {'name': 'High Priority', 'start_offset': -10, 'task_gap': 2, 'duration_range': (3, 5)},
            {'name': 'Medium', 'start_offset': 3, 'task_gap': 2, 'duration_range': (2, 5)},
            {'name': 'Low', 'start_offset': 14, 'task_gap': 3, 'duration_range': (3, 6)},
        ]
        phase_ratios = [0.20, 0.30, 0.30, 0.20]
    elif board_name == 'Marketing Campaign':
        phase_configs = [
            {'name': 'Planning', 'start_offset': -35, 'task_gap': 3, 'duration_range': (5, 10)},
            {'name': 'Content Creation', 'start_offset': -14, 'task_gap': 2, 'duration_range': (4, 8)},
            {'name': 'Launch', 'start_offset': 7, 'task_gap': 2, 'duration_range': (3, 7)},
            {'name': 'Analysis', 'start_offset': 21, 'task_gap': 3, 'duration_range': (4, 8)},
        ]
        phase_ratios = [0.25, 0.35, 0.25, 0.15]
    else:
        # Default configuration
        phase_configs = [
            {'name': 'Phase 1', 'start_offset': -28, 'task_gap': 3, 'duration_range': (3, 7)},
            {'name': 'Phase 2', 'start_offset': -7, 'task_gap': 2, 'duration_range': (4, 8)},
            {'name': 'Phase 3', 'start_offset': 14, 'task_gap': 3, 'duration_range': (3, 6)},
        ]
        phase_ratios = [0.35, 0.40, 0.25]
    
    # Calculate task distribution
    phase_task_counts = [max(1, int(total_tasks * r)) for r in phase_ratios]
    
    # Adjust if we have too many/few tasks
    while sum(phase_task_counts) > total_tasks:
        for i in range(len(phase_task_counts) - 1, -1, -1):
            if phase_task_counts[i] > 1 and sum(phase_task_counts) > total_tasks:
                phase_task_counts[i] -= 1
    while sum(phase_task_counts) < total_tasks:
        phase_task_counts[-1] += 1
    
    # Assign tasks to phases
    task_index = 0
    updated_count = 0
    
    for phase_idx, (config, task_count) in enumerate(zip(phase_configs, phase_task_counts)):
        print(f"\n   📌 Phase {phase_idx + 1}: {config['name']} ({task_count} tasks)")
        
        current_offset = config['start_offset']
        min_dur, max_dur = config['duration_range']
        
        for i in range(task_count):
            if task_index >= total_tasks:
                break
            
            task = task_list[task_index]
            
            # Calculate duration
            duration = min_dur + ((max_dur - min_dur) * (i % 3)) // 2
            
            # Stagger - with some overlap for parallel work
            stagger = (i * config['task_gap'])
            
            # Add some overlap in middle phases
            if phase_idx in [1, 2] and i > 0:
                stagger = max(1, stagger - 2)
            
            start_date = base_date + timedelta(days=current_offset + stagger)
            end_date = start_date + timedelta(days=duration)
            
            # Update the task
            task.start_date = start_date
            task.due_date = timezone.make_aware(
                datetime.combine(end_date, datetime.min.time())
            )
            task.save()
            
            print(f"      ✓ {task.title[:40]:<40} | {start_date} → {end_date} ({duration} days)")
            
            task_index += 1
            updated_count += 1
    
    print(f"\n✅ Updated {updated_count} task dates")

def fix_dependencies(board, task_list):
    """Create logical dependencies between tasks."""
    
    print("\n🔗 Updating Task Dependencies...")
    
    # Clear existing dependencies
    for task in task_list:
        task.dependencies.clear()
    
    # Create dependencies based on the new date order
    # Sort by start_date
    sorted_tasks = sorted(task_list, key=lambda t: (t.start_date, t.id))
    
    # Create a dependency chain with some parallel work
    dependency_count = 0
    
    for i, task in enumerate(sorted_tasks):
        if i == 0:
            continue  # First task has no dependencies
        
        # Determine how many dependencies to add (1-2)
        # This creates a mix of sequential and parallel work
        num_deps = 1 if i % 3 == 0 else min(2, i)
        
        # Add dependencies on tasks that end before or around when this task starts
        potential_deps = [
            t for t in sorted_tasks[:i] 
            if t.due_date and task.start_date and 
            t.due_date.date() <= task.start_date + timedelta(days=2)
        ]
        
        # Take the most recent completed tasks as dependencies
        if potential_deps:
            recent_deps = sorted(potential_deps, key=lambda t: t.due_date, reverse=True)[:num_deps]
            for dep in recent_deps:
                task.dependencies.add(dep)
                dependency_count += 1
    
    print(f"   ✅ Created {dependency_count} task dependencies")

if __name__ == '__main__':
    fix_gantt_dates()
