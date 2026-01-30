"""
Check current state of users and board memberships
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board

def check_state():
    print("\n" + "="*80)
    print("CHECKING DATABASE STATE")
    print("="*80)
    
    # Check all users
    all_users = User.objects.all()
    print(f"\n📋 Total Users in Database: {all_users.count()}")
    for user in all_users:
        is_demo = 'demo' in user.username.lower()
        marker = "🤖" if is_demo else "👤"
        status = "Active" if user.is_active else "INACTIVE"
        print(f"  {marker} {user.username} ({user.email}) - {status}")
    
    # Check demo boards
    demo_boards = Board.objects.filter(is_official_demo_board=True)
    print(f"\n📋 Demo Boards: {demo_boards.count()}")
    
    for board in demo_boards:
        members = board.members.all()
        print(f"\n  Board: {board.name}")
        print(f"  Total members: {members.count()}")
        
        for member in members:
            is_demo = 'demo' in member.username.lower()
            marker = "🤖" if is_demo else "👤"
            print(f"    {marker} {member.username}")
    
    # Check if testuser1 exists and their memberships
    print("\n" + "="*80)
    print("TESTUSER1 STATUS")
    print("="*80)
    try:
        testuser = User.objects.get(username='testuser1')
        print(f"✅ testuser1 found (ID: {testuser.id})")
        print(f"   Email: {testuser.email}")
        print(f"   Active: {testuser.is_active}")
        
        boards_member_of = Board.objects.filter(members=testuser)
        print(f"\n   Member of {boards_member_of.count()} boards:")
        for board in boards_member_of:
            print(f"     - {board.name}")
    except User.DoesNotExist:
        print("❌ testuser1 not found")
    
    # Check DELETED users
    deleted_users = User.objects.filter(username__icontains='deleted')
    if deleted_users.exists():
        print("\n" + "="*80)
        print("⚠️  DELETED USERS FOUND")
        print("="*80)
        for user in deleted_users:
            print(f"  - {user.username} ({user.email})")
            boards = Board.objects.filter(members=user)
            if boards.exists():
                print(f"    Still member of {boards.count()} boards")

if __name__ == '__main__':
    check_state()
