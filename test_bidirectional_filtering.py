"""
Test bidirectional filtering:
- user7 can see user8 (invited)
- user7 CANNOT see user3 (not invited)
- user3 CANNOT see user7 or user8 (not invited by user3)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board
from kanban.resource_leveling import ResourceLevelingService

demo_board = Board.objects.filter(organization__name='Dev Team').first()
service = ResourceLevelingService(demo_board.organization)

print("=" * 80)
print("BIDIRECTIONAL FILTERING TEST")
print("=" * 80)

# Get users
user7 = User.objects.get(username='user7')
user3 = User.objects.get(username='user3')

# Test: Can user7 see user3?
print("\n1. Can user7 see user3?")
print("-" * 80)
user7_report = service.get_team_workload_report(demo_board, requesting_user=user7)
user7_members = [m['username'] for m in user7_report['members']]
print(f"user3 in user7's view: {'✗ NO' if 'user3' not in user7_members else '✓ YES'}")
print(f"user7's visible members: {', '.join(user7_members)}")

# Test: Can user3 see user7 or user8?
print("\n2. Can user3 see user7 or user8?")
print("-" * 80)
user3_report = service.get_team_workload_report(demo_board, requesting_user=user3)
user3_members = [m['username'] for m in user3_report['members']]
print(f"user7 in user3's view: {'✗ NO' if 'user7' not in user3_members else '✓ YES'}")
print(f"user8 in user3's view: {'✗ NO' if 'user8' not in user3_members else '✓ YES'}")
print(f"user3's visible members: {', '.join(user3_members)}")

print("\n" + "=" * 80)
print("EXPECTED BEHAVIOR:")
print("=" * 80)
print("✓ user7 should NOT see user3 (user3 wasn't invited by user7)")
print("✓ user3 should NOT see user7 or user8 (they weren't invited by user3)")
print("✓ Both should see all demo users (john_doe, jane_smith, etc.)")
