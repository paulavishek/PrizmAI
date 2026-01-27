#!/usr/bin/env python
"""Verify timesheet data is correct"""
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.budget_models import TimeEntry
from kanban.models import Task
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum

user = User.objects.get(username='avishekpaul1310')

# Get current week
today = timezone.now().date()
start_of_week = today - timedelta(days=today.weekday())
end_of_week = start_of_week + timedelta(days=6)

# Get tasks assigned to user
assigned_tasks = Task.objects.filter(assigned_to=user).count()

# Get time entries for the week
entries_this_week = TimeEntry.objects.filter(
    user=user,
    work_date__gte=start_of_week,
    work_date__lte=end_of_week
)

# Get tasks with entries this week
tasks_with_entries_this_week = Task.objects.filter(
    time_entries__user=user,
    time_entries__work_date__gte=start_of_week,
    time_entries__work_date__lte=end_of_week,
    assigned_to=user
).distinct()

print(f"\n{'='*80}")
print(f"Timesheet Verification for {user.username}")
print(f"Week: {start_of_week} to {end_of_week}")
print(f"{'='*80}\n")

print(f"📊 Statistics:")
print(f"   - Total tasks assigned to user: {assigned_tasks}")
print(f"   - Tasks with time entries this week: {tasks_with_entries_this_week.count()}")
print(f"   - Time entries this week: {entries_this_week.count()}")

# Daily breakdown
print(f"\n📅 Daily Breakdown:")
total_week = 0
for i in range(7):
    day = start_of_week + timedelta(days=i)
    daily_total = entries_this_week.filter(work_date=day).aggregate(total=Sum('hours_spent'))['total'] or 0
    day_name = day.strftime('%a %m/%d')
    print(f"   {day_name}: {float(daily_total):.2f}h")
    total_week += float(daily_total)

print(f"   {'─' * 20}")
print(f"   Week Total: {total_week:.2f}h")

print(f"\n📝 Tasks that will appear in timesheet:")
for task in tasks_with_entries_this_week[:10]:
    entry_count = entries_this_week.filter(task=task).count()
    total_hours = entries_this_week.filter(task=task).aggregate(total=Sum('hours_spent'))['total']
    print(f"   • {task.title[:55]:<55} ({entry_count} entries, {float(total_hours):.2f}h)")

print(f"\n✅ Timesheet should now display {tasks_with_entries_this_week.count()} tasks!")
print(f"{'='*80}\n")
