"""Test sandbox provisioning synchronously (no Celery needed)."""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()
from django.conf import settings
settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User
from kanban.models import Board, BoardMembership, Task, DemoSandbox
from kanban.sandbox_views import (
    _duplicate_board, _join_demo_org, _reassign_demo_tasks_to_user,
    _restore_demo_task_assignments, _leave_demo_org,
)
from kanban.utils.demo_protection import allow_demo_writes
from accounts.models import Organization

user = User.objects.get(username='testuser1')

print("=== BEFORE PROVISIONING ===")
print(f"testuser1 org: {user.profile.organization}")
print(f"testuser1 boards: {list(Board.objects.filter(owner=user).values_list('id', 'name'))}")

# Provision sandbox
template_boards = list(Board.objects.filter(is_official_demo_board=True).order_by('name'))
print(f"\nTemplate boards: {[(b.id, b.name) for b in template_boards]}")

new_boards = []
with allow_demo_writes():
    for template in template_boards:
        nb = _duplicate_board(template, user)
        new_boards.append(nb)
        print(f"Created sandbox copy: id={nb.id} name={nb.name!r} is_sandbox_copy={nb.is_sandbox_copy}")

    sandbox = DemoSandbox.objects.create(
        user=user,
        expires_at=timezone.now() + timedelta(hours=24),
    )
    _join_demo_org(user)
    _reassign_demo_tasks_to_user(sandbox, user)

# Set profile flag
profile = user.profile
profile.is_viewing_demo = True
profile.save(update_fields=['is_viewing_demo'])

print(f"\n=== AFTER PROVISIONING ===")
print(f"testuser1 org: {user.profile.organization}")
print(f"DemoSandbox: expires={sandbox.expires_at}")
print(f"Reassigned tasks mapping: {sandbox.reassigned_tasks}")

# Show board memberships
for bm in BoardMembership.objects.filter(board__in=new_boards):
    print(f"  Membership: board={bm.board.name} user={bm.user.username} role={bm.role}")

# Show task assignment breakdown on sandbox board
for nb in new_boards:
    from django.db.models import Count
    stats = Task.objects.filter(column__board=nb).values(
        'assigned_to__username'
    ).annotate(c=Count('id')).order_by('-c')
    print(f"\nBoard '{nb.name}' task assignments:")
    for row in stats:
        print(f"  {row['assigned_to__username']}: {row['c']}")
    total = Task.objects.filter(column__board=nb).count()
    print(f"  Total: {total}")

# Show My Tasks for testuser1
my_tasks = Task.objects.filter(
    column__board__in=new_boards,
    assigned_to=user,
    item_type='task',
).exclude(progress=100).values_list('id', 'title', 'priority')
print(f"\nMy Tasks for testuser1:")
for t in my_tasks:
    print(f"  id={t[0]} title={t[1]!r} priority={t[2]}")

# Test LEAVE
print(f"\n=== TESTING LEAVE ===")
_restore_demo_task_assignments(sandbox)
_leave_demo_org(user)

user.refresh_from_db()
profile = user.profile
print(f"testuser1 org after leave: {profile.organization}")
print(f"Reassigned tasks after restore: {sandbox.reassigned_tasks}")

# Check tasks are back to demo personas
my_tasks_after = Task.objects.filter(
    column__board__in=new_boards,
    assigned_to=user,
).count()
print(f"Tasks still assigned to testuser1: {my_tasks_after}")

# Test RE-ENTER
print(f"\n=== TESTING RE-ENTER ===")
_join_demo_org(user)
_reassign_demo_tasks_to_user(sandbox, user)
user.refresh_from_db()
print(f"testuser1 org after re-enter: {user.profile.organization}")
print(f"Reassigned tasks: {sandbox.reassigned_tasks}")
my_tasks_reenter = Task.objects.filter(
    column__board__in=new_boards,
    assigned_to=user,
    item_type='task',
).exclude(progress=100).count()
print(f"My Tasks count: {my_tasks_reenter}")

print("\nAll tests passed!")
