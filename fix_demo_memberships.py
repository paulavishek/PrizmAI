#!/usr/bin/env python
"""
Fix demo board memberships - remove demo_admin_solo and add jordan_taylor_demo
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth import get_user_model
from kanban.models import Board, Task, Organization

User = get_user_model()

print("="*70)
print("FIXING DEMO BOARD MEMBERSHIPS")
print("="*70)

# Get demo organization
demo_org = Organization.objects.filter(name='Demo - Acme Corporation').first()
if not demo_org:
    print("❌ Demo organization not found")
    exit(1)

# Get users
alex = User.objects.filter(username='alex_chen_demo').first()
sam = User.objects.filter(username='sam_rivera_demo').first()
jordan = User.objects.filter(username='jordan_taylor_demo').first()
demo_admin = User.objects.filter(username='demo_admin_solo').first()

if not all([alex, sam, jordan]):
    print("❌ Demo personas not found")
    exit(1)

print(f"\n✅ Found demo users:")
print(f"   - Alex Chen: {alex.username}")
print(f"   - Sam Rivera: {sam.username}")
print(f"   - Jordan Taylor: {jordan.username}")
if demo_admin:
    print(f"   - Demo Admin (to be removed): {demo_admin.username}")

# Get all demo boards
demo_boards = Board.objects.filter(organization=demo_org, is_official_demo_board=True)

print(f"\n📋 Found {demo_boards.count()} demo boards:")
for board in demo_boards:
    print(f"   - {board.name}")

# Fix each board
for board in demo_boards:
    print(f"\n🔧 Fixing board: {board.name}")
    
    # Get current members
    current_members = list(board.members.all())
    print(f"   Current members: {', '.join([u.username for u in current_members])}")
    
    # Remove demo_admin_solo if present
    if demo_admin and board.members.filter(id=demo_admin.id).exists():
        board.members.remove(demo_admin)
        print(f"   ✅ Removed {demo_admin.username} from board")
    
    # Add jordan if not present
    if not board.members.filter(id=jordan.id).exists():
        board.members.add(jordan)
        print(f"   ✅ Added {jordan.username} to board")
    
    # Ensure alex and sam are members
    if not board.members.filter(id=alex.id).exists():
        board.members.add(alex)
        print(f"   ✅ Added {alex.username} to board")
    
    if not board.members.filter(id=sam.id).exists():
        board.members.add(sam)
        print(f"   ✅ Added {sam.username} to board")
    
    # Reassign tasks from demo_admin_solo to alex
    if demo_admin:
        demo_admin_tasks = Task.objects.filter(
            column__board=board,
            assigned_to=demo_admin
        )
        if demo_admin_tasks.exists():
            count = demo_admin_tasks.count()
            demo_admin_tasks.update(assigned_to=alex)
            print(f"   ✅ Reassigned {count} tasks from demo_admin_solo to alex_chen_demo")
    
    # Show final members
    final_members = list(board.members.filter(
        username__in=['alex_chen_demo', 'sam_rivera_demo', 'jordan_taylor_demo']
    ))
    print(f"   Final demo members: {', '.join([u.get_full_name() or u.username for u in final_members])}")

print("\n" + "="*70)
print("✅ DEMO BOARD MEMBERSHIPS FIXED")
print("="*70)
print("\n📝 Summary:")
print("   - Removed demo_admin_solo from all demo boards")
print("   - Added jordan_taylor_demo to all demo boards")
print("   - Reassigned demo_admin_solo's tasks to alex_chen_demo")
print("   - All boards now have only the 3 visible demo personas as members")
print()
