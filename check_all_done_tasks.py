"""
Script to check all boards and their Done columns
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Column, Board
from django.db import models

# Find all boards
boards = Board.objects.all()

print(f"Found {boards.count()} boards:\n")
for board in boards:
    print(f"📋 Board #{board.id}: {board.name}")
    print(f"   Created by: {board.created_by.username}")
    
    # Find Done columns in this board
    done_columns = board.columns.filter(
        models.Q(name__icontains='done') | models.Q(name__icontains='complete')
    )
    
    if done_columns.exists():
        for col in done_columns:
            print(f"\n   ✅ Column: {col.name}")
            tasks = Task.objects.filter(column=col).order_by('position')
            print(f"   Tasks: {tasks.count()}")
            
            for task in tasks:
                print(f"     - Task #{task.id}: {task.title}")
                print(f"       Progress: {task.progress}%")
    else:
        print("   (No Done/Complete columns)")
    print()
