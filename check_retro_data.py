import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Board
from django.utils import timezone
from datetime import datetime, timedelta

board = Board.objects.get(id=1)
tasks = Task.objects.filter(column__board=board)

print(f"Total tasks on board: {tasks.count()}")
print(f"\nFirst 5 task creation dates:")
for task in tasks.order_by('created_at')[:5]:
    print(f"  - Task '{task.title}': created_at={task.created_at}, completed_at={task.completed_at}, progress={task.progress}%")

print(f"\nTasks with completed_at set: {tasks.filter(completed_at__isnull=False).count()}")
print(f"Tasks with progress=100: {tasks.filter(progress=100).count()}")

# Check date range filtering
start_date = datetime(2025, 12, 16).date()
end_date = datetime(2025, 12, 30).date()
print(f"\n\nDate range: {start_date} to {end_date}")

# Old logic - tasks created in range
from django.utils.timezone import make_aware
from datetime import time
period_start_dt = make_aware(datetime.combine(start_date, time.min))
period_end_dt = make_aware(datetime.combine(end_date, time.max))

old_logic = tasks.filter(created_at__range=(period_start_dt, period_end_dt))
print(f"Tasks created in range (old logic): {old_logic.count()}")

# New logic - tasks active in range
new_logic = tasks.filter(created_at__lte=period_end_dt).exclude(completed_at__lt=period_start_dt)
print(f"Tasks active in range (new logic): {new_logic.count()}")

print(f"\n\nSample of active tasks:")
for task in new_logic[:5]:
    print(f"  - '{task.title}': created={task.created_at.date()}, completed={task.completed_at.date() if task.completed_at else 'Not completed'}, progress={task.progress}%")
