"""
Add all demo users as members to all demo boards
This will make them visible in AI Resource Optimization
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board
from kanban.permission_models import BoardMembership, Role

demo_usernames = ['john_doe', 'jane_smith', 'robert_johnson', 'alice_williams', 'bob_martinez', 'carol_anderson', 'david_taylor']
demo_boards = Board.objects.filter(organization__name__in=['Dev Team', 'Marketing Team'])

print("=" * 80)
print("ADDING DEMO USERS TO DEMO BOARDS")
print("=" * 80)

added_count = 0
for username in demo_usernames:
    user = User.objects.filter(username=username).first()
    if not user:
        print(f"\n✗ {username} not found, skipping")
        continue
    
    print(f"\n{username} ({user.profile.organization.name}):")
    
    for board in demo_boards:
        # Add to board members if not already
        if user not in board.members.all():
            board.members.add(user)
            print(f"  ✓ Added to {board.name}")
            added_count += 1
            
            # Create BoardMembership with Editor role for proper RBAC
            editor_role = Role.objects.filter(
                organization=board.organization,
                name='Editor'
            ).first()
            
            if editor_role:
                BoardMembership.objects.get_or_create(
                    board=board,
                    user=user,
                    defaults={'role': editor_role}
                )
        else:
            print(f"  - Already member of {board.name}")

print(f"\n{'='*80}")
print(f"SUMMARY: Added {added_count} memberships")
print("=" * 80)

# Verify
print("\nVERIFICATION - Current board memberships:")
for board in demo_boards:
    members = board.members.all()
    print(f"\n{board.name} ({board.organization.name}): {members.count()} members")
    for member in members:
        try:
            org_name = member.profile.organization.name
        except:
            org_name = "NO ORG"
        print(f"  - {member.username} ({org_name})")
