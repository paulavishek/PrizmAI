"""Check skill matrices for demo boards"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, TeamSkillProfile
from kanban.utils.skill_analysis import build_team_skill_profile

# Get demo boards
demo_boards = Board.objects.filter(is_official_demo_board=True).order_by('name')

print("=" * 80)
print("DEMO BOARD SKILL MATRIX CHECK")
print("=" * 80)

for board in demo_boards:
    print(f'\n{"=" * 80}')
    print(f'Board: {board.name} (ID: {board.id})')
    print(f'{"=" * 80}')
    
    # Get members
    members = board.members.all()
    print(f'\n📊 Members ({members.count()}):')
    for member in members:
        print(f'  - {member.username}', end='')
        try:
            skills = member.profile.skills
            capacity = member.profile.weekly_capacity_hours
            workload = member.profile.current_workload_hours
            print(f' | Capacity: {capacity}h | Workload: {workload}h | Skills: {len(skills) if skills else 0}')
            if skills:
                for skill in skills[:5]:  # Show first 5 skills
                    print(f'      • {skill.get("name", "Unknown")} ({skill.get("level", "Unknown")})')
        except Exception as e:
            print(f' | No profile ({e})')
    
    # Build team skill profile
    profile = build_team_skill_profile(board)
    print(f'\n📈 Team Metrics:')
    print(f'  Total Capacity: {profile["total_capacity_hours"]} hours/week')
    print(f'  Utilized: {profile["utilized_capacity_hours"]} hours/week')
    print(f'  Utilization: {profile["utilization_percentage"]:.1f}%')
    print(f'  Unique Skills: {len(profile["skill_inventory"])}')
    
    # Show skill inventory
    if profile["skill_inventory"]:
        print(f'\n🎯 Skill Inventory:')
        for skill_name, skill_data in list(profile["skill_inventory"].items())[:10]:  # Show first 10
            total = sum([
                skill_data.get('expert', 0),
                skill_data.get('advanced', 0),
                skill_data.get('intermediate', 0),
                skill_data.get('beginner', 0)
            ])
            print(f'  {skill_name}: {total} members')
            print(f'    Expert: {skill_data.get("expert", 0)}, '
                  f'Advanced: {skill_data.get("advanced", 0)}, '
                  f'Intermediate: {skill_data.get("intermediate", 0)}, '
                  f'Beginner: {skill_data.get("beginner", 0)}')
    
    # Check if TeamSkillProfile exists in DB
    try:
        db_profile = TeamSkillProfile.objects.get(board=board)
        print(f'\n💾 Database Profile: EXISTS')
        print(f'  Last Updated: {db_profile.last_updated}')
        print(f'  DB Capacity: {db_profile.total_capacity_hours}h')
        print(f'  DB Utilized: {db_profile.utilized_capacity_hours}h')
        print(f'  DB Utilization: {db_profile.utilization_percentage:.1f}%')
        print(f'  DB Skills Count: {len(db_profile.skill_inventory)}')
    except TeamSkillProfile.DoesNotExist:
        print(f'\n💾 Database Profile: NOT FOUND')

print(f'\n{"=" * 80}')
print("SUMMARY")
print("=" * 80)
print("\nIf all boards show the same skills, the issue is with member assignment.")
print("If utilization is 0%, check that members have capacity/workload data.")
