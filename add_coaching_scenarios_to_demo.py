"""
Add realistic coaching scenarios to demo boards
This will create patterns that trigger AI Coach suggestions
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Task, Column
from kanban.burndown_models import TeamVelocitySnapshot
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta, date
import random

print("=" * 80)
print("ADDING COACHING SCENARIOS TO DEMO BOARDS")
print("=" * 80)

# Get demo boards
demo_boards = Board.objects.filter(
    name__in=['Software Project', 'Bug Tracking', 'Marketing Campaign'],
    organization__name__in=['Dev Team', 'Marketing Team']
)

if not demo_boards.exists():
    print("\n❌ No demo boards found!")
    exit(1)

for board in demo_boards:
    print(f"\n\n{'='*80}")
    print(f"BOARD: {board.name}")
    print(f"{'='*80}")
    
    # Get board members
    members = list(board.members.all())
    if len(members) < 2:
        print("⚠️ Not enough members, skipping")
        continue
    
    # Get columns
    columns = list(board.columns.all())
    if not columns:
        print("⚠️ No columns found, skipping")
        continue
    
    # Find or create appropriate columns
    backlog = board.columns.filter(name__icontains='backlog').first() or columns[0]
    in_progress = board.columns.filter(name__icontains='progress').first() or columns[1] if len(columns) > 1 else columns[0]
    
    print(f"\nUsing columns: Backlog='{backlog.name}', In Progress='{in_progress.name}'")
    
    # SCENARIO 1: Create overloaded team member (>10 tasks)
    print("\n1. Creating RESOURCE OVERLOAD scenario...")
    overloaded_member = members[0]
    print(f"   Making {overloaded_member.username} overloaded with 12 tasks...")
    
    # Create 12 active tasks for this member
    for i in range(12):
        priority = 'high' if i < 6 else 'medium'
        Task.objects.create(
            column=in_progress,
            title=f"Task for {overloaded_member.username} #{i+1}",
            description=f"This is task {i+1} assigned to create workload",
            assigned_to=overloaded_member,
            created_by=overloaded_member,
            priority=priority,
            progress=random.randint(10, 70),
            due_date=date.today() + timedelta(days=random.randint(5, 20)),
            risk_level='low'
        )
    print(f"   ✓ Created 12 tasks for {overloaded_member.username} (6 high priority)")
    
    # SCENARIO 2: Create velocity drop
    print("\n2. Creating VELOCITY DROP scenario...")
    # Find existing velocity snapshots
    snapshots = TeamVelocitySnapshot.objects.filter(board=board).order_by('-period_end')
    
    if snapshots.count() >= 3:
        print("   Modifying velocity data to show significant drop...")
        # Get the most recent 3 snapshots
        recent = list(snapshots[:3])
        
        # Make the latest one much lower
        recent[0].tasks_completed = 2  # Recent dropped to 2
        recent[0].save()
        
        # Make previous ones higher to show the drop
        recent[1].tasks_completed = 10
        recent[1].save()
        recent[2].tasks_completed = 12
        recent[2].save()
        
        print(f"   ✓ Velocity: {recent[2].tasks_completed} → {recent[1].tasks_completed} → {recent[0].tasks_completed} tasks/week")
        print(f"   ✓ This is a ~80% drop, which will trigger a HIGH severity alert")
    else:
        print("   ℹ️ Not enough velocity snapshots to modify")
    
    # SCENARIO 3: Create high-risk task convergence
    print("\n3. Creating RISK CONVERGENCE scenario...")
    target_week = date.today() + timedelta(days=7)
    
    # Create 4 high-risk tasks all due in the same week
    for i in range(4):
        assigned_member = random.choice(members)
        Task.objects.create(
            column=in_progress,
            title=f"High-Risk Task #{i+1}",
            description=f"Critical task with high risk level",
            assigned_to=assigned_member,
            created_by=assigned_member,
            priority='high',
            risk_level='high' if i < 3 else 'critical',
            progress=random.randint(10, 40),
            due_date=target_week + timedelta(days=i),  # All within same week
        )
    print(f"   ✓ Created 4 high/critical risk tasks all due week of {target_week.strftime('%B %d')}")
    
    # SCENARIO 4: Create deadline risk (many tasks due soon)
    print("\n4. Creating DEADLINE RISK scenario...")
    near_deadline = date.today() + timedelta(days=5)
    
    # Create 5 tasks all due very soon with low progress
    for i in range(5):
        assigned_member = random.choice(members)
        Task.objects.create(
            column=in_progress,
            title=f"Urgent Task #{i+1}",
            description=f"Task due very soon with low progress",
            assigned_to=assigned_member,
            created_by=assigned_member,
            priority='high',
            progress=random.randint(5, 25),  # Low progress
            due_date=near_deadline + timedelta(days=random.randint(0, 2)),
            risk_level='medium'
        )
    print(f"   ✓ Created 5 tasks due in next 5-7 days with <30% progress")
    
    print(f"\n✅ Scenarios added to {board.name}")

print("\n\n" + "=" * 80)
print("DONE! Testing the rule engine with new data...")
print("=" * 80)

# Now test the rule engine
from kanban.utils.coaching_rules import CoachingRuleEngine

for board in demo_boards:
    print(f"\n\n{'='*80}")
    print(f"Testing: {board.name}")
    print(f"{'='*80}")
    
    rule_engine = CoachingRuleEngine(board)
    suggestions = rule_engine.analyze_and_generate_suggestions()
    
    print(f"\n✅ Generated {len(suggestions)} suggestion(s):")
    for i, suggestion in enumerate(suggestions, 1):
        print(f"\n{i}. {suggestion['suggestion_type'].upper()}")
        print(f"   Severity: {suggestion['severity']}")
        print(f"   Title: {suggestion['title']}")
        print(f"   Confidence: {suggestion['confidence_score']}")

print("\n\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("\nDemo boards now have realistic coaching scenarios:")
print("✓ Resource overload (>10 tasks per member)")
print("✓ Velocity drop (~80% decrease)")
print("✓ High-risk tasks converging in time")
print("✓ Deadline risks (tasks due soon with low progress)")
print("\nRefresh the AI Coach page to see the new suggestions!")
print("\nNote: The coaching suggestions are stored separately, so you may need to")
print("click 'Refresh Suggestions' button in the AI Coach dashboard.")
