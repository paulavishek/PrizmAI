# filepath: c:\Users\Avishek Paul\TaskFlow\kanban\tests.py
import json
from django.utils import timezone
from datetime import timedelta
from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

# Import models from kanban app
from .models import Board, Column, Task, Comment, TaskLabel, TaskActivity
from accounts.models import Organization, UserProfile


class BoardTestCase(TestCase):
    """Test board functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='boardowner',
            email='owner@example.com',
            password='testpass123'
        )
        self.collaborator = User.objects.create_user(
            username='collaborator',
            email='collab@example.com',
            password='testpass123'
        )
        
        # Create organization
        self.organization = Organization.objects.create(
            name='Test Org',
            domain='testorg.com',
            created_by=self.user
        )
        
        # Create user profiles
        self.user_profile = UserProfile.objects.create(
            user=self.user,
            organization=self.organization
        )
        self.collaborator_profile = UserProfile.objects.create(
            user=self.collaborator,
            organization=self.organization
        )
    
    def test_board_creation(self):
        """Test creating a new board"""
        board = Board.objects.create(
            name='Project Alpha',
            description='Main project board',
            organization=self.organization,
            created_by=self.user
        )
        
        self.assertEqual(board.name, 'Project Alpha')
        self.assertEqual(board.created_by, self.user)
        self.assertEqual(board.organization, self.organization)
        self.assertTrue(board.created_at)
    
    def test_board_name_validation(self):
        """Test board name cannot be empty"""
        with self.assertRaises(ValidationError):
            board = Board(
                name='',
                organization=self.organization,
                created_by=self.user
            )
            board.full_clean()
    
    def test_board_members(self):
        """Test adding and removing board members"""
        board = Board.objects.create(
            name='Team Board',
            organization=self.organization,
            created_by=self.user
        )
        
        # Add collaborator
        board.members.add(self.collaborator)
        self.assertIn(self.collaborator, board.members.all())
        
        # Remove member
        board.members.remove(self.collaborator)
        self.assertNotIn(self.collaborator, board.members.all())
    
    def test_board_deletion_cascade(self):
        """Test that deleting a board cascades properly"""
        board = Board.objects.create(
            name='Temp Board',
            organization=self.organization,
            created_by=self.user
        )
        board_id = board.id
        
        # Create related objects
        column = Column.objects.create(board=board, name='Test Column')
        task = Task.objects.create(column=column, title='Test Task', created_by=self.user)
        
        board.delete()
        
        # Verify cascade
        self.assertFalse(Board.objects.filter(id=board_id).exists())
        self.assertFalse(Column.objects.filter(board_id=board_id).exists())
        self.assertFalse(Task.objects.filter(column__board_id=board_id).exists())


class ColumnTestCase(TestCase):
    """Test column functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass123')
        self.organization = Organization.objects.create(name='Test Org', domain='test.com', created_by=self.user)
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.organization,
            created_by=self.user
        )
    
    def test_column_creation(self):
        """Test creating columns with proper ordering"""
        column1 = Column.objects.create(board=self.board, name='To Do', position=1)
        column2 = Column.objects.create(board=self.board, name='In Progress', position=2)
        column3 = Column.objects.create(board=self.board, name='Done', position=3)
        
        columns = list(Column.objects.filter(board=self.board))
        self.assertEqual(len(columns), 3)
        self.assertEqual(columns[0].name, 'To Do')
        self.assertEqual(columns[1].name, 'In Progress')
        self.assertEqual(columns[2].name, 'Done')
    
    def test_column_position_ordering(self):
        """Test columns are ordered by position"""
        column_c = Column.objects.create(board=self.board, name='Column C', position=3)
        column_a = Column.objects.create(board=self.board, name='Column A', position=1)
        column_b = Column.objects.create(board=self.board, name='Column B', position=2)
        
        ordered_columns = Column.objects.filter(board=self.board)
        self.assertEqual(ordered_columns[0].name, 'Column A')
        self.assertEqual(ordered_columns[1].name, 'Column B')
        self.assertEqual(ordered_columns[2].name, 'Column C')


