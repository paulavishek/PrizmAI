"""
Test the reset demo functionality to ensure it preserves real users
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board
from django.core.management import call_command

def test_reset_demo():
    """Test that reset preserves real users"""
    
    print("\n" + "="*80)
    print("TESTING RESET DEMO - REAL USER PRESERVATION")
    print("="*80)
    
    # Get demo boards and testuser1
    demo_boards = Board.objects.filter(is_official_demo_board=True)
    testuser = User.objects.get(username='testuser1')
    
    print(f"\n📋 Found {demo_boards.count()} demo boards")
    print(f"👤 Found user: {testuser.username}")
    
    # BEFORE: Check memberships
    print("\n" + "-"*80)
    print("BEFORE RESET:")
    print("-"*80)
    memberships_before = {}
    for board in demo_boards:
        is_member = testuser in board.members.all()
        memberships_before[board.name] = is_member
        status = "✅ MEMBER" if is_member else "❌ NOT MEMBER"
        print(f"  {board.name}: {status}")
    
    # Run the reset - call populate_all_demo_data with reset flag
    print("\n" + "-"*80)
    print("RUNNING RESET (populate_all_demo_data --reset)...")
    print("-"*80)
    
    try:
        from io import StringIO
        out = StringIO()
        call_command('populate_all_demo_data', '--reset', stdout=out, stderr=out)
        output = out.getvalue()
        # Print relevant lines
        for line in output.split('\n'):
            if 'demo' in line.lower() or 'user' in line.lower() or 'board' in line.lower():
                print(f"  {line}")
    except Exception as e:
        print(f"⚠️ Reset encountered an error: {e}")
    
    # AFTER: Check memberships again
    print("\n" + "-"*80)
    print("AFTER RESET:")
    print("-"*80)
    
    # Refresh boards from DB
    demo_boards = Board.objects.filter(is_official_demo_board=True)
    testuser = User.objects.get(username='testuser1')
    
    all_preserved = True
    for board in demo_boards:
        is_member = testuser in board.members.all()
        was_member_before = memberships_before.get(board.name, False)
        
        if was_member_before and is_member:
            status = "✅ PRESERVED"
        elif was_member_before and not is_member:
            status = "❌ REMOVED (BUG!)"
            all_preserved = False
        elif not was_member_before and is_member:
            status = "➕ ADDED"
        else:
            status = "⚪ NOT MEMBER"
        
        print(f"  {board.name}: {status}")
    
    # Final verdict
    print("\n" + "="*80)
    if all_preserved:
        print("✅ SUCCESS: All real users preserved after reset!")
    else:
        print("❌ FAILURE: Some real users were removed!")
    print("="*80 + "\n")

if __name__ == '__main__':
    test_reset_demo()
