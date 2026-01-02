"""
Quick check for demo boards visibility in Solo mode
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

from kanban.models import Board, Organization

print("\n" + "="*80)
print("DEMO BOARD AVAILABILITY CHECK")
print("="*80)

# Constants from demo_views.py
DEMO_ORG_NAMES = ['Demo - Acme Corporation']
DEMO_BOARD_NAMES = ['Software Development', 'Bug Tracking', 'Marketing Campaign']

print(f"\nLooking for demo organization: {DEMO_ORG_NAMES}")
demo_orgs = Organization.objects.filter(name__in=DEMO_ORG_NAMES)

if not demo_orgs.exists():
    print("❌ PROBLEM: No demo organizations found!")
    print("\nAll organizations in database:")
    for org in Organization.objects.all():
        print(f"  - {org.name} (ID: {org.id})")
else:
    print(f"✓ Found {demo_orgs.count()} demo organization(s)")
    for org in demo_orgs:
        print(f"  - {org.name} (ID: {org.id})")

print(f"\nLooking for demo boards: {DEMO_BOARD_NAMES}")
demo_boards = Board.objects.filter(
    organization__in=demo_orgs,
    name__in=DEMO_BOARD_NAMES
)

if not demo_boards.exists():
    print("❌ PROBLEM: No demo boards found!")
    print("\nAll boards in demo organizations:")
    for org in demo_orgs:
        boards = Board.objects.filter(organization=org)
        print(f"\nOrganization: {org.name}")
        if boards.exists():
            for board in boards:
                print(f"  - {board.name} (ID: {board.id})")
                print(f"    Members: {board.members.count()}")
        else:
            print("  No boards found")
else:
    print(f"✓ Found {demo_boards.count()} demo board(s)")
    for board in demo_boards:
        print(f"\n  Board: {board.name} (ID: {board.id})")
        print(f"  Organization: {board.organization.name}")
        print(f"  Members: {board.members.count()}")
        print(f"  Columns: {board.columns.count()}")

# Check if demo_admin_solo exists
print("\n" + "="*80)
print("DEMO ADMIN USER CHECK")
print("="*80)

from django.contrib.auth.models import User

demo_admin = User.objects.filter(username='demo_admin_solo').first()
if demo_admin:
    print(f"✓ Demo admin user exists: {demo_admin.username} (ID: {demo_admin.id})")
    print(f"  Email: {demo_admin.email}")
    print(f"  Is staff: {demo_admin.is_staff}")
    print(f"  Is superuser: {demo_admin.is_superuser}")
    
    # Check board memberships
    admin_boards = Board.objects.filter(members=demo_admin)
    print(f"  Member of {admin_boards.count()} boards")
    for board in admin_boards:
        print(f"    - {board.name}")
else:
    print("❌ PROBLEM: demo_admin_solo user not found!")

print("\n" + "="*80)
print("RECOMMENDATION")
print("="*80)

if not demo_orgs.exists() or not demo_boards.exists():
    print("\n⚠️  Demo data is missing or misconfigured!")
    print("\nTo fix this, run:")
    print("  python manage.py populate_demo_data")
    print("\nOR check if organization/board names have changed")
else:
    print("\n✓ Demo boards exist and should be visible")
    print("\nIf boards still don't show in UI, check:")
    print("  1. Browser console for JavaScript errors")
    print("  2. Django server logs for errors")
    print("  3. Session data (demo_mode_selected, is_demo_mode flags)")