class TaskTestCase(TestCase):
    """Test task functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass123')
        self.assignee = User.objects.create_user(username='assignee', password='pass123')
        self.organization = Organization.objects.create(name='Test Org', domain='test.com', created_by=self.user)
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.organization,
            created_by=self.user
        )
        self.column = Column.objects.create(board=self.board, name='Test Column', position=1)
    
    def test_task_creation(self):
        """Test creating tasks with all fields"""
        due_date = timezone.now() + timedelta(days=7)
        task = Task.objects.create(
            title='Test Task',
            description='This is a test task',
            column=self.column,
            created_by=self.user,
            assigned_to=self.assignee,
            due_date=due_date,
            priority='high',
            progress=25
        )
        
        self.assertEqual(task.title, 'Test Task')
        self.assertEqual(task.assigned_to, self.assignee)
        self.assertEqual(task.priority, 'high')
        self.assertEqual(task.progress, 25)
        self.assertTrue(task.created_at)
        self.assertTrue(task.updated_at)
    
    def test_task_title_validation(self):
        """Test task title cannot be empty"""
        with self.assertRaises(ValidationError):
            task = Task(
                title='',
                column=self.column,
                created_by=self.user
            )
            task.full_clean()
    
    def test_task_progress_validation(self):
        """Test task progress must be between 0-100"""
        with self.assertRaises(ValidationError):
            task = Task(
                title='Test Task',
                column=self.column,
                created_by=self.user,
                progress=150
            )
            task.full_clean()
        
        with self.assertRaises(ValidationError):
            task = Task(
                title='Test Task',
                column=self.column,
                created_by=self.user,
                progress=-10
            )
            task.full_clean()
    
    def test_task_position_ordering(self):
        """Test task position within columns"""
        task1 = Task.objects.create(column=self.column, title='Task 1', position=1, created_by=self.user)
        task2 = Task.objects.create(column=self.column, title='Task 2', position=2, created_by=self.user)
        task3 = Task.objects.create(column=self.column, title='Task 3', position=3, created_by=self.user)
        
        ordered_tasks = Task.objects.filter(column=self.column)
        self.assertEqual(ordered_tasks[0].title, 'Task 1')
        self.assertEqual(ordered_tasks[1].title, 'Task 2')
        self.assertEqual(ordered_tasks[2].title, 'Task 3')


class TaskLabelTestCase(TestCase):
    """Test task label functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass123')
        self.organization = Organization.objects.create(name='Test Org', domain='test.com', created_by=self.user)
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.organization,
            created_by=self.user
        )
        self.column = Column.objects.create(board=self.board, name='Test', position=1)
        self.task = Task.objects.create(column=self.column, title='Test Task', created_by=self.user)
    
    def test_label_creation(self):
        """Test creating labels for boards"""
        label = TaskLabel.objects.create(
            board=self.board,
            name='Bug',
            color='#ff0000',
            category='regular'
        )
        
        self.assertEqual(label.name, 'Bug')
        self.assertEqual(label.color, '#ff0000')
        self.assertEqual(label.category, 'regular')
    
    def test_lean_six_sigma_labels(self):
        """Test creating Lean Six Sigma specific labels"""
        lean_label = TaskLabel.objects.create(
            board=self.board,
            name='Value Stream',
            color='#00ff00',
            category='lean'
        )
        
        self.assertEqual(lean_label.category, 'lean')
        self.assertEqual(lean_label.name, 'Value Stream')
    
    def test_task_label_assignment(self):
        """Test assigning labels to tasks"""
        bug_label = TaskLabel.objects.create(board=self.board, name='Bug', color='#ff0000')
        feature_label = TaskLabel.objects.create(board=self.board, name='Feature', color='#00ff00')
        
        # Assign labels to task
        self.task.labels.add(bug_label, feature_label)
        
        self.assertEqual(self.task.labels.count(), 2)
        self.assertIn(bug_label, self.task.labels.all())
        self.assertIn(feature_label, self.task.labels.all())
    
    def test_label_filtering(self):
        """Test filtering tasks by labels"""
        bug_label = TaskLabel.objects.create(board=self.board, name='Bug', color='#ff0000')
        feature_label = TaskLabel.objects.create(board=self.board, name='Feature', color='#00ff00')
        
        task1 = Task.objects.create(column=self.column, title='Bug Task', created_by=self.user)
        task1.labels.add(bug_label)
        
        task2 = Task.objects.create(column=self.column, title='Feature Task', created_by=self.user)
        task2.labels.add(feature_label)
        
        # Filter by bug label
        bug_tasks = Task.objects.filter(labels=bug_label)
        self.assertEqual(bug_tasks.count(), 1)
        self.assertEqual(bug_tasks.first().title, 'Bug Task')


