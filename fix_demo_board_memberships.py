"""
Fix board memberships for users who have demo board access but no BoardMembership records
This gives them proper RBAC roles so they can actually access the boards
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board
from kanban.permission_models import BoardMembership, Role
from messaging.models import ChatRoom

def fix_demo_memberships():
    """Fix BoardMembership records for all users with demo board access"""
    
    demo_board_names = ['Software Project', 'Bug Tracking', 'Marketing Campaign']
    demo_boards = Board.objects.filter(name__in=demo_board_names)
    
    if not demo_boards.exists():
        print("❌ No demo boards found!")
        return
    
    print(f"Found {demo_boards.count()} demo boards\n")
    
    fixed_count = 0
    for board in demo_boards:
        print(f"\n=== {board.name} ({board.organization.name}) ===")
        
        # Get Editor role for this organization
        editor_role = Role.objects.filter(
            organization=board.organization,
            name='Editor'
        ).first()
        
        if not editor_role:
            print(f"  ⚠️  No Editor role found for {board.organization.name}")
            continue
        
        # Get all members of this board
        members = board.members.all()
        print(f"  Members: {members.count()}")
        
        for member in members:
            # Check if BoardMembership exists
            membership = BoardMembership.objects.filter(
                board=board,
                user=member
            ).first()
            
            if not membership:
                # Create BoardMembership with Editor role
                BoardMembership.objects.create(
                    board=board,
                    user=member,
                    role=editor_role
                )
                print(f"    ✓ Created BoardMembership for {member.username} (Editor role)")
                fixed_count += 1
            
            # Add to chat rooms
            chat_rooms = ChatRoom.objects.filter(board=board)
            for room in chat_rooms:
                if member not in room.members.all():
                    room.members.add(member)
                    print(f"    ✓ Added {member.username} to chat room: {room.name}")
    
    print(f"\n✅ Fixed {fixed_count} board membership(s)!")

if __name__ == '__main__':
    fix_demo_memberships()
