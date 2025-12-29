"""
Check if demo data exists in the database
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Organization, Board

# Check for demo organizations
demo_org_names = ['Dev Team', 'Marketing Team']
demo_orgs = Organization.objects.filter(name__in=demo_org_names)

print("=" * 60)
print("DEMO DATA EXISTENCE CHECK")
print("=" * 60)

print(f"\n🔍 Looking for organizations: {demo_org_names}")
print(f"   Found: {demo_orgs.count()} organizations")

if demo_orgs.exists():
    for org in demo_orgs:
        print(f"\n   ✅ Organization: {org.name}")
        print(f"      ID: {org.id}")
        print(f"      Domain: {org.domain}")
        
        # Check boards for this organization
        boards = Board.objects.filter(organization=org)
        print(f"      Boards: {boards.count()}")
        for board in boards:
            print(f"         - {board.name}")
else:
    print("\n   ❌ No demo organizations found!")

# Check for demo boards specifically
demo_board_names = ['Software Project', 'Bug Tracking', 'Marketing Campaign']
demo_boards = Board.objects.filter(name__in=demo_board_names)

print(f"\n🔍 Looking for demo boards: {demo_board_names}")
print(f"   Found: {demo_boards.count()} boards")

if demo_boards.exists():
    for board in demo_boards:
        print(f"\n   ✅ Board: {board.name}")
        print(f"      Organization: {board.organization.name}")
        print(f"      Members: {board.members.count()}")
else:
    print("\n   ❌ No demo boards found!")

print("\n" + "=" * 60)
print("CONCLUSION")
print("=" * 60)

if not demo_orgs.exists() or not demo_boards.exists():
    print("\n⚠️  Demo data is NOT set up!")
    print("\n📝 To fix this, run:")
    print("   python manage.py populate_test_data")
    print("\n   OR")
    print("\n   python manage.py populate_demo_data")
else:
    print("\n✅ Demo data exists!")
