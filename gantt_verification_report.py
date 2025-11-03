"""
Comprehensive Gantt Chart Data Verification Report
"""
import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Task

def generate_gantt_verification_report():
    print("=" * 100)
    print("GANTT CHART DATA VERIFICATION REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    
    boards = Board.objects.all()
    
    for board in boards:
        print(f"\n{'='*100}")
        print(f"BOARD: {board.name} (ID: {board.id})")
        print(f"{'='*100}")
        
        tasks = Task.objects.filter(
            column__board=board,
            start_date__isnull=False,
            due_date__isnull=False
        ).select_related('assigned_to', 'column').prefetch_related('dependencies').order_by('start_date', 'id')
        
        total_tasks = tasks.count()
        tasks_with_deps = tasks.filter(dependencies__isnull=False).distinct().count()
        
        print(f"\nSUMMARY:")
        print(f"  Total tasks with dates: {total_tasks}")
        print(f"  Tasks with dependencies: {tasks_with_deps}")
        print(f"  Tasks without dependencies: {total_tasks - tasks_with_deps}")
        
        print(f"\n{'='*100}")
        print("TASK LIST (in chronological order as shown in Gantt chart)")
        print(f"{'='*100}")
        
        for idx, task in enumerate(tasks, 1):
            due = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
            
            # Calculate duration
            duration = (due - task.start_date).days
            
            # Status indicator
            if task.progress >= 100:
                status_icon = "[DONE]"
            elif task.progress > 0:
                status_icon = "[IN PROGRESS]"
            else:
                status_icon = "[NOT STARTED]"
            
            print(f"\n{idx:2d}. {status_icon} Task #{task.id}: {task.title}")
            print(f"    Column: {task.column.name}")
            print(f"    Timeline: {task.start_date} to {due} ({duration} days)")
            print(f"    Progress: {task.progress}% | Priority: {task.priority.upper()}")
            print(f"    Assigned: {task.assigned_to.username if task.assigned_to else 'Unassigned'}")
            
            deps = task.dependencies.all()
            if deps.exists():
                print(f"    Dependencies ({deps.count()}):")
                for dep in deps:
                    dep_due = dep.due_date.date() if hasattr(dep.due_date, 'date') else dep.due_date
                    print(f"      <- Task #{dep.id}: {dep.title} ({dep.start_date} to {dep_due})")
            else:
                print(f"    Dependencies: None (this task can start independently)")
            
            # Check what tasks depend on this one
            blocking = Task.objects.filter(dependencies=task, column__board=board)
            if blocking.exists():
                print(f"    Blocks ({blocking.count()}):")
                for bt in blocking:
                    print(f"      -> Task #{bt.id}: {bt.title}")
        
        # Dependency Chain Analysis
        print(f"\n{'='*100}")
        print("DEPENDENCY CHAIN ANALYSIS")
        print(f"{'='*100}")
        
        # Find root tasks (no dependencies)
        root_tasks = tasks.filter(dependencies__isnull=True)
        print(f"\nRoot Tasks (no dependencies): {root_tasks.count()}")
        for task in root_tasks:
            print(f"  - Task #{task.id}: {task.title}")
        
        # Find leaf tasks (not blocking anyone)
        all_task_ids = set(tasks.values_list('id', flat=True))
        blocking_task_ids = set()
        for task in tasks:
            blocking = Task.objects.filter(dependencies=task, column__board=board)
            if blocking.exists():
                blocking_task_ids.add(task.id)
        
        leaf_task_ids = all_task_ids - blocking_task_ids
        leaf_tasks = tasks.filter(id__in=leaf_task_ids)
        
        print(f"\nLeaf Tasks (not blocking any other tasks): {leaf_tasks.count()}")
        for task in leaf_tasks:
            print(f"  - Task #{task.id}: {task.title}")
        
        # Check for potential issues
        print(f"\n{'='*100}")
        print("VALIDATION CHECKS")
        print(f"{'='*100}")
        
        issues = []
        
        for task in tasks:
            deps = task.dependencies.all()
            for dep in deps:
                # Check if dependency has dates
                if not dep.start_date or not dep.due_date:
                    issues.append(f"Task #{task.id} depends on Task #{dep.id} which has no dates")
                
                # Check if dependency is in same board
                if dep.column.board != board:
                    issues.append(f"Task #{task.id} depends on Task #{dep.id} from different board")
                
                # Check for circular dependencies (simplified check)
                if task in dep.dependencies.all():
                    issues.append(f"Circular dependency: Task #{task.id} <-> Task #{dep.id}")
                
                # Check date logic
                if dep.due_date and task.start_date:
                    dep_due = dep.due_date.date() if hasattr(dep.due_date, 'date') else dep.due_date
                    if dep_due > task.start_date:
                        issues.append(f"Warning: Task #{task.id} starts before dependency Task #{dep.id} ends")
        
        if issues:
            print("\nISSUES FOUND:")
            for issue in issues:
                print(f"  ! {issue}")
        else:
            print("\n  [OK] No issues found - all dependencies are valid")
        
        print(f"\n{'='*100}")
        print(f"Gantt Chart URL: http://localhost:8000/boards/{board.id}/gantt/")
        print(f"{'='*100}")
    
    print(f"\n{'='*100}")
    print("END OF REPORT")
    print(f"{'='*100}")

if __name__ == '__main__':
    generate_gantt_verification_report()
