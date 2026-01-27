"""Test creating the missing task manually"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from kanban.models import Task, Board, Organization, Column
from django.contrib.auth import get_user_model

User = get_user_model()

demo_org = Organization.objects.filter(is_demo=True).first()
demo_boards = Board.objects.filter(organization=demo_org, is_official_demo_board=True)
software = demo_boards.filter(name__icontains='software').first()

if software:
    alex = User.objects.filter(username='alex_chen_demo').first()
    sam = User.objects.filter(username='sam_rivera_demo').first()
    
    columns = {col.name: col for col in Column.objects.filter(board=software)}
    backlog_col = columns.get('To Do') or columns.get('Backlog') or list(columns.values())[0]
    
    now = timezone.now().date()
    start = now + timedelta(days=10)
    due = start + timedelta(days=5)
    
    # Try to create the missing task
    try:
        task = Task.objects.create(
            column=backlog_col,
            title='Performance optimization',
            description='Database query optimization and caching',
            priority='high',
            complexity_score=8,
            assigned_to=sam,
            created_by=alex,
            progress=0,
            start_date=start,
            due_date=due,
            phase='Phase 3',
            is_seed_demo_data=True,
        )
        print("✅ Successfully created 'Performance optimization' task!")
        print(f"Task ID: {task.id}")
        
        # Count tasks now
        total = Task.objects.filter(column__board=software).count()
        print(f"\nTotal Software Board tasks now: {total}")
    except Exception as e:
        print(f"❌ Error creating task: {e}")
        import traceback
        traceback.print_exc()
