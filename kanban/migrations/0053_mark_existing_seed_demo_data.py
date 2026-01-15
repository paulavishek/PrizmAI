"""
Data migration to mark existing seed demo data.

This migration identifies seed demo data (created by populate scripts) and marks them
with is_seed_demo_data=True so they aren't accidentally cleaned up by the 48-hour
demo cleanup mechanism.

Seed data is identified by:
1. Boards: is_official_demo_board=True
2. Tasks: On official demo boards + created_by_session is NULL or empty + 
   created BEFORE a specific cutoff date (Jan 1, 2026 - seed data was created Dec 31, 2025)
   
Tasks created AFTER the cutoff with NULL session are likely user-created tasks
where session tracking failed (e.g., AI-generated subtasks).
"""
from django.db import migrations
from django.utils import timezone
from datetime import datetime, timezone as dt_timezone


# Seed data was created on Dec 31, 2025
# Any task created after this date with NULL session is likely a user-created task
# where session tracking failed
SEED_DATA_CUTOFF = datetime(2026, 1, 1, 0, 0, 0, tzinfo=dt_timezone.utc)


def mark_seed_demo_data(apps, schema_editor):
    """Mark existing seed demo data as is_seed_demo_data=True"""
    Board = apps.get_model('kanban', 'Board')
    Task = apps.get_model('kanban', 'Task')
    Organization = apps.get_model('accounts', 'Organization')
    
    # Find demo organization
    demo_org = Organization.objects.filter(is_demo=True).first()
    if not demo_org:
        print("No demo organization found, skipping seed data marking")
        return
    
    # Mark official demo boards as seed data
    boards_updated = Board.objects.filter(
        organization=demo_org,
        is_official_demo_board=True
    ).update(is_seed_demo_data=True)
    print(f"Marked {boards_updated} boards as seed demo data")
    
    # Mark tasks on official demo boards that:
    # - Have NULL or empty created_by_session (not user-created)
    # - Are on official demo boards
    # - Were created BEFORE the cutoff date (seed data was created Dec 31, 2025)
    # 
    # Tasks created AFTER the cutoff with NULL session are likely user-created
    # where session tracking failed
    tasks_updated = Task.objects.filter(
        column__board__organization=demo_org,
        column__board__is_official_demo_board=True,
        created_by_session__isnull=True,
        created_at__lt=SEED_DATA_CUTOFF  # Only tasks created BEFORE Jan 1, 2026
    ).update(is_seed_demo_data=True)
    
    # Also update tasks with empty string created_by_session (before cutoff)
    tasks_updated_empty = Task.objects.filter(
        column__board__organization=demo_org,
        column__board__is_official_demo_board=True,
        created_by_session='',
        created_at__lt=SEED_DATA_CUTOFF
    ).update(is_seed_demo_data=True)
    
    total_marked = tasks_updated + tasks_updated_empty
    print(f"Marked {total_marked} tasks as seed demo data (created before {SEED_DATA_CUTOFF})")
    
    # Explicitly mark tasks created AFTER cutoff with NULL session as NOT seed data
    # These are user-created tasks where tracking failed
    user_tasks = Task.objects.filter(
        column__board__organization=demo_org,
        column__board__is_official_demo_board=True,
        created_by_session__isnull=True,
        created_at__gte=SEED_DATA_CUTOFF
    ).update(is_seed_demo_data=False)
    
    if user_tasks > 0:
        print(f"Marked {user_tasks} tasks as NOT seed data (created after {SEED_DATA_CUTOFF}, likely user-created)")


def reverse_mark_seed_demo_data(apps, schema_editor):
    """Reverse: Set all is_seed_demo_data back to False"""
    Board = apps.get_model('kanban', 'Board')
    Task = apps.get_model('kanban', 'Task')
    
    Board.objects.filter(is_seed_demo_data=True).update(is_seed_demo_data=False)
    Task.objects.filter(is_seed_demo_data=True).update(is_seed_demo_data=False)


class Migration(migrations.Migration):
    dependencies = [
        ('kanban', '0052_add_is_seed_demo_data'),
    ]

    operations = [
        migrations.RunPython(
            mark_seed_demo_data,
            reverse_mark_seed_demo_data
        ),
    ]
