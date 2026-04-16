import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import OrganizationGoal, Mission, Strategy, Board

print('=== GOALS ===')
for g in OrganizationGoal.objects.all():
    print(f'  id={g.id} name="{g.name}" is_demo={g.is_demo} is_seed={g.is_seed_demo_data} org_id={g.organization_id}')

print('\n=== MISSIONS ===')
for m in Mission.objects.all():
    print(f'  id={m.id} name="{m.name}" is_demo={m.is_demo} is_seed={m.is_seed_demo_data} goal_id={m.organization_goal_id}')

print('\n=== STRATEGIES ===')
for s in Strategy.objects.all():
    is_demo = getattr(s, 'is_demo', 'N/A')
    is_seed = getattr(s, 'is_seed_demo_data', 'N/A')
    print(f'  id={s.id} name="{s.name}" is_demo={is_demo} is_seed={is_seed} mission_id={s.mission_id}')

print('\n=== STRATEGY->BOARD LINKS ===')
for s in Strategy.objects.prefetch_related('boards').all():
    boards = list(s.boards.values_list('id', 'name'))
    print(f'  strategy={s.id} "{s.name}" -> boards: {boards}')
