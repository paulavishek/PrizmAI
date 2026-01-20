#!/usr/bin/env python
"""Check demo task dependencies"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task

# Check demo tasks
tasks = Task.objects.filter(is_seed_demo_data=True, item_type='task')
print(f'Total demo tasks: {tasks.count()}')

tasks_with_deps = [t for t in tasks if t.dependencies.exists()]
print(f'Tasks with dependencies: {len(tasks_with_deps)}')

if tasks_with_deps:
    print('\nTasks with dependencies (checking dates):')
    for t in tasks_with_deps[:10]:
        print(f'\n  Task: "{t.title}"')
        print(f'    start_date: {t.start_date}, due_date: {t.due_date}')
        for d in t.dependencies.all():
            print(f'    -> depends on: "{d.title}"')
            print(f'       dep start_date: {d.start_date}, dep due_date: {d.due_date}')
            has_dates = d.start_date and d.due_date
            print(f'       Will show in Gantt: {has_dates}')
