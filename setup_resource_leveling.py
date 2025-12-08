"""
Quick setup script for Resource Leveling feature
Run with: python setup_resource_leveling.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.core.management import call_command
from django.contrib.auth.models import User
from kanban.models import Board, Task
from django.utils import timezone
from datetime import timedelta

print("=" * 80)
print("RESOURCE LEVELING SETUP")
print("=" * 80)

# Step 1: Run migrations
print("\n1. Running migrations...")
try:
    call_command('makemigrations', 'kanban', interactive=False)
    call_command('migrate', interactive=False)
    print("   ✓ Migrations completed")
except Exception as e:
    print(f"   ✗ Migration error: {e}")
    sys.exit(1)

# Step 2: Check for boards
print("\n2. Checking for boards...")
board = Board.objects.first()
if not board:
    print("   ✗ No boards found. Please create a board first.")
    sys.exit(1)

print(f"   ✓ Found board: {board.name}")
print(f"   - Members: {board.members.count()}")

# Step 3: Check for tasks
print("\n3. Checking for tasks...")
completed_tasks = Task.objects.filter(
    column__board=board,
    completed_date__isnull=False,
    assigned_to__isnull=False
).count()

print(f"   - Completed tasks: {completed_tasks}")

if completed_tasks < 5:
    print("   ⚠ Few completed tasks found. Creating sample data...")
    
    # Create sample completed tasks
    for user in board.members.all()[:3]:
        for i in range(3):
            Task.objects.get_or_create(
                title=f"Sample task {i+1} by {user.username}",
                defaults={
                    'description': f"This is a sample task to build performance profile for {user.username}",
                    'column': board.columns.first(),
                    'assigned_to': user,
                    'completed_date': timezone.now() - timedelta(days=i+1),
                    'created_at': timezone.now() - timedelta(days=i+8),
                    'complexity_score': 3,
                }
            )
    print("   ✓ Created sample tasks")

# Step 4: Update profiles
print("\n4. Updating performance profiles...")
try:
    from kanban.resource_leveling import ResourceLevelingService
    
    service = ResourceLevelingService(board.organization)
    result = service.update_all_profiles(board)
    
    print(f"   ✓ Updated {result['updated']} profiles")
except Exception as e:
    print(f"   ✗ Error updating profiles: {e}")
    import traceback
    traceback.print_exc()

# Step 5: Generate suggestions
print("\n5. Generating suggestions...")
try:
    suggestions = service.get_board_optimization_suggestions(board, limit=5)
    print(f"   ✓ Generated {len(suggestions)} suggestions")
    
    if suggestions:
        print("\n   Sample suggestions:")
        for i, s in enumerate(suggestions[:3], 1):
            print(f"   {i}. {s.task.title}")
            print(f"      {s.current_assignee.username if s.current_assignee else 'unassigned'} → {s.suggested_assignee.username}")
            print(f"      Savings: {s.time_savings_percentage:.0f}%, Confidence: {s.confidence_score:.0f}%")
except Exception as e:
    print(f"   ⚠ No suggestions generated (this is okay if workload is balanced)")
    print(f"      {e}")

# Step 6: Test API
print("\n6. Testing API endpoints...")
try:
    from kanban.resource_leveling_views import get_team_workload_report
    print("   ✓ API views imported successfully")
except Exception as e:
    print(f"   ✗ Error importing views: {e}")

# Summary
print("\n" + "=" * 80)
print("SETUP COMPLETE!")
print("=" * 80)
print(f"\nNext steps:")
print(f"1. Start your server: python manage.py runserver")
print(f"2. Visit: http://localhost:8000/boards/{board.id}/")
print(f"3. Look for the 'AI Resource Optimization' widget at the top")
print(f"\nTroubleshooting:")
print(f"- If widget doesn't load, check browser console (F12)")
print(f"- Run: python manage.py test_resource_leveling")
print(f"- Check API: http://localhost:8000/api/resource-leveling/boards/{board.id}/workload-report/")
print("\n" + "=" * 80)
