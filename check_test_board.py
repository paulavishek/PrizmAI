"""
Diagnostic script to check the test board and understand why it wasn't deleted
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'prizmAI.settings')
django.setup()

from kanban.models import Board
from accounts.models import Organization

print("=" * 70)
print("CHECKING TEST BOARD STATUS")
print("=" * 70)

# Find the test board
test_boards = Board.objects.filter(name__icontains='test')
print(f"\nFound {test_boards.count()} board(s) with 'test' in name:")

for board in test_boards:
    print(f"\n  Board: {board.name}")
    print(f"  ID: {board.id}")
    print(f"  Organization: {board.organization.name} (is_demo: {board.organization.is_demo})")
    print(f"  Created by: {board.created_by.username}")
    print(f"  is_official_demo_board: {board.is_official_demo_board}")
    print(f"  is_seed_demo_data: {board.is_seed_demo_data}")
    print(f"  created_by_session: {board.created_by_session}")
    print(f"  Created at: {board.created_at}")

# Check demo organization
demo_org = Organization.objects.filter(is_demo=True).first()
if demo_org:
    print(f"\n\nDemo Organization: {demo_org.name}")
    print(f"  Total boards: {demo_org.boards.count()}")
    print(f"  Official demo boards: {demo_org.boards.filter(is_official_demo_board=True).count()}")
    print(f"  User-created boards: {demo_org.boards.filter(is_official_demo_board=False).count()}")
    
    print("\n  User-created boards:")
    for board in demo_org.boards.filter(is_official_demo_board=False):
        print(f"    - {board.name} (created_by_session: {board.created_by_session})")
else:
    print("\n\nNo demo organization found!")

print("\n" + "=" * 70)
