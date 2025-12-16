"""
Test the AI Resource Optimization view as user7
Simulate what user7 would see
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
print(f"Logged in as: {user7.username}")
print(f"Organization: {user7.profile.organization.name}\n")

# Get a demo board
demo_board = Board.objects.filter(organization__name='Dev Team').first()
print(f"Demo Board: {demo_board.name}")
print(f"Board Organization: {demo_board.organization.name}\n")

# Initialize service
service = ResourceLevelingService(demo_board.organization)

# Test: Get team workload report (this is what the UI calls)
print("=" * 80)
print("AI RESOURCE OPTIMIZATION - TEAM WORKLOAD")
print("=" * 80)
report = service.get_team_workload_report(demo_board, requesting_user=user7)
print(f"\nTeam size: {report['team_size']}")
print(f"\nMembers visible to user7:")
for member in report['members']:
    print(f"  - {member['username']}: {member['active_tasks']} tasks, {member['utilization']}% utilization")

# Show all board members for comparison
print("\n" + "=" * 80)
print("ALL BOARD MEMBERS (for comparison)")
print("=" * 80)
all_members = demo_board.members.all()
print(f"Total board members: {all_members.count()}")
for member in all_members:
    org = member.profile.organization.name
    print(f"  - {member.username} ({org})")

# Check tasks assigned to demo users
print("\n" + "=" * 80)
print("TASKS ASSIGNED TO DEMO USERS")
print("=" * 80)
demo_usernames = ['john_doe', 'jane_smith', 'robert_johnson', 'alice_williams', 'bob_martinez']
for username in demo_usernames:
    user = User.objects.filter(username=username).first()
    if user:
        task_count = Task.objects.filter(
            column__board=demo_board,
            assigned_to=user,
            completed_at__isnull=True
        ).count()
        print(f"  {username}: {task_count} active tasks")
