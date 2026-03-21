"""
Management Command: Populate Messaging Demo Data
=================================================
Creates chat rooms, messages, file attachments (metadata), and notifications
to showcase the messaging feature in demo mode.

Usage:
    python manage.py populate_messaging_demo_data
    python manage.py populate_messaging_demo_data --clear  # Clear and recreate

This creates realistic team conversations across all demo boards, allowing
demo users to explore the messaging feature without needing to log in as
multiple accounts.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import random

from kanban.models import Board, Task
from accounts.models import Organization
from messaging.models import (
    ChatRoom, ChatMessage, Notification, 
    FileAttachment, TaskThreadComment
)


class Command(BaseCommand):
    help = 'Populate demo boards with messaging demo data (chat rooms, messages, notifications)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing messaging demo data before creating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('=' * 80))
        self.stdout.write(self.style.NOTICE('POPULATING MESSAGING DEMO DATA'))
        self.stdout.write(self.style.NOTICE('=' * 80))

        # Get demo organization
        try:
            self.demo_org = Organization.objects.get(name='Demo - Acme Corporation')
            self.stdout.write(self.style.SUCCESS(f'✅ Found organization: {self.demo_org.name}'))
        except Organization.DoesNotExist:
            self.stdout.write(self.style.ERROR('❌ Demo - Acme Corporation not found!'))
            self.stdout.write('   Please run: python manage.py create_demo_organization')
            return

        # Get demo boards
        self.demo_boards = Board.objects.filter(organization=self.demo_org)
        self.stdout.write(f'   Found {self.demo_boards.count()} demo boards')

        # Get demo users
        self.demo_admin = User.objects.filter(username='demo_admin_solo').first()
        self.alex = User.objects.filter(username='alex_chen_demo').first()
        self.sam = User.objects.filter(username='sam_rivera_demo').first()
        self.jordan = User.objects.filter(username='jordan_taylor_demo').first()

        self.demo_users = [u for u in [self.demo_admin, self.alex, self.sam, self.jordan] if u]
        self.stdout.write(f'   Found {len(self.demo_users)} demo users')

        if not self.demo_admin:
            # Fall back to the first available demo persona or any superuser so
            # the command can still run in environments without demo_admin_solo.
            self.demo_admin = self.alex or self.sam or self.jordan or \
                User.objects.filter(is_superuser=True).first()
            if self.demo_admin:
                self.stdout.write(self.style.WARNING(
                    f'⚠️  demo_admin_solo not found — using {self.demo_admin.username} as fallback'
                ))
            else:
                self.stdout.write(self.style.ERROR('❌ No usable admin/demo user found!'))
                return

        # Clear existing data if requested
        if options['clear']:
            self.clear_messaging_data()

        # Create demo data
        self.create_chat_rooms_and_messages()
        self.create_file_attachments()
        self.create_notifications()
        self.create_task_comments()

        # Summary
        self.print_summary()

    def clear_messaging_data(self):
        """Clear existing messaging demo data"""
        self.stdout.write(self.style.WARNING('\n🗑️  Clearing existing messaging demo data...'))
        
        # Delete in correct order for foreign key constraints
        Notification.objects.filter(recipient__in=self.demo_users).delete()
        FileAttachment.objects.filter(chat_room__board__in=self.demo_boards).delete()
        ChatMessage.objects.filter(chat_room__board__in=self.demo_boards).delete()
        TaskThreadComment.objects.filter(task__column__board__in=self.demo_boards).delete()
        ChatRoom.objects.filter(board__in=self.demo_boards).delete()
        
        self.stdout.write(self.style.SUCCESS('   ✅ Cleared existing data'))

    def get_user_by_key(self, key):
        """Get user by short key name"""
        user_map = {
            'demo_admin': self.demo_admin,
            'alex': self.alex,
            'sam': self.sam,
            'jordan': self.jordan,
        }
        return user_map.get(key)

    def get_board_members(self, board):
        """Get all members of a board"""
        return list(board.members.all())

    def get_chat_room_configs(self):
        """Return chat room configurations for each board"""
        return {
            'Software Development': [
                {
                    'name': 'General Discussion',
                    'description': 'Team updates, announcements, and general discussions',
                    'messages': [
                        {'author': 'alex', 'content': 'Good morning team! 🌅 Ready for our sprint planning today?', 'minutes_ago': 180},
                        {'author': 'sam', 'content': 'Morning @alex_chen_demo! Yes, I finished reviewing the backlog items.', 'minutes_ago': 175},
                        {'author': 'demo_admin', 'content': 'Great work everyone! The API integration is looking solid. 👏', 'minutes_ago': 120},
                        {'author': 'sam', 'content': '@demo_admin_solo Thank you! I ran into a small issue with the OAuth flow, but resolved it.', 'minutes_ago': 115},
                        {'author': 'alex', 'content': 'Quick update: Client meeting moved to 3 PM. @sam_rivera_demo can you prepare the demo?', 'minutes_ago': 60},
                        {'author': 'sam', 'content': 'Absolutely! I\'ll have the staging environment ready by 2:30 PM.', 'minutes_ago': 55},
                        {'author': 'demo_admin', 'content': 'Perfect. I\'ll update the presentation slides with our latest metrics.', 'minutes_ago': 45},
                    ]
                },
                {
                    'name': 'Technical Support',
                    'description': 'Technical questions, debugging help, and code reviews',
                    'messages': [
                        {'author': 'sam', 'content': 'Has anyone encountered issues with the database migration on PostgreSQL 15?', 'minutes_ago': 240},
                        {'author': 'demo_admin', 'content': '@sam_rivera_demo Yes! Try running `python manage.py migrate --fake-initial` first.', 'minutes_ago': 235},
                        {'author': 'sam', 'content': 'That worked! Thanks @demo_admin_solo 🙏', 'minutes_ago': 230},
                        {'author': 'alex', 'content': 'Good tip! I\'ll add this to our troubleshooting docs.', 'minutes_ago': 200},
                        {'author': 'sam', 'content': 'Also, the WebSocket connection is dropping occasionally. Need to investigate.', 'minutes_ago': 90},
                        {'author': 'demo_admin', 'content': 'Check the Nginx timeout settings. We had similar issues last month.', 'minutes_ago': 85},
                    ]
                },
                {
                    'name': 'Code Reviews',
                    'description': 'Pull request discussions and code review feedback',
                    'messages': [
                        {'author': 'demo_admin', 'content': 'Just submitted PR #142 for the new authentication module. @sam_rivera_demo could you review?', 'minutes_ago': 300},
                        {'author': 'sam', 'content': 'On it! Give me about 30 minutes. 🔍', 'minutes_ago': 295},
                        {'author': 'sam', 'content': 'Reviewed! LGTM with minor suggestions. Left a few comments on the token refresh logic.', 'minutes_ago': 260},
                        {'author': 'demo_admin', 'content': 'Great feedback! I\'ll address those comments and update the PR.', 'minutes_ago': 255},
                        {'author': 'alex', 'content': 'Nice work both of you! This will be a great addition to our security features.', 'minutes_ago': 200},
                    ]
                },
            ],
        }

    def get_file_attachment_data(self):
        """Return file attachment configurations"""
        return {
            'Software Development': [
                {'room': 'General Discussion', 'filename': 'Sprint_15_Planning.pdf', 'file_type': 'pdf', 'file_size': 245760, 'description': 'Sprint 15 planning document with user stories'},
                {'room': 'Technical Support', 'filename': 'Database_Migration_Guide.pdf', 'file_type': 'pdf', 'file_size': 189440, 'description': 'Step-by-step PostgreSQL 15 migration guide'},
                {'room': 'Code Reviews', 'filename': 'Auth_Module_Architecture.png', 'file_type': 'png', 'file_size': 524288, 'description': 'Architecture diagram for authentication module'},
            ],
        }

    def create_chat_rooms_and_messages(self):
        """Create chat rooms and populate with messages"""
        self.stdout.write(self.style.NOTICE('\n📬 Creating Chat Rooms and Messages...'))
        
        rooms_created = 0
        messages_created = 0
        now = timezone.now()
        chat_room_configs = self.get_chat_room_configs()

        for board in self.demo_boards:
            board_name = board.name
            if board_name not in chat_room_configs:
                continue

            board_members = self.get_board_members(board)
            creator = self.demo_admin if self.demo_admin in board_members else board_members[0]

            for room_config in chat_room_configs[board_name]:
                room_name = room_config['name']

                # Create or get chat room
                room, created = ChatRoom.objects.get_or_create(
                    board=board,
                    name=room_name,
                    defaults={
                        'description': room_config['description'],
                        'created_by': creator,
                    }
                )

                if created:
                    rooms_created += 1
                    for member in board_members:
                        room.members.add(member)
                    self.stdout.write(f'   ✅ Created: {board_name} → {room_name}')
                else:
                    # Ensure all board members are in the room
                    for member in board_members:
                        if member not in room.members.all():
                            room.members.add(member)

                # Create messages if none exist
                if ChatMessage.objects.filter(chat_room=room).count() == 0:
                    for msg_data in room_config['messages']:
                        author = self.get_user_by_key(msg_data['author'])
                        if author and author in board_members:
                            msg_time = now - timedelta(minutes=msg_data['minutes_ago'])
                            
                            msg = ChatMessage.objects.create(
                                chat_room=room,
                                author=author,
                                content=msg_data['content'],
                            )
                            ChatMessage.objects.filter(pk=msg.pk).update(created_at=msg_time)
                            messages_created += 1
                            
                            # Handle @mentions
                            for mentioned_username in msg.get_mentioned_usernames():
                                try:
                                    mentioned_user = User.objects.get(username=mentioned_username)
                                    msg.mentioned_users.add(mentioned_user)
                                except User.DoesNotExist:
                                    pass

        self.stdout.write(self.style.SUCCESS(f'   Created {rooms_created} rooms, {messages_created} messages'))

    def create_file_attachments(self):
        """Create file attachment metadata"""
        self.stdout.write(self.style.NOTICE('\n📎 Creating File Attachments...'))
        
        attachments_created = 0
        file_data = self.get_file_attachment_data()

        for board in self.demo_boards:
            board_name = board.name
            if board_name not in file_data:
                continue

            board_members = self.get_board_members(board)

            for file_info in file_data[board_name]:
                try:
                    room = ChatRoom.objects.get(board=board, name=file_info['room'])
                except ChatRoom.DoesNotExist:
                    continue

                if not FileAttachment.objects.filter(chat_room=room, filename=file_info['filename']).exists():
                    uploader = random.choice(board_members)
                    FileAttachment.objects.create(
                        chat_room=room,
                        uploaded_by=uploader,
                        filename=file_info['filename'],
                        file_size=file_info['file_size'],
                        file_type=file_info['file_type'],
                        description=file_info.get('description', ''),
                        file='demo_placeholder.txt',
                    )
                    attachments_created += 1

        self.stdout.write(self.style.SUCCESS(f'   Created {attachments_created} file attachments'))

    def create_notifications(self):
        """Create rich demo notifications for all demo users and superusers"""
        self.stdout.write(self.style.NOTICE('\n🔔 Creating Notifications...'))

        notifications_created = 0
        now = timezone.now()

        # Build the set of recipients: all demo users + every member of any demo
        # board so that any user the developer logs in as (e.g. testuser1) also
        # sees the demo notifications.
        recipients = set(u for u in self.demo_users if u)
        for su in User.objects.filter(is_superuser=True):
            recipients.add(su)
        for board in self.demo_boards:
            for member in board.members.all():
                recipients.add(member)

        # Curated standalone notification templates that don't rely on @mentions
        # being present in chat messages. sender_key must be a different user from
        # the recipient so we skip self-notifications below.
        standalone_templates = [
            {
                'type': 'MENTION',
                'sender_key': 'alex',
                'text': 'Alex Chen mentioned you in General Discussion: "Can you review the updated API specs?"',
                'minutes_ago': 25,
                'is_read': False,
            },
            {
                'type': 'COMMENT',
                'sender_key': 'sam',
                'text': 'Sam Rivera replied to your comment on "Set up CI/CD pipeline": "Great catch! I\'ve incorporated your feedback into the workflow."',
                'minutes_ago': 85,
                'is_read': False,
            },
            {
                'type': 'ACTIVITY',
                'sender_key': 'jordan',
                'text': 'Jordan Taylor moved "User Authentication Module" to In Review.',
                'minutes_ago': 175,
                'is_read': False,
            },
            {
                'type': 'MENTION',
                'sender_key': 'sam',
                'text': 'Sam Rivera mentioned you in Code Reviews: "PR #142 is ready for your approval — ping me with questions."',
                'minutes_ago': 240,
                'is_read': True,
            },
            {
                'type': 'TASK_ASSIGNED_CAL',
                'sender_key': 'alex',
                'text': 'You were assigned to "Database Schema Design" — due in 3 days.',
                'minutes_ago': 360,
                'is_read': True,
            },
            {
                'type': 'COMMENT',
                'sender_key': 'jordan',
                'text': 'Jordan Taylor commented on "API Gateway Configuration": "I\'ve added the rate-limiting logic — please verify on staging."',
                'minutes_ago': 480,
                'is_read': True,
            },
            {
                'type': 'ACTIVITY',
                'sender_key': 'alex',
                'text': 'Alex Chen marked "Sprint Planning" as complete. 🎉',
                'minutes_ago': 720,
                'is_read': True,
            },
            {
                'type': 'EVENT_INVITED',
                'sender_key': 'sam',
                'text': 'You have been invited to "Q2 Sprint Review" on Friday at 3:00 PM.',
                'minutes_ago': 1440,
                'is_read': True,
            },
        ]

        for recipient in recipients:
            for template in standalone_templates:
                sender = self.get_user_by_key(template['sender_key'])
                if not sender or sender == recipient:
                    continue

                # Avoid duplicates across repeated runs
                if Notification.objects.filter(
                    recipient=recipient,
                    sender=sender,
                    notification_type=template['type'],
                    text=template['text'],
                ).exists():
                    continue

                notif = Notification.objects.create(
                    recipient=recipient,
                    sender=sender,
                    notification_type=template['type'],
                    text=template['text'],
                    is_read=template['is_read'],
                )
                # Back-date the notification so timestamps look natural
                Notification.objects.filter(pk=notif.pk).update(
                    created_at=now - timedelta(minutes=template['minutes_ago'])
                )
                notifications_created += 1

        # Also create mention notifications from actual @mentions in chat messages
        for board in self.demo_boards:
            rooms = ChatRoom.objects.filter(board=board)
            for room in rooms:
                messages = ChatMessage.objects.filter(chat_room=room).exclude(mentioned_users=None)
                for msg in messages:
                    for mentioned_user in msg.mentioned_users.all():
                        if msg.author == mentioned_user:
                            continue
                        if Notification.objects.filter(
                            recipient=mentioned_user,
                            chat_message=msg,
                            notification_type='MENTION',
                        ).exists():
                            continue
                        Notification.objects.create(
                            recipient=mentioned_user,
                            sender=msg.author,
                            notification_type='MENTION',
                            text=f'{msg.author.get_full_name() or msg.author.username} mentioned you in {room.name}',
                            chat_message=msg,
                            is_read=False,
                        )
                        notifications_created += 1

        self.stdout.write(self.style.SUCCESS(f'   Created {notifications_created} notifications'))

    def create_task_comments(self):
        """Create task thread comments"""
        self.stdout.write(self.style.NOTICE('\n💬 Creating Task Comments...'))
        
        comments_created = 0
        demo_tasks = Task.objects.filter(column__board__in=self.demo_boards)[:10]

        comment_templates = [
            {'author': 'alex', 'content': 'Great progress on this! Let me know if you need any help.'},
            {'author': 'sam', 'content': 'I\'ve started working on this. Should have an update by EOD.'},
            {'author': 'jordan', 'content': '@demo_admin_solo Can you review the latest changes?'},
            {'author': 'demo_admin', 'content': 'Looks good! Moving this to review. @sam_rivera_demo please verify.'},
            {'author': 'sam', 'content': 'Verified and tested. Ready for production! 🚀'},
        ]

        for task in demo_tasks:
            if TaskThreadComment.objects.filter(task=task).count() == 0:
                num_comments = random.randint(1, 3)
                board_members = self.get_board_members(task.column.board)

                for _ in range(num_comments):
                    template = random.choice(comment_templates)
                    author = self.get_user_by_key(template['author'])

                    if author and author in board_members:
                        comment = TaskThreadComment.objects.create(
                            task=task,
                            author=author,
                            content=template['content'],
                        )
                        comments_created += 1

                        for mentioned_username in comment.get_mentioned_usernames():
                            try:
                                mentioned_user = User.objects.get(username=mentioned_username)
                                comment.mentioned_users.add(mentioned_user)
                            except User.DoesNotExist:
                                pass

        self.stdout.write(self.style.SUCCESS(f'   Created {comments_created} task comments'))

    def print_summary(self):
        """Print summary of created data"""
        total_rooms = ChatRoom.objects.filter(board__in=self.demo_boards).count()
        total_messages = ChatMessage.objects.filter(chat_room__board__in=self.demo_boards).count()
        total_attachments = FileAttachment.objects.filter(chat_room__board__in=self.demo_boards).count()
        total_notifications = Notification.objects.filter(recipient=self.demo_admin).count()
        total_comments = TaskThreadComment.objects.filter(task__column__board__in=self.demo_boards).count()

        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
        self.stdout.write(self.style.SUCCESS('MESSAGING DEMO DATA SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f'''
📊 Total Demo Messaging Data:
   • Chat Rooms: {total_rooms}
   • Chat Messages: {total_messages}
   • File Attachments: {total_attachments}
   • Notifications: {total_notifications}
   • Task Comments: {total_comments}

🎉 Demo messaging feature is now populated!
''')
