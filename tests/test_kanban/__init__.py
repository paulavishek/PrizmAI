"""
Tests for Kanban App Models
=============================

Tests coverage:
- Board model and relationships
- Column model and ordering
- Task model with all features
- TaskLabel model
- Comment model
- TaskFile model
- Task creation, updates, and filtering
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from kanban.models import Board, Column, Task, TaskLabel, Comment, TaskFile
from accounts.models import Organization, UserProfile


class BoardModelTests(TestCase):
    """Test Board model"""
    
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
        UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            is_admin=True
        )
    
    def test_board_creation(self):
        """Test creating a board"""
        board = Board.objects.create(
            name='Project Alpha',
            description='Main project board',
            organization=self.org,
            created_by=self.user
        )
        self.assertEqual(board.name, 'Project Alpha')
        self.assertEqual(board.organization, self.org)
        self.assertEqual(board.created_by, self.user)
    
    def test_board_members_relationship(self):
        """Test adding members to board"""
        board = Board.objects.create(
            name='Project Alpha',
            organization=self.org,
            created_by=self.user
        )
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        board.members.add(user2)
        self.assertEqual(board.members.count(), 1)
        self.assertIn(user2, board.members.all())
    
    def test_board_string_representation(self):
        """Test board __str__ method"""
        board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        self.assertEqual(str(board), 'Test Board')
    
    def test_board_timestamp(self):
        """Test created_at timestamp"""
        board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        self.assertIsNotNone(board.created_at)
    
    def test_board_columns_relationship(self):
        """Test board-columns relationship"""
        board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        Column.objects.create(name='To Do', board=board, position=0)
        Column.objects.create(name='In Progress', board=board, position=1)
        Column.objects.create(name='Done', board=board, position=2)
        
        self.assertEqual(board.columns.count(), 3)


class ColumnModelTests(TestCase):
    """Test Column model"""
    
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
    
    def test_column_creation(self):
        """Test creating a column"""
        column = Column.objects.create(
            name='To Do',
            board=self.board,
            position=0
        )
        self.assertEqual(column.name, 'To Do')
        self.assertEqual(column.board, self.board)
        self.assertEqual(column.position, 0)
    
    def test_column_ordering(self):
        """Test columns are ordered by position"""
        col1 = Column.objects.create(name='To Do', board=self.board, position=0)
        col2 = Column.objects.create(name='In Progress', board=self.board, position=1)
        col3 = Column.objects.create(name='Done', board=self.board, position=2)
        
        columns = Column.objects.all()
        self.assertEqual(columns[0], col1)
        self.assertEqual(columns[1], col2)
        self.assertEqual(columns[2], col3)
    
    def test_column_string_representation(self):
        """Test column __str__ method"""
        column = Column.objects.create(
            name='To Do',
            board=self.board,
            position=0
        )
        self.assertEqual(str(column), 'To Do - Test Board')


class TaskModelTests(TestCase):
    """Test Task model"""
    
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
        self.column = Column.objects.create(
            name='To Do',
            board=self.board,
            position=0
        )
    
    def test_task_creation(self):
        """Test creating a task"""
        task = Task.objects.create(
            title='Test Task',
            description='Task description',
            column=self.column,
            created_by=self.user
        )
        self.assertEqual(task.title, 'Test Task')
        self.assertEqual(task.column, self.column)
        self.assertEqual(task.created_by, self.user)
    
    def test_task_priority_choices(self):
        """Test task priority choices"""
        priorities = ['low', 'medium', 'high', 'urgent']
        for priority in priorities:
            task = Task.objects.create(
                title=f'Task - {priority}',
                column=self.column,
                priority=priority,
                created_by=self.user
            )
            self.assertEqual(task.priority, priority)
    
    def test_task_assignment(self):
        """Test assigning task to user"""
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        task = Task.objects.create(
            title='Assigned Task',
            column=self.column,
            assigned_to=user2,
            created_by=self.user
        )
        self.assertEqual(task.assigned_to, user2)
    
    def test_task_due_date(self):
        """Test setting task due date"""
        due_date = timezone.now() + timedelta(days=5)
        task = Task.objects.create(
            title='Task with due date',
            column=self.column,
            due_date=due_date,
            created_by=self.user
        )
        self.assertEqual(task.due_date, due_date)
    
    def test_task_progress(self):
        """Test task progress field"""
        task = Task.objects.create(
            title='Task Progress',
            column=self.column,
            progress=50,
            created_by=self.user
        )
        self.assertEqual(task.progress, 50)
    
    def test_task_progress_validation(self):
        """Test progress field validation (0-100)"""
        # Valid progress values
        for progress in [0, 25, 50, 75, 100]:
            task = Task(
                title=f'Progress {progress}',
                column=self.column,
                progress=progress,
                created_by=self.user
            )
            task.full_clean()
            self.assertEqual(task.progress, progress)
    
    def test_task_ai_risk_score(self):
        """Test AI risk score field"""
        task = Task.objects.create(
            title='Task with risk',
            column=self.column,
            ai_risk_score=75,
            created_by=self.user
        )
        self.assertEqual(task.ai_risk_score, 75)
    
    def test_task_ai_recommendations(self):
        """Test AI recommendations field"""
        recommendations = 'Consider assigning to expert Python developer'
        task = Task.objects.create(
            title='Task with recommendations',
            column=self.column,
            ai_recommendations=recommendations,
            created_by=self.user
        )
        self.assertEqual(task.ai_recommendations, recommendations)
    
    def test_task_required_skills(self):
        """Test required skills JSON field"""
        skills = [
            {'name': 'Python', 'level': 'Intermediate'},
            {'name': 'Django', 'level': 'Expert'},
        ]
        task = Task.objects.create(
            title='Skill-based task',
            column=self.column,
            required_skills=skills,
            created_by=self.user
        )
        self.assertEqual(task.required_skills, skills)
    
    def test_task_start_date(self):
        """Test task start date for Gantt chart"""
        start_date = timezone.now().date()
        task = Task.objects.create(
            title='Gantt task',
            column=self.column,
            start_date=start_date,
            created_by=self.user
        )
        self.assertEqual(task.start_date, start_date)
    
    def test_task_labels_relationship(self):
        """Test adding labels to task"""
        label = TaskLabel.objects.create(
            name='Bug',
            board=self.board
        )
        task = Task.objects.create(
            title='Bug fix task',
            column=self.column,
            created_by=self.user
        )
        task.labels.add(label)
        self.assertEqual(task.labels.count(), 1)
        self.assertIn(label, task.labels.all())
    
    def test_task_timestamps(self):
        """Test task creation and update timestamps"""
        task = Task.objects.create(
            title='Test Task',
            column=self.column,
            created_by=self.user
        )
        self.assertIsNotNone(task.created_at)
        self.assertIsNotNone(task.updated_at)
    
    def test_task_position(self):
        """Test task position field"""
        task = Task.objects.create(
            title='Positioned task',
            column=self.column,
            position=1,
            created_by=self.user
        )
        self.assertEqual(task.position, 1)


class TaskLabelModelTests(TestCase):
    """Test TaskLabel model"""
    
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
    
    def test_label_creation(self):
        """Test creating a label"""
        label = TaskLabel.objects.create(
            name='Bug',
            board=self.board
        )
        self.assertEqual(label.name, 'Bug')
        self.assertEqual(label.board, self.board)
    
    def test_label_color(self):
        """Test label color field"""
        label = TaskLabel.objects.create(
            name='Feature',
            board=self.board,
            color='#00FF00'
        )
        self.assertEqual(label.color, '#00FF00')
    
    def test_label_category(self):
        """Test label category choices"""
        categories = ['regular', 'lean']
        for category in categories:
            label = TaskLabel.objects.create(
                name=f'Label-{category}',
                board=self.board,
                category=category
            )
            self.assertEqual(label.category, category)


class CommentModelTests(TestCase):
    """Test Comment model"""
    
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
        self.column = Column.objects.create(
            name='To Do',
            board=self.board,
            position=0
        )
        self.task = Task.objects.create(
            title='Test Task',
            column=self.column,
            created_by=self.user
        )
    
    def test_comment_creation(self):
        """Test creating a comment on a task"""
        comment = Comment.objects.create(
            task=self.task,
            user=self.user,
            content='Test comment'
        )
        self.assertEqual(comment.content, 'Test comment')
        self.assertEqual(comment.task, self.task)
        self.assertEqual(comment.user, self.user)
    
    def test_comment_timestamp(self):
        """Test comment creation timestamp"""
        comment = Comment.objects.create(
            task=self.task,
            user=self.user,
            content='Test comment'
        )
        self.assertIsNotNone(comment.created_at)


class TaskFileModelTests(TestCase):
    """Test TaskFile model"""
    
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
        self.column = Column.objects.create(
            name='To Do',
            board=self.board,
            position=0
        )
        self.task = Task.objects.create(
            title='Test Task',
            column=self.column,
            created_by=self.user
        )
    
    def test_file_attachment_creation(self):
        """Test creating file attachment"""
        file_info = TaskFile(
            task=self.task,
            uploaded_by=self.user,
            filename='test.pdf',
            file_size=1024,
            file_type='pdf'
        )
        file_info.save()
        
        self.assertEqual(file_info.task, self.task)
        self.assertEqual(file_info.uploaded_by, self.user)
        self.assertEqual(file_info.filename, 'test.pdf')
    
    def test_file_allowed_types(self):
        """Test file type validation"""
        allowed_types = ['pdf', 'doc', 'docx', 'jpg', 'png']
        for file_type in allowed_types:
            file_obj = TaskFile(
                task=self.task,
                uploaded_by=self.user,
                filename=f'file.{file_type}',
                file_size=512,
                file_type=file_type
            )
            file_obj.save()
            self.assertEqual(file_obj.file_type, file_type)
