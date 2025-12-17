"""
Check which users are members of each demo board and their skills
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board
from accounts.models import Organization

# Get demo boards
demo_org_names = ['Dev Team', 'Marketing Team']
demo_orgs = Organization.objects.filter(name__in=demo_org_names)
demo_boards = Board.objects.filter(organization__in=demo_orgs)

print("=" * 80)
print("DEMO BOARDS - MEMBER ANALYSIS")
print("=" * 80)

for board in demo_boards:
    print(f"\n📋 Board: {board.name}")
    print(f"   Organization: {board.organization.name}")
    
    members = board.members.all()
    print(f"   Total Members: {members.count()}")
    
    if members.count() == 0:
        print("   ⚠️  NO MEMBERS!")
        continue
    
    print(f"\n   Members:")
    for member in members:
        try:
            profile = member.profile
            skills = profile.skills if profile.skills else []
            print(f"   - {member.username} ({member.get_full_name() or 'No name'})")
            print(f"     Email: {member.email}")
            print(f"     Skills: {len(skills)} skills")
            if skills:
                for skill in skills[:3]:  # Show first 3 skills
                    print(f"       • {skill.get('name', 'Unknown')}: {skill.get('level', 'Unknown')}")
                if len(skills) > 3:
                    print(f"       ... and {len(skills) - 3} more")
        except Exception as e:
            print(f"   - {member.username} (Error: {e})")
    
    print()

print("=" * 80)
print("ANALYSIS")
print("=" * 80)
print("\nKey Points:")
print("1. Team Skill Matrix shows skills from ALL members of a board")
print("2. If all 3 boards have the SAME members, they'll show the SAME skills")
print("3. Skills come from user profiles, not from tasks")
print("=" * 80)
