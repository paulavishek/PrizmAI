"""
Management command to retroactively add assignment activities to the activity log
for tasks that were assigned before the activity logging was implemented.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from kanban.models import Task, TaskActivity


class Command(BaseCommand):
    help = 'Add assignment activities for tasks that have assignees but no assignment activity log entry'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write('='*60)
        self.stdout.write('RETROACTIVE ASSIGNMENT ACTIVITY LOGGING')
        self.stdout.write('='*60)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
        
        # Find all tasks with assignees that don't have an assignment activity
        tasks_with_assignees = Task.objects.filter(
            assigned_to__isnull=False
        ).select_related('assigned_to', 'created_by')
        
        tasks_needing_activity = []
        
        for task in tasks_with_assignees:
            # Check if this task has any assignment activity
            has_assignment_activity = TaskActivity.objects.filter(
                task=task,
                activity_type='assigned'
            ).exists()
            
            if not has_assignment_activity:
                tasks_needing_activity.append(task)
        
        self.stdout.write(f'\nFound {len(tasks_needing_activity)} tasks needing assignment activity entries')
        
        if not tasks_needing_activity:
            self.stdout.write(self.style.SUCCESS('All tasks with assignees already have assignment activities!'))
            return
        
        created_count = 0
        
        with transaction.atomic():
            for task in tasks_needing_activity:
                assignee = task.assigned_to
                assignee_name = assignee.get_full_name() or assignee.username
                
                # Use task creator as the person who assigned (best guess for retroactive data)
                assigner = task.created_by if task.created_by else assignee
                
                self.stdout.write(f'  Task "{task.title[:50]}" -> assigned to {assignee_name}')
                
                if not dry_run:
                    TaskActivity.objects.create(
                        task=task,
                        user=assigner,
                        activity_type='assigned',
                        description=f"assigned this task to {assignee_name}"
                    )
                    created_count += 1
        
        if dry_run:
            self.stdout.write(self.style.WARNING(f'\nWould create {len(tasks_needing_activity)} assignment activity entries'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\nCreated {created_count} assignment activity entries'))