class CommentTestCase(TestCase):
    """Test comment functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass123')
        self.other_user = User.objects.create_user(username='other', password='pass123')
        self.organization = Organization.objects.create(name='Test Org', domain='test.com', created_by=self.user)
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.organization,
            created_by=self.user
        )
        self.column = Column.objects.create(board=self.board, name='Test', position=1)
        self.task = Task.objects.create(column=self.column, title='Test Task', created_by=self.user)
    
    def test_comment_creation(self):
        """Test creating comments on tasks"""
        comment = Comment.objects.create(
            task=self.task,
            user=self.user,
            content='This is a test comment'
        )
        
        self.assertEqual(comment.content, 'This is a test comment')
        self.assertEqual(comment.user, self.user)
        self.assertEqual(comment.task, self.task)
        self.assertTrue(comment.created_at)
    
    def test_comment_ordering(self):
        """Test comments are ordered by creation date (newest first)"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Create comments with explicit timestamps to ensure proper ordering
        now = timezone.now()
        comment1 = Comment.objects.create(task=self.task, user=self.user, content='First comment')
        comment1.created_at = now - timedelta(minutes=2)
        comment1.save()
        
        comment2 = Comment.objects.create(task=self.task, user=self.other_user, content='Second comment')
        comment2.created_at = now - timedelta(minutes=1)
        comment2.save()
        
        comment3 = Comment.objects.create(task=self.task, user=self.user, content='Third comment')
        comment3.created_at = now
        comment3.save()
        
        comments = list(Comment.objects.filter(task=self.task))
        self.assertEqual(comments[0].content, 'Third comment')  # Newest first
        self.assertEqual(comments[1].content, 'Second comment')
        self.assertEqual(comments[2].content, 'First comment')


