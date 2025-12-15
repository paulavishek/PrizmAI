"""
Debug script to check demo board members and organizations
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board, Organization
from accounts.models import UserProfile

# Get demo organizations
demo_org_names = ['Dev Team', 'Marketing Team']
demo_orgs = Organization.objects.filter(name__in=demo_org_names)

print(f"\n=== DEMO ORGANIZATIONS ===")
for org in demo_orgs:
    print(f"Organization: {org.name} (ID: {org.id})")
    boards = Board.objects.filter(organization=org)
    print(f"  Boards: {boards.count()}")
    for board in boards:
        print(f"    - {board.name} (ID: {board.id})")
        members = board.members.all()
        print(f"      Members ({members.count()}):")
        for member in members:
            try:
                user_org = member.profile.organization.name
            except:
                user_org = "No organization"
            print(f"        - {member.username} (ID: {member.id}) - Org: {user_org}")

# Get user7 and user8
print(f"\n=== USER7 AND USER8 ===")
try:
    user7 = User.objects.get(username='user7')
    print(f"user7: {user7.username} (ID: {user7.id})")
    print(f"  Organization: {user7.profile.organization.name}")
    demo_boards = Board.objects.filter(organization__name__in=demo_org_names)
    user7_demo_boards = demo_boards.filter(members=user7)
    print(f"  Member of {user7_demo_boards.count()} demo boards:")
    for board in user7_demo_boards:
        print(f"    - {board.name}")
except User.DoesNotExist:
    print("user7 not found")

try:
    user8 = User.objects.get(username='user8')
    print(f"\nuser8: {user8.username} (ID: {user8.id})")
    print(f"  Organization: {user8.profile.organization.name}")
    demo_boards = Board.objects.filter(organization__name__in=demo_org_names)
    user8_demo_boards = demo_boards.filter(members=user8)
    print(f"  Member of {user8_demo_boards.count()} demo boards:")
    for board in user8_demo_boards:
        print(f"    - {board.name}")
except User.DoesNotExist:
    print("user8 not found")

# Check if they're in the same organization
print(f"\n=== ORGANIZATION CHECK ===")
try:
    user7 = User.objects.get(username='user7')
    user8 = User.objects.get(username='user8')
    if user7.profile.organization == user8.profile.organization:
        print(f"✓ user7 and user8 are in the same organization: {user7.profile.organization.name}")
    else:
        print(f"✗ user7 and user8 are in DIFFERENT organizations:")
        print(f"  user7: {user7.profile.organization.name}")
        print(f"  user8: {user8.profile.organization.name}")
except Exception as e:
    print(f"Error: {e}")
