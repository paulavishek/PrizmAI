"""
Script to remove all real users from the database, keeping only demo users.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()

# Demo usernames to KEEP (do not delete these)
DEMO_USERNAMES = [
    'sam_rivera_demo',
    'jordan_taylor_demo', 
    'alex_chen_demo',
    'demo_admin',
    'demo_admin_solo',
]

print("=" * 60)
print("CLEANUP REAL USERS - Keep Demo Users Only")
print("=" * 60)

# Get all users
all_users = User.objects.all().order_by('username')
print(f"\nTotal users in database: {all_users.count()}")

print("\n--- DEMO USERS (will be KEPT) ---")
demo_users = User.objects.filter(username__in=DEMO_USERNAMES)
for user in demo_users:
    print(f"  ✓ {user.username} ({user.email})")

print("\n--- REAL USERS (will be DELETED) ---")
real_users = User.objects.exclude(username__in=DEMO_USERNAMES)
for user in real_users:
    print(f"  ✗ {user.username} ({user.email})")

if real_users.count() == 0:
    print("\n  No real users to delete!")
    sys.exit(0)

print(f"\n⚠️  WARNING: This will delete {real_users.count()} user(s)!")
confirm = input("Type 'DELETE' to confirm: ")

if confirm == 'DELETE':
    try:
        with transaction.atomic():
            # Get the demo admin user to reassign ownership
            demo_admin = User.objects.filter(username='demo_admin_solo').first()
            if not demo_admin:
                demo_admin = User.objects.filter(username__in=DEMO_USERNAMES).first()
            
            # Import models
            from accounts.models import Organization
            from kanban.models import Board, Task, Column, BoardMembership
            
            count = real_users.count()
            
            for user in real_users:
                print(f"\nProcessing {user.username}...")
                
                # 1. Remove board memberships
                BoardMembership.objects.filter(user=user).delete()
                print(f"  - Removed board memberships")
                
                # 2. Reassign organizations created by this user
                orgs = Organization.objects.filter(created_by=user)
                for org in orgs:
                    org.created_by = demo_admin
                    org.save()
                    print(f"  - Reassigned organization: {org.name}")
                
                # 3. Reassign boards created by this user
                boards = Board.objects.filter(created_by=user)
                for board in boards:
                    board.created_by = demo_admin
                    board.save()
                    print(f"  - Reassigned board: {board.name}")
                
                # 4. Unassign tasks assigned to this user (set to None)
                tasks = Task.objects.filter(assigned_to=user)
                tasks.update(assigned_to=None)
                print(f"  - Unassigned {tasks.count()} tasks")
                
                # 5. Reassign tasks created by this user
                created_tasks = Task.objects.filter(created_by=user)
                created_tasks.update(created_by=demo_admin)
                print(f"  - Reassigned {created_tasks.count()} created tasks")
                
                # 6. Delete the user
                user.delete()
                print(f"  ✅ Deleted user: {user.username}")
            
            print(f"\n✅ Successfully deleted {count} real user(s).")
            print(f"Remaining users: {User.objects.count()}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
else:
    print("\n❌ Cancelled. No users were deleted.")
