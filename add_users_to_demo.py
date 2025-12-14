import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board

# Find the user from organization 1
demo_board_names = ['Software Project', 'Bug Tracking', 'Marketing Campaign']
demo_boards = Board.objects.filter(name__in=demo_board_names, organization__name__in=['Dev Team', 'Marketing Team'])

print("Official Demo Boards:")
for board in demo_boards:
    print(f"\n{board.name} (ID: {board.id})")
    print(f"  Organization: {board.organization.name}")
    print(f"  Members ({board.members.count()}): {', '.join([u.username for u in board.members.all()])}")

# Find users from organization 1 who need to be added
org1_users = User.objects.filter(profile__organization__name='organization 1')
print(f"\n\nUsers in 'organization 1': {', '.join([u.username for u in org1_users])}")

print("\n\nAdding users to official demo boards...")
for user in org1_users:
    for board in demo_boards:
        if user not in board.members.all():
            board.members.add(user)
            print(f"  ✓ Added {user.username} to {board.name}")
        else:
            print(f"  ⏭  {user.username} already in {board.name}")

print("\n\nUpdated board memberships:")
for board in demo_boards:
    print(f"{board.name}: {board.members.count()} members")
