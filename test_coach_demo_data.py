"""
Test script to diagnose why AI Coach is not generating suggestions for demo boards
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Task
from kanban.burndown_models import TeamVelocitySnapshot
from kanban.coach_models import CoachingSuggestion
from kanban.utils.coaching_rules import CoachingRuleEngine
from datetime import datetime, timedelta

print("=" * 80)
print("AI COACH DIAGNOSTIC FOR DEMO BOARDS")
print("=" * 80)

# Get demo boards
demo_board_names = ['Software Project', 'Bug Tracking', 'Marketing Campaign']
demo_boards = Board.objects.filter(
    name__in=demo_board_names,
    organization__name__in=['Dev Team', 'Marketing Team']
)

if not demo_boards.exists():
    print("\n❌ No demo boards found!")
    exit(1)

print(f"\nFound {demo_boards.count()} demo boards\n")

for board in demo_boards:
    print(f"\n{'='*80}")
    print(f"BOARD: {board.name} (ID: {board.id})")
    print(f"Organization: {board.organization.name}")
    print(f"{'='*80}")
    
    # 1. Check board members
    members = board.members.all()
    print(f"\n1. BOARD MEMBERS: {members.count()}")
    if members.count() > 0:
        print(f"   Members: {', '.join([m.username for m in members])}")
    else:
        print("   ⚠️ No members found!")
    
    # 2. Check tasks
    all_tasks = Task.objects.filter(column__board=board)
    active_tasks = all_tasks.filter(progress__lt=100, progress__isnull=False)
    high_priority = all_tasks.filter(priority='high')
    print(f"\n2. TASKS:")
    print(f"   Total tasks: {all_tasks.count()}")
    print(f"   Active tasks: {active_tasks.count()}")
    print(f"   High priority: {high_priority.count()}")
    
    # Check task assignments
    assigned_tasks = active_tasks.exclude(assigned_to__isnull=True)
    print(f"   Assigned tasks: {assigned_tasks.count()}")
    if assigned_tasks.count() == 0:
        print("   ⚠️ WARNING: No active tasks are assigned to team members!")
    
    # 3. Check velocity data
    velocity_snapshots = TeamVelocitySnapshot.objects.filter(board=board).order_by('-period_end')[:4]
    print(f"\n3. VELOCITY DATA:")
    print(f"   Velocity snapshots: {velocity_snapshots.count()}")
    if velocity_snapshots.count() > 0:
        for snapshot in velocity_snapshots:
            print(f"   - {snapshot.period_start} to {snapshot.period_end}: "
                  f"{snapshot.tasks_completed} tasks completed")
    else:
        print("   ⚠️ WARNING: No velocity data found!")
        print("   AI Coach needs velocity data to detect patterns")
    
    # 4. Check for overloaded team members
    from django.db.models import Count, Q
    workload_data = Task.objects.filter(
        column__board=board,
        progress__lt=100,
        assigned_to__isnull=False
    ).values('assigned_to__username').annotate(
        task_count=Count('id'),
        high_priority_count=Count('id', filter=Q(priority='high'))
    )
    
    print(f"\n4. TEAM WORKLOAD:")
    if workload_data.count() > 0:
        for member in workload_data:
            print(f"   {member['assigned_to__username']}: {member['task_count']} tasks "
                  f"({member['high_priority_count']} high priority)")
            if member['task_count'] > 10:
                print(f"      ⚠️ OVERLOADED (>10 tasks)")
    else:
        print("   ⚠️ No workload data (no assigned tasks)")
    
    # 5. Check for high-risk tasks
    high_risk_tasks = Task.objects.filter(
        column__board=board,
        progress__lt=100,
        risk_level__in=['high', 'critical']
    )
    print(f"\n5. RISK MANAGEMENT:")
    print(f"   High/Critical risk tasks: {high_risk_tasks.count()}")
    if high_risk_tasks.count() == 0:
        print("   ℹ️ No high-risk tasks to trigger risk convergence checks")
    
    # 6. Check existing coaching suggestions
    existing_suggestions = CoachingSuggestion.objects.filter(
        board=board,
        status='active'
    )
    print(f"\n6. EXISTING COACHING SUGGESTIONS:")
    print(f"   Active suggestions: {existing_suggestions.count()}")
    if existing_suggestions.count() > 0:
        for suggestion in existing_suggestions:
            print(f"   - {suggestion.suggestion_type}: {suggestion.title}")
    
    # 7. Test rule engine
    print(f"\n7. TESTING RULE ENGINE:")
    print("   Running CoachingRuleEngine...")
    try:
        rule_engine = CoachingRuleEngine(board)
        suggestions_data = rule_engine.analyze_and_generate_suggestions()
        print(f"   ✅ Rule engine generated {len(suggestions_data)} suggestion(s)")
        
        if len(suggestions_data) > 0:
            print("\n   Generated suggestions:")
            for i, suggestion in enumerate(suggestions_data, 1):
                print(f"   {i}. {suggestion['suggestion_type']}: {suggestion['title']}")
                print(f"      Severity: {suggestion['severity']}, Confidence: {suggestion['confidence_score']}")
        else:
            print("   ℹ️ No suggestions generated - board appears healthy")
            print("\n   POSSIBLE REASONS:")
            print("   - Not enough velocity data (need 3+ snapshots)")
            print("   - No team members are overloaded (>10 tasks)")
            print("   - No high-risk tasks converging")
            print("   - No significant velocity drop detected")
            print("   - All metrics are within healthy ranges")
            
    except Exception as e:
        print(f"   ❌ Error running rule engine: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 80)
print("DIAGNOSTIC SUMMARY")
print("=" * 80)
print("\nFor AI Coach to generate suggestions, the system needs:")
print("1. ✓ Team velocity data (3+ snapshots showing task completion over time)")
print("2. ✓ Active tasks with assignments (to detect overload)")
print("3. ✓ High-risk tasks with due dates (to detect risk convergence)")
print("4. ✓ Velocity drops or other pattern anomalies")
print("\nIf everything appears healthy, AI Coach correctly shows 'All Looking Good!'")
print("\nTo create conditions for coaching suggestions:")
print("- Run: python manage.py generate_coach_suggestions --board-id <ID> --force")
print("- Or ensure demo boards have the necessary data patterns")
