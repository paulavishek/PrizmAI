#!/usr/bin/env python
"""
Check board member assignments
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth import get_user_model
from kanban.models import Board, Task

User = get_user_model()

# Get Software Development board
board = Board.objects.filter(name='Software Development', is_official_demo_board=True).first()

if not board:
    print("❌ Software Development board not found")
    exit(1)

print(f"Board: {board.name}")
print(f"Organization: {board.organization.name}")
print(f"\n=== BOARD MEMBERS ===")
members = board.members.all()
for member in members:
    print(f"  - {member.get_full_name() or member.username} ({member.username})")

print(f"\n=== TASKS AND ASSIGNMENTS ===")
tasks = Task.objects.filter(column__board=board).select_related('assigned_to')
assignment_counts = {}

for task in tasks:
    assignee = task.assigned_to
    if assignee:
        username = assignee.username
        display_name = assignee.get_full_name() or username
        if username not in assignment_counts:
            assignment_counts[username] = {'name': display_name, 'count': 0}
        assignment_counts[username]['count'] += 1
    else:
        if 'unassigned' not in assignment_counts:
            assignment_counts['unassigned'] = {'name': 'Unassigned', 'count': 0}
        assignment_counts['unassigned']['count'] += 1

print("\nTask Assignment Summary:")
for username, data in sorted(assignment_counts.items(), key=lambda x: x[1]['count'], reverse=True):
    print(f"  {data['name']}: {data['count']} tasks")
    
    # Check if user is a board member
    if username != 'unassigned':
        user = User.objects.get(username=username)
        is_member = board.members.filter(id=user.id).exists()
        if not is_member:
            print(f"    ⚠️  WARNING: {data['name']} is NOT a board member!")

print(f"\n=== UNASSIGNED TASKS (for AI suggestions) ===")
unassigned = tasks.filter(assigned_to__isnull=True)
print(f"Total unassigned tasks: {unassigned.count()}")
if unassigned.count() > 0:
    print("\nUnassigned tasks:")
    for task in unassigned[:5]:  # Show first 5
        print(f"  - {task.title}")
