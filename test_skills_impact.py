"""
Test how skills affect AI suggestions
Show that real users with matching skills get higher scores
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board, Task
from kanban.resource_leveling import ResourceLevelingService

demo_board = Board.objects.filter(organization__name='Dev Team').first()
service = ResourceLevelingService(demo_board.organization)

print("=" * 90)
print(" " * 20 + "SKILLS IMPACT ON AI SUGGESTIONS")
print("=" * 90)

# Find a task that mentions specific technologies
tech_tasks = Task.objects.filter(
    column__board=demo_board,
    assigned_to__isnull=True
).filter(
    title__icontains='data'
) | Task.objects.filter(
    column__board=demo_board,
    assigned_to__isnull=True,
    title__icontains='export'
)

task = tech_tasks.first()
if not task:
    task = Task.objects.filter(column__board=demo_board, assigned_to__isnull=True).first()

print(f"\nTask: {task.title}")
if task.description:
    print(f"Description: {task.description[:100]}...")

# Test as user7 (has DevOps, AWS, Docker, CI/CD skills)
user7 = User.objects.get(username='user7')
print(f"\nAnalyzing as: {user7.username}")
print(f"Skills: {', '.join([s['name'] for s in user7.profile.skills])}")

analysis = service.analyze_task_assignment(task, requesting_user=user7)

if 'error' not in analysis:
    print(f"\n{'─' * 90}")
    print("TOP 10 RECOMMENDATIONS WITH SKILLS:")
    print(f"{'─' * 90}")
    print(f"{'Rank':<6} {'User':<20} {'Score':<8} {'Skills':<50}")
    print("─" * 90)
    
    for i, candidate in enumerate(analysis['all_candidates'][:10], 1):
        user = User.objects.get(username=candidate['username'])
        try:
            skills = user.profile.skills
            skill_names = [s['name'] for s in skills] if skills else []
            skills_str = ', '.join(skill_names[:3])  # Show first 3 skills
            if len(skill_names) > 3:
                skills_str += f" (+{len(skill_names)-3} more)"
        except:
            skills_str = "No skills"
        
        print(f"{i:<6} {candidate['username']:<20} {candidate['overall_score']:<8.1f} {skills_str:<50}")
    
    print(f"\n{'─' * 90}")
    print("ANALYSIS:")
    print(f"{'─' * 90}")
    
    # Check positions of real users
    real_users = ['user7', 'user8', 'user1', 'user3', 'user4', 'user5', 'user6']
    demo_users = ['john_doe', 'jane_smith', 'robert_johnson', 'alice_williams', 'bob_martinez']
    
    real_in_top_5 = sum(1 for c in analysis['all_candidates'][:5] if c['username'] in real_users)
    demo_in_top_5 = sum(1 for c in analysis['all_candidates'][:5] if c['username'] in demo_users)
    
    print(f"  Real users in top 5: {real_in_top_5}")
    print(f"  Demo users in top 5: {demo_in_top_5}")
    
    # Show skill match information
    top_user = User.objects.get(username=analysis['top_recommendation']['username'])
    print(f"\n  Top recommendation: {top_user.username}")
    if hasattr(top_user, 'profile') and top_user.profile.skills:
        print(f"  Skills: {', '.join([s['name'] for s in top_user.profile.skills])}")
    
    print(f"\n{'─' * 90}")
    print("KEY INSIGHT:")
    print(f"{'─' * 90}")
    print("  When tasks require specific skills, real users with matching skills")
    print("  will score higher. Without skills, all users with 0% utilization get")
    print("  equal scores, and demo users appear first alphabetically.")
    print("\n  Now that real users have skills, they should rank higher when their")
    print("  skills match the task requirements!")

else:
    print(f"\nError: {analysis['error']}")

print(f"\n{'=' * 90}")
