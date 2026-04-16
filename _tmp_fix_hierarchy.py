"""Fix demo hierarchy: consolidate to 1 goal, 1 mission, 1 strategy, 1 board."""
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import OrganizationGoal, Mission, Strategy

# Current state:
# Goal 1 "Increase Market Share in Asia by 15%" (demo)
# Mission 1 "Prevent AI Security Threats" (demo, goal=1) -> Strategy 1 "Develop Security Software" (no boards)
# Mission 34 "Build Enterprise Security Platform" (demo, goal=None) -> Strategy 62 "Develop Security Software Platform" (board: Software Dev)
#
# Problem: 2 missions, 2 strategies shown, but only 1 chain actually connects to a board
# Fix: Link Mission 34 to Goal 1, delete orphan Mission 1 + Strategy 1

# Step 1: Link Mission 34 to Goal 1
m34 = Mission.objects.get(id=34)
print(f'Mission 34: "{m34.name}" goal_id={m34.organization_goal_id}')
m34.organization_goal_id = 1
m34.save(update_fields=['organization_goal_id'])
print(f'  -> Updated goal_id to 1')

# Step 2: Delete orphan Strategy 1 (no boards linked)
s1 = Strategy.objects.get(id=1)
print(f'\nStrategy 1: "{s1.name}" boards={list(s1.boards.values_list("id","name"))}')
s1.delete()
print('  -> Deleted')

# Step 3: Delete orphan Mission 1 (no strategies left)
m1 = Mission.objects.get(id=1)
print(f'\nMission 1: "{m1.name}" strategies={list(m1.strategies.values_list("id","name"))}')
m1.delete()
print('  -> Deleted')

# Verify
print('\n=== FINAL STATE ===')
for g in OrganizationGoal.objects.filter(is_demo=True):
    print(f'Goal: "{g.name}" (id={g.id})')
for m in Mission.objects.filter(is_demo=True):
    print(f'  Mission: "{m.name}" (id={m.id}, goal_id={m.organization_goal_id})')
    for s in m.strategies.all():
        boards = list(s.boards.values_list('id', 'name'))
        print(f'    Strategy: "{s.name}" (id={s.id}) -> boards: {boards}')
