"""
Check organization structure and board memberships
Shows the relationship between organizations and boards
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import Organization, UserProfile
from kanban.models import Board

print("=" * 80)
print("ORGANIZATION & BOARD MEMBERSHIP ANALYSIS")
print("=" * 80)

# Find all organizations named "organization"
orgs_named_organization = Organization.objects.filter(name__icontains='organization').exclude(
    name__in=['Dev Team', 'Marketing Team']
)

print(f"\n📋 Found {orgs_named_organization.count()} organization(s) with 'organization' in name:\n")

for org in orgs_named_organization:
    print(f"{'─' * 80}")
    print(f"Organization: {org.name} (ID: {org.id})")
    print(f"  Created by: {org.created_by.username}")
    print(f"  Created on: {org.created_at.strftime('%b %d, %Y')}")
    print(f"  Domain: {org.domain}")
    
    members = org.members.all()
    print(f"  \n  Organization Members ({members.count()}):")
    for profile in members:
        admin_badge = "👑 Admin" if profile.is_admin else "Member"
        print(f"    - {profile.user.username} ({admin_badge})")
    
    boards = org.boards.all()
    print(f"  \n  Boards Created in This Organization ({boards.count()}):")
    if boards.exists():
        for board in boards:
            print(f"    - {board.name} (Created by: {board.created_by.username})")
            print(f"      Board Members: {board.members.count()} - {', '.join([u.username for u in board.members.all()])}")
    else:
        print(f"    (No boards created)")

print(f"\n{'─' * 80}")
print(f"\n📊 DEMO BOARDS (Special Shared Boards):\n")

demo_org_names = ['Dev Team', 'Marketing Team']
demo_boards = Board.objects.filter(organization__name__in=demo_org_names)

for board in demo_boards:
    print(f"  {board.name} ({board.organization.name})")
    print(f"    Members ({board.members.count()}): {', '.join([u.username for u in board.members.all()])}")

print(f"\n{'=' * 80}")
print("RECOMMENDATIONS:")
print("=" * 80)
print("""
1. ⚠️  MULTIPLE ORGANIZATIONS WITH SAME NAME
   - user1, user2, user3, and user5 each created separate "organization" instances
   - These are DIFFERENT organizations (each with unique ID)
   - Each only has 1 member (the creator)

2. 📌 ORGANIZATION vs BOARD MEMBERSHIP
   - Organization membership: Users in the same organization (company/team)
   - Board membership: Users invited to specific projects/boards
   - NOT all org members are automatically board members

3. 💡 WHY YOU SEE user1, user2, user3 AS RESOURCES
   - They accessed the same demo boards as you (Software Project, Bug Tracking, etc.)
   - Demo boards are SHARED across all users, regardless of their organization
   - When you view demo boards, you see all other users who also accessed them

4. ✅ RECOMMENDED FIX
   For your actual organization:
   - Keep organization name unique (e.g., "Acme Corp" instead of "organization")
   - For each board, explicitly invite team members you want
   - Organization = company/team container
   - Boards = individual projects with specific members

5. 🎯 FOR DEMO BOARDS
   - Demo boards are meant to be shared learning environments
   - They belong to "Dev Team" and "Marketing Team" special orgs
   - All users can access them to explore features
   - Your actual organization boards are separate from demo boards
""")

print("\n" + "=" * 80)
