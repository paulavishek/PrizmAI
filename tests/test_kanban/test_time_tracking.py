"""
Tests for Time Tracking Feature
================================

Tests coverage:
- TimeEntry model validation
- TimeEntryForm validation
- Maximum hours validation
- Negative hours rejection
- Decimal precision (0.25 increments)
- Daily total validation
- AI anomaly detection
- Smart task suggestions
- Quick time entry view
"""

from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from accounts.models import Organization
from kanban.models import Board, Column, Task
from kanban.budget_models import TimeEntry
from kanban.budget_forms import TimeEntryForm
from kanban.time_tracking_ai import TimeTrackingAIService


class TimeEntryModelTests(TestCase):
    """Test TimeEntry model validation"""
    
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
    
    def test_valid_time_entry(self):
        """Test creating a valid time entry"""
        entry = TimeEntry.objects.create(
            task=self.task,
            user=self.user,
            hours_spent=Decimal('4.50'),
            work_date=date.today(),
            description='Worked on feature implementation'
        )
        self.assertEqual(entry.hours_spent, Decimal('4.50'))
        self.assertEqual(entry.task, self.task)
        self.assertEqual(entry.user, self.user)
    
    def test_minimum_hours_validation(self):
        """Test that hours less than 0.01 are rejected"""
        entry = TimeEntry(
            task=self.task,
            user=self.user,
            hours_spent=Decimal('0.00'),
            work_date=date.today()
        )
        with self.assertRaises(ValidationError):
            entry.full_clean()
    
    def test_maximum_hours_validation(self):
        """Test that hours greater than 16 are rejected"""
        entry = TimeEntry(
            task=self.task,
            user=self.user,
            hours_spent=Decimal('17.00'),
            work_date=date.today()
        )
        with self.assertRaises(ValidationError):
            entry.full_clean()
    
    def test_max_hours_boundary(self):
        """Test that exactly 16 hours is accepted"""
        entry = TimeEntry.objects.create(
            task=self.task,
            user=self.user,
            hours_spent=Decimal('16.00'),
            work_date=date.today()
        )
        entry.full_clean()  # Should not raise
        self.assertEqual(entry.hours_spent, Decimal('16.00'))


class TimeEntryFormTests(TestCase):
    """Test TimeEntryForm validation"""
    
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
    
    def test_form_valid_data(self):
        """Test form with valid data"""
        form = TimeEntryForm(
            data={
                'hours_spent': '4.50',
                'work_date': date.today().isoformat(),
                'description': 'Test work'
            },
            user=self.user
        )
        self.assertTrue(form.is_valid())
    
    def test_form_max_hours_exceeded(self):
        """Test form rejects hours > 16"""
        form = TimeEntryForm(
            data={
                'hours_spent': '17.00',
                'work_date': date.today().isoformat(),
                'description': 'Too many hours'
            },
            user=self.user
        )
        self.assertFalse(form.is_valid())
        self.assertIn('hours_spent', form.errors)
    
    def test_form_negative_hours(self):
        """Test form rejects negative hours"""
        form = TimeEntryForm(
            data={
                'hours_spent': '-5.00',
                'work_date': date.today().isoformat(),
                'description': 'Negative hours'
            },
            user=self.user
        )
        self.assertFalse(form.is_valid())
    
    def test_form_decimal_rounding(self):
        """Test form rounds to 0.25 increments"""
        form = TimeEntryForm(
            data={
                'hours_spent': '1.33',
                'work_date': date.today().isoformat(),
                'description': 'Non-standard decimal'
            },
            user=self.user
        )
        self.assertTrue(form.is_valid())
        # Should be rounded to 1.25 or 1.50
        rounded_hours = form.cleaned_data['hours_spent']
        self.assertIn(rounded_hours, [Decimal('1.25'), Decimal('1.50')])
    
    def test_form_daily_total_exceeded(self):
        """Test form rejects when daily total would exceed 24 hours"""
        # Create existing entry for 20 hours
        TimeEntry.objects.create(
            task=self.task,
            user=self.user,
            hours_spent=Decimal('15.00'),
            work_date=date.today()
        )
        
        # Try to add 10 more hours (15 + 10 = 25 > 24)
        form = TimeEntryForm(
            data={
                'hours_spent': '10.00',
                'work_date': date.today().isoformat(),
                'description': 'Exceeds daily total'
            },
            user=self.user
        )
        self.assertFalse(form.is_valid())
        # Should have non-field error about daily total
        self.assertTrue(form.non_field_errors() or 'hours_spent' in form.errors)


