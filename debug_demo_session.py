"""
Debug the demo session to understand why boards aren't showing
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.utils import timezone
from kanban.models import Board, Organization

print("\n" + "="*80)
print("ACTIVE DEMO SESSIONS CHECK")
print("="*80)

# Get all active sessions
active_sessions = Session.objects.filter(expire_date__gte=timezone.now())
print(f"\nFound {active_sessions.count()} active sessions")

DEMO_ORG_NAMES = ['Demo - Acme Corporation']
demo_orgs = Organization.objects.filter(name__in=DEMO_ORG_NAMES)

for session in active_sessions:
    data = session.get_decoded()
    is_demo = data.get('is_demo_mode', False)
    demo_mode = data.get('demo_mode', None)
    user_id = data.get('_auth_user_id', None)
    
    if is_demo or demo_mode or user_id == '6':  # 6 is demo_admin_solo
        print(f"\n{'='*70}")
        print(f"Session Key: {session.session_key}")
        print(f"Expires: {session.expire_date}")
        print(f"is_demo_mode: {is_demo}")
        print(f"demo_mode: {demo_mode}")
        print(f"demo_mode_selected: {data.get('demo_mode_selected', False)}")
        print(f"demo_admin_logged_in: {data.get('demo_admin_logged_in', False)}")
        
        if user_id:
            try:
                user = User.objects.get(id=user_id)
                print(f"User: {user.username} (ID: {user.id})")
                
                # Check board memberships
                user_boards = Board.objects.filter(
                    organization__in=demo_orgs,
                    members=user
                )
                print(f"User is member of {user_boards.count()} demo boards:")
                for board in user_boards:
                    print(f"  - {board.name}")
                    
                # Check the filter that's causing the issue
                user_demo_orgs = Organization.objects.filter(
                    name__in=DEMO_ORG_NAMES,
                    boards__members=user
                ).distinct()
                print(f"\nuser_demo_orgs query result: {user_demo_orgs.count()} orgs")
                for org in user_demo_orgs:
                    print(f"  - {org.name}")
                    
            except User.DoesNotExist:
                print(f"User ID {user_id} not found!")
        else:
            print("No user authenticated (anonymous)")

print("\n" + "="*80)
print("DEMO ADMIN DIRECT CHECK")
print("="*80)

demo_admin = User.objects.get(username='demo_admin_solo')
print(f"\nUser: {demo_admin.username} (ID: {demo_admin.id})")

# Replicate the exact query from demo_dashboard view
user_demo_orgs = Organization.objects.filter(
    name__in=DEMO_ORG_NAMES,
    boards__members=demo_admin
).distinct()

print(f"user_demo_orgs query: {user_demo_orgs.count()} organizations")
for org in user_demo_orgs:
    print(f"  - {org.name}")

demo_boards = Board.objects.filter(
    organization__in=demo_orgs,
    name__in=['Software Development', 'Bug Tracking', 'Marketing Campaign']
).prefetch_related('members')

print(f"\nInitial demo_boards: {demo_boards.count()} boards")

# Apply the filter that might be causing issues
filtered_boards = demo_boards.filter(organization__in=user_demo_orgs)
print(f"After filter (line 457): {filtered_boards.count()} boards")

if filtered_boards.count() == 0:
    print("\n❌ THIS IS THE BUG!")
    print("The filter on line 457 is removing all boards!")
else:
    print("\n✓ Boards are visible after filter")
