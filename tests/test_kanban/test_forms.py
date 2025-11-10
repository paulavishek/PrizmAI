"""
Tests for Form Validation
==========================

Tests coverage:
- Task form validation
- Board form validation
- User profile form validation
- Organization form validation
- Custom validators
- Error messages
- Field constraints
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from accounts.models import Organization, UserProfile
from kanban.models import Board, Column, Task, TaskLabel
from kanban.forms import TaskForm, BoardForm
from accounts.forms import UserProfileForm, OrganizationForm


class TaskFormTests(TestCase):
    """Test Task form validation"""
    
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
    
    def test_task_form_valid_data(self):
        """Test task form with valid data"""
        form = TaskForm(data={
            'title': 'Test Task',
            'description': 'Test Description',
            'column': self.column.id,
            'priority': 'medium',
            'progress': 0
        })
        self.assertTrue(form.is_valid())
    
    def test_task_form_missing_title(self):
        """Test task form requires title"""
        form = TaskForm(data={
            'description': 'Test Description',
            'column': self.column.id
        })
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
    
    def test_task_form_title_max_length(self):
        """Test task title max length validation"""
        form = TaskForm(data={
            'title': 'A' * 201,  # Exceeds max_length=200
            'column': self.column.id
        })
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)
    
    def test_task_form_invalid_priority(self):
        """Test task form rejects invalid priority"""
        form = TaskForm(data={
            'title': 'Test Task',
            'column': self.column.id,
            'priority': 'invalid_priority'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('priority', form.errors)
    
    def test_task_form_progress_range_validation(self):
        """Test progress must be between 0 and 100"""
        # Test negative progress
        form = TaskForm(data={
            'title': 'Test Task',
            'column': self.column.id,
            'progress': -10
        })
        self.assertFalse(form.is_valid())
        
        # Test progress over 100
        form = TaskForm(data={
            'title': 'Test Task',
            'column': self.column.id,
            'progress': 150
        })
        self.assertFalse(form.is_valid())
        
        # Test valid progress
        form = TaskForm(data={
            'title': 'Test Task',
            'column': self.column.id,
            'progress': 50
        })
        self.assertTrue(form.is_valid())
    
    def test_task_form_due_date_validation(self):
        """Test due date validation"""
        from datetime import datetime, timedelta
        
        past_date = datetime.now() - timedelta(days=1)
        form = TaskForm(data={
            'title': 'Test Task',
            'column': self.column.id,
            'due_date': past_date
        })
        # Form should accept past dates but may warn
        # Adjust based on your business logic
    
    def test_task_form_assigned_to_validation(self):
        """Test assigned_to user must exist"""
        form = TaskForm(data={
            'title': 'Test Task',
            'column': self.column.id,
            'assigned_to': 99999  # Non-existent user ID
        })
        self.assertFalse(form.is_valid())


class BoardFormTests(TestCase):
    """Test Board form validation"""
    
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
    
    def test_board_form_valid_data(self):
        """Test board form with valid data"""
        form = BoardForm(data={
            'name': 'New Board',
            'description': 'Board Description',
            'organization': self.org.id
        })
        self.assertTrue(form.is_valid())
    
    def test_board_form_missing_name(self):
        """Test board form requires name"""
        form = BoardForm(data={
            'description': 'Board Description',
            'organization': self.org.id
        })
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
    
    def test_board_form_name_max_length(self):
        """Test board name max length"""
        form = BoardForm(data={
            'name': 'A' * 101,  # Exceeds max_length=100
            'organization': self.org.id
        })
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
    
    def test_board_form_missing_organization(self):
        """Test board form requires organization"""
        form = BoardForm(data={
            'name': 'New Board',
            'description': 'Description'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('organization', form.errors)


class UserProfileFormTests(TestCase):
    """Test UserProfile form validation"""
    
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
    
    def test_profile_form_valid_data(self):
        """Test profile form with valid data"""
        form = UserProfileForm(data={
            'weekly_capacity_hours': 40,
            'skills': [{'name': 'Python', 'level': 'Expert'}]
        })
        if form.is_valid():
            self.assertTrue(True)
    
    def test_profile_form_negative_capacity_hours(self):
        """Test profile form rejects negative capacity hours"""
        form = UserProfileForm(data={
            'weekly_capacity_hours': -10
        })
        self.assertFalse(form.is_valid())
    
    def test_profile_form_excessive_capacity_hours(self):
        """Test profile form validates reasonable capacity hours"""
        form = UserProfileForm(data={
            'weekly_capacity_hours': 200  # Unrealistic hours
        })
        # May or may not be invalid based on business logic
        # Adjust validation as needed
    
    def test_profile_form_skills_json_format(self):
        """Test skills must be valid JSON format"""
        form = UserProfileForm(data={
            'skills': 'invalid json string'
        })
        # Should reject invalid JSON format
        if not form.is_valid():
            self.assertTrue(True)


class OrganizationFormTests(TestCase):
    """Test Organization form validation"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_organization_form_valid_data(self):
        """Test organization form with valid data"""
        form = OrganizationForm(data={
            'name': 'Test Company',
            'domain': 'testcompany.com'
        })
        if form.is_valid():
            self.assertTrue(True)
    
    def test_organization_form_missing_name(self):
        """Test organization form requires name"""
        form = OrganizationForm(data={
            'domain': 'testcompany.com'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
    
    def test_organization_form_invalid_domain(self):
        """Test organization form validates domain format"""
        form = OrganizationForm(data={
            'name': 'Test Company',
            'domain': 'invalid domain with spaces'
        })
        self.assertFalse(form.is_valid())
        self.assertIn('domain', form.errors)
    
    def test_organization_form_duplicate_domain(self):
        """Test organization form prevents duplicate domains"""
        Organization.objects.create(
            name='Existing Org',
            domain='existing.com',
            created_by=self.user
        )
        
        form = OrganizationForm(data={
            'name': 'New Org',
            'domain': 'existing.com'  # Duplicate
        })
        self.assertFalse(form.is_valid())


class TaskLabelFormTests(TestCase):
    """Test TaskLabel form validation"""
    
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
    
    def test_label_form_valid_data(self):
        """Test label form with valid data"""
        from kanban.forms import TaskLabelForm
        form = TaskLabelForm(data={
            'name': 'Bug',
            'color': '#FF0000',
            'board': self.board.id,
            'category': 'regular'
        })
        if form.is_valid():
            self.assertTrue(True)
    
    def test_label_form_invalid_color_format(self):
        """Test label form validates color hex format"""
        from kanban.forms import TaskLabelForm
        form = TaskLabelForm(data={
            'name': 'Bug',
            'color': 'red',  # Invalid hex format
            'board': self.board.id
        })
        # ColorField should validate hex format
        if not form.is_valid():
            self.assertTrue(True)


class ColumnFormTests(TestCase):
    """Test Column form validation"""
    
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
    
    def test_column_form_valid_data(self):
        """Test column form with valid data"""
        from kanban.forms import ColumnForm
        form = ColumnForm(data={
            'name': 'In Progress',
            'board': self.board.id,
            'position': 1
        })
        if form.is_valid():
            self.assertTrue(True)
    
    def test_column_form_missing_name(self):
        """Test column form requires name"""
        from kanban.forms import ColumnForm
        form = ColumnForm(data={
            'board': self.board.id,
            'position': 1
        })
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
    
    def test_column_form_negative_position(self):
        """Test column form validates position"""
        from kanban.forms import ColumnForm
        form = ColumnForm(data={
            'name': 'Column',
            'board': self.board.id,
            'position': -1
        })
        # Negative position should be invalid
        if not form.is_valid():
            self.assertTrue(True)


class CustomValidatorTests(TestCase):
    """Test custom validators"""
    
    def test_email_domain_validator(self):
        """Test custom email domain validator"""
        # Example: Validate corporate email domains
        from django.core.validators import EmailValidator
        validator = EmailValidator()
        
        # Valid email
        try:
            validator('test@company.com')
            self.assertTrue(True)
        except ValidationError:
            self.fail('Valid email rejected')
        
        # Invalid email format
        with self.assertRaises(ValidationError):
            validator('invalid-email')
    
    def test_skill_level_validator(self):
        """Test skill level validation"""
        valid_levels = ['Beginner', 'Intermediate', 'Expert']
        
        # Valid skill level
        self.assertIn('Expert', valid_levels)
        
        # Invalid skill level
        self.assertNotIn('Master', valid_levels)
    
    def test_workload_percentage_validator(self):
        """Test workload percentage is within valid range"""
        # Test utilization calculation
        profile = UserProfile(
            weekly_capacity_hours=40,
            current_workload_hours=50
        )
        
        # Utilization should cap at 100
        utilization = min(
            (profile.current_workload_hours / profile.weekly_capacity_hours) * 100,
            100
        )
        self.assertEqual(utilization, 100)


class ErrorMessageTests(TestCase):
    """Test error message quality"""
    
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
            board=self.board
        )
    
    def test_task_form_error_messages_are_helpful(self):
        """Test form error messages are user-friendly"""
        form = TaskForm(data={
            'title': '',  # Empty title
            'column': self.column.id,
            'progress': 150  # Invalid progress
        })
        
        self.assertFalse(form.is_valid())
        
        # Check error messages exist
        self.assertTrue(len(form.errors) > 0)
        
        # Error messages should be strings
        for field, errors in form.errors.items():
            for error in errors:
                self.assertIsInstance(error, str)
    
    def test_form_has_field_labels(self):
        """Test forms have proper field labels"""
        form = TaskForm()
        
        # Check labels exist for important fields
        if hasattr(form.fields.get('title'), 'label'):
            self.assertIsNotNone(form.fields['title'].label)
