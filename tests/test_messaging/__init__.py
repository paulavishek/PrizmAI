"""
Tests for Messaging App Models
================================

Tests coverage:
- TaskThreadComment model with @mentions
- ChatRoom model and relationships
- ChatMessage model with read tracking
- Notification model
- FileAttachment model
- Message mention and notification logic
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from kanban.models import Board, Column, Task
from messaging.models import (
    TaskThreadComment, ChatRoom, ChatMessage, Notification,
    FileAttachment, UserTypingStatus
)
from accounts.models import Organization, UserProfile


class TaskThreadCommentTests(TestCase):
    """Test TaskThreadComment model"""
    
    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user1
        )
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user1
        )
        self.column = Column.objects.create(
            name='To Do',
            board=self.board,
            position=0
        )
        self.task = Task.objects.create(
            title='Test Task',
            column=self.column,
            created_by=self.user1
        )
    
    def test_comment_creation(self):
        """Test creating a task thread comment"""
        comment = TaskThreadComment.objects.create(
            task=self.task,
            author=self.user1,
            content='This is a test comment'
        )
        self.assertEqual(comment.content, 'This is a test comment')
        self.assertEqual(comment.task, self.task)
        self.assertEqual(comment.author, self.user1)
    
    def test_mention_extraction(self):
        """Test extracting @mentions from comment"""
        comment = TaskThreadComment.objects.create(
            task=self.task,
            author=self.user1,
            content='@user2 please review this task'
        )
        mentions = comment.get_mentioned_usernames()
        self.assertIn('user2', mentions)
    
    def test_multiple_mentions(self):
        """Test extracting multiple mentions"""
        comment = TaskThreadComment.objects.create(
            task=self.task,
            author=self.user1,
            content='@user2 @user1 check this out'
        )
        mentions = comment.get_mentioned_usernames()
        self.assertEqual(len(mentions), 2)
        self.assertIn('user1', mentions)
        self.assertIn('user2', mentions)
    
    def test_duplicate_mentions_removed(self):
        """Test duplicate mentions are removed"""
        comment = TaskThreadComment.objects.create(
            task=self.task,
            author=self.user1,
            content='@user2 @user2 review this'
        )
        mentions = comment.get_mentioned_usernames()
        self.assertEqual(len(mentions), 1)
    
    def test_comment_ordering(self):
        """Test comments are ordered by creation date"""
        comment1 = TaskThreadComment.objects.create(
            task=self.task,
            author=self.user1,
            content='First comment'
        )
        comment2 = TaskThreadComment.objects.create(
            task=self.task,
            author=self.user2,
            content='Second comment'
        )
        comments = TaskThreadComment.objects.all()
        self.assertEqual(comments[0], comment1)
        self.assertEqual(comments[1], comment2)
    
    def test_mentioned_users_relationship(self):
        """Test mentioned users many-to-many relationship"""
        comment = TaskThreadComment.objects.create(
            task=self.task,
            author=self.user1,
            content='Test comment'
        )
        comment.mentioned_users.add(self.user2)
        self.assertEqual(comment.mentioned_users.count(), 1)
        self.assertIn(self.user2, comment.mentioned_users.all())
    
    def test_comment_string_representation(self):
        """Test comment __str__ method"""
        comment = TaskThreadComment.objects.create(
            task=self.task,
            author=self.user1,
            content='Test comment'
        )
        expected_str = f"Comment by {self.user1.username} on Task {self.task.id}"
        self.assertEqual(str(comment), expected_str)


class ChatRoomTests(TestCase):
    """Test ChatRoom model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
    
    def test_chat_room_creation(self):
        """Test creating a chat room"""
        room = ChatRoom.objects.create(
            board=self.board,
            name='General',
            created_by=self.user
        )
        self.assertEqual(room.name, 'General')
        self.assertEqual(room.board, self.board)
        self.assertEqual(room.created_by, self.user)
    
    def test_chat_room_members(self):
        """Test adding members to chat room"""
        room = ChatRoom.objects.create(
            board=self.board,
            name='General',
            created_by=self.user
        )
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        room.members.add(self.user, user2)
        self.assertEqual(room.members.count(), 2)
    
    def test_chat_room_group_name(self):
        """Test getting channel group name for WebSocket"""
        room = ChatRoom.objects.create(
            board=self.board,
            name='General',
            created_by=self.user
        )
        group_name = room.get_room_group_name()
        self.assertEqual(group_name, f'chat_room_{room.id}')
    
    def test_unique_room_per_board(self):
        """Test room names are unique per board"""
        ChatRoom.objects.create(
            board=self.board,
            name='General',
            created_by=self.user
        )
        with self.assertRaises(Exception):
            ChatRoom.objects.create(
                board=self.board,
                name='General',
                created_by=self.user
            )
    
    def test_chat_room_string_representation(self):
        """Test chat room __str__ method"""
        room = ChatRoom.objects.create(
            board=self.board,
            name='General',
            created_by=self.user
        )
        expected_str = f"General ({self.board.name})"
        self.assertEqual(str(room), expected_str)


