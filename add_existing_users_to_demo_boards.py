"""
Add all existing real users to demo boards.
Run this once to add users who registered before the auto-add feature was implemented.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board

def add_users_to_demo_boards():
    """Add all non-demo users to demo boards"""
    
    # Get all demo boards
    demo_boards = Board.objects.filter(is_official_demo_board=True)
    print(f"Found {demo_boards.count()} demo boards")
    
    # Get all real users (not demo users)
    all_users = User.objects.exclude(username__icontains='demo')
    print(f"Found {all_users.count()} real users")
    
    added_count = 0
    for user in all_users:
        for board in demo_boards:
            if user not in board.members.all():
                board.members.add(user)
                added_count += 1
                print(f"✓ Added {user.username} to '{board.name}'")
            else:
                print(f"  {user.username} already in '{board.name}'")
    
    print(f"\nCompleted! Added {added_count} user-board memberships.")

if __name__ == '__main__':
    add_users_to_demo_boards()
