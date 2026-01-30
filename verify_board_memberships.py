"""
Verify that real users (testuser1) are members of demo boards
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board

def verify_board_memberships():
    """Check board memberships"""
    
    # Get demo boards
    demo_boards = Board.objects.filter(is_official_demo_board=True)
    print(f"\n📋 Demo Boards: {demo_boards.count()}")
    
    # Get testuser1
    try:
        testuser = User.objects.get(username='testuser1')
        print(f"\n👤 User: {testuser.username}")
        
        for board in demo_boards:
            members = board.members.all()
            print(f"\n  Board: {board.name}")
            print(f"  Total members: {members.count()}")
            
            for member in members:
                is_demo = 'demo' in member.username.lower()
                marker = "🤖" if is_demo else "👤"
                print(f"    {marker} {member.username}")
            
            if testuser in members:
                print(f"    ✅ testuser1 IS a member")
            else:
                print(f"    ❌ testuser1 is NOT a member")
    
    except User.DoesNotExist:
        print("❌ testuser1 not found")

if __name__ == '__main__':
    verify_board_memberships()
