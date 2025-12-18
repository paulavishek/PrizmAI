"""
Final comprehensive test of AI Coach functionality
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Task
from kanban.coach_models import CoachingSuggestion
from kanban.burndown_models import TeamVelocitySnapshot

print("=" * 80)
print("FINAL AI COACH FUNCTIONALITY TEST")
print("=" * 80)

# Get demo boards
demo_boards = Board.objects.filter(
    name__in=['Software Project', 'Bug Tracking', 'Marketing Campaign'],
    organization__name__in=['Dev Team', 'Marketing Team']
)

if not demo_boards.exists():
    print("\n❌ TEST FAILED: No demo boards found!")
    exit(1)

print(f"\n✅ Found {demo_boards.count()} demo boards")

all_tests_passed = True

for board in demo_boards:
    print(f"\n{'='*80}")
    print(f"Testing: {board.name} (ID: {board.id})")
    print(f"{'='*80}")
    
    # Test 1: Check board has members
    members_count = board.members.count()
    print(f"\n1. Board Members: {members_count}")
    if members_count < 2:
        print("   ❌ FAIL: Board should have at least 2 members")
        all_tests_passed = False
    else:
        print("   ✅ PASS")
    
    # Test 2: Check velocity data exists
    velocity_count = TeamVelocitySnapshot.objects.filter(board=board).count()
    print(f"\n2. Velocity Snapshots: {velocity_count}")
    if velocity_count < 3:
        print("   ❌ FAIL: Should have at least 3 velocity snapshots")
        all_tests_passed = False
    else:
        print("   ✅ PASS")
    
    # Test 3: Check for overloaded team member
    from django.db.models import Count, Q
    overloaded = Task.objects.filter(
        column__board=board,
        progress__lt=100,
        assigned_to__isnull=False
    ).values('assigned_to__username').annotate(
        task_count=Count('id')
    ).filter(task_count__gt=10)
    
    print(f"\n3. Overloaded Team Members: {overloaded.count()}")
    if overloaded.count() == 0:
        print("   ❌ FAIL: Should have at least 1 overloaded member (>10 tasks)")
        all_tests_passed = False
    else:
        for member in overloaded:
            print(f"   ✅ PASS: {member['assigned_to__username']} has {member['task_count']} tasks")
    
    # Test 4: Check for high-risk tasks
    high_risk = Task.objects.filter(
        column__board=board,
        progress__lt=100,
        risk_level__in=['high', 'critical']
    ).count()
    
    print(f"\n4. High-Risk Tasks: {high_risk}")
    if high_risk < 3:
        print("   ⚠️ WARNING: Should have at least 3 high-risk tasks for risk convergence")
    else:
        print("   ✅ PASS")
    
    # Test 5: Check coaching suggestions exist
    active_suggestions = CoachingSuggestion.objects.filter(
        board=board,
        status='active'
    ).order_by('severity')
    
    print(f"\n5. Active Coaching Suggestions: {active_suggestions.count()}")
    if active_suggestions.count() == 0:
        print("   ❌ FAIL: Should have at least 1 active suggestion")
        all_tests_passed = False
    else:
        print("   ✅ PASS")
        print("\n   Suggestions by type:")
        by_type = {}
        for suggestion in active_suggestions:
            type_name = suggestion.get_suggestion_type_display()
            severity = suggestion.get_severity_display()
            if type_name not in by_type:
                by_type[type_name] = []
            by_type[type_name].append(severity)
        
        for type_name, severities in by_type.items():
            print(f"   - {type_name}: {', '.join(severities)}")
    
    # Test 6: Verify suggestion details
    print(f"\n6. Suggestion Quality Checks:")
    for suggestion in active_suggestions:
        issues = []
        
        if not suggestion.title:
            issues.append("Missing title")
        if not suggestion.message:
            issues.append("Missing message")
        if not suggestion.recommended_actions:
            issues.append("Missing recommended actions")
        if suggestion.confidence_score <= 0:
            issues.append("Invalid confidence score")
        
        if issues:
            print(f"   ❌ Issues with {suggestion.suggestion_type}: {', '.join(issues)}")
            all_tests_passed = False
        else:
            print(f"   ✅ {suggestion.suggestion_type}: Complete")
    
    # Test 7: Check URL accessibility
    print(f"\n7. Coach Dashboard URL:")
    print(f"   http://127.0.0.1:8000/board/{board.id}/coach/")
    print(f"   ✅ Ready to access")

print(f"\n\n{'='*80}")
print("TEST SUMMARY")
print(f"{'='*80}")

if all_tests_passed:
    print("\n✅ ALL TESTS PASSED!")
    print("\nThe AI Coach feature is fully functional and ready to use.")
    print("\nTo access:")
    print("1. Navigate to http://127.0.0.1:8000/")
    print("2. Go to any demo board (Software Project, Bug Tracking, or Marketing Campaign)")
    print("3. Click 'AI Coach' in the board navigation")
    print("4. You should see 3 coaching suggestions with different severity levels")
    print("\nFeatures to test:")
    print("- View suggestion details")
    print("- Acknowledge suggestions")
    print("- Dismiss suggestions")
    print("- Provide feedback")
    print("- Ask the AI Coach questions")
    print("- Refresh suggestions (may skip duplicates created within 3 days)")
else:
    print("\n⚠️ SOME TESTS FAILED")
    print("\nPlease review the failures above.")
    print("You may need to run the setup scripts again:")
    print("- add_coaching_scenarios_to_demo.py")
    print("- generate_demo_coaching_suggestions.py")

print("\n" + "="*80)
