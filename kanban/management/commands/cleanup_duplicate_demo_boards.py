"""
Management command to identify and remove duplicate demo boards.

This command:
1. Identifies official demo boards in Demo organizations (Dev Team, Marketing Team)
2. Finds duplicate demo boards in user organizations
3. Safely removes duplicate boards or offers to migrate users to official demo boards
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from accounts.models import Organization
from kanban.models import Board, Task


class Command(BaseCommand):
    help = 'Cleanup duplicate demo boards across organizations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--auto-fix',
            action='store_true',
            help='Automatically remove duplicates and migrate users to official demo boards',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        auto_fix = options['auto_fix']

        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('Duplicate Demo Board Cleanup Tool'))
        self.stdout.write(self.style.SUCCESS('='*70))

        # Define official demo organizations and boards
        demo_org_names = ['Dev Team', 'Marketing Team']
        demo_board_names = ['Software Project', 'Bug Tracking', 'Marketing Campaign']

        # Find official demo organizations
        demo_orgs = Organization.objects.filter(name__in=demo_org_names)
        
        if not demo_orgs.exists():
            self.stdout.write(self.style.ERROR('\n❌ No demo organizations found!'))
            self.stdout.write(self.style.WARNING('Expected organizations: Dev Team, Marketing Team'))
            self.stdout.write(self.style.WARNING('Run "python manage.py populate_test_data" first to create demo data.'))
            return

        self.stdout.write(f'\n✓ Found {demo_orgs.count()} demo organization(s): {", ".join([org.name for org in demo_orgs])}')

        # Find official demo boards
        official_demo_boards = Board.objects.filter(
            organization__in=demo_orgs,
            name__in=demo_board_names
        )

        if not official_demo_boards.exists():
            self.stdout.write(self.style.ERROR('\n❌ No official demo boards found!'))
            self.stdout.write(self.style.WARNING(f'Expected boards: {", ".join(demo_board_names)}'))
            return

        self.stdout.write(f'✓ Found {official_demo_boards.count()} official demo board(s):')
        for board in official_demo_boards:
            task_count = Task.objects.filter(column__board=board).count()
            member_count = board.members.count()
            self.stdout.write(f'  • {board.name} ({board.organization.name}) - {task_count} tasks, {member_count} members')

        # Find duplicate demo boards in other organizations
        self.stdout.write(self.style.NOTICE('\n🔍 Searching for duplicate demo boards in user organizations...'))
        
        duplicate_boards = Board.objects.filter(
            name__in=demo_board_names
        ).exclude(
            organization__in=demo_orgs
        )

        if not duplicate_boards.exists():
            self.stdout.write(self.style.SUCCESS('\n✅ No duplicate demo boards found! Your system is clean.'))
            return

        self.stdout.write(self.style.WARNING(f'\n⚠️  Found {duplicate_boards.count()} duplicate demo board(s):'))
        
        # Group duplicates by organization
        duplicates_by_org = {}
        for board in duplicate_boards:
            org_name = board.organization.name if board.organization else 'No Organization'
            if org_name not in duplicates_by_org:
                duplicates_by_org[org_name] = []
            duplicates_by_org[org_name].append(board)

        # Display duplicates
        total_tasks_to_remove = 0
        total_members_affected = 0
        
        for org_name, boards in duplicates_by_org.items():
            self.stdout.write(f'\n  📁 Organization: {org_name}')
            for board in boards:
                task_count = Task.objects.filter(column__board=board).count()
                member_count = board.members.count()
                total_tasks_to_remove += task_count
                total_members_affected += member_count
                
                self.stdout.write(
                    f'    • {board.name} (ID: {board.id}) - '
                    f'{task_count} tasks, {member_count} members'
                )

        # Summary
        self.stdout.write(self.style.WARNING(f'\n📊 Summary:'))
        self.stdout.write(f'  • Duplicate boards found: {duplicate_boards.count()}')
        self.stdout.write(f'  • Total tasks in duplicates: {total_tasks_to_remove}')
        self.stdout.write(f'  • Members affected: {total_members_affected}')

        if dry_run:
            self.stdout.write(self.style.NOTICE('\n🔍 DRY RUN MODE - No changes will be made'))
            self.stdout.write(self.style.NOTICE('Run without --dry-run to perform cleanup'))
            return

        # Perform cleanup
        if auto_fix:
            self.stdout.write(self.style.WARNING('\n🔧 AUTO-FIX MODE: Cleaning up duplicates...'))
        else:
            confirm = input('\n⚠️  Do you want to remove these duplicate boards? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('\n❌ Cleanup cancelled by user'))
                return

        # Migrate users to official demo boards and remove duplicates
        self.stdout.write(self.style.NOTICE('\n🔄 Migrating users to official demo boards...'))
        
        migrated_users = set()
        deleted_boards = 0
        deleted_tasks = 0
        
        for board in duplicate_boards:
            try:
                # Get members of the duplicate board
                members = list(board.members.all())
                
                # Find the corresponding official demo board
                official_board = official_demo_boards.filter(name=board.name).first()
                
                if official_board:
                    # Add members to the official board
                    for member in members:
                        if member not in official_board.members.all():
                            official_board.members.add(member)
                            migrated_users.add(member.username)
                            self.stdout.write(f'  ✓ Migrated {member.username} to official {official_board.name}')
                
                # Get task count before deletion
                task_count = Task.objects.filter(column__board=board).count()
                
                # Store board info
                board_name = board.name
                board_id = board.id
                
                # Delete the duplicate board (this will cascade delete related objects)
                # Delete in a transaction for each board
                with transaction.atomic():
                    board.delete()
                
                deleted_boards += 1
                deleted_tasks += task_count
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  ✓ Removed duplicate board: {board_name} (ID: {board_id}) '
                        f'with {task_count} tasks'
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'  ✗ Failed to remove board: {board.name} (ID: {board.id})'
                    )
                )
                self.stdout.write(self.style.ERROR(f'    Error: {str(e)}'))

        # Final summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('✅ Cleanup Complete!'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(f'  • Removed {deleted_boards} duplicate board(s)')
        self.stdout.write(f'  • Deleted {deleted_tasks} duplicate tasks')
        self.stdout.write(f'  • Migrated {len(migrated_users)} user(s) to official demo boards')
        if deleted_boards > 0:
            self.stdout.write(self.style.SUCCESS('\n💡 Users can now access the official demo boards from their dashboard!'))
        self.stdout.write(self.style.SUCCESS('='*70 + '\n'))
