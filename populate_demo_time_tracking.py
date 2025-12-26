"""
Populate demo boards with realistic time tracking data
Creates time entries for demo users on demo boards
"""
import os
import django
import random
from datetime import datetime, timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q, Sum
from kanban.models import Board, Task
from kanban.budget_models import TimeEntry


def create_demo_time_entries():
    """Create realistic time entries for demo boards"""
    
    print("=" * 60)
    print("Adding Time Tracking Data to Demo Boards")
    print("=" * 60)
    
    # Get demo boards
    demo_boards = Board.objects.filter(
        Q(organization__name='Dev Team') | 
        Q(organization__name='Marketing Team')
    )
    
    if not demo_boards.exists():
        print("❌ No demo boards found!")
        return
    
    print(f"\nFound {demo_boards.count()} demo boards")
    
    time_entries_created = 0
    
    for board in demo_boards:
        print(f"\n📋 Processing board: {board.name}")
        
        # Get tasks on this board
        tasks = Task.objects.filter(column__board=board)
        print(f"   Found {tasks.count()} tasks")
        
        # Get board members
        members = board.members.all()
        if not members.exists():
            print("   ⚠️ No members found, skipping")
            continue
        
        print(f"   Found {members.count()} members")
        
        # Create time entries for tasks
        for task in tasks:
            # Skip if task already has many time entries
            existing_entries = TimeEntry.objects.filter(task=task).count()
            if existing_entries >= 5:
                continue
            
            # Determine assignee or random member
            user = task.assigned_to if task.assigned_to else random.choice(members)
            
            # Create 1-5 time entries per task
            num_entries = random.randint(1, 5)
            
            for i in range(num_entries):
                # Random date within last 30 days
                days_ago = random.randint(1, 30)
                work_date = (timezone.now() - timedelta(days=days_ago)).date()
                
                # Random hours between 0.5 and 8
                hours_spent = Decimal(str(round(random.uniform(0.5, 8.0), 2)))
                
                # Sample descriptions
                descriptions = [
                    'Implemented core functionality',
                    'Code review and testing',
                    'Fixed bugs and edge cases',
                    'Updated documentation',
                    'Refactored code for better performance',
                    'Integration testing',
                    'UI/UX improvements',
                    'Database optimization',
                    'Security enhancements',
                    'API development',
                    'Unit test creation',
                    'Performance tuning',
                    'Debugging production issues',
                    'Requirements analysis',
                    'Design mockups',
                    'Client meeting and feedback',
                    'Code deployment',
                    'Pair programming session',
                    'Research and planning',
                    'Technical documentation',
                ]
                
                description = random.choice(descriptions)
                
                # Check if entry already exists for this date
                if not TimeEntry.objects.filter(
                    task=task, 
                    user=user, 
                    work_date=work_date
                ).exists():
                    TimeEntry.objects.create(
                        task=task,
                        user=user,
                        hours_spent=hours_spent,
                        work_date=work_date,
                        description=description
                    )
                    time_entries_created += 1
        
        # Show board stats
        total_hours = TimeEntry.objects.filter(
            task__column__board=board
        ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
        
        total_entries = TimeEntry.objects.filter(
            task__column__board=board
        ).count()
        
        print(f"   ✅ Board totals: {total_entries} entries, {total_hours}h logged")
    
    print(f"\n" + "=" * 60)
    print(f"✅ Created {time_entries_created} new time entries")
    print("=" * 60)
    
    # Show overall stats
    print("\n📊 Overall Demo Statistics:")
    for board in demo_boards:
        total_hours = TimeEntry.objects.filter(
            task__column__board=board
        ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
        
        total_entries = TimeEntry.objects.filter(
            task__column__board=board
        ).count()
        
        tasks_with_time = Task.objects.filter(
            column__board=board,
            time_entries__isnull=False
        ).distinct().count()
        
        print(f"\n   {board.name}:")
        print(f"   • Total entries: {total_entries}")
        print(f"   • Total hours: {total_hours}h")
        print(f"   • Tasks with time: {tasks_with_time}")
        
        # User breakdown
        user_stats = TimeEntry.objects.filter(
            task__column__board=board
        ).values('user__username').annotate(
            total_hours=Sum('hours_spent')
        ).order_by('-total_hours')[:5]
        
        if user_stats:
            print(f"   • Top contributors:")
            for stat in user_stats:
                print(f"     - {stat['user__username']}: {stat['total_hours']}h")
    
    print("\n" + "=" * 60)
    print("Demo time tracking data setup complete! 🎉")
    print("=" * 60)
    print("\nYou can now:")
    print("  • View time tracking dashboard: /time-tracking/")
    print("  • View your timesheet: /timesheet/")
    print("  • View team timesheet: /board/<board_id>/team-timesheet/")
    print("  • Log time on tasks via task detail page")
    print("=" * 60)


if __name__ == '__main__':
    create_demo_time_entries()
