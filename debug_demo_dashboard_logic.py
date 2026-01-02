"""
Debug script to simulate demo_dashboard view logic for demo_admin_solo user
"""
import os
import sys

# Add the project directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')

try:
    import django
    django.setup()
except Exception as e:
    print(f"Error setting up Django: {e}")
    sys.exit(1)

from django.contrib.auth.models import User
from kanban.models import Board, Organization

print("\n" + "="*80)
print("SIMULATING demo_dashboard VIEW LOGIC FOR demo_admin_solo")
print("="*80)

# Get demo_admin_solo user
demo_admin = User.objects.get(username='demo_admin_solo')
print(f"\nUser: {demo_admin.username} (ID: {demo_admin.id})")
print(f"Is authenticated: True (simulated)")

# Constants from demo_views.py
DEMO_ORG_NAMES = ['Demo - Acme Corporation']
DEMO_BOARD_NAMES = ['Software Development', 'Bug Tracking', 'Marketing Campaign']

# Get demo organizations
demo_orgs = Organization.objects.filter(name__in=DEMO_ORG_NAMES)
print(f"\nDemo organizations found: {demo_orgs.count()}")
for org in demo_orgs:
    print(f"  - {org.name}")

# Get demo boards
demo_boards = Board.objects.filter(
    organization__in=demo_orgs,
    name__in=DEMO_BOARD_NAMES
).prefetch_related('members')

print(f"\nDemo boards found (initial query): {demo_boards.count()}")
for board in demo_boards:
    print(f"  - {board.name} (members: {board.members.count()})")

# Check if user has org access (THIS IS THE KEY QUERY)
print("\n" + "="*80)
print("CHECKING USER'S ORG ACCESS (Line 417-420 in demo_views.py)")
print("="*80)

user_demo_orgs = Organization.objects.filter(
    name__in=DEMO_ORG_NAMES,
    boards__members=demo_admin
).distinct()

print(f"\nOrganizations where user is a member: {user_demo_orgs.count()}")
for org in user_demo_orgs:
    print(f"  - {org.name}")

if not user_demo_orgs.exists():
    print("\n⚠️  PROBLEM FOUND: user_demo_orgs is EMPTY!")
    print("This means demo_admin_solo is not being found as a board member")
    print("\nChecking board memberships directly...")
    for board in demo_boards:
        is_member = demo_admin in board.members.all()
        print(f"  {board.name}: is_member={is_member}")
else:
    print("\n✓ User has organization access")

# Filter boards by user's orgs (Line 457 in demo_views.py)
print("\n" + "="*80)
print("FILTERING BOARDS BY USER'S ORGS (Line 457 in demo_views.py)")
print("="*80)

filtered_demo_boards = demo_boards.filter(organization__in=user_demo_orgs)
print(f"\nFiltered demo boards: {filtered_demo_boards.count()}")
for board in filtered_demo_boards:
    print(f"  - {board.name}")

if filtered_demo_boards.count() == 0:
    print("\n❌ THIS IS THE BUG! Boards are being filtered out!")
    print("\nThe query 'demo_boards.filter(organization__in=user_demo_orgs)'")
    print("is returning 0 boards even though the user is a member.")
else:
    print("\n✓ Boards would be visible in UI")

# Test if removing the filter would help
print("\n" + "="*80)
print("TESTING WITHOUT FILTER")
print("="*80)
print(f"\nIf we skip the filter and use original demo_boards: {demo_boards.count()} boards")
print("This is what SHOULD be shown to the user")
