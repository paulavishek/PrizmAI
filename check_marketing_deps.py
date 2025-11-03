import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Task

board = Board.objects.get(name='Marketing Campaign')
tasks = Task.objects.filter(
    column__board=board, 
    start_date__isnull=False, 
    due_date__isnull=False
).order_by('start_date')

print('='*80)
print('MARKETING CAMPAIGN - DEPENDENCY CHECK')
print('='*80)

for i, task in enumerate(tasks, 1):
    deps = task.dependencies.all()
    due = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
    
    print(f'\n{i}. Task #{task.id}: {task.title}')
    print(f'   Dates: {task.start_date} to {due}')
    print(f'   Column: {task.column.name}')
    print(f'   Assigned: {task.assigned_to.username if task.assigned_to else "Unassigned"}')
    
    if deps.exists():
        print(f'   Dependencies: {deps.count()}')
        for dep in deps:
            print(f'     - Task #{dep.id}: {dep.title}')
    else:
        print(f'   Dependencies: NONE ⚠')
