"""
Test AI suggestions to ensure they show the right users
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
print(" " * 25 + "AI SUGGESTIONS TEST")
print("=" * 90)

# Get an unassigned task
unassigned_task = Task.objects.filter(
    column__board=demo_board,
    assigned_to__isnull=True
).first()

if unassigned_task:
    print(f"\nTask: {unassigned_task.title}")
    print(f"Status: Unassigned")
    
    # Test as user7
    print(f"\n{'─' * 90}")
    print("AI Suggestions for user7:")
    print(f"{'─' * 90}")
    
    user7 = User.objects.get(username='user7')
    analysis = service.analyze_task_assignment(unassigned_task, requesting_user=user7)
    
    if 'error' not in analysis:
        print(f"\nTop recommendation: {analysis['top_recommendation']['username']}")
        print(f"\nAll candidates ({len(analysis['all_candidates'])}):")
        for i, candidate in enumerate(analysis['all_candidates'][:5], 1):
            print(f"  {i}. {candidate['username']} (score: {candidate['overall_score']:.1f})")
        
        # Verify candidates
        candidate_usernames = [c['username'] for c in analysis['all_candidates']]
        demo_users = ['john_doe', 'jane_smith', 'robert_johnson', 'alice_williams', 'bob_martinez']
        
        print(f"\n{'─' * 90}")
        print("Verification:")
        print(f"{'─' * 90}")
        
        demo_present = all(u in candidate_usernames for u in demo_users if User.objects.filter(username=u).exists())
        user8_present = 'user8' in candidate_usernames
        user3_present = 'user3' in candidate_usernames
        user1_present = 'user1' in candidate_usernames
        
        print(f"  {'✓' if demo_present else '✗'} Demo users present in suggestions")
        print(f"  {'✓' if user8_present else '✗'} user8 present (invited by user7)")
        print(f"  {'✓' if not user3_present else '✗'} user3 NOT present (not invited)")
        print(f"  {'✓' if not user1_present else '✗'} user1 NOT present (different org)")
        
        if demo_present and user8_present and not user3_present and not user1_present:
            print(f"\n{'=' * 90}")
            print("✓ AI SUGGESTIONS TEST PASSED!")
            print("=" * 90)
        else:
            print(f"\n{'=' * 90}")
            print("✗ AI SUGGESTIONS TEST FAILED!")
            print("=" * 90)
    else:
        print(f"Error: {analysis['error']}")
else:
    print("\nNo unassigned tasks found to test")
    
    # Get a task assigned to a demo user instead
    demo_task = Task.objects.filter(
        column__board=demo_board,
        assigned_to__username__in=['john_doe', 'jane_smith', 'robert_johnson']
    ).first()
    
    if demo_task:
        print(f"\nTask: {demo_task.title}")
        print(f"Currently assigned to: {demo_task.assigned_to.username}")
        
        user7 = User.objects.get(username='user7')
        analysis = service.analyze_task_assignment(demo_task, requesting_user=user7)
        
        if 'error' not in analysis:
            print(f"\nAI can analyze tasks assigned to demo users: ✓")
            print(f"Top recommendation: {analysis['top_recommendation']['username']}")
