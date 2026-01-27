"""Delete the manually created task and reset demo"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Task, Board, Organization

# First, let's count tasks before deletion
demo_org = Organization.objects.filter(is_demo=True).first()
demo_boards = Board.objects.filter(organization=demo_org, is_official_demo_board=True)
total_before = Task.objects.filter(column__board__in=demo_boards).count()

print(f"Tasks before deletion: {total_before}")

# Delete the manually created task (ID 6215)
try:
    task = Task.objects.get(id=6215)
    print(f"Deleting: {task.title} (ID: {task.id})")
    task.delete()
    print("✅ Task deleted successfully")
except Task.DoesNotExist:
    print("⚠️ Task already deleted or not found")

# Count after deletion
total_after = Task.objects.filter(column__board__in=demo_boards).count()
print(f"Tasks after deletion: {total_after}")