class TaskActivityTestCase(TestCase):
    """Test task activity tracking"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass123')
        self.organization = Organization.objects.create(name='Test Org', domain='test.com', created_by=self.user)
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.organization,
            created_by=self.user
        )
        self.column = Column.objects.create(board=self.board, name='Test', position=1)
        self.task = Task.objects.create(column=self.column, title='Test Task', created_by=self.user)
    
    def test_activity_creation(self):
        """Test creating task activities"""
        activity = TaskActivity.objects.create(
            task=self.task,
            user=self.user,
            activity_type='created',
            description='Task was created'
        )
        
        self.assertEqual(activity.activity_type, 'created')
        self.assertEqual(activity.description, 'Task was created')
        self.assertEqual(activity.user, self.user)
        self.assertTrue(activity.created_at)
    
    def test_activity_types(self):
        """Test different activity types"""
        activities = [
            ('created', 'Task was created'),
            ('moved', 'Task moved to Done'),
            ('assigned', 'Task assigned to user'),
            ('updated', 'Task updated'),
            ('commented', 'Comment added'),
            ('label_added', 'Bug label added'),
            ('label_removed', 'Bug label removed'),
        ]
        
        for activity_type, description in activities:
            activity = TaskActivity.objects.create(
                task=self.task,
                user=self.user,
                activity_type=activity_type,
                description=description
            )
            self.assertEqual(activity.activity_type, activity_type)
    
    def test_activity_ordering(self):
        """Test activities are ordered by creation date (newest first)"""
        from django.utils import timezone
        from datetime import timedelta
        
        # Create activities with explicit timestamps to ensure proper ordering
        now = timezone.now()
        activity1 = TaskActivity.objects.create(
            task=self.task, user=self.user, activity_type='created', description='First'
        )
        activity1.created_at = now - timedelta(minutes=2)
        activity1.save()
        
        activity2 = TaskActivity.objects.create(
            task=self.task, user=self.user, activity_type='updated', description='Second'
        )
        activity2.created_at = now - timedelta(minutes=1)
        activity2.save()
        
        activity3 = TaskActivity.objects.create(
            task=self.task, user=self.user, activity_type='moved', description='Third'
        )
        activity3.created_at = now
        activity3.save()
        
        activities = list(TaskActivity.objects.filter(task=self.task))
        self.assertEqual(activities[0].description, 'Third')  # Newest first
        self.assertEqual(activities[1].description, 'Second')
        self.assertEqual(activities[2].description, 'First')


class LeanSixSigmaTestCase(TestCase):
    """Test Lean Six Sigma specific functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='leanuser', password='pass123')
        self.organization = Organization.objects.create(name='Lean Org', domain='lean.com', created_by=self.user)
        self.board = Board.objects.create(
            name='Value Stream Board',
            organization=self.organization,
            created_by=self.user
        )
        
        # Create Lean Six Sigma columns
        self.define_column = Column.objects.create(board=self.board, name='Define', position=1)
        self.measure_column = Column.objects.create(board=self.board, name='Measure', position=2)
        self.analyze_column = Column.objects.create(board=self.board, name='Analyze', position=3)
        self.improve_column = Column.objects.create(board=self.board, name='Improve', position=4)
        self.control_column = Column.objects.create(board=self.board, name='Control', position=5)
    
    def test_dmaic_workflow(self):
        """Test DMAIC (Define, Measure, Analyze, Improve, Control) workflow"""
        # Create a task that moves through DMAIC phases
        task = Task.objects.create(
            title='Process Improvement Initiative',
            description='Reduce customer wait time',
            column=self.define_column,
            created_by=self.user,
            priority='high'
        )
        
        # Define phase
        self.assertEqual(task.column.name, 'Define')
        TaskActivity.objects.create(
            task=task,
            user=self.user,
            activity_type='created',
            description='Problem defined: Customer wait time too long'
        )
        
        # Move to Measure
        task.column = self.measure_column
        task.save()
        TaskActivity.objects.create(
            task=task,
            user=self.user,
            activity_type='moved',
            description='Moved to Measure phase'
        )
        
        # Verify task progression
        self.assertEqual(task.column.name, 'Measure')
        self.assertEqual(task.activities.count(), 2)
    
    def test_lean_labels(self):
        """Test Lean Six Sigma specific labels"""
        lean_labels = [
            ('Value Stream', '#00ff00'),
            ('Waste Elimination', '#ff9900'),
            ('Process Improvement', '#0099ff'),
            ('Quality Control', '#9900ff'),
            ('Customer Voice', '#ff0099'),
        ]
        
        created_labels = []
        for name, color in lean_labels:
            label = TaskLabel.objects.create(
                board=self.board,
                name=name,
                color=color,
                category='lean'
            )
            created_labels.append(label)
        
        # Verify all lean labels were created
        lean_board_labels = TaskLabel.objects.filter(board=self.board, category='lean')
        self.assertEqual(lean_board_labels.count(), 5)
        
        # Test label assignment to tasks
        task = Task.objects.create(
            title='Identify Value Stream',
            column=self.define_column,
            created_by=self.user
        )
        
        value_stream_label = TaskLabel.objects.get(name='Value Stream')
        task.labels.add(value_stream_label)
        
        self.assertIn(value_stream_label, task.labels.all())
        self.assertEqual(value_stream_label.category, 'lean')


