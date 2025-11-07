"""
Management command to safely delete all demo data from TaskFlow.
This removes organizations, boards, tasks, users, and all related demo content.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from accounts.models import Organization, UserProfile
from kanban.models import (
    Board, Column, TaskLabel, Task, Comment, TaskActivity,
    ResourceDemandForecast, TeamCapacityAlert, WorkloadDistributionRecommendation,
    TaskFile
)
from kanban.stakeholder_models import (
    ProjectStakeholder, StakeholderTaskInvolvement, 
    StakeholderEngagementRecord, EngagementMetrics, StakeholderTag
)
from messaging.models import (
    ChatRoom, ChatMessage, Notification, UserTypingStatus, 
    FileAttachment, TaskThreadComment
)
from wiki.models import WikiCategory, WikiPage, WikiAttachment, MeetingNotes


class Command(BaseCommand):
    help = 'Delete all demo data (users, organizations, boards, tasks, etc.) - USE WITH CAUTION'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--no-confirm',
            action='store_true',
            help='Skip confirmation prompt (dangerous!)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        no_confirm = options['no_confirm']

        # Define demo users to delete
        demo_usernames = [
            'john_doe', 'jane_smith', 'robert_johnson', 
            'alice_williams', 'bob_martinez', 
            'carol_anderson', 'david_taylor'
        ]

        # Define demo organizations to delete
        demo_org_names = ['Dev Team', 'Marketing Team']

        self.stdout.write(self.style.WARNING('='*70))
        self.stdout.write(self.style.WARNING('DEMO DATA DELETION SCRIPT'))
        self.stdout.write(self.style.WARNING('='*70))
        self.stdout.write('')

        if dry_run:
            self.stdout.write(self.style.NOTICE('DRY RUN MODE - No data will be deleted'))
            self.stdout.write('')

        # Count what will be deleted
        demo_users = User.objects.filter(username__in=demo_usernames)
        demo_orgs = Organization.objects.filter(name__in=demo_org_names)
        
        # Get boards from demo organizations
        demo_boards = Board.objects.filter(organization__in=demo_orgs)
        
        # Count all related data
        tasks_count = Task.objects.filter(column__board__in=demo_boards).count()
        columns_count = Column.objects.filter(board__in=demo_boards).count()
        labels_count = TaskLabel.objects.filter(board__in=demo_boards).count()
        comments_count = Comment.objects.filter(task__column__board__in=demo_boards).count()
        activities_count = TaskActivity.objects.filter(task__column__board__in=demo_boards).count()
        
        # Resource management data
        forecasts_count = ResourceDemandForecast.objects.filter(board__in=demo_boards).count()
        alerts_count = TeamCapacityAlert.objects.filter(board__in=demo_boards).count()
        recommendations_count = WorkloadDistributionRecommendation.objects.filter(board__in=demo_boards).count()
        
        # Stakeholder data
        stakeholders_count = ProjectStakeholder.objects.filter(board__in=demo_boards).count()
        involvement_count = StakeholderTaskInvolvement.objects.filter(task__column__board__in=demo_boards).count()
        engagement_count = StakeholderEngagementRecord.objects.filter(stakeholder__board__in=demo_boards).count()
        
        # Messaging data
        chat_rooms_count = ChatRoom.objects.filter(board__in=demo_boards).count()
        chat_messages_count = ChatMessage.objects.filter(chat_room__board__in=demo_boards).count()
        thread_comments_count = TaskThreadComment.objects.filter(task__column__board__in=demo_boards).count()
        notifications_count = Notification.objects.filter(
            recipient__in=demo_users
        ).count() + Notification.objects.filter(sender__in=demo_users).count()
        
        # Wiki and knowledge base data
        wiki_categories_count = WikiCategory.objects.filter(organization__in=demo_orgs).count()
        wiki_pages_count = WikiPage.objects.filter(organization__in=demo_orgs).count()
        wiki_attachments_count = WikiAttachment.objects.filter(page__organization__in=demo_orgs).count()
        
        # Meeting notes
        meeting_notes_count = MeetingNotes.objects.filter(organization__in=demo_orgs).count()
        
        # User profiles
        profiles_count = UserProfile.objects.filter(user__in=demo_users).count()

        # Display summary
        self.stdout.write(self.style.NOTICE('📊 DELETION SUMMARY:'))
        self.stdout.write('')
        self.stdout.write(f'  Users:                    {demo_users.count()}')
        self.stdout.write(f'  Organizations:            {demo_orgs.count()}')
        self.stdout.write(f'  User Profiles:            {profiles_count}')
        self.stdout.write('')
        self.stdout.write(f'  Boards:                   {demo_boards.count()}')
        self.stdout.write(f'  Columns:                  {columns_count}')
        self.stdout.write(f'  Labels:                   {labels_count}')
        self.stdout.write(f'  Tasks:                    {tasks_count}')
        self.stdout.write(f'  Comments:                 {comments_count}')
        self.stdout.write(f'  Task Activities:          {activities_count}')
        self.stdout.write('')
        self.stdout.write(f'  Resource Forecasts:       {forecasts_count}')
        self.stdout.write(f'  Capacity Alerts:          {alerts_count}')
        self.stdout.write(f'  Workload Recommendations: {recommendations_count}')
        self.stdout.write('')
        self.stdout.write(f'  Stakeholders:             {stakeholders_count}')
        self.stdout.write(f'  Task Involvements:        {involvement_count}')
        self.stdout.write(f'  Engagement Records:       {engagement_count}')
        self.stdout.write('')
        self.stdout.write(f'  Chat Rooms:               {chat_rooms_count}')
        self.stdout.write(f'  Chat Messages:            {chat_messages_count}')
        self.stdout.write(f'  Thread Comments:          {thread_comments_count}')
        self.stdout.write(f'  Notifications:            {notifications_count}')
        self.stdout.write('')
        self.stdout.write(f'  Wiki Categories:          {wiki_categories_count}')
        self.stdout.write(f'  Wiki Pages:               {wiki_pages_count}')
        self.stdout.write(f'  Wiki Attachments:         {wiki_attachments_count}')
        self.stdout.write('')
        self.stdout.write(f'  Meeting Notes:            {meeting_notes_count}')
        self.stdout.write('')

        total_items = (
            demo_users.count() + demo_orgs.count() + profiles_count +
            demo_boards.count() + columns_count + labels_count + tasks_count +
            comments_count + activities_count + forecasts_count + alerts_count +
            recommendations_count + stakeholders_count + involvement_count +
            engagement_count + chat_rooms_count + chat_messages_count +
            thread_comments_count + notifications_count + wiki_categories_count +
            wiki_pages_count + wiki_attachments_count + meeting_notes_count
        )

        self.stdout.write(self.style.WARNING(f'  TOTAL ITEMS TO DELETE:    {total_items}'))
        self.stdout.write('')

        # Safety check - prevent deletion if no demo data found
        if demo_users.count() == 0 and demo_orgs.count() == 0:
            self.stdout.write(self.style.SUCCESS('✅ No demo data found. Database is already clean!'))
            return

        # List users and orgs that will be deleted
        self.stdout.write(self.style.NOTICE('👥 Demo Users to Delete:'))
        for user in demo_users:
            self.stdout.write(f'  - {user.username} ({user.email})')
        self.stdout.write('')

        self.stdout.write(self.style.NOTICE('🏢 Demo Organizations to Delete:'))
        for org in demo_orgs:
            self.stdout.write(f'  - {org.name} ({org.domain})')
        self.stdout.write('')

        # Confirmation prompt (unless --no-confirm flag is used)
        if not dry_run and not no_confirm:
            self.stdout.write(self.style.ERROR('⚠️  WARNING: This action cannot be undone!'))
            self.stdout.write('')
            confirm = input('Type "DELETE" to confirm deletion: ')
            
            if confirm != 'DELETE':
                self.stdout.write(self.style.SUCCESS('❌ Deletion cancelled.'))
                return

        if dry_run:
            self.stdout.write(self.style.SUCCESS(''))
            self.stdout.write(self.style.SUCCESS('✅ DRY RUN COMPLETE - No data was deleted'))
            self.stdout.write(self.style.SUCCESS('   Run without --dry-run to actually delete the data'))
            return

        # Perform deletion within a transaction (atomic operation)
        try:
            with transaction.atomic():
                self.stdout.write('')
                self.stdout.write(self.style.NOTICE('🗑️  Starting deletion process...'))
                self.stdout.write('')

                # Delete in correct order to respect foreign key constraints
                
                # 1. Delete messaging data first (depends on users and boards)
                self.stdout.write('  Deleting notifications...')
                Notification.objects.filter(recipient__in=demo_users).delete()
                Notification.objects.filter(sender__in=demo_users).delete()
                
                self.stdout.write('  Deleting typing status...')
                UserTypingStatus.objects.filter(chat_room__board__in=demo_boards).delete()
                
                self.stdout.write('  Deleting file attachments...')
                FileAttachment.objects.filter(chat_room__board__in=demo_boards).delete()
                
                self.stdout.write('  Deleting chat messages...')
                ChatMessage.objects.filter(chat_room__board__in=demo_boards).delete()
                
                self.stdout.write('  Deleting task thread comments...')
                TaskThreadComment.objects.filter(task__column__board__in=demo_boards).delete()
                
                self.stdout.write('  Deleting chat rooms...')
                ChatRoom.objects.filter(board__in=demo_boards).delete()

                # 2. Delete wiki and knowledge base data (depends on organizations)
                self.stdout.write('  Deleting wiki attachments...')
                WikiAttachment.objects.filter(page__organization__in=demo_orgs).delete()
                
                self.stdout.write('  Deleting wiki pages...')
                WikiPage.objects.filter(organization__in=demo_orgs).delete()
                
                self.stdout.write('  Deleting wiki categories...')
                WikiCategory.objects.filter(organization__in=demo_orgs).delete()
                
                # 3. Delete meeting notes (depends on organizations)
                self.stdout.write('  Deleting meeting notes...')
                MeetingNotes.objects.filter(organization__in=demo_orgs).delete()

                # 4. Delete stakeholder data (depends on boards and tasks)
                self.stdout.write('  Deleting stakeholder engagement records...')
                StakeholderEngagementRecord.objects.filter(stakeholder__board__in=demo_boards).delete()
                
                self.stdout.write('  Deleting stakeholder task involvements...')
                StakeholderTaskInvolvement.objects.filter(task__column__board__in=demo_boards).delete()
                
                self.stdout.write('  Deleting stakeholder tags...')
                StakeholderTag.objects.filter(board__in=demo_boards).delete()
                
                self.stdout.write('  Deleting engagement metrics...')
                EngagementMetrics.objects.filter(stakeholder__board__in=demo_boards).delete()
                
                self.stdout.write('  Deleting stakeholders...')
                ProjectStakeholder.objects.filter(board__in=demo_boards).delete()

                # 5. Delete resource management data (depends on boards)
                self.stdout.write('  Deleting workload recommendations...')
                WorkloadDistributionRecommendation.objects.filter(board__in=demo_boards).delete()
                
                self.stdout.write('  Deleting capacity alerts...')
                TeamCapacityAlert.objects.filter(board__in=demo_boards).delete()
                
                self.stdout.write('  Deleting resource forecasts...')
                ResourceDemandForecast.objects.filter(board__in=demo_boards).delete()

                # 6. Delete task-related data
                self.stdout.write('  Deleting task files...')
                TaskFile.objects.filter(task__column__board__in=demo_boards).delete()
                
                self.stdout.write('  Deleting task activities...')
                TaskActivity.objects.filter(task__column__board__in=demo_boards).delete()
                
                self.stdout.write('  Deleting comments...')
                Comment.objects.filter(task__column__board__in=demo_boards).delete()
                
                self.stdout.write('  Deleting tasks...')
                Task.objects.filter(column__board__in=demo_boards).delete()

                # 7. Delete board structure
                self.stdout.write('  Deleting task labels...')
                TaskLabel.objects.filter(board__in=demo_boards).delete()
                
                self.stdout.write('  Deleting columns...')
                Column.objects.filter(board__in=demo_boards).delete()
                
                self.stdout.write('  Deleting boards...')
                demo_boards.delete()

                # 8. Delete user profiles (depends on users and orgs)
                self.stdout.write('  Deleting user profiles...')
                UserProfile.objects.filter(user__in=demo_users).delete()

                # 9. Delete organizations
                self.stdout.write('  Deleting organizations...')
                demo_orgs.delete()

                # 10. Finally delete users
                self.stdout.write('  Deleting users...')
                demo_users.delete()

                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('='*70))
                self.stdout.write(self.style.SUCCESS('✅ DEMO DATA DELETION COMPLETE!'))
                self.stdout.write(self.style.SUCCESS('='*70))
                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS(f'Successfully deleted {total_items} items from the database.'))
                self.stdout.write('')
                self.stdout.write(self.style.NOTICE('ℹ️  The database is now clean and ready for new demo data.'))
                self.stdout.write(self.style.NOTICE('   Run "python manage.py populate_test_data" to create new demo data.'))
                self.stdout.write('')

        except Exception as e:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('='*70))
            self.stdout.write(self.style.ERROR('❌ ERROR DURING DELETION'))
            self.stdout.write(self.style.ERROR('='*70))
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('⚠️  Transaction rolled back - No data was deleted.'))
            self.stdout.write(self.style.NOTICE('   The database remains unchanged.'))
            self.stdout.write('')
            raise
