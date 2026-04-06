"""
Live workspace isolation test — runs against the real DB.
Usage: python test_workspace_isolation_live.py
"""
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import Organization, UserProfile
from kanban.models import Board, BoardMembership, Column, Task, Mission, Strategy, OrganizationGoal, Workspace
from kanban.utils.demo_protection import get_user_boards, get_user_missions, get_user_goals, get_demo_workspace
from kanban.sandbox_views import _join_demo_org, _leave_demo_org
from accounts.middleware import WorkspaceMiddleware

user = User.objects.get(username='testuser1')
profile = user.profile
real_org = Organization.objects.filter(created_by=user, is_demo=False).first()
real_ws = Workspace.objects.filter(created_by=user, is_demo=False, is_active=True).order_by('-created_at').first()
demo_org = Organization.objects.filter(is_demo=True).first()
demo_ws = Workspace.objects.filter(organization=demo_org, is_demo=True).first()

assert real_org, "No real org found for testuser1"
assert real_ws, "No real workspace found for testuser1"
assert demo_org, "No demo org found"
assert demo_ws, "No demo workspace found"

# Ensure clean state
profile.organization = real_org
profile.active_workspace = real_ws
profile.is_viewing_demo = False
profile.save(update_fields=['organization', 'active_workspace', 'is_viewing_demo'])

PASS = 0
FAIL = 0

def ck(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f'  PASS: {name}')
    else:
        FAIL += 1
        print(f'  FAIL: {name}')

# ═══════════════════════════════════════════════════════
print('=== Board isolation ===')
boards = get_user_boards(user)
names = set(boards.values_list('name', flat=True))
ck('Real boards visible in real mode', len(names) > 0)
ck('No sandbox in real mode', not boards.filter(is_sandbox_copy=True).exists())
ck('No official demo in real mode', not boards.filter(is_official_demo_board=True).exists())

profile.is_viewing_demo = True
profile.active_workspace = demo_ws
profile.save(update_fields=['is_viewing_demo', 'active_workspace'])
bd = get_user_boards(user)
nd = set(bd.values_list('name', flat=True))
sandbox_count = bd.filter(is_sandbox_copy=True).count()
ck('Sandbox visible in demo', sandbox_count > 0)
# Real workspace boards must NOT appear
real_board_names = set(Board.objects.filter(workspace=real_ws).values_list('name', flat=True))
leaked = nd & real_board_names
ck('No real boards leak into demo', len(leaked) == 0)
if leaked:
    print(f'    LEAKED: {leaked}')

# ═══════════════════════════════════════════════════════
print('\n=== Mission isolation ===')
md = get_user_missions(user)
mnd = set(md.values_list('name', flat=True))
ck('Demo missions in demo', md.filter(is_demo=True).exists() or md.filter(is_seed_demo_data=True).exists())
real_mission_names = set(Mission.objects.filter(workspace=real_ws).values_list('name', flat=True))
leaked_m = mnd & real_mission_names
ck('No real missions leak into demo', len(leaked_m) == 0)
if leaked_m:
    print(f'    LEAKED: {leaked_m}')

profile.is_viewing_demo = False
profile.active_workspace = real_ws
profile.save(update_fields=['is_viewing_demo', 'active_workspace'])
mr = get_user_missions(user)
mnr = set(mr.values_list('name', flat=True))
ck('Real missions in real', len(mnr) > 0)
ck('No demo missions in real', not mr.filter(is_demo=True).exists())
ck('No seed missions in real', not mr.filter(is_seed_demo_data=True).exists())

# ═══════════════════════════════════════════════════════
print('\n=== Goal isolation ===')
gr = get_user_goals(user)
gnr = set(gr.values_list('name', flat=True))
ck('Real goals in real', len(gnr) > 0)
ck('No demo goals in real', not gr.filter(is_demo=True).exists())
ck('No seed goals in real', not gr.filter(is_seed_demo_data=True).exists())

profile.is_viewing_demo = True
profile.active_workspace = demo_ws
profile.save(update_fields=['is_viewing_demo', 'active_workspace'])
gd = get_user_goals(user)
gnd = set(gd.values_list('name', flat=True))
ck('Demo goals in demo', gd.filter(is_demo=True).exists() or gd.filter(is_seed_demo_data=True).exists())
real_goal_names = set(OrganizationGoal.objects.filter(workspace=real_ws).values_list('name', flat=True))
leaked_g = gnd & real_goal_names
ck('No real goals leak into demo', len(leaked_g) == 0)
if leaked_g:
    print(f'    LEAKED: {leaked_g}')

# ═══════════════════════════════════════════════════════
print('\n=== Join/Leave demo org cycle ===')
profile.organization = real_org
profile.is_viewing_demo = False
profile.active_workspace = real_ws
profile.save(update_fields=['organization', 'is_viewing_demo', 'active_workspace'])

_join_demo_org(user)
profile.refresh_from_db()
ck('Join: org switched to demo', profile.organization_id == demo_org.id)

_leave_demo_org(user)
profile.refresh_from_db()
ck('Leave: org restored to real', profile.organization_id == real_org.id)
ck('Leave: org not None', profile.organization is not None)
ck('Leave: org is not demo', not profile.organization.is_demo)

# Double cycle
_join_demo_org(user)
profile.refresh_from_db()
_leave_demo_org(user)
profile.refresh_from_db()
ck('Double cycle: org still real', profile.organization_id == real_org.id)

# ═══════════════════════════════════════════════════════
print('\n=== get_demo_workspace independence ===')
profile.organization = real_org
profile.save(update_fields=['organization'])
ws = get_demo_workspace()
ck('Found from real org context', ws is not None and ws.is_demo)

# ═══════════════════════════════════════════════════════
print('\n=== Middleware heal ===')

# Case 1: demo=True, ws=None
profile.is_viewing_demo = True
profile.active_workspace = None
profile.save(update_fields=['is_viewing_demo', 'active_workspace'])
WorkspaceMiddleware._heal_workspace_state(profile)
profile.refresh_from_db()
ck('Heal case 1: demo+no ws -> demo ws', profile.active_workspace is not None and profile.active_workspace.is_demo)

# Case 2: demo=False, org=demo_org
profile.is_viewing_demo = False
profile.organization = demo_org
profile.active_workspace = None
profile.save(update_fields=['is_viewing_demo', 'organization', 'active_workspace'])
WorkspaceMiddleware._heal_workspace_state(profile)
profile.refresh_from_db()
ck('Heal case 2: non-demo+demo org -> real org', profile.organization_id == real_org.id)
ck('Heal case 2: non-demo+demo org -> real ws', profile.active_workspace_id == real_ws.id)

# Case 3: demo=True, ws=real_ws (wrong ws type)
profile.is_viewing_demo = True
profile.active_workspace = real_ws
profile.save(update_fields=['is_viewing_demo', 'active_workspace'])
WorkspaceMiddleware._heal_workspace_state(profile)
profile.refresh_from_db()
ck('Heal case 3: demo+real ws -> demo ws', profile.active_workspace.is_demo)

# ═══════════════════════════════════════════════════════
# Restore clean state
profile.organization = real_org
profile.active_workspace = real_ws
profile.is_viewing_demo = False
profile.save(update_fields=['organization', 'active_workspace', 'is_viewing_demo'])

print(f'\n{"="*50}')
print(f'RESULTS: {PASS} passed, {FAIL} failed')
print(f'{"="*50}')
sys.exit(1 if FAIL > 0 else 0)
