"""
Script to check demo board tasks in Done column
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Column, Board
from django.db import models

# Find demo boards
demo_boards = Board.objects.filter(
    models.Q(name__icontains='demo') | models.Q(created_by__username='demo')
)

print(f"Found {demo_boards.count()} demo boards:")
for board in demo_boards:
    print(f"\n📋 Board: {board.name}")
    print(f"   Created by: {board.created_by.username}")
    
    # Find Done columns in this board
    done_columns = board.columns.filter(
        models.Q(name__icontains='done') | models.Q(name__icontains='complete')
    )
    
    for col in done_columns:
        print(f"\n   Column: {col.name}")
        tasks = Task.objects.filter(column=col)
        print(f"   Tasks in this column: {tasks.count()}")
        
        for task in tasks:
            print(f"     - Task #{task.id}: {task.title}")
            print(f"       Progress: {task.progress}%")
            print(f"       Position: {task.position}")
