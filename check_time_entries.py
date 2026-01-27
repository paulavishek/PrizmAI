#!/usr/bin/env python
"""Check time entries per user"""
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.budget_models import TimeEntry
from django.contrib.auth.models import User
from django.db.models import Sum

print("\n=== Time Entries by User ===")
for u in User.objects.filter(time_entries__isnull=False).distinct():
    total_hours = TimeEntry.objects.filter(user=u).aggregate(total=Sum('hours_spent'))['total']
    count = TimeEntry.objects.filter(user=u).count()
    print(f"{u.username}: {float(total_hours):.2f} hours ({count} entries)")

print(f"\nTotal: {TimeEntry.objects.count()} entries")

# Check the user 'avishekpaul1310'
paul_user = User.objects.filter(username='avishekpaul1310').first()
if paul_user:
    paul_entries = TimeEntry.objects.filter(user=paul_user).count()
    paul_hours = TimeEntry.objects.filter(user=paul_user).aggregate(total=Sum('hours_spent'))['total'] or 0
    print(f"\navishekpaul1310: {float(paul_hours):.2f} hours ({paul_entries} entries)")
else:
    print("\navishekpaul1310 user not found")
