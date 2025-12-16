"""
Add skills to all real users (non-demo users)
This will make them show up better in AI suggestions when skills match
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import UserProfile

# Define demo users to exclude
demo_usernames = ['john_doe', 'jane_smith', 'robert_johnson', 'alice_williams', 
                  'bob_martinez', 'carol_anderson', 'david_taylor', 'admin']

# Get all real users (non-demo users)
all_users = User.objects.exclude(username__in=demo_usernames)

print("=" * 80)
print("ADDING SKILLS TO REAL USERS")
print("=" * 80)

# Define skill sets for different users
skill_sets = [
    # Technical skills
    [
        {'name': 'Python', 'level': 'Expert'},
        {'name': 'JavaScript', 'level': 'Intermediate'},
        {'name': 'React', 'level': 'Intermediate'},
        {'name': 'Django', 'level': 'Advanced'},
    ],
    # Project management skills
    [
        {'name': 'Project Management', 'level': 'Expert'},
        {'name': 'Agile', 'level': 'Advanced'},
        {'name': 'Scrum', 'level': 'Advanced'},
        {'name': 'Documentation', 'level': 'Expert'},
    ],
    # Design & UX skills
    [
        {'name': 'UI Design', 'level': 'Advanced'},
        {'name': 'UX Research', 'level': 'Intermediate'},
        {'name': 'Figma', 'level': 'Advanced'},
        {'name': 'CSS', 'level': 'Expert'},
    ],
    # DevOps skills
    [
        {'name': 'DevOps', 'level': 'Advanced'},
        {'name': 'AWS', 'level': 'Intermediate'},
        {'name': 'Docker', 'level': 'Advanced'},
        {'name': 'CI/CD', 'level': 'Intermediate'},
    ],
    # Data & Analytics
    [
        {'name': 'Data Analysis', 'level': 'Advanced'},
        {'name': 'SQL', 'level': 'Expert'},
        {'name': 'Python', 'level': 'Advanced'},
        {'name': 'Visualization', 'level': 'Intermediate'},
    ],
    # Full-stack development
    [
        {'name': 'Full-Stack Development', 'level': 'Advanced'},
        {'name': 'Node.js', 'level': 'Advanced'},
        {'name': 'MongoDB', 'level': 'Intermediate'},
        {'name': 'API Development', 'level': 'Expert'},
    ],
]

updated_count = 0
for i, user in enumerate(all_users):
    try:
        profile = user.profile
        
        # Check if user already has skills
        if profile.skills:
            print(f"\n{user.username}: Already has {len(profile.skills)} skills")
            for skill in profile.skills:
                print(f"  - {skill.get('name', 'Unknown')}")
            continue
        
        # Assign skills cyclically
        skills = skill_sets[i % len(skill_sets)]
        profile.skills = skills
        profile.save()
        
        print(f"\n✓ {user.username} ({profile.organization.name}):")
        for skill in skills:
            print(f"  - {skill['name']} ({skill['level']})")
        
        updated_count += 1
        
    except Exception as e:
        print(f"\n✗ Error updating {user.username}: {e}")

print(f"\n{'=' * 80}")
print(f"SUMMARY: Updated {updated_count} user(s) with skills")
print("=" * 80)

# Verify
print("\n\nVERIFICATION - All real users and their skills:")
print("=" * 80)
for user in all_users:
    try:
        profile = user.profile
        skill_names = [s['name'] for s in profile.skills] if profile.skills else []
        print(f"\n{user.username} ({profile.organization.name}):")
        if skill_names:
            print(f"  Skills: {', '.join(skill_names)}")
        else:
            print(f"  Skills: None")
    except Exception as e:
        print(f"{user.username}: Error - {e}")
