"""
Assign demo users to demo tasks across all boards
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
import django
django.setup()

from kanban.models import Task, Board, Organization, Column
from django.contrib.auth.models import User
import random

# Get demo org and users
org = Organization.objects.get(name='Demo - Acme Corporation')
boards = Board.objects.filter(organization=org)

# Get demo users
alex = User.objects.get(username='alex_chen_demo')
sam = User.objects.get(username='sam_rivera_demo')
jordan = User.objects.get(username='jordan_taylor_demo')

print(f'Demo Users: alex={alex.id}, sam={sam.id}, jordan={jordan.id}')

def assign_tasks_by_pattern(board, users):
    """Assign tasks to users based on board type and task context"""
    tasks = Task.objects.filter(column__board=board, assigned_to__isnull=True)
    count = 0
    
    for i, task in enumerate(tasks):
        title = task.title.lower()
        
        # Assign based on title keywords
        if any(word in title for word in ['security', 'auth', 'api', 'database', 'sql', 'backend']):
            task.assigned_to = users[0]  # Alex - backend/security
        elif any(word in title for word in ['ui', 'ux', 'design', 'responsive', 'dashboard', 'mobile', 'css']):
            task.assigned_to = users[1]  # Sam - frontend/UI
        elif any(word in title for word in ['marketing', 'content', 'blog', 'social', 'email', 'video']):
            task.assigned_to = users[2]  # Jordan - marketing/content
        elif any(word in title for word in ['test', 'qa', 'review', 'audit', 'bug', 'fix']):
            task.assigned_to = users[1]  # Sam - QA
        elif any(word in title for word in ['document', 'wiki', 'help', 'guide']):
            task.assigned_to = users[2]  # Jordan - documentation
        else:
            # Cycle through users for remaining tasks
            task.assigned_to = users[i % len(users)]
        
        task.save()
        count += 1
        print(f'  Assigned: {task.title[:50]} -> {task.assigned_to.username}')
    
    return count

print('\n=== Assigning Tasks to Demo Users ===\n')

# Software Development board - assign to alex and sam
sw_board = Board.objects.get(name='Software Development', organization=org)
print(f'Board: {sw_board.name}')
sw_users = [alex, sam, jordan]
sw_count = assign_tasks_by_pattern(sw_board, sw_users)
print(f'  Assigned {sw_count} tasks\n')

# Marketing Campaign board - assign mainly to jordan
mk_board = Board.objects.get(name='Marketing Campaign', organization=org)
print(f'Board: {mk_board.name}')
mk_users = [jordan, alex, sam]
mk_count = assign_tasks_by_pattern(mk_board, mk_users)
print(f'  Assigned {mk_count} tasks\n')

# Bug Tracking board - assign to sam and alex
bug_board = Board.objects.get(name='Bug Tracking', organization=org)
print(f'Board: {bug_board.name}')
bug_users = [sam, alex, jordan]
bug_count = assign_tasks_by_pattern(bug_board, bug_users)
print(f'  Assigned {bug_count} tasks\n')

# Verify
print('\n=== Verification ===')
for board in boards:
    total = Task.objects.filter(column__board=board).count()
    assigned = Task.objects.filter(column__board=board, assigned_to__isnull=False).count()
    print(f'{board.name}: {assigned}/{total} assigned')

print('\n✅ Done!')
