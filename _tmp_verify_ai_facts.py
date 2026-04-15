import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'kanban_board.settings'
django.setup()

from kanban.models import Board, Task, Column, BoardMembership
from django.utils import timezone
from datetime import timedelta

board = Board.objects.get(id=44)
print(f'Board: {board.name}')

# Team size
members = BoardMembership.objects.filter(board=board).count()
print(f'Team members (memberships): {members}')

# Active tasks
columns = Column.objects.filter(board=board)
all_tasks = Task.objects.filter(column__board=board)
active_tasks = all_tasks.filter(progress__isnull=False, progress__lt=100)
print(f'Total tasks: {all_tasks.count()}')
print(f'Active tasks (progress<100): {active_tasks.count()}')

# Tasks by column
for col in columns.order_by('position'):
    task_count = Task.objects.filter(column=col).count()
    print(f'  Column "{col.name}": {task_count} tasks')

# Velocity
now = timezone.now()
week_ago = now - timedelta(days=7)
two_weeks_ago = now - timedelta(days=14)

completed_this_week = Task.objects.filter(column__board=board, completed_at__gte=week_ago).count()
completed_last_week = Task.objects.filter(column__board=board, completed_at__gte=two_weeks_ago, completed_at__lt=week_ago).count()
print(f'Completed this week: {completed_this_week}')
print(f'Completed last week: {completed_last_week}')

total_completed = Task.objects.filter(column__board=board, completed_at__isnull=False).count()
print(f'Total completed ever: {total_completed}')

# Check what AI coach service sees
from kanban.utils.ai_coach_service import AICoachService
ai_coach = AICoachService()

# Simulate the context gathering
active_count = Task.objects.filter(
    column__board=board, progress__isnull=False, progress__lt=100
).count()
team_size = board.memberships.count()
print(f'\nAI Coach would see:')
print(f'  active_tasks: {active_count}')
print(f'  team_size: {team_size}')
