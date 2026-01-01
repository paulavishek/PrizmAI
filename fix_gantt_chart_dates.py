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
    
    # Get the Software Development board
    try:
        board = Board.objects.get(name='Software Development', organization=org)
    except Board.DoesNotExist:
        print("❌ Software Development board not found!")
        return
    
    print(f"\n📊 Processing Board: {board.name}")
    
    # Get all tasks with dates
    tasks = Task.objects.filter(
        column__board=board,
        start_date__isnull=False,
        due_date__isnull=False
    ).select_related('column').order_by('id')
    
    print(f"   Found {tasks.count()} tasks with dates")
    
    # Base date - use a fixed reference point (today)
    base_date = timezone.now().date()
    
    # Create a staggered timeline that looks impressive
    # We'll spread tasks across 8 weeks with proper overlap
    
    # Define task schedule: (task_id_offset, start_offset_days, duration_days)
    # This creates a waterfall-like effect with some parallel work
    
    task_list = list(tasks)
    total_tasks = len(task_list)
    
    if total_tasks == 0:
        print("   No tasks to update!")
        return
    
    print(f"\n📅 Updating {total_tasks} task dates...")
    
    # Organize tasks into logical phases
    # Phase 1: Foundation (past - completed)
    # Phase 2: Development (ongoing)  
    # Phase 3: Testing & Review (upcoming)
    # Phase 4: Deployment & Future (future)
    
    phase_configs = [
        # Phase 1: Foundation (25% of tasks) - Completed work (past)
        {'name': 'Foundation', 'start_offset': -42, 'task_gap': 3, 'duration_range': (4, 8)},
        # Phase 2: Development (35% of tasks) - Current work (past to present)
        {'name': 'Development', 'start_offset': -21, 'task_gap': 2, 'duration_range': (5, 14)},
        # Phase 3: Testing (25% of tasks) - Near future
        {'name': 'Testing', 'start_offset': 7, 'task_gap': 2, 'duration_range': (3, 7)},
        # Phase 4: Deployment (15% of tasks) - Future
        {'name': 'Deployment', 'start_offset': 28, 'task_gap': 3, 'duration_range': (4, 10)},
    ]
    
    # Calculate task distribution
    phase_task_counts = [
        int(total_tasks * 0.25),  # Foundation
        int(total_tasks * 0.35),  # Development
        int(total_tasks * 0.25),  # Testing
        total_tasks - int(total_tasks * 0.25) - int(total_tasks * 0.35) - int(total_tasks * 0.25),  # Remaining
    ]
    
    # Ensure we have at least 1 task per phase
    for i in range(len(phase_task_counts)):
        if phase_task_counts[i] < 1:
            phase_task_counts[i] = 1
    
    # Adjust if we have too many tasks assigned
    while sum(phase_task_counts) > total_tasks:
        for i in range(len(phase_task_counts) - 1, -1, -1):
            if phase_task_counts[i] > 1 and sum(phase_task_counts) > total_tasks:
                phase_task_counts[i] -= 1
    
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
            
            # Calculate duration based on position in phase (varying durations)
            duration = min_dur + ((max_dur - min_dur) * (i % 3)) // 2
            
            # Add some stagger - tasks don't all start on the same day
            stagger = (i * config['task_gap'])
            
            # For parallel work effect in Development phase, create overlapping tasks
            if config['name'] == 'Development' and i > 0:
                # Some tasks start before the previous one ends
                stagger = max(1, stagger - 3)
            
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
    
    # Now fix dependencies to create a logical flow
    fix_dependencies(board, task_list)
    
    print("\n" + "=" * 70)
    print("✅ Gantt Chart Data Fixed Successfully!")
    print("=" * 70)

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
