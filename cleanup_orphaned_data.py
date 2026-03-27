"""One-time cleanup of testuser1's orphaned Tier 2 sandbox data."""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

# Override cache to avoid Redis retries during deletion
from django.conf import settings
settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

from kanban.models import Board, Task, Mission, DemoSandbox
from django.contrib.auth.models import User

user = User.objects.get(username='testuser1')

# 1. Delete orphaned boards (old Tier 2 sandbox copies without is_sandbox_copy flag)
orphan_boards = Board.objects.filter(
    owner=user,
    is_official_demo_board=False,
    is_seed_demo_data=False,
    is_sandbox_copy=False,
)
print(f"Orphaned boards to delete: {list(orphan_boards.values_list('id', 'name'))}")
orphan_boards.delete()

# 2. Delete missions created by testuser1 during demo exploration
orphan_missions = Mission.objects.filter(
    created_by=user, is_demo=False, is_seed_demo_data=False,
)
print(f"Orphaned missions to delete: {list(orphan_missions.values_list('id', 'name'))}")
orphan_missions.delete()

# 3. Delete stale DemoSandbox record
try:
    sandbox = user.demo_sandbox
    print(f"Deleting stale DemoSandbox (id={sandbox.id})")
    sandbox.delete()
except DemoSandbox.DoesNotExist:
    print("No existing DemoSandbox")

print("Cleanup complete.")
print(f"Remaining boards for testuser1: {list(Board.objects.filter(owner=user).values_list('id', 'name'))}")
print(f"Remaining missions by testuser1: {list(Mission.objects.filter(created_by=user).values_list('id', 'name'))}")
print(f"Remaining tasks assigned to testuser1: {Task.objects.filter(assigned_to=user).count()}")
