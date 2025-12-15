"""
Test Resource Leveling filtering for user1 (different organization)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board
from kanban.resource_leveling import ResourceLevelingService

# Get user1
user1 = User.objects.get(username='user1')
print(f"Testing as user1: {user1.username}")
print(f"Organization: {user1.profile.organization.name}\n")

# Get a demo board
demo_board = Board.objects.filter(organization__name='Dev Team').first()
print(f"Demo Board: {demo_board.name}")
print(f"Board Organization: {demo_board.organization.name}\n")

# Initialize service
service = ResourceLevelingService(demo_board.organization)

# Test: Get team workload report
print("=== TEAM WORKLOAD REPORT (user1's view) ===")
report = service.get_team_workload_report(demo_board, requesting_user=user1)
print(f"Team size: {report['team_size']}")
print(f"Members:")
for member in report['members']:
    print(f"  - {member['username']}: {member['active_tasks']} tasks, {member['utilization']}% utilization")

print("\n" + "="*50)
print("EXPECTED: user1 should only see users from 'organization 1'")
print("ACTUAL: See above - should NOT include user7, user8 from 'organization'")
