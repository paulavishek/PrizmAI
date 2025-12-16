"""
Check demo data statistics
Shows current task counts and overdue tasks
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from kanban.models import Board, Task
from accounts.models import Organization

demo_org_names = ['Dev Team', 'Marketing Team']
demo_orgs = Organization.objects.filter(name__in=demo_org_names)
demo_boards = Board.objects.filter(organization__in=demo_orgs)

print("=" * 80)
print(" " * 30 + "DEMO STATISTICS")
print("=" * 80)

# Overall stats
total_tasks = Task.objects.filter(column__board__in=demo_boards).count()
completed_tasks = Task.objects.filter(column__board__in=demo_boards, progress=100).count()
incomplete_tasks = total_tasks - completed_tasks

overdue_tasks = Task.objects.filter(
    column__board__in=demo_boards,
    due_date__lt=timezone.now(),
    progress__lt=100
).exclude(column__name__icontains='done')

overdue_count = overdue_tasks.count()

print(f"\n📊 Overall Statistics:")
print(f"  Demo boards: {demo_boards.count()}")
print(f"  Total tasks: {total_tasks}")
print(f"  Completed: {completed_tasks} ({completed_tasks/total_tasks*100 if total_tasks else 0:.1f}%)")
print(f"  Incomplete: {incomplete_tasks}")
print(f"  Overdue: {overdue_count}")

print(f"\n📋 Per Board Breakdown:")
for board in demo_boards:
    tasks = Task.objects.filter(column__board=board)
    board_total = tasks.count()
    board_completed = tasks.filter(progress=100).count()
    board_overdue = tasks.filter(
        due_date__lt=timezone.now(),
        progress__lt=100
    ).exclude(column__name__icontains='done').count()
    
    print(f"\n  {board.name}:")
    print(f"    Total: {board_total}")
    print(f"    Completed: {board_completed}")
    print(f"    Overdue: {board_overdue}")
    
    # Per column
    for column in board.columns.all():
        col_tasks = tasks.filter(column=column).count()
        if col_tasks > 0:
            print(f"      - {column.name}: {col_tasks} tasks")

if overdue_count > 0:
    print(f"\n🚨 Overdue Tasks List:")
    for i, task in enumerate(overdue_tasks[:10], 1):
        task_due_date = task.due_date if hasattr(task.due_date, 'date') else task.due_date
        if isinstance(task_due_date, timezone.datetime):
            task_due_date = task_due_date.date()
        days_overdue = (timezone.now().date() - task_due_date).days
        print(f"  {i}. {task.title[:50]} - {days_overdue} days overdue")
        print(f"     Board: {task.column.board.name}, Column: {task.column.name}")

# Date distribution
print(f"\n📅 Date Distribution:")
now = timezone.now()
past_due = Task.objects.filter(column__board__in=demo_boards, due_date__lt=now).count()
future_due = Task.objects.filter(column__board__in=demo_boards, due_date__gte=now).count()
next_7_days = Task.objects.filter(
    column__board__in=demo_boards,
    due_date__gte=now,
    due_date__lt=now + timezone.timedelta(days=7)
).count()

print(f"  Past due dates: {past_due}")
print(f"  Future due dates: {future_due}")
print(f"  Due in next 7 days: {next_7_days}")

# Assessment
print(f"\n{'=' * 80}")
print("Assessment:")
print(f"{'=' * 80}")

status = []
if total_tasks < 120:
    status.append(f"✅ Task count is manageable ({total_tasks} tasks)")
else:
    status.append(f"⚠️  Task count is high ({total_tasks} tasks, consider reducing)")

if 4 <= overdue_count <= 6:
    status.append(f"✅ Overdue count is ideal ({overdue_count} tasks)")
elif overdue_count < 4:
    status.append(f"ℹ️  Overdue count is low ({overdue_count} tasks)")
else:
    status.append(f"⚠️  Overdue count is high ({overdue_count} tasks)")

completion_rate = (completed_tasks / total_tasks * 100) if total_tasks else 0
if completion_rate >= 60:
    status.append(f"✅ Completion rate is healthy ({completion_rate:.1f}%)")
else:
    status.append(f"⚠️  Completion rate is low ({completion_rate:.1f}%)")

for s in status:
    print(f"  {s}")

print(f"\n💡 Tip: Run 'python manage.py refresh_demo_dates' to refresh dates")
print(f"{'=' * 80}\n")
