"""
Check Gantt chart dependencies for Software Project board
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Board

# Get Software Project board
board = Board.objects.filter(name='Software Project').first()

if board:
    print(f"\n📊 Board: {board.name}")
    print(f"=" * 80)
    
    # Get all tasks ordered by start date
    tasks = Task.objects.filter(
        column__board=board,
        start_date__isnull=False
    ).select_related('column').prefetch_related('dependencies').order_by('start_date')
    
    print(f"\nTotal tasks: {tasks.count()}")
    print(f"\nTasks with their dependencies:\n")
    
    for i, task in enumerate(tasks[:10], 1):  # Show first 10
        deps = task.dependencies.all()
        print(f"{i}. {task.title[:50]:<50}")
        print(f"   Column: {task.column.name:<15} | Dates: {task.start_date} → {task.due_date.date()}")
        if deps:
            print(f"   Dependencies ({deps.count()}):")
            for dep in deps:
                print(f"      ← {dep.title[:45]} (ends: {dep.due_date.date()})")
        else:
            print(f"   Dependencies: NONE")
        print()
