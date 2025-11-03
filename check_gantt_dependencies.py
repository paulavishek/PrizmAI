"""
Script to check Gantt chart task dependencies and verify data integrity
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Task, Column
from datetime import datetime

def check_gantt_dependencies():
    print("=" * 80)
    print("GANTT CHART DEPENDENCY VERIFICATION")
    print("=" * 80)
    
    boards = Board.objects.all()
    
    for board in boards:
        print(f"\n{'='*80}")
        print(f"BOARD: {board.name} (ID: {board.id})")
        print(f"{'='*80}")
        
        # Get all tasks with dates (tasks that appear in Gantt chart)
        tasks = Task.objects.filter(
            column__board=board,
            start_date__isnull=False,
            due_date__isnull=False
        ).select_related('assigned_to', 'column').prefetch_related('dependencies').order_by('start_date', 'id')
        
        print(f"\nTotal tasks with dates: {tasks.count()}")
        
        if tasks.count() == 0:
            print("No tasks with dates found for this board.")
            continue
        
        print("\nTask Details:")
        print("-" * 80)
        
        for idx, task in enumerate(tasks, 1):
            print(f"\n{idx}. Task ID: {task.id}")
            print(f"   Title: {task.title}")
            print(f"   Status: {task.column.name}")
            print(f"   Start Date: {task.start_date}")
            print(f"   Due Date: {task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date}")
            print(f"   Progress: {task.progress}%")
            print(f"   Priority: {task.priority}")
            print(f"   Assigned to: {task.assigned_to.username if task.assigned_to else 'Unassigned'}")
            
            # Check dependencies
            deps = task.dependencies.all()
            if deps.exists():
                print(f"   Dependencies ({deps.count()}):")
                for dep in deps:
                    dep_has_dates = dep.start_date and dep.due_date
                    status_icon = "✓" if dep_has_dates else "✗"
                    print(f"      {status_icon} Task #{dep.id}: {dep.title}")
                    if not dep_has_dates:
                        print(f"         WARNING: Dependency has no dates! (start: {dep.start_date}, due: {dep.due_date})")
                    else:
                        print(f"         Start: {dep.start_date}, Due: {dep.due_date.date() if hasattr(dep.due_date, 'date') else dep.due_date}")
            else:
                print(f"   Dependencies: None")
            
            # Check if this task is a dependency for others
            dependent_tasks = Task.objects.filter(dependencies=task)
            if dependent_tasks.exists():
                print(f"   Blocks these tasks ({dependent_tasks.count()}):")
                for dt in dependent_tasks:
                    print(f"      → Task #{dt.id}: {dt.title}")
        
        print("\n" + "="*80)
        print("DEPENDENCY ANALYSIS")
        print("="*80)
        
        # Count tasks with and without dependencies
        tasks_with_deps = tasks.filter(dependencies__isnull=False).distinct().count()
        tasks_without_deps = tasks.count() - tasks_with_deps
        
        print(f"\nTasks with dependencies: {tasks_with_deps}")
        print(f"Tasks without dependencies: {tasks_without_deps}")
        
        # Check for missing dependency data issues
        print("\nPOTENTIAL ISSUES:")
        print("-" * 80)
        
        issues_found = False
        
        for task in tasks:
            deps = task.dependencies.all()
            for dep in deps:
                # Issue 1: Dependency doesn't have dates
                if not dep.start_date or not dep.due_date:
                    print(f"⚠ Task #{task.id} depends on Task #{dep.id} which has no dates")
                    print(f"  This dependency will NOT be shown in Gantt chart!")
                    issues_found = True
                
                # Issue 2: Dependency is not in the same board
                if dep.column.board != board:
                    print(f"⚠ Task #{task.id} depends on Task #{dep.id} from a different board")
                    issues_found = True
                
                # Issue 3: Self-dependency
                if dep.id == task.id:
                    print(f"⚠ Task #{task.id} depends on itself (self-dependency)")
                    issues_found = True
        
        if not issues_found:
            print("✓ No issues found with dependencies")
        
        print("\n" + "="*80)
        print(f"GANTT CHART URL: http://localhost:8000/boards/{board.id}/gantt/")
        print("="*80)

if __name__ == '__main__':
    check_gantt_dependencies()
