"""
Management command to refresh all user performance profiles
Run this to sync workload data after the signal handler fix
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from accounts.models import Organization
from kanban.resource_leveling_models import UserPerformanceProfile
from kanban.models import Board


class Command(BaseCommand):
    help = 'Refresh all user performance profiles and workload data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--organization',
            type=int,
            help='Only refresh profiles for a specific organization ID',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting profile refresh...'))
        
        # Determine which organizations to process
        if options['organization']:
            organizations = Organization.objects.filter(id=options['organization'])
            if not organizations.exists():
                self.stdout.write(self.style.ERROR(f'Organization ID {options["organization"]} not found'))
                return
        else:
            organizations = Organization.objects.all()
        
        total_updated = 0
        
        for org in organizations:
            self.stdout.write(f'\nProcessing organization: {org.name}')
            
            # Get all boards in this organization
            boards = Board.objects.filter(organization=org)
            self.stdout.write(f'  Found {boards.count()} boards')
            
            # Get all unique users who are members of these boards
            board_members = set()
            for board in boards:
                board_members.update(board.members.all())
            
            self.stdout.write(f'  Found {len(board_members)} unique team members')
            
            # Process each user
            for user in board_members:
                try:
                    # Get or create profile
                    profile, created = UserPerformanceProfile.objects.get_or_create(
                        user=user,
                        organization=org
                    )
                    
                    # Update all metrics
                    old_workload = profile.current_workload_hours
                    old_tasks = profile.current_active_tasks
                    
                    profile.update_metrics()
                    profile.update_current_workload()
                    
                    action = 'Created' if created else 'Updated'
                    self.stdout.write(
                        f'    {action} profile for {user.username}: '
                        f'{old_tasks} → {profile.current_active_tasks} tasks, '
                        f'{old_workload:.1f}h → {profile.current_workload_hours:.1f}h workload'
                    )
                    
                    total_updated += 1
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'    Error updating {user.username}: {str(e)}')
                    )
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Successfully refreshed {total_updated} user profiles')
        )
        self.stdout.write(
            self.style.SUCCESS('All workload data is now in sync!')
        )
