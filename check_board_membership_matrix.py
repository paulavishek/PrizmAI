"""
Check which demo users are members of which boards
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board

demo_usernames = ['john_doe', 'jane_smith', 'robert_johnson', 'alice_williams', 'bob_martinez', 'carol_anderson', 'david_taylor']
demo_boards = Board.objects.filter(organization__name__in=['Dev Team', 'Marketing Team'])

print("=== BOARD MEMBERSHIP MATRIX ===\n")
print(f"{'User':<20} | {'Software Project':<18} | {'Bug Tracking':<18} | {'Marketing Campaign':<18}")
print("-" * 90)

for username in demo_usernames:
    user = User.objects.filter(username=username).first()
    if user:
        row = f"{username:<20} |"
        for board in demo_boards:
            is_member = "✓ MEMBER" if user in board.members.all() else "✗ NOT MEMBER"
            row += f" {is_member:<18} |"
        print(row)
    else:
        print(f"{username:<20} | NOT FOUND")
