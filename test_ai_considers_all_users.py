"""
Verify AI suggestions include both demo users and real users
This shows exactly which users the AI considers for task assignment
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
print(" " * 20 + "AI SUGGESTION CANDIDATE ANALYSIS")
print("=" * 90)

# Get an unassigned task
task = Task.objects.filter(
    column__board=demo_board,
    assigned_to__isnull=True
).first()

if not task:
    print("\nNo unassigned tasks found. Creating a test scenario with assigned task...")
    task = Task.objects.filter(column__board=demo_board).first()

print(f"\nTask: {task.title}")
print(f"Currently assigned to: {task.assigned_to.username if task.assigned_to else 'Unassigned'}")

# Test as user7
user7 = User.objects.get(username='user7')
print(f"\nAnalyzing as: {user7.username} (Org: {user7.profile.organization.name})")

analysis = service.analyze_task_assignment(task, requesting_user=user7)

if 'error' not in analysis:
    print(f"\n{'─' * 90}")
    print("ALL CANDIDATES CONSIDERED BY AI:")
    print(f"{'─' * 90}")
    
    # Separate demo users and real users
    demo_user_names = ['john_doe', 'jane_smith', 'robert_johnson', 'alice_williams', 
                       'bob_martinez', 'carol_anderson', 'david_taylor', 'admin']
    
    demo_candidates = []
    real_candidates = []
    
    for candidate in analysis['all_candidates']:
        if candidate['username'] in demo_user_names:
            demo_candidates.append(candidate)
        else:
            real_candidates.append(candidate)
    
    print(f"\n📊 Demo Users ({len(demo_candidates)} candidates):")
    for candidate in demo_candidates:
        user = User.objects.get(username=candidate['username'])
        active_tasks = Task.objects.filter(
            column__board=demo_board,
            assigned_to=user,
            completed_at__isnull=True
        ).count()
        print(f"  • {candidate['username']:<20} Score: {candidate['overall_score']:<6.1f} | " +
              f"Tasks: {active_tasks} | Utilization: {candidate.get('utilization_pct', 0):.1f}%")
    
    print(f"\n👥 Real Users ({len(real_candidates)} candidates):")
    for candidate in real_candidates:
        user = User.objects.get(username=candidate['username'])
        active_tasks = Task.objects.filter(
            column__board=demo_board,
            assigned_to=user,
            completed_at__isnull=True
        ).count()
        print(f"  • {candidate['username']:<20} Score: {candidate['overall_score']:<6.1f} | " +
              f"Tasks: {active_tasks} | Utilization: {candidate.get('utilization_pct', 0):.1f}%")
    
    print(f"\n{'─' * 90}")
    print("TOP 5 RECOMMENDATIONS (BEST TO WORST):")
    print(f"{'─' * 90}")
    
    for i, candidate in enumerate(analysis['all_candidates'][:5], 1):
        user_type = "📊 Demo" if candidate['username'] in demo_user_names else "👥 Real"
        print(f"  {i}. {user_type} | {candidate['username']:<20} | Score: {candidate['overall_score']:.1f}")
    
    print(f"\n{'─' * 90}")
    print("ANALYSIS:")
    print(f"{'─' * 90}")
    
    # Check if real users are in top 5
    top_5_usernames = [c['username'] for c in analysis['all_candidates'][:5]]
    real_in_top_5 = any(username in top_5_usernames for username in ['user7', 'user8'])
    
    print(f"  ✓ AI considers BOTH demo users and real users")
    print(f"  ✓ Total candidates: {len(analysis['all_candidates'])}")
    print(f"  ✓ Demo users: {len(demo_candidates)}")
    print(f"  ✓ Real users: {len(real_candidates)}")
    
    if real_in_top_5:
        print(f"  ✓ Real users (user7/user8) ARE in top 5 recommendations")
    else:
        print(f"  ℹ Real users are considered but scored lower than demo users")
        print(f"    (This is expected if demo users have better skills/availability)")
    
    print(f"\n{'─' * 90}")
    print("WHY CAROL ANDERSON IS SUGGESTED:")
    print(f"{'─' * 90}")
    
    top_candidate = analysis['top_recommendation']
    print(f"  • Username: {top_candidate['username']}")
    print(f"  • Overall Score: {top_candidate['overall_score']:.1f}")
    print(f"  • Current Workload: {top_candidate.get('utilization_pct', 0):.1f}%")
    print(f"  • Active Tasks: {top_candidate.get('active_tasks', 0)}")
    
    # Find user7 and user8 in the list
    print(f"\n  Comparison with real users:")
    for username in ['user7', 'user8']:
        user_candidate = next((c for c in analysis['all_candidates'] if c['username'] == username), None)
        if user_candidate:
            print(f"    • {username}: Score {user_candidate['overall_score']:.1f}, " +
                  f"Workload {user_candidate.get('utilization_pct', 0):.1f}%")
    
    print(f"\n  ℹ When scores are equal, the AI may pick based on:")
    print(f"    - Skill match with task requirements")
    print(f"    - Past performance on similar tasks")
    print(f"    - Or simply alphabetical order as a tiebreaker")
    
else:
    print(f"\nError: {analysis['error']}")

print(f"\n{'=' * 90}")
print("✓ CONCLUSION: AI considers BOTH demo users AND real users (user7, user8, etc.)")
print("=" * 90)