class BoardAnalyticsTestCase(TestCase):
    """Test board analytics and reporting functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='analyst', password='pass123')
        self.organization = Organization.objects.create(name='Analytics Org', domain='analytics.com', created_by=self.user)
        self.board = Board.objects.create(
            name='Analytics Board',
            organization=self.organization,
            created_by=self.user
        )
        
        # Create columns
        self.todo_column = Column.objects.create(board=self.board, name='To Do', position=1)
        self.progress_column = Column.objects.create(board=self.board, name='In Progress', position=2)
        self.done_column = Column.objects.create(board=self.board, name='Done', position=3)
        
        # Create sample tasks
        self.create_sample_tasks()
    
    def create_sample_tasks(self):
        """Create sample tasks for analytics testing"""
        # Tasks in different columns with different priorities
        Task.objects.create(
            title='High Priority Task 1',
            column=self.todo_column,
            created_by=self.user,
            priority='high',
            progress=0
        )
        
        Task.objects.create(
            title='Medium Priority Task 1',
            column=self.progress_column,
            created_by=self.user,
            priority='medium',
            progress=50
        )
        
        Task.objects.create(
            title='Completed Task 1',
            column=self.done_column,
            created_by=self.user,
            priority='low',
            progress=100
        )
        
        Task.objects.create(
            title='Completed Task 2',
            column=self.done_column,
            created_by=self.user,
            priority='high',
            progress=100
        )
    
    def test_task_distribution_analytics(self):
        """Test analyzing task distribution across columns"""
        # Count tasks per column
        todo_count = Task.objects.filter(column=self.todo_column).count()
        progress_count = Task.objects.filter(column=self.progress_column).count()
        done_count = Task.objects.filter(column=self.done_column).count()
        
        self.assertEqual(todo_count, 1)
        self.assertEqual(progress_count, 1)
        self.assertEqual(done_count, 2)
        
        # Verify total tasks
        total_tasks = Task.objects.filter(column__board=self.board).count()
        self.assertEqual(total_tasks, 4)
    
    def test_priority_distribution_analytics(self):
        """Test analyzing task distribution by priority"""
        high_priority = Task.objects.filter(column__board=self.board, priority='high').count()
        medium_priority = Task.objects.filter(column__board=self.board, priority='medium').count()
        low_priority = Task.objects.filter(column__board=self.board, priority='low').count()
        
        self.assertEqual(high_priority, 2)
        self.assertEqual(medium_priority, 1)
        self.assertEqual(low_priority, 1)
    
    def test_completion_rate_analytics(self):
        """Test calculating task completion rates"""
        total_tasks = Task.objects.filter(column__board=self.board).count()
        completed_tasks = Task.objects.filter(column__board=self.board, progress=100).count()
        
        completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
        
        self.assertEqual(total_tasks, 4)
        self.assertEqual(completed_tasks, 2)
        self.assertEqual(completion_rate, 50.0)


class TaskProgressTestCase(TestCase):
    """Test task progress tracking and analytics"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='progressuser', password='pass123')
        self.organization = Organization.objects.create(name='Progress Org', domain='progress.com', created_by=self.user)
        self.board = Board.objects.create(
            name='Progress Board',
            organization=self.organization,
            created_by=self.user
        )
        self.column = Column.objects.create(board=self.board, name='In Progress', position=1)
    
    def test_progress_validation(self):
        """Test progress field validation (0-100)"""
        # Valid progress values
        for progress in [0, 25, 50, 75, 100]:
            task = Task.objects.create(
                title=f'Task {progress}%',
                column=self.column,
                created_by=self.user,
                progress=progress
            )
            self.assertEqual(task.progress, progress)
    
    def test_progress_tracking_workflow(self):
        """Test tracking task progress through activities"""
        task = Task.objects.create(
            title='Progress Tracking Task',
            column=self.column,
            created_by=self.user,
            progress=0
        )
        
        # Track progress updates
        progress_updates = [
            (25, 'Initial progress made'),
            (50, 'Halfway complete'),
            (75, 'Almost finished'),
            (100, 'Task completed'),
        ]
        
        for progress, description in progress_updates:
            task.progress = progress
            task.save()
            
            TaskActivity.objects.create(
                task=task,
                user=self.user,
                activity_type='updated',
                description=f'Progress updated to {progress}%: {description}'
            )
        
        # Verify final state
        self.assertEqual(task.progress, 100)
        self.assertEqual(task.activities.count(), 4)
        
        # Verify progress history through activities
        progress_activities = task.activities.filter(
            description__icontains='Progress updated'
        )
        self.assertEqual(progress_activities.count(), 4)


