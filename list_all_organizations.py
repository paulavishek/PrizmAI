"""
List all organizations in the database
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Organization, Board

print("=" * 60)
print("ALL ORGANIZATIONS IN DATABASE")
print("=" * 60)

all_orgs = Organization.objects.all()

print(f"\nTotal Organizations: {all_orgs.count()}\n")

for org in all_orgs:
    print(f"📊 Organization: {org.name}")
    print(f"   ID: {org.id}")
    print(f"   Domain: {org.domain}")
    
    # Get boards for this organization
    boards = Board.objects.filter(organization=org)
    print(f"   Boards ({boards.count()}):")
    for board in boards:
        print(f"      - {board.name} (Members: {board.members.count()})")
    print()
