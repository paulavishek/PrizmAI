import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'kanban_board.settings'
django.setup()
from kanban.models import Task, Board
from wiki.models import WikiPage
from django.utils import timezone

board = Board.objects.get(id=78)
today = timezone.now().date()

print('=== TASKS ===')
tasks = Task.objects.filter(column__board=board, item_type='task').select_related('column','assigned_to').prefetch_related('dependencies').order_by('column__position','title')
for t in tasks:
    deps = [d.title for d in t.dependencies.all()]
    assignee = t.assigned_to.get_full_name() if t.assigned_to else 'Unassigned'
    due_str = ''
    if t.due_date:
        d = t.due_date.date() if hasattr(t.due_date, 'date') else t.due_date
        due_str = f' due={d}' + (' OVERDUE' if d < today else '')
    dep_str = f' dep_of=[{deps[0]}]' if deps else ''
    print(f'  [{t.column.name}] {t.title} | {assignee} | {t.priority} | risk={t.risk_level}{due_str}{dep_str}')

print()
print('=== MILESTONES ===')
for m in Task.objects.filter(column__board=board).exclude(item_type='task').select_related('column').order_by('due_date'):
    d = m.due_date.date() if m.due_date and hasattr(m.due_date, 'date') else m.due_date
    print(f'  [{m.column.name}] {m.title} | due={d}')

print()
print('=== WIKI PAGES ===')
for p in WikiPage.objects.filter(organization_id=1, is_published=True).order_by('title'):
    print(f'  {p.title}')

print()
print('=== GOALS/MISSIONS/STRATEGIES ===')
from kanban.models import OrganizationGoal, Mission, Strategy
for g in OrganizationGoal.objects.filter(is_demo=True):
    print(f'  Goal: {g.name}')
    for m in g.missions.all():
        print(f'    Mission: {m.name} ({m.status})')
        for s in m.strategies.all():
            print(f'      Strategy: {s.name} ({s.status})')
