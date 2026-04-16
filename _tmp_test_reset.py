"""Dry-run test of reset_my_demo flow for testuser2."""
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, DemoSandbox, Task
from kanban.sandbox_views import _purge_existing_sandbox, _reassign_demo_tasks_to_user
from kanban.utils.demo_protection import allow_demo_writes
from django.contrib.auth.models import User

user = User.objects.get(pk=49)  # testuser2

print("=== BEFORE PURGE ===")
sb_boards = Board.objects.filter(owner=user, is_sandbox_copy=True)
print(f"Sandbox boards: {list(sb_boards.values_list('name', 'id'))}")
try:
    sb = user.demo_sandbox
    print(f"DemoSandbox: id={sb.id}")
except DemoSandbox.DoesNotExist:
    print("No DemoSandbox")

print("\n=== PURGING ===")
_purge_existing_sandbox(user)

print("\n=== AFTER PURGE ===")
sb_boards = Board.objects.filter(owner=user, is_sandbox_copy=True)
print(f"Sandbox boards: {list(sb_boards.values_list('name', 'id'))}")
try:
    sb = user.demo_sandbox
    print(f"DemoSandbox still exists: id={sb.id}")
except DemoSandbox.DoesNotExist:
    print("DemoSandbox deleted correctly")

# Now simulate provisioning
from kanban.sandbox_views import _duplicate_board, _join_demo_org
from django.utils import timezone

template_boards = list(Board.objects.filter(is_official_demo_board=True).order_by('name'))
print(f"\nTemplate boards to clone: {[b.name for b in template_boards]}")

new_boards = []
with allow_demo_writes():
    for tmpl in template_boards:
        new_board = _duplicate_board(tmpl, user)
        new_boards.append(new_board)
        tc = Task.objects.filter(column__board=new_board).count()
        print(f"Cloned: {new_board.name} (id={new_board.id}, tasks={tc})")

    sb = DemoSandbox.objects.create(user=user, last_reset_at=timezone.now())
    _join_demo_org(user)
    _reassign_demo_tasks_to_user(sb, user)

print("\n=== AFTER PROVISION ===")
sb.refresh_from_db()
print(f"DemoSandbox: id={sb.id}, reassigned_tasks={sb.reassigned_tasks}")
for b in Board.objects.filter(owner=user, is_sandbox_copy=True):
    tc = Task.objects.filter(column__board=b).count()
    assigned = Task.objects.filter(column__board=b, assigned_to=user).count()
    print(f"  {b.name} (id={b.id}): {tc} tasks, {assigned} assigned to user")

print("\nDone!")
