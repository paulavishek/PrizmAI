"""
Check demo tasks assignees
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
import django
django.setup()

from kanban.models import Task, Board, Organization

# Check demo boards
demo_orgs = Organization.objects.filter(name__in=['Dev Team', 'Marketing Team'])
print('Demo Organizations:', [o.name for o in demo_orgs])

demo_boards = Board.objects.filter(organization__in=demo_orgs)
print('Demo Boards:', [b.name for b in demo_boards])

# Check tasks and their assignees
for board in demo_boards:
    print(f'\n=== Board: {board.name} ===')
    tasks = Task.objects.filter(column__board=board)[:10]
    assigned_count = 0
    unassigned_count = 0
    for task in tasks:
        if task.assigned_to:
            assigned_count += 1
            assignee = task.assigned_to.username
        else:
            unassigned_count += 1
            assignee = 'NONE'
        print(f'  {task.title[:40]:40s} | Assigned: {assignee}')
    
    # Total counts
    total_tasks = Task.objects.filter(column__board=board).count()
    total_assigned = Task.objects.filter(column__board=board, assigned_to__isnull=False).count()
    total_unassigned = Task.objects.filter(column__board=board, assigned_to__isnull=True).count()
    print(f'\n  SUMMARY: Total={total_tasks}, Assigned={total_assigned}, Unassigned={total_unassigned}')

# Check for demo users
from django.contrib.auth.models import User
demo_users = User.objects.filter(username__in=['alex_dev', 'sam_dev', 'jordan_dev'])
print('\n=== Demo Users ===')
for user in demo_users:
    print(f'  {user.username} (ID: {user.id})')

# Check board members
print('\n=== Board Members ===')
for board in demo_boards:
    print(f'\nBoard: {board.name}')
    members = board.members.all()
    print(f'  Members: {[m.username for m in members]}')
