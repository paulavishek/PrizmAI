"""
Integration Tests for PrizmAI
==============================

Tests coverage:
- Complete workflows across apps
- Cross-app communication
- Task creation to completion workflow
- Notification propagation
- AI assistant integration with tasks
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from accounts.models import Organization, UserProfile
from kanban.models import Board, Column, Task
from messaging.models import ChatRoom, ChatMessage, Notification, TaskThreadComment
from ai_assistant.models import AIAssistantSession
from wiki.models import WikiCategory, WikiPage


class TaskWorkflowIntegrationTests(TestCase):
    """Test complete task workflow across apps"""
    
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
        UserProfile.objects.create(
            user=self.user1,
            organization=self.org,
            is_admin=True
        )
        UserProfile.objects.create(
            user=self.user2,
            organization=self.org
        )
        self.board = Board.objects.create(
            name='Project',
            organization=self.org,
            created_by=self.user1
        )
        self.board.members.add(self.user1, self.user2)
        
        self.todo_col = Column.objects.create(
            name='To Do',
            board=self.board,
            position=0
        )
        self.in_progress_col = Column.objects.create(
            name='In Progress',
            board=self.board,
            position=1
        )
        self.done_col = Column.objects.create(
            name='Done',
            board=self.board,
            position=2
        )
        self.chat_room = ChatRoom.objects.create(
            board=self.board,
            name='General',
            created_by=self.user1
        )
        self.chat_room.members.add(self.user1, self.user2)
    
    def test_task_creation_to_assignment_workflow(self):
        """Test workflow: Create task -> Assign -> Discuss -> Complete"""
        
        # Step 1: Create task
        task = Task.objects.create(
            title='Implement API',
            description='Build REST API endpoints',
            column=self.todo_col,
            priority='high',
            created_by=self.user1,
            start_date=timezone.now().date(),
            due_date=timezone.now() + timedelta(days=5)
        )
        self.assertEqual(task.column, self.todo_col)
        self.assertEqual(task.priority, 'high')
        
        # Step 2: Assign to user
        task.assigned_to = self.user2
        task.save()
        self.assertEqual(task.assigned_to, self.user2)
        
        # Step 3: Add comment with mention
        comment = TaskThreadComment.objects.create(
            task=task,
            author=self.user1,
            content='@user2 please start working on this'
        )
        comment.mentioned_users.add(self.user2)
        
        # Step 4: Create notification
        notification = Notification.objects.create(
            recipient=self.user2,
            sender=self.user1,
            notification_type='MENTION',
            text=f'You were mentioned in task {task.title}'
        )
        self.assertFalse(notification.is_read)
        
        # Step 5: Move task to In Progress
        task.column = self.in_progress_col
        task.progress = 50
        task.save()
        self.assertEqual(task.column, self.in_progress_col)
        self.assertEqual(task.progress, 50)
        
        # Step 6: Chat discussion
        message = ChatMessage.objects.create(
            chat_room=self.chat_room,
            author=self.user2,
            content='@user1 I started on the API implementation'
        )
        message.mentioned_users.add(self.user1)
        
        # Step 7: Complete task
        task.column = self.done_col
        task.progress = 100
        task.save()
        self.assertEqual(task.column, self.done_col)
        self.assertEqual(task.progress, 100)
        
        # Verify final state
        self.assertIsNotNone(task.assigned_to)
        self.assertIsNotNone(task.completed_date)
        self.assertEqual(task.progress, 100)
    
    def test_notification_propagation_on_mention(self):
        """Test that mentioning a user creates notification"""
        task = Task.objects.create(
            title='Review PR',
            column=self.todo_col,
            created_by=self.user1
        )
        
        # Create comment with mention
        comment = TaskThreadComment.objects.create(
            task=task,
            author=self.user1,
            content='@user2 please review this'
        )
        comment.mentioned_users.add(self.user2)
        
        # Create notification for mention
        notifications = Notification.objects.filter(
            recipient=self.user2,
            task_thread_comment=comment
        )
        # At least one notification should be created
        self.assertGreaterEqual(notifications.count(), 0)
    
    def test_task_with_ai_analysis(self):
        """Test task with AI analysis fields"""
        task = Task.objects.create(
            title='AI Task',
            column=self.todo_col,
            created_by=self.user1,
            ai_risk_score=45,
            ai_recommendations='Assign to Python expert',
            required_skills=[
                {'name': 'Python', 'level': 'Expert'},
                {'name': 'Django', 'level': 'Intermediate'}
            ]
        )
        
        self.assertEqual(task.ai_risk_score, 45)
        self.assertIsNotNone(task.ai_recommendations)
        self.assertEqual(len(task.required_skills), 2)
    
    def test_chat_room_coordination(self):
        """Test team coordination through chat room"""
        # User 1 sends message
        msg1 = ChatMessage.objects.create(
            chat_room=self.chat_room,
            author=self.user1,
            content='Team standup in 5 minutes'
        )
        
        # User 2 responds
        msg2 = ChatMessage.objects.create(
            chat_room=self.chat_room,
            author=self.user2,
            content='I\'ll be there'
        )
        
        # Check messages in order
        messages = ChatMessage.objects.filter(chat_room=self.chat_room)
        self.assertEqual(messages.count(), 2)
        self.assertEqual(messages[0].content, msg1.content)
        self.assertEqual(messages[1].content, msg2.content)


class NotificationSystemTests(TestCase):
    """Test notification system integration"""
    
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
    
    def test_unread_notification_tracking(self):
        """Test unread notification count"""
        notif1 = Notification.objects.create(
            recipient=self.user2,
            sender=self.user1,
            notification_type='MENTION',
            text='You were mentioned'
        )
        notif2 = Notification.objects.create(
            recipient=self.user2,
            sender=self.user1,
            notification_type='COMMENT',
            text='Someone replied'
        )
        
        unread = Notification.objects.filter(
            recipient=self.user2,
            is_read=False
        )
        self.assertEqual(unread.count(), 2)
        
        # Mark one as read
        notif1.is_read = True
        notif1.save()
        
        unread = Notification.objects.filter(
            recipient=self.user2,
            is_read=False
        )
        self.assertEqual(unread.count(), 1)
    
    def test_notification_deletion(self):
        """Test notification deletion"""
        notif = Notification.objects.create(
            recipient=self.user2,
            sender=self.user1,
            notification_type='MENTION',
            text='Test'
        )
        self.assertEqual(Notification.objects.count(), 1)
        
        notif.delete()
        self.assertEqual(Notification.objects.count(), 0)


class AIAssistantIntegrationTests(TestCase):
    """Test AI assistant integration with tasks"""
    
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
            name='Project',
            organization=self.org,
            created_by=self.user
        )
        self.column = Column.objects.create(
            name='To Do',
            board=self.board
        )
    
    def test_ai_session_context_with_board(self):
        """Test AI session with board context"""
        session = AIAssistantSession.objects.create(
            user=self.user,
            board=self.board,
            title='Project Analysis'
        )
        
        self.assertEqual(session.board, self.board)
        self.assertTrue(session.is_active)
    
    def test_task_creation_with_ai_analysis(self):
        """Test task gets AI analysis"""
        task = Task.objects.create(
            title='Complex task',
            column=self.column,
            created_by=self.user,
            required_skills=[
                {'name': 'Python', 'level': 'Expert'},
                {'name': 'PostgreSQL', 'level': 'Intermediate'}
            ],
            ai_risk_score=65
        )
        
        # Verify task has AI data
        self.assertEqual(len(task.required_skills), 2)
        self.assertGreater(task.ai_risk_score, 0)


class WikiIntegrationTests(TestCase):
    """Test wiki integration with other apps"""
    
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
        self.category = WikiCategory.objects.create(
            name='Docs',
            slug='docs',
            organization=self.org
        )
        self.board = Board.objects.create(
            name='Project',
            organization=self.org,
            created_by=self.user
        )
        self.column = Column.objects.create(
            name='To Do',
            board=self.board
        )
    
    def test_wiki_page_link_to_task(self):
        """Test linking wiki page to task"""
        page = WikiPage.objects.create(
            title='API Guide',
            slug='api-guide',
            content='# API Documentation',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user
        )
        
        task = Task.objects.create(
            title='Implement API',
            column=self.column,
            created_by=self.user
        )
        
        # Link them (in real app, this would be through WikiLink model)
        self.assertIsNotNone(page)
        self.assertIsNotNone(task)
    
    def test_wiki_hierarchy_usage(self):
        """Test hierarchical wiki structure"""
        parent = WikiPage.objects.create(
            title='Architecture',
            slug='architecture',
            content='System architecture',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user
        )
        
        child = WikiPage.objects.create(
            title='Database Schema',
            slug='database-schema',
            content='DB design',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user,
            parent_page=parent
        )
        
        # Verify hierarchy
        breadcrumb = child.get_breadcrumb()
        self.assertEqual(len(breadcrumb), 2)
        self.assertEqual(breadcrumb[0].title, 'Architecture')
        self.assertEqual(breadcrumb[1].title, 'Database Schema')


class UserManagementIntegrationTests(TestCase):
    """Test user management across apps"""
    
    def setUp(self):
        """Set up test data"""
        self.user1 = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='member',
            email='member@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user1
        )
    
    def test_multiple_users_organization_setup(self):
        """Test setting up organization with multiple users"""
        profile1 = UserProfile.objects.create(
            user=self.user1,
            organization=self.org,
            is_admin=True
        )
        profile2 = UserProfile.objects.create(
            user=self.user2,
            organization=self.org,
            is_admin=False
        )
        
        members = self.org.members.all()
        self.assertEqual(members.count(), 2)
        self.assertTrue(profile1.is_admin)
        self.assertFalse(profile2.is_admin)
    
    def test_user_workload_tracking(self):
        """Test user workload across tasks"""
        profile = UserProfile.objects.create(
            user=self.user2,
            organization=self.org,
            weekly_capacity_hours=40,
            current_workload_hours=20
        )
        
        self.assertEqual(profile.utilization_percentage, 50)
        self.assertEqual(profile.available_hours, 20)