class ChatMessageTests(TestCase):
    """Test ChatMessage model"""
    
    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user1
        )
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user1
        )
        self.room = ChatRoom.objects.create(
            board=self.board,
            name='General',
            created_by=self.user1
        )
        self.room.members.add(self.user1, self.user2)
    
    def test_message_creation(self):
        """Test creating a chat message"""
        message = ChatMessage.objects.create(
            chat_room=self.room,
            author=self.user1,
            content='Hello team!'
        )
        self.assertEqual(message.content, 'Hello team!')
        self.assertEqual(message.chat_room, self.room)
        self.assertEqual(message.author, self.user1)
    
    def test_message_read_status(self):
        """Test message read status tracking"""
        message = ChatMessage.objects.create(
            chat_room=self.room,
            author=self.user1,
            content='Hello'
        )
        self.assertFalse(message.is_read)
        
        message.mark_as_read(self.user2)
        self.assertEqual(message.read_by.count(), 1)
    
    def test_get_unread_count(self):
        """Test getting unread count"""
        message = ChatMessage.objects.create(
            chat_room=self.room,
            author=self.user1,
            content='Hello'
        )
        unread = message.get_unread_count()
        self.assertEqual(unread, 2)  # user1 and user2
    
    def test_mention_extraction_from_message(self):
        """Test extracting mentions from chat message"""
        message = ChatMessage.objects.create(
            chat_room=self.room,
            author=self.user1,
            content='@user2 check this out'
        )
        mentions = message.get_mentioned_usernames()
        self.assertIn('user2', mentions)
    
    def test_message_ordering(self):
        """Test messages are ordered by creation time"""
        msg1 = ChatMessage.objects.create(
            chat_room=self.room,
            author=self.user1,
            content='First'
        )
        msg2 = ChatMessage.objects.create(
            chat_room=self.room,
            author=self.user2,
            content='Second'
        )
        messages = ChatMessage.objects.all()
        self.assertEqual(messages[0], msg1)
        self.assertEqual(messages[1], msg2)
    
    def test_message_string_representation(self):
        """Test message __str__ method"""
        message = ChatMessage.objects.create(
            chat_room=self.room,
            author=self.user1,
            content='Test'
        )
        expected_str = f"Message by {self.user1.username} in {self.room.name}"
        self.assertEqual(str(message), expected_str)


class NotificationTests(TestCase):
    """Test Notification model"""
    
    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
    
    def test_notification_creation(self):
        """Test creating a notification"""
        notification = Notification.objects.create(
            recipient=self.user2,
            sender=self.user1,
            notification_type='MENTION',
            text='You were mentioned'
        )
        self.assertEqual(notification.recipient, self.user2)
        self.assertEqual(notification.sender, self.user1)
        self.assertEqual(notification.notification_type, 'MENTION')
    
    def test_notification_read_status(self):
        """Test notification read status"""
        notification = Notification.objects.create(
            recipient=self.user2,
            sender=self.user1,
            notification_type='MENTION',
            text='You were mentioned'
        )
        self.assertFalse(notification.is_read)
    
    def test_notification_types(self):
        """Test all notification type choices"""
        types = ['MENTION', 'COMMENT', 'CHAT_MESSAGE', 'ACTIVITY']
        for notif_type in types:
            notification = Notification.objects.create(
                recipient=self.user2,
                sender=self.user1,
                notification_type=notif_type,
                text=f'Test {notif_type}'
            )
            self.assertEqual(notification.notification_type, notif_type)
    
    def test_notification_ordering(self):
        """Test notifications ordered by creation time (newest first)"""
        notif1 = Notification.objects.create(
            recipient=self.user2,
            sender=self.user1,
            notification_type='MENTION',
            text='First'
        )
        notif2 = Notification.objects.create(
            recipient=self.user2,
            sender=self.user1,
            notification_type='MENTION',
            text='Second'
        )
        notifications = Notification.objects.all()
        self.assertEqual(notifications[0], notif2)  # Newest first
        self.assertEqual(notifications[1], notif1)


class FileAttachmentTests(TestCase):
    """Test FileAttachment model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        self.room = ChatRoom.objects.create(
            board=self.board,
            name='General',
            created_by=self.user
        )
    
    def test_file_attachment_creation(self):
        """Test creating file attachment"""
        attachment = FileAttachment(
            chat_room=self.room,
            uploaded_by=self.user,
            filename='document.pdf',
            file_size=2048,
            file_type='pdf'
        )
        attachment.save()
        
        self.assertEqual(attachment.chat_room, self.room)
        self.assertEqual(attachment.uploaded_by, self.user)
        self.assertEqual(attachment.filename, 'document.pdf')
    
    def test_file_type_validation(self):
        """Test file type validation"""
        allowed_types = ['pdf', 'doc', 'docx', 'jpg', 'png']
        for file_type in allowed_types:
            attachment = FileAttachment(
                chat_room=self.room,
                uploaded_by=self.user,
                filename=f'file.{file_type}',
                file_size=1024,
                file_type=file_type
            )
            attachment.save()
            self.assertEqual(attachment.file_type, file_type)
    
    def test_file_size_tracking(self):
        """Test file size tracking"""
        attachment = FileAttachment(
            chat_room=self.room,
            uploaded_by=self.user,
            filename='large.pdf',
            file_size=10485760,  # 10MB
            file_type='pdf'
        )
        attachment.save()
        self.assertEqual(attachment.file_size, 10485760)
    
    def test_soft_delete(self):
        """Test soft delete functionality"""
        attachment = FileAttachment.objects.create(
            chat_room=self.room,
            uploaded_by=self.user,
            filename='document.pdf',
            file_size=2048,
            file_type='pdf'
        )
        self.assertIsNone(attachment.deleted_at)
        
        attachment.deleted_at = timezone.now()
        attachment.save()
        
        attachment.refresh_from_db()
        self.assertIsNotNone(attachment.deleted_at)
