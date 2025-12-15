"""
Reset Demo Board Members
Removes all members from demo boards so users must explicitly be invited
This enforces invitation-based access control in demo mode
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board, Organization
from kanban.permission_models import BoardMembership
from messaging.models import ChatRoom

def reset_demo_boards():
    """Remove all members from demo boards except the board creator"""
    
    # Get demo organizations
    demo_org_names = ['Dev Team', 'Marketing Team']
    demo_orgs = Organization.objects.filter(name__in=demo_org_names)
    
    if not demo_orgs.exists():
        print('❌ No demo organizations found')
        return
    
    print(f'Found {demo_orgs.count()} demo organizations')
    
    # Get all demo boards
    demo_boards = Board.objects.filter(organization__in=demo_orgs)
    
    print(f'\n📋 Processing {demo_boards.count()} demo boards...\n')
    
    total_removed = 0
    
    for board in demo_boards:
        print(f'Board: {board.name} ({board.organization.name})')
        
        # Get all members except the creator
        members_to_remove = board.members.exclude(id=board.created_by.id)
        
        member_count = members_to_remove.count()
        print(f'  Current members: {board.members.count()}')
        print(f'  Members to remove: {member_count}')
        
        if member_count > 0:
            # Remove BoardMemberships
            BoardMembership.objects.filter(
                board=board,
                user__in=members_to_remove
            ).delete()
            
            # Remove from chat rooms
            chat_rooms = ChatRoom.objects.filter(board=board)
            for room in chat_rooms:
                for member in members_to_remove:
                    room.members.remove(member)
            
            # Remove from board members
            board.members.set([board.created_by])
            
            total_removed += member_count
            print(f'  ✓ Removed {member_count} members')
            print(f'  Remaining: {board.members.count()} (creator only)')
        else:
            print(f'  ✓ Already clean (creator only)')
        
        print()
    
    print(f'\n✅ Complete! Removed {total_removed} member assignments from demo boards.')
    print('\n📌 Demo boards are now reset:')
    print('   - Only board creators have access')
    print('   - Users must click "Load Demo Data" to get initial access')
    print('   - After that, use "Add Member" button to invite others')
    print('   - This enforces invitation-based access control even in demo mode')

if __name__ == '__main__':
    reset_demo_boards()
