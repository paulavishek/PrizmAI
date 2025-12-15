"""
Test Resource Leveling filtering for user7 and user8
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board, Task
from kanban.resource_leveling import ResourceLevelingService

# Get user7
user7 = User.objects.get(username='user7')
print(f"Testing as user7: {user7.username}")
print(f"Organization: {user7.profile.organization.name}\n")

# Get a demo board
demo_board = Board.objects.filter(organization__name='Dev Team').first()
print(f"Demo Board: {demo_board.name}")
print(f"Board Organization: {demo_board.organization.name}\n")

# Initialize service
service = ResourceLevelingService(demo_board.organization)

# Test 1: Get team workload report
print("=== TEAM WORKLOAD REPORT ===")
report = service.get_team_workload_report(demo_board, requesting_user=user7)
print(f"Team size: {report['team_size']}")
print(f"Members:")
for member in report['members']:
    print(f"  - {member['username']}: {member['active_tasks']} tasks, {member['utilization']}% utilization")

# Test 2: Get a task and analyze assignment
print("\n=== TASK ASSIGNMENT ANALYSIS ===")
task = Task.objects.filter(column__board=demo_board, assigned_to__isnull=True).first()
if task:
    print(f"Task: {task.title}")
    print(f"Currently assigned: {task.assigned_to.username if task.assigned_to else 'Unassigned'}")
    
    analysis = service.analyze_task_assignment(task, requesting_user=user7)
    
    if 'error' not in analysis:
        print(f"\nTop recommendation:")
        rec = analysis['top_recommendation']
        print(f"  User: {rec['username']}")
        print(f"  Score: {rec['overall_score']}")
        print(f"  Reasoning: {analysis.get('reasoning', 'N/A')}")
        
        print(f"\nAll candidates ({len(analysis['all_candidates'])}):")
        for candidate in analysis['all_candidates'][:5]:  # Show top 5
            print(f"  - {candidate['username']}: score {candidate['overall_score']}")
    else:
        print(f"Error: {analysis['error']}")
else:
    print("No unassigned tasks found")

# Test 3: Get board optimization suggestions
print("\n=== BOARD OPTIMIZATION SUGGESTIONS ===")
suggestions = service.get_board_optimization_suggestions(demo_board, limit=5, requesting_user=user7)
print(f"Total suggestions: {len(suggestions)}")
for i, sugg in enumerate(suggestions, 1):
    print(f"\n{i}. Task: {sugg.task.title}")
    print(f"   Current: {sugg.current_assignee.username if sugg.current_assignee else 'Unassigned'}")
    print(f"   Suggested: {sugg.suggested_assignee.username}")
    print(f"   Confidence: {sugg.confidence_score}%")
    print(f"   Reasoning: {sugg.reasoning[:100]}...")
