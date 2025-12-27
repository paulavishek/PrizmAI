"""
Management command to reset demo data
Removes all user-created changes and restores demo to original state
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.core.management import call_command
from accounts.models import Organization
from kanban.models import Board, Column, Task, Comment, TaskActivity


class Command(BaseCommand):
    help = 'Reset demo data to original state (removes user-created changes)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-confirm',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        no_confirm = options['no_confirm']

        # Demo organizations
        demo_org_names = ['Dev Team', 'Marketing Team']
        
        self.stdout.write(self.style.WARNING('='*80))
        self.stdout.write(self.style.WARNING('RESET DEMO DATA'))
        self.stdout.write(self.style.WARNING('='*80))
        self.stdout.write('')

        # Get demo organizations
        demo_orgs = Organization.objects.filter(name__in=demo_org_names)
        
        if not demo_orgs.exists():
            self.stdout.write(self.style.ERROR('No demo organizations found'))
            return

        # Get demo boards
        demo_boards = Board.objects.filter(organization__in=demo_orgs)
        
        # Count what will be reset
        self.stdout.write(f'📊 Current Demo State:')
        self.stdout.write(f'  Demo organizations: {demo_orgs.count()}')
        self.stdout.write(f'  Demo boards: {demo_boards.count()}')
        self.stdout.write(f'  Total tasks: {Task.objects.filter(column__board__in=demo_boards).count()}')
        self.stdout.write(f'  Total comments: {Comment.objects.filter(task__column__board__in=demo_boards).count()}')
        self.stdout.write(f'  Total activities: {TaskActivity.objects.filter(task__column__board__in=demo_boards).count()}')
        self.stdout.write('')

        # Ask for confirmation
        if not no_confirm:
            self.stdout.write(self.style.WARNING('⚠️  WARNING:'))
            self.stdout.write('This will:')
            self.stdout.write('  1. DELETE all demo data')
            self.stdout.write('  2. RECREATE fresh demo data')
            self.stdout.write('  3. RESET all board memberships')
            self.stdout.write('  4. REFRESH all dates to be current')
            self.stdout.write('')
            response = input('Do you want to continue? (yes/no): ')
            
            if response.lower() != 'yes':
                self.stdout.write(self.style.ERROR('\n❌ Operation cancelled'))
                return

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*80))
        self.stdout.write(self.style.SUCCESS('RESETTING DEMO DATA...'))
        self.stdout.write(self.style.SUCCESS('='*80))
        self.stdout.write('')

        try:
            with transaction.atomic():
                # Step 1: Delete all demo data
                self.stdout.write('[1/4] Deleting existing demo data...')
                call_command('delete_demo_data', '--no-confirm')
                self.stdout.write(self.style.SUCCESS('  ✓ Demo data deleted'))
                
                # Step 2: Create fresh demo data
                self.stdout.write('\n[2/4] Creating fresh demo data...')
                call_command('populate_test_data')
                self.stdout.write(self.style.SUCCESS('  ✓ Demo data created'))
                
                # Step 3: Reset board memberships
                self.stdout.write('\n[3/4] Resetting board memberships...')
                # Get refreshed demo boards
                demo_boards = Board.objects.filter(
                    organization__name__in=demo_org_names
                )
                for board in demo_boards:
                    # Keep only the creator
                    board.members.set([board.created_by])
                self.stdout.write(self.style.SUCCESS('  ✓ Board memberships reset'))
                
                # Step 4: Refresh dates
                self.stdout.write('\n[4/4] Refreshing dates...')
                call_command('refresh_demo_dates', '--no-confirm')
                self.stdout.write(self.style.SUCCESS('  ✓ Dates refreshed'))

            # Final stats
            demo_orgs = Organization.objects.filter(name__in=demo_org_names)
            demo_boards = Board.objects.filter(organization__in=demo_orgs)
            total_tasks = Task.objects.filter(column__board__in=demo_boards).count()

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('='*80))
            self.stdout.write(self.style.SUCCESS('✅ DEMO RESET COMPLETE!'))
            self.stdout.write(self.style.SUCCESS('='*80))
            self.stdout.write('')
            self.stdout.write(f'📊 Reset Demo State:')
            self.stdout.write(f'  Demo organizations: {demo_orgs.count()}')
            self.stdout.write(f'  Demo boards: {demo_boards.count()}')
            self.stdout.write(f'  Total tasks: {total_tasks}')
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('🎉 Demo data restored to original state!'))
            self.stdout.write('')
            self.stdout.write('📌 Next steps:')
            self.stdout.write('  - Visit demo boards to see fresh data')
            self.stdout.write('  - All user-created changes have been removed')
            self.stdout.write('  - Demo users need to be re-invited to boards')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error during reset: {str(e)}'))
            raise
