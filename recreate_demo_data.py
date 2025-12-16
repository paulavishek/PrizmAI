"""
Clean up and recreate demo data with reduced task count
This will:
1. Delete existing demo data
2. Recreate demo data with ~90 tasks total (30 per board)
3. Ensure dates are dynamic with exactly 4-5 overdue tasks
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.core.management import call_command
from django.contrib.auth.models import User
from kanban.models import Board, Task
from accounts.models import Organization

print("=" * 80)
print(" " * 20 + "DEMO DATA CLEANUP AND RECREATION")
print("=" * 80)

# Check current state
demo_org_names = ['Dev Team', 'Marketing Team']
demo_orgs = Organization.objects.filter(name__in=demo_org_names)
demo_boards = Board.objects.filter(organization__in=demo_orgs)

print(f"\n📊 Current State:")
print(f"  Demo organizations: {demo_orgs.count()}")
print(f"  Demo boards: {demo_boards.count()}")
print(f"  Total tasks: {Task.objects.filter(column__board__in=demo_boards).count()}")

overdue = Task.objects.filter(
    column__board__in=demo_boards,
    due_date__lt=django.utils.timezone.now(),
    progress__lt=100
).count()
print(f"  Overdue tasks: {overdue}")

# Ask for confirmation
print(f"\n⚠️  WARNING: This will DELETE all demo data and recreate it!")
response = input("\nDo you want to continue? (yes/no): ")

if response.lower() != 'yes':
    print("\n❌ Operation cancelled.")
    exit(0)

print(f"\n{'=' * 80}")
print("STEP 1: Deleting existing demo data...")
print(f"{'=' * 80}")

# Delete demo data
call_command('delete_demo_data', '--no-confirm')

print(f"\n{'=' * 80}")
print("STEP 2: Creating new demo data with reduced task count...")
print(f"{'=' * 80}")

# Recreate demo data (will use the updated 20-25 tasks per board)
call_command('populate_test_data')

# Check final state
demo_orgs = Organization.objects.filter(name__in=demo_org_names)
demo_boards = Board.objects.filter(organization__in=demo_orgs)
total_tasks = Task.objects.filter(column__board__in=demo_boards).count()
overdue = Task.objects.filter(
    column__board__in=demo_boards,
    due_date__lt=django.utils.timezone.now(),
    progress__lt=100
).count()

print(f"\n{'=' * 80}")
print("✅ DEMO DATA RECREATED SUCCESSFULLY!")
print(f"{'=' * 80}")
print(f"\n📊 Final State:")
print(f"  Demo organizations: {demo_orgs.count()}")
print(f"  Demo boards: {demo_boards.count()}")
print(f"  Total tasks: {total_tasks}")
print(f"  Overdue tasks: {overdue}")

for board in demo_boards:
    task_count = Task.objects.filter(column__board=board).count()
    print(f"    - {board.name}: {task_count} tasks")

print(f"\n💡 Tip: Run 'python manage.py refresh_demo_dates' to refresh dates anytime!")
print(f"{'=' * 80}\n")
