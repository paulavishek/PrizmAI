"""
Check task dates and dependencies
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
import django
django.setup()
from kanban.models import Task, Board, Organization

org = Organization.objects.get(name='Demo - Acme Corporation')
sw_board = Board.objects.get(name='Software Development', organization=org)
tasks = Task.objects.filter(column__board=sw_board).select_related('assigned_to')[:20]

print('=== Task Dates and Dependencies ===')
for task in tasks:
    deps = list(task.dependencies.values_list('id', 'title'))
    dep_str = deps if deps else "None"
    print(f'{task.id}: {task.title[:40]}')
    print(f'    Start: {task.start_date}, Due: {task.due_date}')
    print(f'    Dependencies: {dep_str}')
    print()

# Count tasks with dates
total = Task.objects.filter(column__board=sw_board).count()
with_start = Task.objects.filter(column__board=sw_board, start_date__isnull=False).count()
with_due = Task.objects.filter(column__board=sw_board, due_date__isnull=False).count()
with_deps = 0
for t in Task.objects.filter(column__board=sw_board):
    if t.dependencies.exists():
        with_deps += 1

print(f'\n=== Summary ===')
print(f'Total tasks: {total}')
print(f'With start date: {with_start}')
print(f'With due date: {with_due}')
print(f'With dependencies: {with_deps}')
