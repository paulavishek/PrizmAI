"""
Management command to populate time tracking demo data.

This creates comprehensive time entries for demo users so that the
Time Tracking Dashboard and My Timesheet features show demo data.

Demo data is created for:
- alex_chen_demo
- sam_rivera_demo  
- jordan_taylor_demo

The entries are spread over the last 30 days to show realistic time tracking
patterns with activity every day.

Usage:
    python manage.py populate_time_tracking_demo_data
    python manage.py populate_time_tracking_demo_data --reset  # Clear existing and recreate
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from datetime import timedelta
from decimal import Decimal
import random

from accounts.models import Organization
from kanban.models import Board, Task
from kanban.budget_models import TimeEntry


class Command(BaseCommand):
    help = 'Populate time tracking demo data for demo users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing time tracking demo data before creating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write('POPULATING TIME TRACKING DEMO DATA')
        self.stdout.write('=' * 80)

        # Get demo organization
        try:
            demo_org = Organization.objects.get(is_demo=True, name='Demo - Acme Corporation')
            self.stdout.write(self.style.SUCCESS(f'✓ Found organization: {demo_org.name}'))
        except Organization.DoesNotExist:
            self.stdout.write(self.style.ERROR('✗ Demo - Acme Corporation not found!'))
            self.stdout.write('  Please run: python manage.py create_demo_organization')
            return

        # Get demo users
        demo_users = {
            'alex': User.objects.filter(username='alex_chen_demo').first(),
            'sam': User.objects.filter(username='sam_rivera_demo').first(),
            'jordan': User.objects.filter(username='jordan_taylor_demo').first(),
        }
        
        # Filter out None values
        demo_users = {k: v for k, v in demo_users.items() if v is not None}
        
        if not demo_users:
            self.stdout.write(self.style.ERROR('✗ No demo users found!'))
            self.stdout.write('  Please run: python manage.py create_demo_organization')
            return

        self.stdout.write(self.style.SUCCESS(f'✓ Found {len(demo_users)} demo users'))

        # Get demo boards and tasks
        demo_boards = Board.objects.filter(organization=demo_org)
        demo_tasks = Task.objects.filter(
            column__board__in=demo_boards
        ).select_related('column', 'column__board', 'assigned_to')
        
        self.stdout.write(f'  Found {demo_boards.count()} demo boards')
        self.stdout.write(f'  Found {demo_tasks.count()} demo tasks')

        if demo_tasks.count() == 0:
            self.stdout.write(self.style.ERROR('✗ No demo tasks found!'))
            self.stdout.write('  Please run: python manage.py populate_all_demo_data')
            return

        # Reset if requested
        if options['reset']:
            self.reset_time_entries(demo_users.values(), demo_org)

        with transaction.atomic():
            stats = self.create_time_entries(demo_users, demo_tasks)

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('✓ TIME TRACKING DEMO DATA COMPLETE'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f'  Time entries created: {stats["entries"]}')
        self.stdout.write(f'  Users with entries: {stats["users"]}')
        self.stdout.write(f'  Days covered: {stats["days"]}')
        self.stdout.write('')

    def reset_time_entries(self, demo_users, demo_org):
        """Delete existing time tracking demo data"""
        self.stdout.write('\nResetting time tracking demo data...')
        
        # Delete time entries for demo users on demo boards
        deleted = TimeEntry.objects.filter(
            user__in=demo_users,
            task__column__board__organization=demo_org
        ).delete()
        
        self.stdout.write(f'  Deleted {deleted[0]} time entries')

    def create_time_entries(self, demo_users, demo_tasks):
        """Create comprehensive time tracking entries"""
        now = timezone.now()
        today = now.date()
        entries_created = 0
        days_with_entries = set()
        users_with_entries = set()
        
        # Work descriptions for variety
        descriptions = [
            "Working on implementation",
            "Code review and testing",
            "Bug fixing and debugging",
            "Feature development", 
            "Documentation updates",
            "Meeting and planning session",
            "Research and analysis",
            "Deployment and configuration",
            "Performance optimization",
            "Unit testing and QA",
            "Integration work",
            "Design review",
            "Sprint planning activities",
            "Architecture review",
            "Technical documentation",
            "Code refactoring",
            "Security review",
            "Database work",
            "API development",
            "UI/UX improvements",
            "Backlog grooming",
            "Standup and sync meeting",
            "Pair programming session",
            "Code mentoring",
            "Infrastructure setup",
        ]
        
        # User work patterns - different users have different work styles
        user_patterns = {
            'alex': {
                'avg_hours_per_day': 6.5,
                'entries_per_day': (2, 4),
                'works_weekends': False,
                'preferred_tasks': ['planning', 'review', 'architecture', 'meeting'],
            },
            'sam': {
                'avg_hours_per_day': 7.0,
                'entries_per_day': (3, 5),
                'works_weekends': True,  # Sometimes works weekends
                'preferred_tasks': ['implementation', 'testing', 'bug', 'feature'],
            },
            'jordan': {
                'avg_hours_per_day': 5.5,
                'entries_per_day': (2, 3),
                'works_weekends': False,
                'preferred_tasks': ['documentation', 'research', 'design', 'ui'],
            },
        }
        
        # Create entries for each demo user
        for user_key, user in demo_users.items():
            pattern = user_patterns.get(user_key, user_patterns['alex'])
            
            # Get tasks assigned to this user, or any tasks if none assigned
            user_tasks = list(demo_tasks.filter(assigned_to=user))
            if not user_tasks:
                # Use random tasks from the demo pool
                user_tasks = list(demo_tasks)[:20]
            
            if not user_tasks:
                continue
            
            # Create entries over the last 30 days
            for days_ago in range(30):
                entry_date = today - timedelta(days=days_ago)
                
                # Skip weekends occasionally (based on user pattern)
                is_weekend = entry_date.weekday() >= 5
                if is_weekend and not pattern['works_weekends']:
                    # 80% chance to skip weekends
                    if random.random() < 0.8:
                        continue
                elif is_weekend:
                    # Even users who work weekends do so less
                    if random.random() < 0.5:
                        continue
                
                # Number of entries for this day
                min_entries, max_entries = pattern['entries_per_day']
                num_entries = random.randint(min_entries, max_entries)
                
                # Reduce entries on some days for variety
                if random.random() < 0.2:
                    num_entries = max(1, num_entries - 1)
                
                daily_target = pattern['avg_hours_per_day']
                # Add some daily variation
                daily_target *= random.uniform(0.7, 1.3)
                hours_per_entry = daily_target / num_entries
                
                for _ in range(num_entries):
                    # Pick a task - prefer tasks assigned to this user
                    task = random.choice(user_tasks)
                    
                    # Calculate hours with natural variation
                    hours = hours_per_entry * random.uniform(0.6, 1.4)
                    # Round to quarter hours
                    hours = round(hours * 4) / 4
                    hours = max(0.25, min(hours, 8.0))  # Clamp between 0.25 and 8 hours
                    
                    # Check if entry already exists for this task/user/date
                    existing = TimeEntry.objects.filter(
                        task=task,
                        user=user,
                        work_date=entry_date
                    ).exists()
                    
                    if not existing:
                        # Pick a contextual description
                        desc = random.choice(descriptions)
                        task_context = task.title[:40] if len(task.title) > 40 else task.title
                        
                        TimeEntry.objects.create(
                            task=task,
                            user=user,
                            hours_spent=Decimal(str(hours)),
                            work_date=entry_date,
                            description=f"{desc} - {task_context}",
                        )
                        entries_created += 1
                        days_with_entries.add(entry_date)
                        users_with_entries.add(user.username)
        
        return {
            'entries': entries_created,
            'users': len(users_with_entries),
            'days': len(days_with_entries),
        }
