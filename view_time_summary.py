#!/usr/bin/env python
"""Show detailed time entry breakdown for avishekpaul1310"""
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.budget_models import TimeEntry
from django.contrib.auth.models import User
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta

user = User.objects.get(username='avishekpaul1310')
now = timezone.now().date()

# Calculate time periods
today = now
week_start = today - timedelta(days=today.weekday())
month_start = today.replace(day=1)

# Get time entries
entries = TimeEntry.objects.filter(user=user)

# Calculate metrics
today_hours = entries.filter(work_date=today).aggregate(total=Sum('hours_spent'))['total'] or 0
week_hours = entries.filter(work_date__gte=week_start).aggregate(total=Sum('hours_spent'))['total'] or 0
month_hours = entries.filter(work_date__gte=month_start).aggregate(total=Sum('hours_spent'))['total'] or 0
total_hours = entries.aggregate(total=Sum('hours_spent'))['total'] or 0

print(f"\n{'='*60}")
print(f"Time Tracking Summary for {user.username}")
print(f"{'='*60}")
print(f"\n📊 Time Statistics:")
print(f"   TODAY:      {float(today_hours):.2f}h")
print(f"   THIS WEEK:  {float(week_hours):.2f}h")
print(f"   THIS MONTH: {float(month_hours):.2f}h")
print(f"   TOTAL:      {float(total_hours):.2f}h")

print(f"\n📝 Recent Time Entries:")
print(f"{'Date':<12} {'Task':<40} {'Hours':<8} {'Description':<30}")
print("-" * 100)

recent_entries = entries.select_related('task').order_by('-work_date', '-created_at')[:10]
for entry in recent_entries:
    task_title = entry.task.title[:37] + "..." if len(entry.task.title) > 40 else entry.task.title
    desc = entry.description[:27] + "..." if len(entry.description) > 30 else entry.description
    print(f"{entry.work_date} {task_title:<40} {float(entry.hours_spent):>6.2f}h  {desc:<30}")

print(f"\n✅ Time tracking is now populated!")
print(f"{'='*60}\n")
