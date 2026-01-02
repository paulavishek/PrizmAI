"""
Populate demo time tracking data for the demo_admin_solo user

This script creates realistic time entries for the solo demo user so they
can see the time tracking features in action when they log in.
"""
import os
import django
import random
from datetime import timedelta
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Sum
from kanban.models import Board, Task, Column
from kanban.budget_models import TimeEntry


def populate_solo_demo_time_tracking():
    """Create time entries for the solo demo user"""
    
    print("=" * 60)
    print("Populating Time Tracking Data for Solo Demo User")
    print("=" * 60)
    
    # Get demo_admin_solo user
    demo_admin = User.objects.filter(username='demo_admin_solo').first()
    if not demo_admin:
        print("❌ demo_admin_solo user not found!")
        return
    
    print(f"\n✓ Found demo admin: {demo_admin.username} (ID: {demo_admin.id})")
    
    # Get demo boards
    demo_boards = Board.objects.filter(members=demo_admin)
    if not demo_boards.exists():
        print("❌ No demo boards found for demo_admin_solo!")
        return
    
    print(f"✓ Found {demo_boards.count()} demo boards")
    
    # Sample descriptions for time entries
    work_descriptions = [
        'Implemented core functionality',
        'Code review and testing',
        'Fixed bugs and edge cases',
        'Updated documentation',
        'Refactored for better performance',
        'Integration testing with external APIs',
        'UI/UX improvements and polish',
        'Database query optimization',
        'Security enhancements and audit',
        'REST API development',
        'Unit test creation and coverage',
        'Performance tuning and profiling',
        'Debugging production issues',
        'Requirements analysis and planning',
        'Design mockups and prototyping',
        'Client meeting and feedback session',
        'Code deployment and release',
        'Pair programming session',
        'Research and spike work',
        'Technical documentation update',
        'Sprint planning and estimation',
        'Backlog grooming session',
        'Architecture review',
        'Dependency updates and maintenance',
        'CI/CD pipeline improvements',
    ]
    
    today = timezone.now().date()
    time_entries_created = 0
    tasks_assigned = 0
    
    for board in demo_boards:
        print(f"\n📋 Processing board: {board.name}")
        
        # Get tasks on this board
        tasks = list(Task.objects.filter(column__board=board))
        if not tasks:
            print(f"   ⚠️ No tasks found on this board")
            continue
        
        print(f"   Found {len(tasks)} tasks")
        
        # Assign some tasks to demo_admin_solo (30-50% of tasks)
        num_to_assign = max(5, len(tasks) // 3)
        tasks_to_assign = random.sample(tasks, min(num_to_assign, len(tasks)))
        
        for task in tasks_to_assign:
            if task.assigned_to != demo_admin:
                task.assigned_to = demo_admin
                task.save()
                tasks_assigned += 1
        
        print(f"   ✓ Assigned {len(tasks_to_assign)} tasks to demo_admin_solo")
        
        # Create time entries for the assigned tasks
        for task in tasks_to_assign:
            # Skip if task already has many time entries from demo_admin
            existing_entries = TimeEntry.objects.filter(
                task=task, user=demo_admin
            ).count()
            if existing_entries >= 5:
                continue
            
            # Create 2-6 time entries per task (simulating work over multiple days)
            num_entries = random.randint(2, 6)
            
            for i in range(num_entries):
                # Random date within last 30 days (weighted towards recent)
                # More entries in recent days
                if random.random() < 0.5:
                    days_ago = random.randint(0, 7)  # 50% in last week
                else:
                    days_ago = random.randint(8, 30)  # 50% in last 3 weeks
                
                work_date = today - timedelta(days=days_ago)
                
                # Random hours between 0.5 and 6 hours
                hours_values = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
                hours_spent = Decimal(str(random.choice(hours_values)))
                
                description = random.choice(work_descriptions)
                
                # Check if entry already exists for this exact task/date
                if not TimeEntry.objects.filter(
                    task=task, 
                    user=demo_admin, 
                    work_date=work_date
                ).exists():
                    TimeEntry.objects.create(
                        task=task,
                        user=demo_admin,
                        hours_spent=hours_spent,
                        work_date=work_date,
                        description=description
                    )
                    time_entries_created += 1
        
        # Show board stats
        board_entries = TimeEntry.objects.filter(
            task__column__board=board,
            user=demo_admin
        )
        total_hours = board_entries.aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
        total_entries = board_entries.count()
        
        print(f"   ✅ Board totals: {total_entries} entries, {total_hours}h logged")
    
    print(f"\n" + "=" * 60)
    print(f"✅ Summary:")
    print(f"   • Tasks assigned to demo_admin_solo: {tasks_assigned}")
    print(f"   • Time entries created: {time_entries_created}")
    print("=" * 60)
    
    # Show overall stats
    print("\n📊 Demo Time Tracking Statistics:")
    
    total_hours = TimeEntry.objects.filter(
        user=demo_admin
    ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
    
    total_entries = TimeEntry.objects.filter(user=demo_admin).count()
    
    print(f"\n   Total for demo_admin_solo:")
    print(f"   • Total entries: {total_entries}")
    print(f"   • Total hours: {total_hours}h")
    
    # Daily breakdown for the current week
    week_start = today - timedelta(days=today.weekday())
    print(f"\n   This week's breakdown:")
    for i in range(7):
        day = week_start + timedelta(days=i)
        day_hours = TimeEntry.objects.filter(
            user=demo_admin,
            work_date=day
        ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
        day_name = day.strftime('%a %m/%d')
        marker = " ← today" if day == today else ""
        print(f"   • {day_name}: {day_hours}h{marker}")
    
    week_total = TimeEntry.objects.filter(
        user=demo_admin,
        work_date__gte=week_start,
        work_date__lte=today
    ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
    print(f"\n   Week total: {week_total}h")
    
    print("\n" + "=" * 60)
    print("Demo time tracking data setup complete! 🎉")
    print("=" * 60)
    print("\nSolo demo users can now:")
    print("  • View time tracking dashboard: /time-tracking/")
    print("  • View their timesheet: /timesheet/")
    print("  • View team timesheet: /board/<board_id>/team-timesheet/")
    print("  • Log additional time on tasks via task detail page")
    print("=" * 60)


if __name__ == '__main__':
    populate_solo_demo_time_tracking()
