#!/usr/bin/env python
"""Populate time entries for avishekpaul1310 user"""
import django
import os
import random
from decimal import Decimal
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.budget_models import TimeEntry
from kanban.models import Task
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import models as django_models

# Get the user
user = User.objects.filter(username='avishekpaul1310').first()
if not user:
    print("User avishekpaul1310 not found!")
    exit(1)

print(f"Found user: {user.username}")

# Get tasks assigned to this user or accessible boards
tasks = Task.objects.filter(assigned_to=user, progress__gt=0)
if not tasks.exists():
    # Get tasks from boards the user can access
    from kanban.models import Board
    boards = Board.objects.filter(
        django_models.Q(created_by=user) | django_models.Q(members=user)
    ).distinct()
    
    if boards.exists():
        tasks = Task.objects.filter(column__board__in=boards, progress__gt=0)
    
print(f"Found {tasks.count()} tasks in progress")

if not tasks.exists():
    print("No tasks found. Creating time entries for any available tasks...")
    tasks = Task.objects.filter(progress__gt=0)[:20]  # Get any 20 tasks in progress

now = timezone.now().date()
entries_created = 0

# Descriptions for variety
descriptions = [
    "Worked on implementation",
    "Code review and testing",
    "Bug fixing and debugging",
    "Feature development",
    "Documentation updates",
    "Meeting and planning",
    "Research and analysis",
    "Deployment and configuration",
    "Performance optimization",
    "Unit testing",
    "Integration work",
    "Design review",
    "Sprint planning",
]

print(f"\nCreating time entries for {user.username}...")

for task in tasks[:15]:  # Create entries for up to 15 tasks
    # Create 1-3 time entries per task
    num_entries = random.randint(1, 3)
    for i in range(num_entries):
        hours = round(random.uniform(0.5, 4.0), 2)  # Random hours between 0.5 and 4
        entry_date = now - timedelta(days=random.randint(0, 13))  # Last 2 weeks
        description = random.choice(descriptions)
        
        TimeEntry.objects.create(
            task=task,
            user=user,
            hours_spent=Decimal(str(hours)),
            description=description,
            work_date=entry_date,
        )
        entries_created += 1

print(f"✅ Created {entries_created} time entries for {user.username}")

# Show summary
from django.db.models import Sum
total_hours = TimeEntry.objects.filter(user=user).aggregate(total=Sum('hours_spent'))['total']
print(f"\nTotal hours logged: {float(total_hours):.2f} hours")
