# Generated migration to migrate Milestone data to Task model
from django.db import migrations
from django.utils import timezone


def migrate_milestones_to_tasks(apps, schema_editor):
    """
    Migrate existing Milestone records to Task records with item_type='milestone'.
    This allows unifying tasks and milestones into a single model.
    """
    Milestone = apps.get_model('kanban', 'Milestone')
    Task = apps.get_model('kanban', 'Task')
    Column = apps.get_model('kanban', 'Column')

    milestones = Milestone.objects.all()
    migrated_count = 0

    for milestone in milestones:
        # Find a suitable column for the milestone (prefer Backlog, then first column)
        backlog_column = Column.objects.filter(
            board=milestone.board,
            name__icontains='backlog'
        ).first()

        if not backlog_column:
            # Get the first column of the board
            backlog_column = Column.objects.filter(board=milestone.board).order_by('position').first()

        if not backlog_column:
            # Skip if no columns exist for this board
            print(f"Skipping milestone '{milestone.title}' - no columns in board")
            continue

        # Create Task from Milestone
        task = Task.objects.create(
            title=milestone.title,
            description=milestone.description or '',
            column=backlog_column,
            item_type='milestone',
            due_date=timezone.make_aware(
                timezone.datetime.combine(milestone.target_date, timezone.datetime.min.time())
            ) if milestone.target_date else None,
            start_date=None,  # Milestones don't have start dates
            created_by=milestone.created_by,
            progress=100 if milestone.is_completed else 0,
            position=0,
            priority='medium',  # Default priority for milestones
        )

        migrated_count += 1
        print(f"Migrated milestone '{milestone.title}' to task ID {task.id}")

    print(f"Successfully migrated {migrated_count} milestones to tasks")


def reverse_migration(apps, schema_editor):
    """
    Reverse migration - delete tasks that were created from milestones.
    Note: This is a lossy operation as we can't perfectly reconstruct the original milestones.
    """
    Task = apps.get_model('kanban', 'Task')

    # Delete all tasks with item_type='milestone'
    deleted_count, _ = Task.objects.filter(item_type='milestone').delete()
    print(f"Deleted {deleted_count} milestone tasks (reverse migration)")


class Migration(migrations.Migration):

    dependencies = [
        ('kanban', '0054_add_phase_system'),
    ]

    operations = [
        migrations.RunPython(migrate_milestones_to_tasks, reverse_migration),
    ]