class LeanSixSigmaIntegrationTestCase(TestCase):
    """Test complete Lean Six Sigma integration workflow"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='leanmaster', password='pass123')
        self.team_member = User.objects.create_user(username='teammate', password='pass123')
        
        self.organization = Organization.objects.create(
            name='Lean Enterprise',
            domain='leanenterprise.com',
            created_by=self.user
        )
        
        # Create user profiles
        UserProfile.objects.create(user=self.user, organization=self.organization)
        UserProfile.objects.create(user=self.team_member, organization=self.organization)
        
        # Create Value Stream Mapping board
        self.vsm_board = Board.objects.create(
            name='Value Stream Mapping',
            description='End-to-end process improvement',
            organization=self.organization,
            created_by=self.user
        )
        self.vsm_board.members.add(self.team_member)
        
        # Create DMAIC columns
        self.setup_dmaic_columns()
        self.setup_lean_labels()
    
    def setup_dmaic_columns(self):
        """Setup DMAIC methodology columns"""
        self.define_col = Column.objects.create(board=self.vsm_board, name='Define', position=1)
        self.measure_col = Column.objects.create(board=self.vsm_board, name='Measure', position=2)
        self.analyze_col = Column.objects.create(board=self.vsm_board, name='Analyze', position=3)
        self.improve_col = Column.objects.create(board=self.vsm_board, name='Improve', position=4)
        self.control_col = Column.objects.create(board=self.vsm_board, name='Control', position=5)
    
    def setup_lean_labels(self):
        """Setup Lean Six Sigma labels"""
        self.lean_labels = {}
        lean_label_data = [
            ('Value Stream', '#1f77b4'),
            ('Waste Elimination', '#ff7f0e'),
            ('Process Improvement', '#2ca02c'),
            ('Quality Control', '#d62728'),
            ('Customer Voice', '#9467bd'),
            ('Kaizen', '#8c564b'),
            ('Poka-Yoke', '#e377c2'),
            ('5S', '#7f7f7f'),
        ]
        
        for name, color in lean_label_data:
            label = TaskLabel.objects.create(
                board=self.vsm_board,
                name=name,
                color=color,
                category='lean'
            )
            self.lean_labels[name.lower().replace(' ', '_')] = label
    
    def test_complete_dmaic_workflow(self):
        """Test complete DMAIC process workflow"""
        # Define Phase - Create improvement initiative
        improvement_task = Task.objects.create(
            title='Reduce Order Processing Time',
            description='Current order processing takes 3 days, target is 1 day',
            column=self.define_col,
            created_by=self.user,
            priority='high',
            progress=10
        )
        
        # Add relevant labels
        improvement_task.labels.add(
            self.lean_labels['value_stream'],
            self.lean_labels['process_improvement']
        )
        
        # Log define activities
        TaskActivity.objects.create(
            task=improvement_task,
            user=self.user,
            activity_type='created',
            description='Problem statement: Order processing takes too long'
        )
        
        # Measure Phase - Move task and update progress
        improvement_task.column = self.measure_col
        improvement_task.progress = 30
        improvement_task.save()
        
        TaskActivity.objects.create(
            task=improvement_task,
            user=self.user,
            activity_type='moved',
            description='Moved to Measure phase'
        )
        
        # Control Phase
        improvement_task.column = self.control_col
        improvement_task.progress = 100
        improvement_task.save()
        
        improvement_task.labels.add(self.lean_labels['quality_control'])
        
        TaskActivity.objects.create(
            task=improvement_task,
            user=self.user,
            activity_type='moved',
            description='Moved to Control phase'
        )
        
        # Verify complete workflow
        self.assertEqual(improvement_task.column, self.control_col)
        self.assertEqual(improvement_task.progress, 100)
        self.assertEqual(improvement_task.activities.count(), 3)
        self.assertEqual(improvement_task.labels.filter(category='lean').count(), 3)


if __name__ == '__main__':
    import unittest
    unittest.main()


# Priority Suggestion Feature Tests
from .priority_models import PriorityDecision, PriorityModel, PrioritySuggestionLog
from ai_assistant.utils.priority_service import PrioritySuggestionService, PriorityModelTrainer


class PrioritySuggestionServiceTest(TestCase):
    """Test priority suggestion service"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.organization = Organization.objects.create(name='Test Org', domain='test.com', created_by=self.user)
        UserProfile.objects.create(user=self.user, organization=self.organization)
        
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.organization,
            created_by=self.user
        )
        self.board.members.add(self.user)
        
        self.column = Column.objects.create(name='To Do', board=self.board, position=0)
        self.service = PrioritySuggestionService()
    
    def test_rule_based_suggestion_urgent(self):
        """Test rule-based suggestion for urgent task"""
        from django.utils import timezone
        from datetime import timedelta
        
        task = Task(
            title='Urgent Task',
            column=self.column,
            created_by=self.user,
            due_date=timezone.now() - timedelta(days=1),  # Overdue
            complexity_score=8
        )
        
        suggestion = self.service.suggest_priority(task)
        
        self.assertIsNotNone(suggestion)
        self.assertIn(suggestion['suggested_priority'], ['urgent', 'high'])
        self.assertFalse(suggestion['is_ml_based'])
        self.assertIn('overdue', suggestion['reasoning']['explanation'].lower())
    
    def test_rule_based_suggestion_low(self):
        """Test rule-based suggestion for low priority task"""
        from django.utils import timezone
        from datetime import timedelta
        
        task = Task(
            title='Low Priority Task',
            column=self.column,
            created_by=self.user,
            due_date=timezone.now() + timedelta(days=30),  # Far future
            complexity_score=2
        )
        
        suggestion = self.service.suggest_priority(task)
        
        self.assertIsNotNone(suggestion)
        self.assertEqual(suggestion['suggested_priority'], 'low')


