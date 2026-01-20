import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
import django
django.setup()

from kanban.models import Task, Board
from django.db.models import Min, Max

board = Board.objects.filter(name='Software Development', is_official_demo_board=True).first()
print(f"Board: {board.name} (ID: {board.id})")

tasks = Task.objects.filter(column__board=board).order_by('phase', 'start_date')
print(f"Total tasks: {tasks.count()}")

for phase in ['Phase 1', 'Phase 2', 'Phase 3']:
    phase_tasks = tasks.filter(phase=phase)
    agg = phase_tasks.aggregate(min_start=Min('start_date'), max_due=Max('due_date'))
    print(f"\n{phase}: {phase_tasks.count()} items")
    print(f"  Start: {agg['min_start']}")
    print(f"  End: {agg['max_due']}")
    
    # Show first 3 tasks in each phase
    for t in phase_tasks[:3]:
        print(f"    - {t.title[:40]}: {t.start_date} to {t.due_date} ({t.item_type})")
