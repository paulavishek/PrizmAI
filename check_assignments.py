import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Task
from accounts.models import Organization
from django.db.models import Count

demo_org = Organization.objects.filter(name='Demo - Acme Corporation').first()
software_board = Board.objects.filter(organization=demo_org, name__icontains='software').first()

if software_board:
    print(f'Board: {software_board.name} (ID: {software_board.id})')
    print('='*70)
    
    # Check task assignments
    total_tasks = Task.objects.filter(column__board=software_board).count()
    assigned_tasks = Task.objects.filter(column__board=software_board).exclude(assigned_to=None).count()
    unassigned_tasks = Task.objects.filter(column__board=software_board, assigned_to=None).count()
    
    print(f'Total tasks: {total_tasks}')
    print(f'Assigned tasks: {assigned_tasks}')
    print(f'Unassigned tasks: {unassigned_tasks}')
    
    print('\nAssignments by user:')
    assignments = Task.objects.filter(column__board=software_board).values('assigned_to__username').annotate(count=Count('id')).order_by('-count')
    for a in assignments:
        username = a['assigned_to__username'] or 'Unassigned'
        print(f'  {username}: {a["count"]} tasks')
else:
    print('Software board not found!')