class PriorityDecisionTest(TestCase):
    """Test priority decision tracking"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.organization = Organization.objects.create(name='Test Org', domain='test.com', created_by=self.user)
        UserProfile.objects.create(user=self.user, organization=self.organization)
        
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.organization,
            created_by=self.user
        )
        
        self.column = Column.objects.create(name='To Do', board=self.board, position=0)
        self.task = Task.objects.create(
            title='Test Task',
            column=self.column,
            created_by=self.user,
            priority='medium'
        )
    
    def test_log_decision(self):
        """Test logging priority decision"""
        decision = PriorityDecision.log_decision(
            task=self.task,
            priority='high',
            user=self.user,
            decision_type='initial'
        )
        
        self.assertIsNotNone(decision)
        self.assertEqual(decision.actual_priority, 'high')
        self.assertEqual(decision.task, self.task)
        self.assertEqual(decision.decided_by, self.user)
        self.assertIsNotNone(decision.task_context)
    
    def test_log_ai_accepted_decision(self):
        """Test logging when user accepts AI suggestion"""
        decision = PriorityDecision.log_decision(
            task=self.task,
            priority='high',
            user=self.user,
            decision_type='ai_accepted',
            suggested_priority='high',
            confidence=0.85
        )
        
        self.assertTrue(decision.was_correct)
        self.assertEqual(decision.suggested_priority, 'high')
        self.assertEqual(decision.confidence_score, 0.85)
    
    def test_log_ai_rejected_decision(self):
        """Test logging when user rejects AI suggestion"""
        decision = PriorityDecision.log_decision(
            task=self.task,
            priority='medium',
            user=self.user,
            decision_type='ai_rejected',
            suggested_priority='high',
            confidence=0.75
        )
        
        self.assertFalse(decision.was_correct)
        self.assertEqual(decision.suggested_priority, 'high')
        self.assertEqual(decision.actual_priority, 'medium')
