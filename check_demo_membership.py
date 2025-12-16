"""
Check demo board membership for user7 and user8
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board

# Get demo board
demo_boards = Board.objects.filter(organization__name__in=['Dev Team', 'Marketing Team'])

print("=== DEMO BOARDS ===")
for board in demo_boards:
    print(f"\nBoard: {board.name} ({board.organization.name})")
    members = board.members.all()
    print(f"Total members: {members.count()}")
    print(f"Members: {[u.username for u in members]}")

# Check user7 and user8
print("\n=== USER DETAILS ===")
for username in ['user7', 'user8']:
    user = User.objects.filter(username=username).first()
    if user:
        print(f"\n{username}:")
        print(f"  Organization: {user.profile.organization.name}")
        print(f"  Member of demo boards: {[b.name for b in demo_boards.filter(members=user)]}")
    else:
        print(f"\n{username}: NOT FOUND")
