#!/usr/bin/env python
"""Check task assignments for time entries"""
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.budget_models import TimeEntry
from kanban.models import Task
from django.contrib.auth.models import User

user = User.objects.get(username='avishekpaul1310')

# Get all tasks with time entries for this user
tasks_with_entries = Task.objects.filter(time_entries__user=user).distinct()

print(f"\n{'='*80}")
print(f"Task Assignment Analysis for {user.username}")
print(f"{'='*80}\n")

assigned_count = 0
not_assigned_count = 0

print("Tasks WITH time entries but NOT assigned to user:")
print("-" * 80)
for task in tasks_with_entries:
    if task.assigned_to != user:
        not_assigned_count += 1
        entry_count = TimeEntry.objects.filter(task=task, user=user).count()
        assigned_to = task.assigned_to.username if task.assigned_to else "Unassigned"
        print(f"  • {task.title[:60]:<60} | Assigned to: {assigned_to} | Entries: {entry_count}")
    else:
        assigned_count += 1

print(f"\n{'='*80}")
print(f"Summary:")
print(f"  - Tasks assigned to user: {assigned_count}")
print(f"  - Tasks NOT assigned to user: {not_assigned_count}")
print(f"  - Total tasks with time entries: {tasks_with_entries.count()}")
print(f"{'='*80}\n")

if not_assigned_count > 0:
    print(f"⚠️  Issue found: {not_assigned_count} tasks have time entries but are not assigned to {user.username}")
    print("This is why they don't show up in 'My Timesheet'")
    print("\nFixing: Assigning these tasks to the user...")
    
    for task in tasks_with_entries:
        if task.assigned_to != user:
            task.assigned_to = user
            task.save()
    
    print(f"✅ Fixed! All {not_assigned_count} tasks are now assigned to {user.username}")
