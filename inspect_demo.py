"""Inspect demo data structure."""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()
from django.conf import settings
settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

from accounts.models import Organization, UserProfile
from kanban.models import Board, BoardMembership, Task, Mission, Strategy, DemoSandbox
from django.contrib.auth.models import User
from django.db.models import Count

# Demo org
print("=== ORGANIZATIONS ===")
for o in Organization.objects.all():
    print(f"  id={o.id} name={o.name!r} is_demo={o.is_demo}")

print("\n=== DEMO USERS ===")
for u in User.objects.filter(email__contains='demo.prizmai'):
    p = u.profile
    print(f"  id={u.id} username={u.username} org={p.organization_id}")

print("\n=== TESTUSER1 ===")
u1 = User.objects.get(username='testuser1')
p1 = u1.profile
print(f"  id={u1.id} org={p1.organization_id} is_viewing_demo={p1.is_viewing_demo}")

print("\n=== BOARD MEMBERSHIPS (demo board) ===")
for bm in BoardMembership.objects.filter(board__is_official_demo_board=True):
    print(f"  board={bm.board_id} user={bm.user.username} role={bm.role}")

print("\n=== DEMO BOARD TASKS ===")
board = Board.objects.filter(is_official_demo_board=True).first()
if board:
    print(f"  Board id={board.id} name={board.name!r} owner_id={board.owner_id}")
    stats = Task.objects.filter(column__board=board).values(
        'assigned_to__username'
    ).annotate(c=Count('id')).order_by('-c')
    for row in stats:
        print(f"  assigned_to={row['assigned_to__username']} count={row['c']}")
    print(f"  Total: {Task.objects.filter(column__board=board).count()}")
    # Show risk levels
    risk_stats = Task.objects.filter(column__board=board).values('risk_level').annotate(c=Count('id'))
    print(f"  Risk breakdown: {list(risk_stats)}")

print("\n=== DEMO SANDBOX ===")
for s in DemoSandbox.objects.all():
    print(f"  user={s.user.username} expires={s.expires_at}")

print("\n=== MISSIONS (demo) ===")
for m in Mission.objects.filter(is_demo=True):
    print(f"  id={m.id} name={m.name!r} created_by={m.created_by.username}")
    for s in m.strategies.all():
        print(f"    strategy id={s.id} name={s.name!r}")
        for b in s.boards.all():
            print(f"      board id={b.id} name={b.name!r}")
