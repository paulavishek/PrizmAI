"""
Tests for Stakeholder Management Models
========================================

Tests coverage:
- ProjectStakeholder model and power/interest matrix
- StakeholderTaskInvolvement tracking
- StakeholderEngagementRecord logging
- EngagementMetrics calculations
- StakeholderTag system
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from accounts.models import Organization, UserProfile
from kanban.models import Board, Column, Task
from kanban.stakeholder_models import (
    ProjectStakeholder, StakeholderTaskInvolvement,
    StakeholderEngagementRecord, EngagementMetrics,
    StakeholderTag, ProjectStakeholderTag
)


class ProjectStakeholderTests(TestCase):
    """Test ProjectStakeholder model"""
    
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
    
    def test_stakeholder_creation(self):
        """Test creating a project stakeholder"""
        stakeholder = ProjectStakeholder.objects.create(
            name='John Doe',
            role='Product Manager',
            organization='Product Team',
            email='john@example.com',
            phone='123-456-7890',
            board=self.board,
            influence_level='high',
            interest_level='high',
            created_by=self.user
        )
        self.assertEqual(stakeholder.name, 'John Doe')
        self.assertEqual(stakeholder.influence_level, 'high')
        self.assertTrue(stakeholder.is_active)
    
    def test_stakeholder_influence_levels(self):
        """Test all influence level choices"""
        levels = ['low', 'medium', 'high']
        for level in levels:
            stakeholder = ProjectStakeholder.objects.create(
                name=f'Stakeholder {level}',
                role='Role',
                board=self.board,
                influence_level=level,
                created_by=self.user
            )
            self.assertEqual(stakeholder.influence_level, level)
    
    def test_stakeholder_engagement_strategy(self):
        """Test engagement strategy choices"""
        strategies = ['inform', 'consult', 'involve', 'collaborate', 'empower']
        for strategy in strategies:
            stakeholder = ProjectStakeholder.objects.create(
                name=f'Stakeholder {strategy}',
                role='Role',
                board=self.board,
                current_engagement=strategy,
                created_by=self.user
            )
            self.assertEqual(stakeholder.current_engagement, strategy)
    
    def test_get_quadrant_manage_closely(self):
        """Test quadrant: Manage Closely (high influence, high interest)"""
        stakeholder = ProjectStakeholder.objects.create(
            name='Key Stakeholder',
            role='CEO',
            board=self.board,
            influence_level='high',
            interest_level='high',
            created_by=self.user
        )
        self.assertEqual(stakeholder.get_quadrant(), 'Manage Closely')
    
    def test_get_quadrant_keep_satisfied(self):
        """Test quadrant: Keep Satisfied (high influence, low interest)"""
        stakeholder = ProjectStakeholder.objects.create(
            name='Executive',
            role='VP',
            board=self.board,
            influence_level='high',
            interest_level='low',
            created_by=self.user
        )
        self.assertEqual(stakeholder.get_quadrant(), 'Keep Satisfied')
    
    def test_get_quadrant_keep_informed(self):
        """Test quadrant: Keep Informed (low influence, high interest)"""
        stakeholder = ProjectStakeholder.objects.create(
            name='Team Member',
            role='Developer',
            board=self.board,
            influence_level='low',
            interest_level='high',
            created_by=self.user
        )
        self.assertEqual(stakeholder.get_quadrant(), 'Keep Informed')
    
    def test_get_quadrant_monitor(self):
        """Test quadrant: Monitor (low influence, low interest)"""
        stakeholder = ProjectStakeholder.objects.create(
            name='External User',
            role='Consultant',
            board=self.board,
            influence_level='low',
            interest_level='low',
            created_by=self.user
        )
        self.assertEqual(stakeholder.get_quadrant(), 'Monitor')
    
    def test_get_engagement_gap(self):
        """Test engagement gap calculation"""
        stakeholder = ProjectStakeholder.objects.create(
            name='Stakeholder',
            role='Manager',
            board=self.board,
            current_engagement='inform',  # Level 1
            desired_engagement='collaborate',  # Level 4
            created_by=self.user
        )
        gap = stakeholder.get_engagement_gap()
        self.assertEqual(gap, 3)  # 4 - 1 = 3
    
    def test_unique_stakeholder_per_board(self):
        """Test stakeholders are unique per board by email and name"""
        ProjectStakeholder.objects.create(
            name='John Doe',
            role='Manager',
            board=self.board,
            email='john@example.com',
            created_by=self.user
        )
        
        # Duplicate should raise error
        with self.assertRaises(Exception):
            ProjectStakeholder.objects.create(
                name='John Doe',
                role='Another Role',
                board=self.board,
                email='john@example.com',
                created_by=self.user
            )


class StakeholderTaskInvolvementTests(TestCase):
    """Test StakeholderTaskInvolvement model"""
    
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
        self.stakeholder = ProjectStakeholder.objects.create(
            name='Jane Smith',
            role='Reviewer',
            board=self.board,
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
    
    def test_involvement_creation(self):
        """Test creating stakeholder task involvement"""
        involvement = StakeholderTaskInvolvement.objects.create(
            stakeholder=self.stakeholder,
            task=self.task,
            involvement_type='reviewer',
            engagement_status='consulted'
        )
        self.assertEqual(involvement.stakeholder, self.stakeholder)
        self.assertEqual(involvement.task, self.task)
        self.assertEqual(involvement.involvement_type, 'reviewer')
    
    def test_involvement_types(self):
        """Test all involvement type choices"""
        types = ['owner', 'contributor', 'reviewer', 'approver', 'observer', 'beneficiary', 'impacted']
        for inv_type in types:
            involvement = StakeholderTaskInvolvement.objects.create(
                stakeholder=self.stakeholder,
                task=self.task,
                involvement_type=inv_type
            )
            self.assertEqual(involvement.involvement_type, inv_type)
            involvement.delete()  # Clean up for next iteration
    
    def test_engagement_tracking(self):
        """Test engagement count and timestamp"""
        involvement = StakeholderTaskInvolvement.objects.create(
            stakeholder=self.stakeholder,
            task=self.task,
            involvement_type='contributor',
            engagement_count=5,
            last_engagement=timezone.now()
        )
        self.assertEqual(involvement.engagement_count, 5)
        self.assertIsNotNone(involvement.last_engagement)
    
    def test_satisfaction_rating(self):
        """Test satisfaction rating field"""
        involvement = StakeholderTaskInvolvement.objects.create(
            stakeholder=self.stakeholder,
            task=self.task,
            involvement_type='approver',
            satisfaction_rating=4
        )
        self.assertEqual(involvement.satisfaction_rating, 4)
    
    def test_feedback_and_concerns(self):
        """Test feedback and concerns tracking"""
        involvement = StakeholderTaskInvolvement.objects.create(
            stakeholder=self.stakeholder,
            task=self.task,
            involvement_type='reviewer',
            feedback='Great work on this task!',
            concerns='Timeline might be tight'
        )
        self.assertEqual(involvement.feedback, 'Great work on this task!')
        self.assertEqual(involvement.concerns, 'Timeline might be tight')
    
    def test_unique_involvement_per_task(self):
        """Test only one involvement record per stakeholder-task pair"""
        StakeholderTaskInvolvement.objects.create(
            stakeholder=self.stakeholder,
            task=self.task,
            involvement_type='reviewer'
        )
        
        with self.assertRaises(Exception):
            StakeholderTaskInvolvement.objects.create(
                stakeholder=self.stakeholder,
                task=self.task,
                involvement_type='approver'
            )


class StakeholderEngagementRecordTests(TestCase):
    """Test StakeholderEngagementRecord model"""
    
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
        self.stakeholder = ProjectStakeholder.objects.create(
            name='Bob Johnson',
            role='Sponsor',
            board=self.board,
            created_by=self.user
        )
    
    def test_engagement_record_creation(self):
        """Test creating engagement record"""
        record = StakeholderEngagementRecord.objects.create(
            stakeholder=self.stakeholder,
            date=timezone.now().date(),
            description='Status update meeting',
            communication_channel='meeting',
            outcome='Approved next phase',
            created_by=self.user
        )
        self.assertEqual(record.stakeholder, self.stakeholder)
        self.assertEqual(record.communication_channel, 'meeting')
    
    def test_communication_channels(self):
        """Test all communication channel choices"""
        channels = ['email', 'phone', 'meeting', 'video', 'chat', 'presentation', 'survey', 'other']
        for channel in channels:
            record = StakeholderEngagementRecord.objects.create(
                stakeholder=self.stakeholder,
                date=timezone.now().date(),
                description=f'Engagement via {channel}',
                communication_channel=channel,
                created_by=self.user
            )
            self.assertEqual(record.communication_channel, channel)
            record.delete()
    
    def test_follow_up_tracking(self):
        """Test follow-up required and completion tracking"""
        record = StakeholderEngagementRecord.objects.create(
            stakeholder=self.stakeholder,
            date=timezone.now().date(),
            description='Initial discussion',
            communication_channel='email',
            follow_up_required=True,
            follow_up_date=timezone.now().date() + timedelta(days=7),
            created_by=self.user
        )
        self.assertTrue(record.follow_up_required)
        self.assertFalse(record.follow_up_completed)
        self.assertIsNotNone(record.follow_up_date)
    
    def test_engagement_sentiment(self):
        """Test engagement sentiment tracking"""
        sentiments = ['positive', 'neutral', 'negative']
        for sentiment in sentiments:
            record = StakeholderEngagementRecord.objects.create(
                stakeholder=self.stakeholder,
                date=timezone.now().date(),
                description='Meeting',
                communication_channel='meeting',
                engagement_sentiment=sentiment,
                created_by=self.user
            )
            self.assertEqual(record.engagement_sentiment, sentiment)
            record.delete()
    
    def test_satisfaction_rating(self):
        """Test satisfaction rating"""
        record = StakeholderEngagementRecord.objects.create(
            stakeholder=self.stakeholder,
            date=timezone.now().date(),
            description='Review session',
            communication_channel='video',
            satisfaction_rating=5,
            created_by=self.user
        )
        self.assertEqual(record.satisfaction_rating, 5)


class EngagementMetricsTests(TestCase):
    """Test EngagementMetrics model"""
    
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
        self.stakeholder = ProjectStakeholder.objects.create(
            name='Alice Williams',
            role='Director',
            board=self.board,
            created_by=self.user
        )
    
    def test_metrics_creation(self):
        """Test creating engagement metrics"""
        metrics = EngagementMetrics.objects.create(
            board=self.board,
            stakeholder=self.stakeholder,
            total_engagements=10,
            engagements_this_month=3,
            period_start=timezone.now().date(),
            period_end=timezone.now().date()
        )
        self.assertEqual(metrics.stakeholder, self.stakeholder)
        self.assertEqual(metrics.total_engagements, 10)
    
    def test_average_satisfaction_calculation(self):
        """Test average satisfaction tracking"""
        metrics = EngagementMetrics.objects.create(
            board=self.board,
            stakeholder=self.stakeholder,
            average_satisfaction=4.5,
            period_start=timezone.now().date(),
            period_end=timezone.now().date()
        )
        self.assertEqual(float(metrics.average_satisfaction), 4.5)
    
    def test_sentiment_counts(self):
        """Test positive/negative engagement counts"""
        metrics = EngagementMetrics.objects.create(
            board=self.board,
            stakeholder=self.stakeholder,
            positive_engagements_count=8,
            negative_engagements_count=2,
            period_start=timezone.now().date(),
            period_end=timezone.now().date()
        )
        self.assertEqual(metrics.positive_engagements_count, 8)
        self.assertEqual(metrics.negative_engagements_count, 2)
    
    def test_days_since_last_engagement(self):
        """Test days since last engagement tracking"""
        metrics = EngagementMetrics.objects.create(
            board=self.board,
            stakeholder=self.stakeholder,
            days_since_last_engagement=5,
            period_start=timezone.now().date(),
            period_end=timezone.now().date()
        )
        self.assertEqual(metrics.days_since_last_engagement, 5)
    
    def test_calculate_engagement_health(self):
        """Test engagement health score calculation"""
        metrics = EngagementMetrics.objects.create(
            board=self.board,
            stakeholder=self.stakeholder,
            average_engagements_per_month=4,
            average_satisfaction=4.0,
            engagement_gap=1,
            period_start=timezone.now().date(),
            period_end=timezone.now().date()
        )
        
        health_score = metrics.calculate_engagement_health()
        self.assertGreater(health_score, 0)
        self.assertLessEqual(health_score, 100)
    
    def test_primary_channel_tracking(self):
        """Test primary communication channel tracking"""
        metrics = EngagementMetrics.objects.create(
            board=self.board,
            stakeholder=self.stakeholder,
            primary_channel='email',
            channels_used=[
                {'channel': 'email', 'count': 10},
                {'channel': 'meeting', 'count': 3}
            ],
            period_start=timezone.now().date(),
            period_end=timezone.now().date()
        )
        self.assertEqual(metrics.primary_channel, 'email')
        self.assertEqual(len(metrics.channels_used), 2)


class StakeholderTagTests(TestCase):
    """Test StakeholderTag model"""
    
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
    
    def test_tag_creation(self):
        """Test creating stakeholder tag"""
        tag = StakeholderTag.objects.create(
            name='VIP',
            color='#FF0000',
            board=self.board,
            created_by=self.user
        )
        self.assertEqual(tag.name, 'VIP')
        self.assertEqual(tag.color, '#FF0000')
    
    def test_unique_tag_per_board(self):
        """Test tags are unique per board"""
        StakeholderTag.objects.create(
            name='Executive',
            board=self.board,
            created_by=self.user
        )
        
        with self.assertRaises(Exception):
            StakeholderTag.objects.create(
                name='Executive',
                board=self.board,
                created_by=self.user
            )
    
    def test_tag_stakeholder_association(self):
        """Test associating tags with stakeholders"""
        tag = StakeholderTag.objects.create(
            name='Key Decision Maker',
            board=self.board,
            created_by=self.user
        )
        stakeholder = ProjectStakeholder.objects.create(
            name='CEO',
            role='Chief Executive',
            board=self.board,
            created_by=self.user
        )
        
        # Create association
        assoc = ProjectStakeholderTag.objects.create(
            stakeholder=stakeholder,
            tag=tag
        )
        self.assertEqual(assoc.stakeholder, stakeholder)
        self.assertEqual(assoc.tag, tag)
