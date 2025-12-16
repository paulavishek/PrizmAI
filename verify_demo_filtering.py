"""
Verify the filtering works correctly:
1. Demo users are visible to everyone
2. Only invited real users from same org are visible
3. Non-invited users from same org are NOT visible
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board
from kanban.resource_leveling import ResourceLevelingService

demo_board = Board.objects.filter(organization__name='Dev Team').first()

print("=" * 80)
print("VERIFICATION: AI RESOURCE OPTIMIZATION FILTERING")
print("=" * 80)

# Test as user7
print("\n1. USER7's VIEW (invited user8)")
print("-" * 80)
user7 = User.objects.get(username='user7')
service = ResourceLevelingService(demo_board.organization)
report = service.get_team_workload_report(demo_board, requesting_user=user7)

print(f"Organization: {user7.profile.organization.name}")
print(f"Visible team members: {report['team_size']}")
print("\nMembers:")
for member in report['members']:
    print(f"  ✓ {member['username']}: {member['active_tasks']} tasks")

# Test as user1 (different org)
print("\n\n2. USER1's VIEW (from 'organization 1')")
print("-" * 80)
user1 = User.objects.get(username='user1')
report = service.get_team_workload_report(demo_board, requesting_user=user1)

print(f"Organization: {user1.profile.organization.name}")
print(f"Visible team members: {report['team_size']}")
print("\nMembers:")
for member in report['members']:
    print(f"  ✓ {member['username']}: {member['active_tasks']} tasks")

# Test as user3 (from 'organization' but NOT invited by user7)
print("\n\n3. USER3's VIEW (from 'organization' but NOT invited)")
print("-" * 80)
user3 = User.objects.get(username='user3')

# Check if user3 is a member
is_member = user3 in demo_board.members.all()
print(f"Organization: {user3.profile.organization.name}")
print(f"Is board member: {is_member}")

if is_member:
    report = service.get_team_workload_report(demo_board, requesting_user=user3)
    print(f"Visible team members: {report['team_size']}")
    print("\nMembers:")
    for member in report['members']:
        print(f"  ✓ {member['username']}: {member['active_tasks']} tasks")
else:
    print("❌ user3 is NOT a board member (correct!)")

# Verify the key requirements
print("\n\n" + "=" * 80)
print("VERIFICATION RESULTS")
print("=" * 80)

# Check user7's view
user7_report = service.get_team_workload_report(demo_board, requesting_user=user7)
user7_members = [m['username'] for m in user7_report['members']]

checks = []
checks.append(("Demo users visible to user7", all(u in user7_members for u in ['john_doe', 'jane_smith', 'robert_johnson', 'alice_williams', 'bob_martinez'])))
checks.append(("user8 visible to user7 (invited)", 'user8' in user7_members))
checks.append(("user3 NOT visible to user7 (not invited)", 'user3' not in user7_members))
checks.append(("user1 NOT visible to user7 (different org)", 'user1' not in user7_members))

for check, passed in checks:
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{status}: {check}")
