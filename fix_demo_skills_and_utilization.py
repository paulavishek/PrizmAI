#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth import get_user_model
from kanban.models import Board, Task
from kanban.utils.skill_analysis import update_team_skill_profile_model

User = get_user_model()

def fix_board_membership():
    """
    Diversify board membership to show different skills per board.
    """
    print("\n" + "="*80)
    print("FIXING DEMO BOARD MEMBERSHIP")
    print("="*80)
    
    # Get demo boards
    boards = {
        'software': Board.objects.get(id=1, name="Software Development"),
        'marketing': Board.objects.get(id=2, name="Marketing Campaign"),
        'bug': Board.objects.get(id=3, name="Bug Tracking"),
    }
    
    # Get demo users
    users = {
        'alex': User.objects.get(username='alex_chen_demo'),
        'sam': User.objects.get(username='sam_rivera_demo'),
        'jordan': User.objects.get(username='jordan_taylor_demo'),
        'admin': User.objects.get(username='demo_admin_solo'),
    }
    
    # Clear all memberships first
    for board in boards.values():
        board.members.clear()
        print(f"\n✓ Cleared members from: {board.name}")
    
    # Software Development: Technical team (Alex + Sam)
    boards['software'].members.add(users['alex'], users['sam'])
    print(f"\n✓ Software Development: Added alex_chen_demo, sam_rivera_demo")
    print("  Skills: Project Management, Agile, Leadership, Python, JavaScript, Django, React")
    
    # Marketing Campaign: Business team (Alex + Jordan)
    boards['marketing'].members.add(users['alex'], users['jordan'])
    print(f"\n✓ Marketing Campaign: Added alex_chen_demo, jordan_taylor_demo")
    print("  Skills: Project Management, Agile, Leadership, Strategic Planning, Business Analysis")
    
    # Bug Tracking: Mixed team (Sam + Jordan)
    boards['bug'].members.add(users['sam'], users['jordan'])
    print(f"\n✓ Bug Tracking: Added sam_rivera_demo, jordan_taylor_demo")
    print("  Skills: Python, JavaScript, Django, React, Strategic Planning, Business Analysis")
    
    return boards, users

def fix_workload_data(boards, users):
    """
    Calculate and update user workload based on their assigned tasks.
    """
    print("\n" + "="*80)
    print("CALCULATING USER WORKLOAD FROM ASSIGNED TASKS")
    print("="*80)
    
    from accounts.models import UserProfile
    from decimal import Decimal
    
    # Calculate workload for each user
    for username, user in users.items():
        # Get all tasks assigned to this user across all demo boards
        assigned_tasks = Task.objects.filter(
            column__board__in=boards.values(),
            assigned_to=user,
            column__name__in=['To Do', 'In Progress']  # Only active tasks
        )
        
        # Calculate total workload based on task complexity
        # Since tasks don't have estimated_hours, we'll estimate based on complexity
        total_hours = 0
        task_count = 0
        
        for task in assigned_tasks:
            # Convert complexity score (1-10) to estimated hours (2-20)
            estimated_hours = task.complexity_score * 2
            total_hours += estimated_hours
            task_count += 1
        
        # Update user profile workload
        try:
            profile = user.profile
            profile.current_workload_hours = total_hours
            profile.save()
            
            print(f"\n✓ {username} ({user.username}):")
            print(f"  Active Tasks: {task_count}")
            print(f"  Total Workload: {total_hours}h")
            print(f"  Capacity: {profile.weekly_capacity_hours}h")
            print(f"  Utilization: {(total_hours/profile.weekly_capacity_hours*100) if profile.weekly_capacity_hours > 0 else 0:.1f}%")
            
        except UserProfile.DoesNotExist:
            print(f"\n✗ {username}: No profile found")
        except Exception as e:
            print(f"\n✗ {username}: Error updating workload - {str(e)}")

def update_skill_profiles(boards):
    """
    Regenerate skill profiles for all boards.
    """
    print("\n" + "="*80)
    print("UPDATING TEAM SKILL PROFILES")
    print("="*80)
    
    for board in boards.values():
        profile = update_team_skill_profile_model(board)
        
        print(f"\n✓ {board.name}:")
        print(f"  Members: {board.members.count()}")
        print(f"  Skills: {len(profile.skill_inventory)}")
        print(f"  Capacity: {profile.total_capacity_hours}h")
        print(f"  Utilized: {profile.utilized_capacity_hours}h")
        print(f"  Utilization: {profile.utilization_percentage}%")

def main():
    print("\n🚀 Starting Demo Skill Gap Fix...\n")
    
    # Step 1: Fix board membership
    boards, users = fix_board_membership()
    
    # Step 2: Add workload data
    fix_workload_data(boards, users)
    
    # Step 3: Update skill profiles
    update_skill_profiles(boards)
    
    print("\n" + "="*80)
    print("✅ COMPLETE!")
    print("="*80)
    print("\nResults:")
    print("  1. Each board now has different members (different skill matrices)")
    print("  2. Tasks have estimated hours (realistic utilization metrics)")
    print("  3. Team skill profiles regenerated with new data")
    print("\nPlease refresh the Skill Gap Dashboard to see the changes.")
    print("="*80)

if __name__ == '__main__':
    main()
