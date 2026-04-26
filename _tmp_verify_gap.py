import os; os.environ['DJANGO_SETTINGS_MODULE'] = 'kanban_board.settings'
import django; django.setup()
from kanban.models import Board, Task
from requirements.models import Requirement, ProjectObjective

board = Board.objects.get(id=64)
print(f"Board: {board.name}")
print(f"Objectives: {ProjectObjective.objects.filter(board=board).count()}")
print(f"Requirements: {Requirement.objects.filter(board=board).count()}")
print()

tasks = Task.objects.filter(column__board=board)
print(f"Tasks count: {tasks.count()}")
for t in tasks:
    req_count = t.linked_requirements.count()
    print(f"  - \"{t.title}\" [col={t.column.name}, priority={t.priority}] (linked reqs: {req_count})")
