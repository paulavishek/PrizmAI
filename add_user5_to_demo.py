"""
Add user5 to demo boards
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board
from kanban.permission_models import BoardMembership, Role
from messaging.models import ChatRoom

print("=" * 80)
print("ADDING USER5 TO DEMO BOARDS")
print("=" * 80)

# Get user5
try:
    user5 = User.objects.get(username='user5')
    print(f"\n✓ Found user: {user5.username}")
except User.DoesNotExist:
    print("\n❌ user5 not found!")
    exit(1)

# Get demo boards
demo_board_names = ['Software Project', 'Bug Tracking', 'Marketing Campaign']
demo_boards = Board.objects.filter(
    name__in=demo_board_names, 
    organization__name__in=['Dev Team', 'Marketing Team']
)

if not demo_boards.exists():
    print("❌ Demo boards not found!")
    exit(1)

print(f"\n✓ Found {demo_boards.count()} demo boards\n")

added_count = 0
for board in demo_boards:
    print(f"Processing: {board.name} ({board.organization.name})")
    
    # Add to board members
    if user5 not in board.members.all():
        board.members.add(user5)
        print(f"  ✓ Added to board members")
        added_count += 1
    else:
        print(f"  ⏭  Already a board member")
    
    # Get Editor role
    editor_role = Role.objects.filter(
        organization=board.organization,
        name='Editor'
    ).first()
    
    if editor_role:
        # Create BoardMembership
        membership, created = BoardMembership.objects.get_or_create(
            board=board,
            user=user5,
            defaults={'role': editor_role}
        )
        if created:
            print(f"  ✓ Created BoardMembership (Editor role)")
        else:
            print(f"  ⏭  BoardMembership already exists")
    
    # Add to chat rooms
    chat_rooms = ChatRoom.objects.filter(board=board)
    for room in chat_rooms:
        if user5 not in room.members.all():
            room.members.add(user5)
            print(f"  ✓ Added to chat room: {room.name}")

print(f"\n{'=' * 80}")
print(f"✅ Successfully added user5 to {added_count} demo board(s)!")
print(f"{'=' * 80}\n")

print("Updated board memberships:")
for board in demo_boards:
    print(f"\n{board.name}:")
    print(f"  Members ({board.members.count()}): {', '.join([u.username for u in board.members.all()])}")
