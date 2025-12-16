"""
FINAL VERIFICATION: Demo Mode AI Resource Optimization

This test verifies the complete filtering behavior:
1. All users see demo users (john_doe, jane_smith, robert_johnson, alice_williams, bob_martinez, carol_anderson, david_taylor)
2. Real users only see other real users from their organization who are members of the board
3. Users don't see other users from their org unless they invited them (are both members)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board
from kanban.resource_leveling import ResourceLevelingService

demo_board = Board.objects.filter(organization__name='Dev Team').first()
service = ResourceLevelingService(demo_board.organization)

print("=" * 90)
print(" " * 25 + "FINAL VERIFICATION TEST")
print("=" * 90)

# Define expected demo users
demo_users = ['john_doe', 'jane_smith', 'robert_johnson', 'alice_williams', 'bob_martinez', 
              'carol_anderson', 'david_taylor', 'admin']

# Test scenarios
scenarios = [
    {
        'user': 'user7',
        'org': 'organization',
        'should_see': demo_users + ['user7', 'user8'],
        'should_not_see': ['user1', 'user3'],
        'reason': 'user7 invited user8, both are members'
    },
    {
        'user': 'user8',
        'org': 'organization', 
        'should_see': demo_users + ['user7', 'user8'],
        'should_not_see': ['user1', 'user3'],
        'reason': 'user8 was invited by user7, both are members'
    },
    {
        'user': 'user3',
        'org': 'organization',
        'should_see': demo_users + ['user3'],
        'should_not_see': ['user1', 'user7', 'user8'],
        'reason': 'user3 is alone, no other org members invited'
    },
    {
        'user': 'user1',
        'org': 'organization 1',
        'should_see': demo_users + ['user1'],
        'should_not_see': ['user3', 'user7', 'user8'],
        'reason': 'user1 is from different org'
    }
]

all_passed = True

for scenario in scenarios:
    username = scenario['user']
    user = User.objects.get(username=username)
    
    print(f"\n{'─' * 90}")
    print(f"Testing: {username} (Org: {scenario['org']})")
    print(f"Reason: {scenario['reason']}")
    print(f"{'─' * 90}")
    
    # Get report
    report = service.get_team_workload_report(demo_board, requesting_user=user)
    visible_members = [m['username'] for m in report['members']]
    
    # Check should_see
    print(f"\n✓ Should see ({len(scenario['should_see'])} users):")
    see_passed = True
    for expected in scenario['should_see']:
        is_visible = expected in visible_members
        status = "✓" if is_visible else "✗ FAIL"
        if not is_visible:
            see_passed = False
            all_passed = False
        print(f"  {status} {expected}")
    
    # Check should_not_see
    print(f"\n✗ Should NOT see ({len(scenario['should_not_see'])} users):")
    not_see_passed = True
    for unexpected in scenario['should_not_see']:
        is_visible = unexpected in visible_members
        status = "✓" if not is_visible else "✗ FAIL"
        if is_visible:
            not_see_passed = False
            all_passed = False
        print(f"  {status} {unexpected}")
    
    scenario_passed = see_passed and not_see_passed
    print(f"\nScenario result: {'✓ PASSED' if scenario_passed else '✗ FAILED'}")

print(f"\n{'=' * 90}")
print(f" " * 30 + "FINAL RESULT")
print(f"{'=' * 90}")
print(f"\n{'✓ ALL TESTS PASSED!' if all_passed else '✗ SOME TESTS FAILED'}")
print()

if all_passed:
    print("The AI Resource Optimization filtering is working correctly:")
    print("  1. All users can see demo users with their tasks")
    print("  2. Real users only see other real users from their org who are board members")
    print("  3. Invitation-based access control is enforced")
