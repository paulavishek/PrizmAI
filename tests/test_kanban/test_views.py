"""
Tests for Kanban App Views
===========================

Tests coverage:
- Board views (list, detail, create, update, delete)
- Task views (list, detail, create, update, delete, move)
- Column views (create, update, delete, reorder)
- Permission checks
- Context data validation
- Form processing
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from accounts.models import Organization, UserProfile
from kanban.models import Board, Column, Task, TaskLabel


class BoardViewTests(TestCase):
    """Test Board views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
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
        self.profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            is_admin=True
        )
        self.board = Board.objects.create(
            name='Test Board',
            description='Test Description',
            organization=self.org,
            created_by=self.user
        )
        self.board.members.add(self.user)
    
    def test_board_list_view_requires_login(self):
        """Test board list view requires authentication"""
        response = self.client.get(reverse('kanban:board_list'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        self.assertIn('/accounts/login/', response.url)
    
    def test_board_list_view_authenticated(self):
        """Test authenticated user can view board list"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('kanban:board_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Board')
    
    def test_board_list_shows_only_user_boards(self):
        """Test user only sees boards they have access to"""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        other_org = Organization.objects.create(
            name='Other Org',
            domain='other.org',
            created_by=other_user
        )
        other_board = Board.objects.create(
            name='Other Board',
            organization=other_org,
            created_by=other_user
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('kanban:board_list'))
        
        self.assertContains(response, 'Test Board')
        self.assertNotContains(response, 'Other Board')
    
    def test_board_detail_view_requires_membership(self):
        """Test board detail requires user to be member"""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        self.client.login(username='otheruser', password='testpass123')
        response = self.client.get(
            reverse('kanban:board_detail', kwargs={'pk': self.board.id})
        )
        self.assertEqual(response.status_code, 403)  # Forbidden
    
    def test_board_detail_view_shows_columns_and_tasks(self):
        """Test board detail displays columns and tasks"""
        column = Column.objects.create(
            name='To Do',
            board=self.board,
            position=0
        )
        task = Task.objects.create(
            title='Test Task',
            column=column,
            created_by=self.user
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('kanban:board_detail', kwargs={'pk': self.board.id})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'To Do')
        self.assertContains(response, 'Test Task')
    
    def test_board_create_view_get(self):
        """Test GET request to board create view"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('kanban:board_create'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create Board')
    
    def test_board_create_view_post_success(self):
        """Test creating board via POST"""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': 'New Board',
            'description': 'New Description',
            'organization': self.org.id
        }
        response = self.client.post(reverse('kanban:board_create'), data)
        
        self.assertEqual(response.status_code, 302)  # Redirect after success
        self.assertTrue(
            Board.objects.filter(name='New Board').exists()
        )
    
    def test_board_create_view_post_validation_error(self):
        """Test board creation with invalid data"""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': '',  # Empty name should fail
            'organization': self.org.id
        }
        response = self.client.post(reverse('kanban:board_create'), data)
        
        self.assertEqual(response.status_code, 200)  # Stay on form
        self.assertContains(response, 'This field is required')
    
    def test_board_update_view_requires_admin(self):
        """Test only admins can update board"""
        non_admin = User.objects.create_user(
            username='nonadmin',
            email='nonadmin@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=non_admin,
            organization=self.org,
            is_admin=False
        )
        self.board.members.add(non_admin)
        
        self.client.login(username='nonadmin', password='testpass123')
        response = self.client.get(
            reverse('kanban:board_update', kwargs={'pk': self.board.id})
        )
        self.assertEqual(response.status_code, 403)
    
    def test_board_update_view_post(self):
        """Test updating board"""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': 'Updated Board Name',
            'description': 'Updated Description',
            'organization': self.org.id
        }
        response = self.client.post(
            reverse('kanban:board_update', kwargs={'pk': self.board.id}),
            data
        )
        
        self.board.refresh_from_db()
        self.assertEqual(self.board.name, 'Updated Board Name')
    
    def test_board_delete_view_requires_admin(self):
        """Test only admins can delete board"""
        non_admin = User.objects.create_user(
            username='nonadmin',
            email='nonadmin@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=non_admin,
            organization=self.org,
            is_admin=False
        )
        
        self.client.login(username='nonadmin', password='testpass123')
        response = self.client.post(
            reverse('kanban:board_delete', kwargs={'pk': self.board.id})
        )
        self.assertEqual(response.status_code, 403)


