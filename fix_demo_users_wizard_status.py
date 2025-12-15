"""
Fix wizard status for users who have demo board access but wizard not marked as completed
This was causing users to get stuck in wizard loop even though they had demo boards
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board

def fix_demo_users():
    """Fix wizard status for users with demo board access"""
    
    demo_board_names = ['Software Project', 'Bug Tracking', 'Marketing Campaign']
    
    # Find all users who are members of demo boards but haven't completed wizard
    users_with_demo_access = User.objects.filter(
        board_memberships__name__in=demo_board_names,
        profile__completed_wizard=False
    ).distinct()
    
    if not users_with_demo_access.exists():
        print("✓ No users need fixing - all users with demo access have wizard completed")
        return
    
    print(f"Found {users_with_demo_access.count()} user(s) with demo access but wizard not completed:\n")
    
    for user in users_with_demo_access:
        # Get their demo boards
        demo_boards = Board.objects.filter(
            members=user,
            name__in=demo_board_names
        )
        
        print(f"User: {user.username}")
        print(f"  Organization: {user.profile.organization.name}")
        print(f"  Demo boards: {[b.name for b in demo_boards]}")
        print(f"  Completed wizard: {user.profile.completed_wizard}")
        
        # Fix the wizard status
        user.profile.completed_wizard = True
        user.profile.save()
        
        print(f"  ✓ Marked wizard as completed\n")
    
    print(f"✅ Successfully fixed {users_with_demo_access.count()} user(s)!")

if __name__ == '__main__':
    fix_demo_users()
