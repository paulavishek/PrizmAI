"""
Check for original demo users
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board

# Check for demo users
demo_usernames = ['john_doe', 'jane_smith', 'robert_johnson', 'alice_williams', 'bob_martinez', 'carol_anderson', 'david_taylor']

print("=== ORIGINAL DEMO USERS ===")
for username in demo_usernames:
    user = User.objects.filter(username=username).first()
    if user:
        print(f"{username}: EXISTS")
        try:
            print(f"  Organization: {user.profile.organization.name}")
        except:
            print(f"  Organization: NO PROFILE")
    else:
        print(f"{username}: NOT FOUND")

# Check demo board organizations
print("\n=== DEMO ORGANIZATIONS ===")
demo_boards = Board.objects.filter(organization__name__in=['Dev Team', 'Marketing Team']).first()
if demo_boards:
    print(f"Demo org exists: {demo_boards.organization.name}")
    # Check if any users belong to this org
    from accounts.models import UserProfile
    users_in_demo_org = UserProfile.objects.filter(organization=demo_boards.organization)
    print(f"Users in {demo_boards.organization.name}: {[u.user.username for u in users_in_demo_org]}")