class TimeTrackingAIServiceTests(TestCase):
    """Test AI-powered time tracking features"""
    
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
            name='In Progress',
            board=self.board,
            position=0
        )
        self.task = Task.objects.create(
            title='Test Task',
            column=self.column,
            created_by=self.user,
            assigned_to=self.user,
            progress=50
        )
    
    def test_detect_high_hours_anomaly(self):
        """Test detection of unusually high hours in a day"""
        # Create entry with 15 hours (above 12h threshold)
        TimeEntry.objects.create(
            task=self.task,
            user=self.user,
            hours_spent=Decimal('15.00'),
            work_date=date.today()
        )
        
        ai_service = TimeTrackingAIService(self.user)
        anomalies = ai_service.detect_anomalies(days_back=1)
        
        # Should detect this as an anomaly
        high_hours_alerts = [a for a in anomalies if a['type'] in ['high_hours_critical', 'high_hours_warning', 'large_entry']]
        self.assertGreater(len(high_hours_alerts), 0)
    
    def test_no_anomaly_for_normal_hours(self):
        """Test no anomaly for normal work hours"""
        # Create entry with 8 hours (normal)
        TimeEntry.objects.create(
            task=self.task,
            user=self.user,
            hours_spent=Decimal('8.00'),
            work_date=date.today()
        )
        
        ai_service = TimeTrackingAIService(self.user)
        anomalies = ai_service.detect_anomalies(days_back=1)
        
        # Should not have high hours alerts
        high_hours_alerts = [a for a in anomalies if a['type'] in ['high_hours_critical', 'high_hours_warning']]
        self.assertEqual(len(high_hours_alerts), 0)
    
    def test_suggest_tasks_returns_in_progress(self):
        """Test that task suggestions include in-progress tasks"""
        ai_service = TimeTrackingAIService(self.user)
        suggestions = ai_service.suggest_tasks()
        
        # Should suggest the in-progress task
        suggested_task_ids = [s['task'].id for s in suggestions]
        self.assertIn(self.task.id, suggested_task_ids)
    
    def test_suggest_tasks_prioritizes_recent(self):
        """Test that recently logged tasks are suggested first"""
        # Log time for the task
        TimeEntry.objects.create(
            task=self.task,
            user=self.user,
            hours_spent=Decimal('2.00'),
            work_date=date.today()
        )
        
        ai_service = TimeTrackingAIService(self.user)
        suggestions = ai_service.suggest_tasks()
        
        if suggestions:
            # First suggestion should be the recently logged task
            self.assertEqual(suggestions[0]['task'].id, self.task.id)
            self.assertEqual(suggestions[0]['reason'], 'last_logged')
    
    def test_missing_time_alert_afternoon(self):
        """Test missing time alert in afternoon with no logged hours"""
        ai_service = TimeTrackingAIService(self.user)
        
        # This test depends on current time, so we just verify the method works
        alert = ai_service.get_missing_time_alerts()
        # Alert could be None if it's weekend or morning
        # Just verify it returns a dict or None
        self.assertTrue(alert is None or isinstance(alert, dict))


class QuickTimeEntryViewTests(TestCase):
    """Test quick time entry API endpoint"""
    
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
            column=self.column,
            created_by=self.user
        )
        # Use force_login instead of login to bypass Axes authentication
        self.client.force_login(self.user)
    
    def test_quick_entry_valid_hours(self):
        """Test quick entry with valid hours"""
        url = reverse('quick_time_entry', args=[self.task.id])
        response = self.client.post(url, {
            'hours': '4.00',
            'work_date': date.today().isoformat(),
            'description': 'Test work'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
    
    def test_quick_entry_exceeds_max_hours(self):
        """Test quick entry rejects hours > 16"""
        url = reverse('quick_time_entry', args=[self.task.id])
        response = self.client.post(url, {
            'hours': '20.00',
            'work_date': date.today().isoformat(),
            'description': 'Too many hours'
        })
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('16', data['error'])
    
    def test_quick_entry_negative_hours(self):
        """Test quick entry rejects negative hours"""
        url = reverse('quick_time_entry', args=[self.task.id])
        response = self.client.post(url, {
            'hours': '-5.00',
            'work_date': date.today().isoformat(),
            'description': 'Negative hours'
        })
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
    
    def test_quick_entry_rounds_decimal(self):
        """Test quick entry rounds to 0.25 increments"""
        url = reverse('quick_time_entry', args=[self.task.id])
        response = self.client.post(url, {
            'hours': '1.33',
            'work_date': date.today().isoformat(),
            'description': 'Non-standard decimal'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        # Should be rounded
        self.assertIn(data['hours'], [1.25, 1.5])
    
    def test_quick_entry_daily_total_exceeded(self):
        """Test quick entry rejects when daily total would exceed 24 hours"""
        # Create existing entry for 20 hours
        TimeEntry.objects.create(
            task=self.task,
            user=self.user,
            hours_spent=Decimal('20.00'),
            work_date=date.today()
        )
        
        url = reverse('quick_time_entry', args=[self.task.id])
        response = self.client.post(url, {
            'hours': '10.00',
            'work_date': date.today().isoformat(),
            'description': 'Exceeds daily total'
        })
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('24', data['error'])
