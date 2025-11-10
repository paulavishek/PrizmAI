"""
Tests for Advanced Kanban Features
===================================

Tests coverage:
- TaskActivity logging
- MeetingTranscript storage and processing
- ResourceDemandForecast analytics
- TeamCapacityAlert system
- WorkloadDistributionRecommendation
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from accounts.models import Organization, UserProfile
from kanban.models import (
    Board, Column, Task, TaskActivity, MeetingTranscript,
    ResourceDemandForecast, TeamCapacityAlert,
    WorkloadDistributionRecommendation
)


class TaskActivityTests(TestCase):
    """Test TaskActivity model"""
    
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
        self.task = Task.objects.create(
            title='Test Task',
            column=self.column,
            created_by=self.user
        )
    
    def test_activity_creation(self):
        """Test creating task activity log"""
        activity = TaskActivity.objects.create(
            task=self.task,
            user=self.user,
            action='created',
            description='Task created'
        )
        self.assertEqual(activity.task, self.task)
        self.assertEqual(activity.user, self.user)
        self.assertEqual(activity.action, 'created')
    
    def test_activity_ordering(self):
        """Test activities are ordered by timestamp"""
        activity1 = TaskActivity.objects.create(
            task=self.task,
            user=self.user,
            action='created',
            description='Created'
        )
        activity2 = TaskActivity.objects.create(
            task=self.task,
            user=self.user,
            action='updated',
            description='Updated'
        )
        
        activities = TaskActivity.objects.all()
        self.assertEqual(activities[0], activity2)  # Newest first


class MeetingTranscriptTests(TestCase):
    """Test MeetingTranscript model"""
    
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
    
    def test_transcript_creation(self):
        """Test creating meeting transcript"""
        transcript = MeetingTranscript.objects.create(
            board=self.board,
            title='Sprint Planning',
            date=timezone.now(),
            transcript='Meeting transcript content...',
            created_by=self.user
        )
        self.assertEqual(transcript.board, self.board)
        self.assertEqual(transcript.title, 'Sprint Planning')
        self.assertIsNotNone(transcript.transcript)
    
    def test_transcript_with_attendees(self):
        """Test transcript with attendees"""
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        transcript = MeetingTranscript.objects.create(
            board=self.board,
            title='Daily Standup',
            date=timezone.now(),
            transcript='Standup notes...',
            created_by=self.user
        )
        transcript.attendees.add(self.user, user2)
        
        self.assertEqual(transcript.attendees.count(), 2)
    
    def test_transcript_summary(self):
        """Test AI-generated summary field"""
        transcript = MeetingTranscript.objects.create(
            board=self.board,
            title='Retrospective',
            date=timezone.now(),
            transcript='Full transcript...',
            summary='Summary of key points',
            created_by=self.user
        )
        self.assertEqual(transcript.summary, 'Summary of key points')
    
    def test_action_items_extraction(self):
        """Test action items JSON field"""
        action_items = [
            {'task': 'Update documentation', 'owner': 'user1'},
            {'task': 'Fix bug #123', 'owner': 'user2'}
        ]
        transcript = MeetingTranscript.objects.create(
            board=self.board,
            title='Meeting',
            date=timezone.now(),
            transcript='Content...',
            action_items=action_items,
            created_by=self.user
        )
        self.assertEqual(len(transcript.action_items), 2)


class ResourceDemandForecastTests(TestCase):
    """Test ResourceDemandForecast model"""
    
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
    
    def test_forecast_creation(self):
        """Test creating resource demand forecast"""
        forecast = ResourceDemandForecast.objects.create(
            board=self.board,
            forecast_date=timezone.now().date() + timedelta(days=30),
            required_resources=5,
            available_resources=3,
            skill_requirements={'Python': 3, 'React': 2}
        )
        self.assertEqual(forecast.board, self.board)
        self.assertEqual(forecast.required_resources, 5)
        self.assertEqual(forecast.available_resources, 3)
    
    def test_forecast_gap_calculation(self):
        """Test resource gap calculation"""
        forecast = ResourceDemandForecast.objects.create(
            board=self.board,
            forecast_date=timezone.now().date(),
            required_resources=10,
            available_resources=7
        )
        # Gap should be 3 (10 - 7)
        gap = forecast.required_resources - forecast.available_resources
        self.assertEqual(gap, 3)
    
    def test_skill_requirements_json(self):
        """Test skill requirements JSON field"""
        skills = {
            'Python': 5,
            'Django': 3,
            'JavaScript': 2,
            'DevOps': 1
        }
        forecast = ResourceDemandForecast.objects.create(
            board=self.board,
            forecast_date=timezone.now().date(),
            skill_requirements=skills
        )
        self.assertEqual(forecast.skill_requirements, skills)
    
    def test_confidence_score(self):
        """Test forecast confidence score"""
        forecast = ResourceDemandForecast.objects.create(
            board=self.board,
            forecast_date=timezone.now().date(),
            confidence_score=85
        )
        self.assertEqual(forecast.confidence_score, 85)


class TeamCapacityAlertTests(TestCase):
    """Test TeamCapacityAlert model"""
    
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
    
    def test_alert_creation(self):
        """Test creating capacity alert"""
        alert = TeamCapacityAlert.objects.create(
            board=self.board,
            alert_type='overload',
            severity='high',
            message='Team is over capacity by 20%',
            affected_users=[self.user.id]
        )
        self.assertEqual(alert.board, self.board)
        self.assertEqual(alert.alert_type, 'overload')
        self.assertEqual(alert.severity, 'high')
    
    def test_alert_severity_levels(self):
        """Test different severity levels"""
        severities = ['low', 'medium', 'high', 'critical']
        for severity in severities:
            alert = TeamCapacityAlert.objects.create(
                board=self.board,
                alert_type='overload',
                severity=severity,
                message=f'Alert with {severity} severity'
            )
            self.assertEqual(alert.severity, severity)
            alert.delete()
    
    def test_alert_acknowledgment(self):
        """Test alert acknowledgment"""
        alert = TeamCapacityAlert.objects.create(
            board=self.board,
            alert_type='underutilized',
            severity='low',
            message='Team has excess capacity',
            is_acknowledged=False
        )
        self.assertFalse(alert.is_acknowledged)
        
        alert.is_acknowledged = True
        alert.acknowledged_by = self.user
        alert.acknowledged_at = timezone.now()
        alert.save()
        
        alert.refresh_from_db()
        self.assertTrue(alert.is_acknowledged)
        self.assertEqual(alert.acknowledged_by, self.user)
    
    def test_alert_resolution(self):
        """Test alert resolution"""
        alert = TeamCapacityAlert.objects.create(
            board=self.board,
            alert_type='skill_gap',
            severity='high',
            message='Missing required skills',
            is_resolved=False
        )
        
        alert.is_resolved = True
        alert.resolved_at = timezone.now()
        alert.resolution_notes = 'Hired new team member'
        alert.save()
        
        alert.refresh_from_db()
        self.assertTrue(alert.is_resolved)
        self.assertIsNotNone(alert.resolved_at)


class WorkloadDistributionRecommendationTests(TestCase):
    """Test WorkloadDistributionRecommendation model"""
    
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
            board=self.board
        )
        self.task = Task.objects.create(
            title='Task to redistribute',
            column=self.column,
            created_by=self.user1
        )
    
    def test_recommendation_creation(self):
        """Test creating workload distribution recommendation"""
        recommendation = WorkloadDistributionRecommendation.objects.create(
            board=self.board,
            task=self.task,
            current_assignee=self.user1,
            recommended_assignee=self.user2,
            reason='Better skill match and lower workload',
            confidence_score=85
        )
        self.assertEqual(recommendation.task, self.task)
        self.assertEqual(recommendation.current_assignee, self.user1)
        self.assertEqual(recommendation.recommended_assignee, self.user2)
    
    def test_recommendation_acceptance(self):
        """Test accepting a recommendation"""
        recommendation = WorkloadDistributionRecommendation.objects.create(
            board=self.board,
            task=self.task,
            recommended_assignee=self.user2,
            reason='Load balancing',
            is_accepted=False
        )
        
        recommendation.is_accepted = True
        recommendation.accepted_at = timezone.now()
        recommendation.save()
        
        recommendation.refresh_from_db()
        self.assertTrue(recommendation.is_accepted)
        self.assertIsNotNone(recommendation.accepted_at)
    
    def test_recommendation_rejection(self):
        """Test rejecting a recommendation"""
        recommendation = WorkloadDistributionRecommendation.objects.create(
            board=self.board,
            task=self.task,
            recommended_assignee=self.user2,
            reason='Optimize workload',
            is_rejected=False
        )
        
        recommendation.is_rejected = True
        recommendation.rejected_at = timezone.now()
        recommendation.rejection_reason = 'Current assignee has domain expertise'
        recommendation.save()
        
        recommendation.refresh_from_db()
        self.assertTrue(recommendation.is_rejected)
        self.assertEqual(
            recommendation.rejection_reason,
            'Current assignee has domain expertise'
        )
    
    def test_recommendation_confidence_score(self):
        """Test confidence score tracking"""
        recommendation = WorkloadDistributionRecommendation.objects.create(
            board=self.board,
            task=self.task,
            recommended_assignee=self.user2,
            reason='AI analysis',
            confidence_score=92
        )
        self.assertEqual(recommendation.confidence_score, 92)
    
    def test_alternative_assignees(self):
        """Test alternative assignees JSON field"""
        user3 = User.objects.create_user(
            username='user3',
            email='user3@example.com',
            password='testpass123'
        )
        
        alternatives = [
            {'user_id': self.user2.id, 'score': 90},
            {'user_id': user3.id, 'score': 75}
        ]
        
        recommendation = WorkloadDistributionRecommendation.objects.create(
            board=self.board,
            task=self.task,
            recommended_assignee=self.user2,
            reason='Best fit',
            alternative_assignees=alternatives
        )
        self.assertEqual(len(recommendation.alternative_assignees), 2)