class TaskViewTests(TestCase):
    """Test Task views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
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
        self.profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org
        )
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        self.board.members.add(self.user)
        self.column = Column.objects.create(
            name='To Do',
            board=self.board,
            position=0
        )
        self.task = Task.objects.create(
            title='Test Task',
            description='Test Description',
            column=self.column,
            created_by=self.user
        )
    
    def test_task_detail_view_requires_board_access(self):
        """Test task detail requires access to board"""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        self.client.login(username='otheruser', password='testpass123')
        response = self.client.get(
            reverse('kanban:task_detail', kwargs={'pk': self.task.id})
        )
        self.assertEqual(response.status_code, 403)
    
    def test_task_detail_view_shows_task_info(self):
        """Test task detail displays all task information"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('kanban:task_detail', kwargs={'pk': self.task.id})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Task')
        self.assertContains(response, 'Test Description')
    
    def test_task_create_view_post(self):
        """Test creating task via POST"""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'title': 'New Task',
            'description': 'New task description',
            'column': self.column.id,
            'priority': 'high'
        }
        response = self.client.post(
            reverse('kanban:task_create', kwargs={'board_id': self.board.id}),
            data
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Task.objects.filter(title='New Task').exists()
        )
    
    def test_task_update_view_post(self):
        """Test updating task"""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'title': 'Updated Task',
            'description': 'Updated description',
            'column': self.column.id,
            'priority': 'urgent'
        }
        response = self.client.post(
            reverse('kanban:task_update', kwargs={'pk': self.task.id}),
            data
        )
        
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, 'Updated Task')
        self.assertEqual(self.task.priority, 'urgent')
    
    def test_task_move_to_column(self):
        """Test moving task to different column"""
        in_progress = Column.objects.create(
            name='In Progress',
            board=self.board,
            position=1
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('kanban:task_move', kwargs={'pk': self.task.id}),
            {'column_id': in_progress.id}
        )
        
        self.task.refresh_from_db()
        self.assertEqual(self.task.column, in_progress)
    
    def test_task_assignment(self):
        """Test assigning task to user"""
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        self.board.members.add(user2)
        
        self.client.login(username='testuser', password='testpass123')
        data = {
            'title': self.task.title,
            'column': self.column.id,
            'assigned_to': user2.id
        }
        response = self.client.post(
            reverse('kanban:task_update', kwargs={'pk': self.task.id}),
            data
        )
        
        self.task.refresh_from_db()
        self.assertEqual(self.task.assigned_to, user2)
    
    def test_task_delete_requires_permission(self):
        """Test task deletion requires proper permissions"""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        
        self.client.login(username='otheruser', password='testpass123')
        response = self.client.post(
            reverse('kanban:task_delete', kwargs={'pk': self.task.id})
        )
        self.assertEqual(response.status_code, 403)


class ColumnViewTests(TestCase):
    """Test Column views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
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
        self.profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            is_admin=True
        )
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        self.board.members.add(self.user)
    
    def test_column_create_view_post(self):
        """Test creating column"""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': 'New Column',
            'board': self.board.id,
            'position': 0
        }
        response = self.client.post(
            reverse('kanban:column_create', kwargs={'board_id': self.board.id}),
            data
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Column.objects.filter(name='New Column').exists()
        )
    
    def test_column_update_view_post(self):
        """Test updating column"""
        column = Column.objects.create(
            name='To Do',
            board=self.board,
            position=0
        )
        
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': 'Backlog',
            'board': self.board.id,
            'position': 0
        }
        response = self.client.post(
            reverse('kanban:column_update', kwargs={'pk': column.id}),
            data
        )
        
        column.refresh_from_db()
        self.assertEqual(column.name, 'Backlog')
    
    def test_column_delete_view(self):
        """Test deleting column"""
        column = Column.objects.create(
            name='Temp Column',
            board=self.board,
            position=0
        )
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(
            reverse('kanban:column_delete', kwargs={'pk': column.id})
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            Column.objects.filter(pk=column.id).exists()
        )
    
    def test_column_reorder_view(self):
        """Test reordering columns"""
        col1 = Column.objects.create(name='Col1', board=self.board, position=0)
        col2 = Column.objects.create(name='Col2', board=self.board, position=1)
        col3 = Column.objects.create(name='Col3', board=self.board, position=2)
        
        self.client.login(username='testuser', password='testpass123')
        data = {
            'column_order': [col3.id, col1.id, col2.id]
        }
        response = self.client.post(
            reverse('kanban:column_reorder', kwargs={'board_id': self.board.id}),
            data,
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)


class TaskLabelViewTests(TestCase):
    """Test TaskLabel views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
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
        self.profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            is_admin=True
        )
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
    
    def test_label_create_view_post(self):
        """Test creating label"""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'name': 'Bug',
            'color': '#FF0000',
            'board': self.board.id,
            'category': 'regular'
        }
        response = self.client.post(
            reverse('kanban:label_create', kwargs={'board_id': self.board.id}),
            data
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            TaskLabel.objects.filter(name='Bug').exists()
        )
