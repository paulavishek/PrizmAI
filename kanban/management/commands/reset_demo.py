"""
Management command to reset demo data
Removes all user-created changes and restores demo to original state.

This command aligns with the dashboard reset button in demo_views.py.
It uses the new demo system with 'Demo - Acme Corporation' organization.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.core.management import call_command
from io import StringIO
from accounts.models import Organization
from kanban.models import Board, Task, Comment, TaskActivity, TaskFile
from kanban.budget_models import TimeEntry
from kanban.stakeholder_models import ProjectStakeholder


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
        
        self.stdout.write(self.style.WARNING('='*80))
        self.stdout.write(self.style.WARNING('RESET DEMO DATA'))
        self.stdout.write(self.style.WARNING('='*80))
        self.stdout.write('')

        # Get demo organization (new system)
        demo_org = Organization.objects.filter(is_demo=True).first()
        
        if not demo_org:
            self.stdout.write(self.style.ERROR('No demo organization found'))
            self.stdout.write('Please run: python manage.py create_demo_organization')
            return

        # Get demo boards
        demo_boards = Board.objects.filter(
            organization=demo_org,
            is_official_demo_board=True
        )
        
        # Count what will be reset
        task_count = Task.objects.filter(column__board__in=demo_boards).count()
        comment_count = Comment.objects.filter(task__column__board__in=demo_boards).count()
        activity_count = TaskActivity.objects.filter(task__column__board__in=demo_boards).count()
        time_entry_count = TimeEntry.objects.filter(task__column__board__in=demo_boards).count()
        stakeholder_count = ProjectStakeholder.objects.filter(board__in=demo_boards).count()
        
        self.stdout.write('Current Demo State:')
        self.stdout.write(f'  Organization: {demo_org.name}')
        self.stdout.write(f'  Demo boards: {demo_boards.count()}')
        self.stdout.write(f'  Tasks: {task_count}')
        self.stdout.write(f'  Comments: {comment_count}')
        self.stdout.write(f'  Activities: {activity_count}')
        self.stdout.write(f'  Time Entries: {time_entry_count}')
        self.stdout.write(f'  Stakeholders: {stakeholder_count}')
        self.stdout.write('')

        # Ask for confirmation
        if not no_confirm:
            self.stdout.write(self.style.WARNING('WARNING:'))
            self.stdout.write('This will:')
            self.stdout.write('  1. DELETE all demo tasks and related data')
            self.stdout.write('  2. RECREATE fresh demo data with all fields populated')
            self.stdout.write('  3. REFRESH AI assistant and messaging data')
            self.stdout.write('  4. REFRESH all dates to be current')
            self.stdout.write('  5. DETECT conflicts for fresh data')
            self.stdout.write('')
            response = input('Do you want to continue? (yes/no): ')
            
            if response.lower() != 'yes':
                self.stdout.write(self.style.ERROR('\nOperation cancelled'))
                return

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*80))
        self.stdout.write(self.style.SUCCESS('RESETTING DEMO DATA...'))
        self.stdout.write(self.style.SUCCESS('='*80))
        self.stdout.write('')

        try:
            # Capture output for logging
            out = StringIO()
            
            # Step 1: Repopulate wiki demo data first (pages needed for task wiki links)
            self.stdout.write('[1/6] Repopulating wiki data...')
            try:
                call_command('populate_wiki_demo_data', '--reset', stdout=out, stderr=out)
                self.stdout.write(self.style.SUCCESS('  Done'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Skipped: {str(e)}'))
            
            # Step 2: Repopulate main demo tasks (with --reset to clear and recreate)
            self.stdout.write('[2/6] Repopulating demo tasks and data...')
            call_command('populate_demo_data', '--reset', stdout=out, stderr=out)
            self.stdout.write(self.style.SUCCESS('  Done'))
            
            # Step 3: Repopulate AI assistant data
            self.stdout.write('[3/6] Repopulating AI assistant data...')
            try:
                call_command('populate_ai_assistant_demo_data', '--reset', stdout=out, stderr=out)
                self.stdout.write(self.style.SUCCESS('  Done'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Skipped: {str(e)}'))
            
            # Step 4: Repopulate messaging data
            self.stdout.write('[4/6] Repopulating messaging data...')
            try:
                call_command('populate_messaging_demo_data', '--clear', stdout=out, stderr=out)
                self.stdout.write(self.style.SUCCESS('  Done'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Skipped: {str(e)}'))
            
            # Step 5: Refresh all dates to current
            self.stdout.write('[5/6] Refreshing dates...')
            try:
                call_command('refresh_demo_dates', '--force', stdout=out, stderr=out)
                self.stdout.write(self.style.SUCCESS('  Done'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Skipped: {str(e)}'))
            
            # Step 6: Detect conflicts for fresh data
            self.stdout.write('[6/6] Detecting conflicts...')
            try:
                call_command('detect_conflicts', stdout=out, stderr=out)
                self.stdout.write(self.style.SUCCESS('  Done'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Skipped: {str(e)}'))

            # Final stats
            from wiki.models import WikiPage, WikiLink
            from messaging.models import ChatRoom, ChatMessage
            from ai_assistant.models import AIAssistantSession
            from kanban.conflict_models import ConflictDetection
            
            demo_boards = Board.objects.filter(
                organization=demo_org,
                is_official_demo_board=True
            )
            task_count = Task.objects.filter(column__board__in=demo_boards).count()
            comment_count = Comment.objects.filter(task__column__board__in=demo_boards).count()
            activity_count = TaskActivity.objects.filter(task__column__board__in=demo_boards).count()
            time_entry_count = TimeEntry.objects.filter(task__column__board__in=demo_boards).count()
            stakeholder_count = ProjectStakeholder.objects.filter(board__in=demo_boards).count()
            file_count = TaskFile.objects.filter(task__column__board__in=demo_boards).count()
            wiki_page_count = WikiPage.objects.filter(organization=demo_org).count()
            wiki_link_count = WikiLink.objects.filter(wiki_page__organization=demo_org).count()
            chat_room_count = ChatRoom.objects.filter(board__in=demo_boards).count()
            chat_message_count = ChatMessage.objects.filter(chat_room__board__in=demo_boards).count()
            ai_session_count = AIAssistantSession.objects.filter(board__in=demo_boards).count()
            conflict_count = ConflictDetection.objects.filter(board__in=demo_boards, status='active').count()

            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('='*80))
            self.stdout.write(self.style.SUCCESS('DEMO RESET COMPLETE!'))
            self.stdout.write(self.style.SUCCESS('='*80))
            self.stdout.write('')
            self.stdout.write('Reset Demo State:')
            self.stdout.write(f'  Organization: {demo_org.name}')
            self.stdout.write(f'  Demo boards: {demo_boards.count()}')
            self.stdout.write(f'  Tasks: {task_count}')
            self.stdout.write(f'  Comments: {comment_count}')
            self.stdout.write(f'  Activities: {activity_count}')
            self.stdout.write(f'  Time Entries: {time_entry_count}')
            self.stdout.write(f'  Stakeholders: {stakeholder_count}')
            self.stdout.write(f'  File Attachments: {file_count}')
            self.stdout.write(f'  Wiki Pages: {wiki_page_count}')
            self.stdout.write(f'  Wiki Links: {wiki_link_count}')
            self.stdout.write(f'  Chat Rooms: {chat_room_count}')
            self.stdout.write(f'  Chat Messages: {chat_message_count}')
            self.stdout.write(f'  AI Sessions: {ai_session_count}')
            self.stdout.write(f'  Active Conflicts: {conflict_count}')
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Demo data restored to original state!'))
            self.stdout.write('')
            self.stdout.write('Next steps:')
            self.stdout.write('  - Visit /demo/ to see fresh demo data')
            self.stdout.write('  - All user-created changes have been removed')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\nError during reset: {str(e)}'))
            raise
