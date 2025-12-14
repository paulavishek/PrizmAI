import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Task

print("Checking current boards...")
boards = Board.objects.all()
print(f"\nTotal boards: {boards.count()}\n")

for board in boards:
    org_name = board.organization.name if board.organization else "No Org"
    task_count = Task.objects.filter(column__board=board).count()
    print(f"{board.id}: {board.name} ({org_name}) - {task_count} tasks")
