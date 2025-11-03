"""
Simple script to verify Gantt dependencies for Software Project board
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Task

def verify_software_project_dependencies():
    board = Board.objects.get(name="Software Project")
    
    # Get the last few tasks
    task_ids = [30, 31, 32, 33]
    
    print("=" * 80)
    print("SOFTWARE PROJECT - DEPENDENCY VERIFICATION")
    print("=" * 80)
    
    for task_id in task_ids:
        task = Task.objects.get(id=task_id)
        deps = task.dependencies.all()
        
        print(f"\nTask #{task.id}: {task.title}")
        print(f"  Start: {task.start_date}, Due: {task.due_date.date()}")
        if deps.exists():
            print(f"  Dependencies ({deps.count()}):")
            for dep in deps:
                print(f"    - Task #{dep.id}: {dep.title}")
        else:
            print(f"  Dependencies: NONE")
    
    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE")
    print("=" * 80)

if __name__ == '__main__':
    verify_software_project_dependencies()
