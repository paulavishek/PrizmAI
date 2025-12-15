"""
Add user8 to all demo boards for testing
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board

# Get user8
try:
    user8 = User.objects.get(username='user8')
    print(f"Found user8: {user8.username} (ID: {user8.id})")
    print(f"Organization: {user8.profile.organization.name}")
except User.DoesNotExist:
    print("Error: user8 not found")
    exit(1)

# Get demo boards
demo_org_names = ['Dev Team', 'Marketing Team']
demo_boards = Board.objects.filter(organization__name__in=demo_org_names)

print(f"\nAdding user8 to {demo_boards.count()} demo boards...")
added_count = 0
for board in demo_boards:
    if user8 not in board.members.all():
        board.members.add(user8)
        print(f"  ✓ Added to: {board.name} ({board.organization.name})")
        added_count += 1
    else:
        print(f"  - Already member: {board.name} ({board.organization.name})")

print(f"\nTotal boards added: {added_count}")
print(f"Total demo boards user8 is now member of: {demo_boards.filter(members=user8).count()}")
