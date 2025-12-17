"""
Find duplicate tasks in all demo boards
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Board
from collections import defaultdict

# Get all demo boards
board_names = ['Software Project', 'Bug Tracking', 'Marketing Campaign']

for board_name in board_names:
    board = Board.objects.filter(name=board_name).first()
    
    if board:
        print(f"\n{'='*80}")
        print(f"📊 Board: {board.name}")
        print(f"{'='*80}")
        
        # Get all tasks
        tasks = Task.objects.filter(column__board=board).order_by('title')
        
        # Group by title to find duplicates
        task_groups = defaultdict(list)
        for task in tasks:
            task_groups[task.title].append(task)
        
        print(f"\nTotal tasks: {tasks.count()}")
        
        # Show duplicates
        duplicates_found = False
        for title, task_list in task_groups.items():
            if len(task_list) > 1:
                if not duplicates_found:
                    print(f"\n⚠️  DUPLICATES FOUND:")
                duplicates_found = True
                print(f"\n  {title}")
                for task in task_list:
                    deps = task.dependencies.count()
                    print(f"    - ID: {task.id} | Column: {task.column.name:<15} | Deps: {deps} | Dates: {task.start_date} → {task.due_date.date() if task.due_date else 'None'}")
        
        if not duplicates_found:
            print(f"\n✓ No duplicates found")
        
        # Count tasks with/without dependencies
        tasks_with_deps = sum(1 for t in tasks if t.dependencies.count() > 0)
        tasks_without_deps = tasks.count() - tasks_with_deps
        
        print(f"\nDependency Summary:")
        print(f"  - Tasks WITH dependencies: {tasks_with_deps}")
        print(f"  - Tasks WITHOUT dependencies: {tasks_without_deps}")
        
        if tasks_without_deps > 1:
            print(f"\n⚠️  Warning: {tasks_without_deps} tasks have no dependencies (should typically be 1 starting task)")
            print(f"\n  Tasks without dependencies:")
            for task in tasks:
                if task.dependencies.count() == 0:
                    print(f"    • {task.title[:50]} (ID: {task.id}, Date: {task.start_date})")
    else:
        print(f"\n❌ Board '{board_name}' not found")

print(f"\n{'='*80}")
