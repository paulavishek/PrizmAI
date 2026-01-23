import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Task, TaskLabel

print("All Boards:")
boards = Board.objects.all()
for b in boards:
    print(f"{b.id}: {b.name} - Org: {b.organization.name}")

print("\n\nBoards with tasks:")
for b in boards:
    task_count = Task.objects.filter(column__board=b).count()
    if task_count > 0:
        print(f"{b.id}: {b.name} - Tasks: {task_count}")

print("\n\nLean Six Sigma Labels:")
lean_labels = TaskLabel.objects.filter(category='lean')
for label in lean_labels:
    print(f"Label: {label.name}, Color: {label.color}")
    
# Check tasks with lean labels
print("\n\nTasks with Lean Six Sigma labels per board:")
for b in boards:
    task_count = Task.objects.filter(column__board=b).count()
    if task_count > 0:
        lean_task_count = Task.objects.filter(column__board=b, labels__category='lean').distinct().count()
        print(f"{b.id}: {b.name} - Total Tasks: {task_count}, With Lean Labels: {lean_task_count}")
