"""
Test reset demo functionality after recent changes
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board
from django.core.management import call_command
from io import StringIO

def test_reset_demo():
    print("\n" + "="*80)
    print("TESTING RESET DEMO AFTER RECENT CHANGES")
    print("="*80)
    
    # Check state BEFORE reset
    print("\n📋 BEFORE RESET:")
    print("-"*80)
    
    demo_boards = Board.objects.filter(is_official_demo_board=True)
    testuser = User.objects.get(username='testuser1')
    
    for board in demo_boards:
        members = board.members.all()
        is_member = testuser in members
        print(f"  {board.name}: {members.count()} members")
        print(f"    testuser1 member: {'✅ YES' if is_member else '❌ NO'}")
    
    # Check for deleted/anonymized users
    all_users = User.objects.all()
    deleted_or_inactive = User.objects.filter(is_active=False)
    print(f"\n  Total users: {all_users.count()}")
    print(f"  Inactive users: {deleted_or_inactive.count()}")
    if deleted_or_inactive.exists():
        for user in deleted_or_inactive:
            print(f"    - {user.username} (inactive)")
    
    # RUN RESET
    print("\n" + "="*80)
    print("RUNNING RESET DEMO...")
    print("="*80)
    
    try:
        out = StringIO()
        call_command('populate_all_demo_data', '--reset', stdout=out, stderr=out)
        print("✅ Reset completed successfully")
    except Exception as e:
        print(f"❌ Reset failed: {e}")
        return
    
    # Check state AFTER reset
    print("\n📋 AFTER RESET:")
    print("-"*80)
    
    # Refresh from DB
    demo_boards = Board.objects.filter(is_official_demo_board=True)
    testuser = User.objects.get(username='testuser1')
    
    all_good = True
    for board in demo_boards:
        members = board.members.all()
        is_member = testuser in members
        print(f"  {board.name}: {members.count()} members")
        print(f"    testuser1 member: {'✅ YES' if is_member else '❌ NO'}")
        
        # List all members
        for member in members:
            is_demo = 'demo' in member.username.lower()
            is_deleted = '_deleted_' in member.username.lower() or 'deleted' in member.username.lower()
            marker = "🤖" if is_demo else "👤"
            if is_deleted:
                marker = "⚠️"
            print(f"      {marker} {member.username}")
            
            if is_deleted:
                print(f"        ❌ ERROR: Deleted/anonymized user still a member!")
                all_good = False
        
        if not is_member:
            all_good = False
    
    # Check for deleted/anonymized users
    all_users = User.objects.all()
    deleted_or_inactive = User.objects.filter(is_active=False)
    print(f"\n  Total users: {all_users.count()}")
    print(f"  Inactive users: {deleted_or_inactive.count()}")
    
    # Check if any inactive/deleted users appear in "available users" query
    # Simulate the view's query
    org_users = User.objects.filter(
        is_active=True
    ).exclude(
        id__in=demo_boards.first().members.values_list('id', flat=True)
    ).exclude(
        username__icontains='deleted'
    )
    
    print(f"\n  Users that would appear in 'Available Users': {org_users.count()}")
    for user in org_users:
        print(f"    - {user.username}")
    
    # Final verdict
    print("\n" + "="*80)
    if all_good:
        print("✅ SUCCESS: Reset demo works correctly!")
        print("   - testuser1 preserved as member of all boards")
        print("   - No deleted/anonymized users in member lists")
    else:
        print("❌ ISSUES DETECTED")
    print("="*80 + "\n")

if __name__ == '__main__':
    test_reset_demo()
