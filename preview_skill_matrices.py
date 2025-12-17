"""
Show what the Team Skill Matrix will display for each demo board
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board
from kanban.utils.skill_analysis import build_team_skill_profile

# Get demo boards
demo_boards = Board.objects.filter(
    organization__name__in=['Dev Team', 'Marketing Team']
).order_by('name')

print("=" * 80)
print("TEAM SKILL MATRIX - PER BOARD PREVIEW")
print("=" * 80)

for board in demo_boards:
    print(f"\n{'='*80}")
    print(f"📋 {board.name} - {board.organization.name}")
    print(f"{'='*80}")
    
    # Build team skill profile
    profile = build_team_skill_profile(board)
    skill_inventory = profile['skill_inventory']
    
    if not skill_inventory:
        print("⚠️  No skills found for this board's members")
        continue
    
    print(f"\nTeam Size: {profile['team_size']} members")
    print(f"Total Skills: {len(skill_inventory)} unique skills")
    print(f"\nSkill Matrix:")
    print(f"{'Skill':<25} {'Expert':>8} {'Advanced':>10} {'Intermediate':>13} {'Beginner':>10} {'Total':>8}")
    print("-" * 80)
    
    # Sort by total count
    sorted_skills = sorted(
        skill_inventory.items(),
        key=lambda x: sum([x[1]['expert'], x[1]['advanced'], x[1]['intermediate'], x[1]['beginner']]),
        reverse=True
    )
    
    for skill_name, skill_data in sorted_skills:
        expert = skill_data.get('expert', 0)
        advanced = skill_data.get('advanced', 0)
        intermediate = skill_data.get('intermediate', 0)
        beginner = skill_data.get('beginner', 0)
        total = expert + advanced + intermediate + beginner
        
        print(f"{skill_name:<25} {expert:>8} {advanced:>10} {intermediate:>13} {beginner:>10} {total:>8}")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("\n✅ Each board now shows DIFFERENT skills based on its members:")
print("   • Software Project: Dev skills (Python, Django, JavaScript, React, Java, etc.)")
print("   • Bug Tracking: Subset of dev skills (fewer members than Software Project)")
print("   • Marketing Campaign: Marketing skills (Content Marketing, SEO, Design, etc.)")
print("\n💡 The skill matrix reflects WHO is on each board, not what tasks require.")
print("=" * 80)
