"""Comprehensive diagnostic of all Spectra context data for board 78."""
import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'kanban_board.settings'
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board, Task, Column
from django.db.models import Count, Q
from django.utils import timezone

user = User.objects.get(username='testuser1')
board = Board.objects.get(id=78)

print("=" * 60)
print(f"BOARD: {board.name} (id={board.id})")
print(f"  owner={board.owner}, created_by={board.created_by}")
print(f"  strategy_id={board.strategy_id}")
print("=" * 60)

# 1. Tasks
print("\n=== TASKS ===")
tasks = Task.objects.filter(column__board=board, item_type='task').select_related('column', 'assigned_to')
print(f"Total tasks: {tasks.count()}")
for t in tasks.order_by('column__position', 'title'):
    assignee = t.assigned_to.get_full_name() or t.assigned_to.username if t.assigned_to else 'Unassigned'
    print(f"  [{t.column.name}] {t.title} | Assigned: {assignee} | Priority: {t.priority} | Due: {t.due_date}")

# 2. Milestones
print("\n=== MILESTONES ===")
milestones = Task.objects.filter(column__board=board).exclude(item_type='task')
print(f"Total non-task items: {milestones.count()}")
for m in milestones.order_by('due_date'):
    print(f"  [{m.item_type}] {m.title} | Due: {m.due_date} | Column: {m.column.name}")

# 3. Task counts by assignee
print("\n=== TASK COUNTS BY ASSIGNEE ===")
from django.db.models import Count
assignee_counts = tasks.values('assigned_to__first_name', 'assigned_to__last_name', 'assigned_to__username').annotate(count=Count('id')).order_by('-count')
for ac in assignee_counts:
    name = f"{ac['assigned_to__first_name'] or ''} {ac['assigned_to__last_name'] or ''}".strip() or ac['assigned_to__username'] or 'Unassigned'
    print(f"  {name}: {ac['count']}")

# 4. Overdue tasks
print("\n=== OVERDUE TASKS ===")
today = timezone.now().date()
overdue = tasks.filter(due_date__lt=today, progress__lt=100)
for t in overdue:
    assignee = t.assigned_to.get_full_name() or t.assigned_to.username if t.assigned_to else 'Unassigned'
    print(f"  {t.title} | Due: {t.due_date} | Assigned: {assignee} | Progress: {t.progress}%")

# 5. Dependencies
print("\n=== DEPENDENCIES ===")
all_items = Task.objects.filter(column__board=board)
deps_parent = all_items.filter(parent_task__isnull=False).select_related('parent_task')
print(f"Tasks with parent_task set: {deps_parent.count()}")
for t in deps_parent:
    print(f"  {t.title} -> depends on: {t.parent_task.title}")

# Check for ManyToMany dependencies field
print(f"\nHas 'dependencies' field: {hasattr(Task, 'dependencies')}")
if hasattr(Task, 'dependencies'):
    for t in all_items:
        deps = t.dependencies.all()
        if deps.exists():
            print(f"  {t.title} depends on: {', '.join(d.title for d in deps)}")

# 6. Strategic hierarchy
print("\n=== STRATEGIC HIERARCHY ===")
print(f"Board strategy_id: {board.strategy_id}")
if board.strategy_id:
    strategy = board.strategy
    print(f"Strategy: {strategy.name} (status={strategy.status})")
    mission = strategy.mission if hasattr(strategy, 'mission') else None
    print(f"Mission: {mission}")
    if mission:
        goal = mission.organization_goal if hasattr(mission, 'organization_goal') else None
        print(f"Goal: {goal}")

# Check if there are any goals/missions at all
print("\n=== ALL GOALS/MISSIONS/STRATEGIES ===")
try:
    from kanban.models import OrganizationGoal, Mission, Strategy
    goals = OrganizationGoal.objects.all()
    print(f"Total goals: {goals.count()}")
    for g in goals:
        print(f"  Goal: {g.name} (org={g.organization})")
    
    missions = Mission.objects.all()
    print(f"Total missions: {missions.count()}")
    for m in missions:
        print(f"  Mission: {m.name} (goal={m.organization_goal}, status={m.status})")
    
    strategies = Strategy.objects.all()
    print(f"Total strategies: {strategies.count()}")
    for s in strategies:
        print(f"  Strategy: {s.name} (mission={s.mission}, status={s.status})")
        # Check boards linked to this strategy
        linked_boards = Board.objects.filter(strategy=s)
        for b in linked_boards:
            print(f"    -> Board: {b.name} (id={b.id})")
except ImportError as e:
    print(f"Import error: {e}")

# 7. Wiki pages
print("\n=== WIKI PAGES ===")
try:
    from wiki.models import WikiPage
    pages = WikiPage.objects.all()
    print(f"Total wiki pages: {pages.count()}")
    for p in pages:
        print(f"  {p.title} (board={getattr(p, 'board_id', None)}, workspace={getattr(p, 'workspace_id', None)})")
except Exception as e:
    print(f"Wiki error: {e}")

# 8. Columns
print("\n=== COLUMNS ===")
for col in Column.objects.filter(board=board).order_by('position'):
    task_count = Task.objects.filter(column=col, item_type='task').count()
    milestone_count = Task.objects.filter(column=col).exclude(item_type='task').count()
    print(f"  {col.name} (pos={col.position}): {task_count} tasks, {milestone_count} milestones")
