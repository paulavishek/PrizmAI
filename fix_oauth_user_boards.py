"""
Quick script to add OAuth users to demo boards
This fixes the issue where OAuth users weren't automatically added as board members
"""
import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board

def fix_oauth_user_boards(username=None):
    """Add users to all official demo boards."""
    
    # Get all demo boards
    demo_boards = Board.objects.filter(is_official_demo_board=True)
    
    if not demo_boards.exists():
        print("No official demo boards found.")
        return
    
    print(f"Found {demo_boards.count()} official demo board(s):")
    for board in demo_boards:
        print(f"  - {board.name}")
    
    # Get the user
    if username is None:
        # Try to find the most recent non-demo user
        user = User.objects.exclude(email__endswith='@demo.prizmai.local').order_by('-date_joined').first()
        if not user:
            print("\n✗ Error: No non-demo users found.")
            return
        print(f"\nAuto-detected user: {user.username} ({user.email})")
    else:
        try:
            user = User.objects.get(username=username)
            print(f"\nFound user: {user.username} ({user.email})")
        except User.DoesNotExist:
            print(f"\n✗ Error: User '{username}' not found.")
            print("Available users in the system:")
            for u in User.objects.all().order_by('username'):
                print(f"  - {u.username} ({u.email})")
            return
        
        # Add user to all demo boards
        boards_added = 0
        boards_already_member = 0
        
        for board in demo_boards:
            if user not in board.members.all():
                board.members.add(user)
                boards_added += 1
                print(f"  ✓ Added {user.username} to '{board.name}'")
            else:
                boards_already_member += 1
                print(f"  - {user.username} already a member of '{board.name}'")
        
        print(f"\nSummary:")
        print(f"  - Added to {boards_added} board(s)")
        print(f"  - Already member of {boards_already_member} board(s)")
        print(f"\n✓ Done! {user.username} should now appear in AI Resource Optimization.")

if __name__ == '__main__':
    import sys
    username = sys.argv[1] if len(sys.argv) > 1 else None
    fix_oauth_user_boards(username)
