"""
Add diverse skills to demo board members so each board has unique skill profiles
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board
from accounts.models import Organization

# Get demo boards
demo_boards = Board.objects.filter(
    organization__name__in=['Dev Team', 'Marketing Team']
)

# Skills for Software Project board (Dev Team - technical focus)
software_dev_skills = {
    'john_doe': [
        {'name': 'Python', 'level': 'Expert'},
        {'name': 'Django', 'level': 'Advanced'},
        {'name': 'SQL', 'level': 'Advanced'},
        {'name': 'API Design', 'level': 'Intermediate'},
    ],
    'jane_smith': [
        {'name': 'JavaScript', 'level': 'Expert'},
        {'name': 'React', 'level': 'Advanced'},
        {'name': 'TypeScript', 'level': 'Advanced'},
        {'name': 'Node.js', 'level': 'Intermediate'},
    ],
    'robert_johnson': [
        {'name': 'Java', 'level': 'Expert'},
        {'name': 'Spring Boot', 'level': 'Advanced'},
        {'name': 'Microservices', 'level': 'Advanced'},
        {'name': 'Kubernetes', 'level': 'Intermediate'},
    ],
    'alice_williams': [
        {'name': 'UI/UX Design', 'level': 'Expert'},
        {'name': 'Figma', 'level': 'Advanced'},
        {'name': 'CSS', 'level': 'Advanced'},
        {'name': 'Accessibility', 'level': 'Intermediate'},
    ],
    'bob_martinez': [
        {'name': 'QA Testing', 'level': 'Expert'},
        {'name': 'Selenium', 'level': 'Advanced'},
        {'name': 'Test Automation', 'level': 'Advanced'},
        {'name': 'Performance Testing', 'level': 'Intermediate'},
    ],
}

# Skills for Marketing Campaign board (Marketing Team - marketing focus)
marketing_skills = {
    'carol_anderson': [
        {'name': 'Content Marketing', 'level': 'Expert'},
        {'name': 'SEO', 'level': 'Advanced'},
        {'name': 'Social Media', 'level': 'Advanced'},
        {'name': 'Google Analytics', 'level': 'Intermediate'},
    ],
    'david_taylor': [
        {'name': 'Graphic Design', 'level': 'Expert'},
        {'name': 'Adobe Photoshop', 'level': 'Advanced'},
        {'name': 'Brand Strategy', 'level': 'Advanced'},
        {'name': 'Video Editing', 'level': 'Intermediate'},
    ],
}

print("=" * 80)
print("ADDING DIVERSE SKILLS TO DEMO BOARD MEMBERS")
print("=" * 80)

# Apply software development skills
print("\n📋 Software Development Team Skills:")
for username, skills in software_dev_skills.items():
    try:
        user = User.objects.get(username=username)
        user.profile.skills = skills
        user.profile.save()
        print(f"✅ {username}: Added {len(skills)} skills")
        for skill in skills:
            print(f"   • {skill['name']}: {skill['level']}")
    except User.DoesNotExist:
        print(f"❌ {username}: User not found")

# Apply marketing skills
print("\n📋 Marketing Team Skills:")
for username, skills in marketing_skills.items():
    try:
        user = User.objects.get(username=username)
        user.profile.skills = skills
        user.profile.save()
        print(f"✅ {username}: Added {len(skills)} skills")
        for skill in skills:
            print(f"   • {skill['name']}: {skill['level']}")
    except User.DoesNotExist:
        print(f"❌ {username}: User not found")

print("\n" + "=" * 80)
print("✅ SKILLS ADDED SUCCESSFULLY!")
print("=" * 80)
print("\nNow each board will show different skills:")
print("- Software Project: Python, Django, JavaScript, React, Java, UI/UX, QA, etc.")
print("- Bug Tracking: Mix of Dev Team skills (Python, Django, JavaScript, etc.)")
print("- Marketing Campaign: Content Marketing, SEO, Graphic Design, etc.")
print("\n⚠️  Note: Bug Tracking board shares Dev Team members, so it will show")
print("   a subset of Software Project skills based on which members are assigned.")
print("=" * 80)
