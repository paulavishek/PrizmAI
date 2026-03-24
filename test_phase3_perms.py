"""Phase 3 RBAC verification — Upward Visibility Rule."""
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'kanban_board.settings'
django.setup()

from kanban.models import Board, Strategy, Mission, BoardMembership

boards = Board.objects.filter(strategy__isnull=False).select_related(
    'strategy__mission__organization_goal'
)
board = boards.first()
strategy = board.strategy
mission = strategy.mission
goal = mission.organization_goal

memberships = BoardMembership.objects.filter(board=board, role='member')
if not memberships.exists():
    print('No board members found — skipping')
    exit()

user = memberships.first().user
print(f'Board member: {user.username}')
print(f'Board: {board.name}')
print(f'Strategy: {strategy.name}')
print(f'Mission: {mission.name}')
if goal:
    print(f'Goal: {goal.name}')

# View checks (should be True via descendant board membership)
view_strategy = user.has_perm('prizmai.view_strategy', strategy)
view_mission = user.has_perm('prizmai.view_mission', mission)
view_goal = user.has_perm('prizmai.view_goal', goal) if goal else 'N/A'

# Edit checks (should be False - upward boundary)
edit_strategy = user.has_perm('prizmai.edit_strategy', strategy)
edit_mission = user.has_perm('prizmai.edit_mission', mission)
edit_goal = user.has_perm('prizmai.edit_goal', goal) if goal else 'N/A'

print(f'  view_strategy: {view_strategy} (expect True)')
print(f'  view_mission:  {view_mission} (expect True)')
print(f'  view_goal:     {view_goal} (expect True)')
print(f'  edit_strategy: {edit_strategy} (expect False)')
print(f'  edit_mission:  {edit_mission} (expect False)')
print(f'  edit_goal:     {edit_goal} (expect False)')

failures = []
if not view_strategy:
    failures.append('view_strategy should be True')
if not view_mission:
    failures.append('view_mission should be True')
if goal and not view_goal:
    failures.append('view_goal should be True')
# Only check edit=False if user is NOT also the record owner/creator/OrgAdmin
is_strategy_owner = (strategy.owner == user or strategy.created_by == user)
is_mission_owner = (mission.owner == user or mission.created_by == user)
is_org_admin = user.groups.filter(name='OrgAdmin').exists()

if not is_strategy_owner and not is_org_admin and edit_strategy:
    failures.append('edit_strategy should be False for pure board member')
if not is_mission_owner and not is_org_admin and edit_mission:
    failures.append('edit_mission should be False for pure board member')

if failures:
    for f in failures:
        print(f'  FAIL: {f}')
else:
    print('  UPWARD READ-ONLY VISIBILITY: PASS')
