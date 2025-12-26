"""
Create a demo welcome message for RBAC features
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.models import Board
from kanban.permission_models import BoardMembership

# Get all demo board members
demo_boards = Board.objects.filter(organization__name__in=['Dev Team', 'Marketing Team'])
demo_users = User.objects.filter(board_memberships__board__in=demo_boards).distinct()

print("=" * 80)
print("DEMO USER ROLE DISTRIBUTION")
print("=" * 80)

for board in demo_boards:
    print(f"\n📋 {board.name}")
    print(f"   Organization: {board.organization.name}")
    print(f"\n   Members by Role:")
    
    memberships = BoardMembership.objects.filter(board=board).select_related('user', 'role')
    
    role_counts = {}
    for membership in memberships:
        role_name = membership.role.name
        if role_name not in role_counts:
            role_counts[role_name] = []
        role_counts[role_name].append(membership.user.username)
    
    for role_name, usernames in role_counts.items():
        print(f"   • {role_name}: {len(usernames)} users")
        if len(usernames) <= 5:
            for username in usernames:
                print(f"     - {username}")
        else:
            for username in usernames[:3]:
                print(f"     - {username}")
            print(f"     ... and {len(usernames) - 3} more")

print("\n" + "=" * 80)
print("🎯 QUICK TEST SCENARIOS")
print("=" * 80)

print("""
SCENARIO 1: Test as a Member (Restricted)
1. Go to /demo/ and open 'Software Project'
2. Notice your role badge says 'Member'
3. See blue info banner with restrictions
4. Try to drag a task to 'Done' → Error message!
5. You can only work in 'To Do' and 'In Progress'

SCENARIO 2: Test as an Editor (Full Access)
1. Go to board settings → 'Manage Members & Roles'
2. Change your role to 'Editor' (if admin) or ask admin
3. Refresh the board
4. Notice: No restriction warnings!
5. You can move tasks to any column

SCENARIO 3: View Audit Logs
1. Make some role changes
2. Move tasks between columns
3. Go to board settings → 'Permission Audit Log'
4. See complete history of all actions
5. Filter by action type or date

SCENARIO 4: Manage Team Roles
1. Go to board settings → 'Manage Members & Roles'
2. See all members with their current roles
3. Change someone's role using dropdown
4. See instant confirmation
5. Check audit log to see the change recorded
""")

print("=" * 80)
print("✅ Ready to explore RBAC in demo!")
print("=" * 80)
