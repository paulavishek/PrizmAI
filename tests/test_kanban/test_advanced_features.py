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
    WorkloadDistributionRecommendation, BoardMembership
)
from kanban.utils.skill_analysis import calculate_skill_gaps, _normalize_skill_name


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


class SkillGapMatchingTests(TestCase):
    """Skill-gap detection must match generic task disciplines to the specific
    technologies stored on team-member profiles (and tolerate parenthetical
    qualifiers). Regression coverage for the false "Critical – Cannot proceed"
    gaps reported when a capable team's skills were named differently from the
    skills the AI extracted from task titles.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='lead', email='lead@example.com', password='x'
        )
        self.board = Board.objects.create(name='SkillBoard', created_by=self.user)
        self.column = Column.objects.create(name='To Do', board=self.board)
        # One member who is a backend Expert and a DevOps/CI-CD Expert, using the
        # specific-technology + parenthetical names that real profiles store.
        UserProfile.objects.create(
            user=self.user,
            skills=[
                {'name': 'Python', 'level': 'Expert'},
                {'name': 'Django', 'level': 'Expert'},
                {'name': 'CI/CD (GitHub Actions)', 'level': 'Expert'},
            ],
        )
        BoardMembership.objects.create(board=self.board, user=self.user, role='owner')

    def _make_task(self, title, skills):
        return Task.objects.create(
            title=title, column=self.column, created_by=self.user,
            required_skills=skills,
        )

    def test_normalize_collapses_aliases_to_buckets(self):
        """Generic disciplines and their specific technologies share one key."""
        self.assertEqual(_normalize_skill_name('Backend Development'), 'backend')
        self.assertEqual(_normalize_skill_name('Python'), 'backend')
        self.assertEqual(_normalize_skill_name('Django'), 'backend')
        # Parenthetical qualifiers are stripped before aliasing.
        self.assertEqual(_normalize_skill_name('CI/CD'), 'devops')
        self.assertEqual(_normalize_skill_name('CI/CD (GitHub Actions)'), 'devops')
        # Unmapped specialties keep their own canonical key (remain genuine gaps).
        self.assertEqual(_normalize_skill_name('OAuth'), 'oauth')

    def test_covered_discipline_not_reported_as_zero_coverage(self):
        """CI/CD tasks must not be a zero-coverage gap when a member is a
        CI/CD Expert under the name 'CI/CD (GitHub Actions)'."""
        # 2+ tasks needed to pass the frequency filter.
        self._make_task('Set up CI pipeline', [{'name': 'CI/CD', 'level': 'Advanced'}])
        self._make_task('Add deploy workflow', [{'name': 'CI/CD', 'level': 'Advanced'}])

        gaps = calculate_skill_gaps(self.board)
        zero_coverage = [g for g in gaps if not g.get('has_team_coverage')]
        # No gap should claim the team has zero people for a covered discipline.
        self.assertFalse(
            any(g['available_count'] == 0 and g.get('severity') == 'critical'
                and g['skill_name'] in ('DevOps / CI-CD', 'CI/CD')
                for g in gaps),
            f"CI/CD wrongly flagged as zero-coverage critical: {gaps}"
        )
        # And the covered backend discipline should show coverage too.
        self._make_task('Build API a', [{'name': 'Backend Development', 'level': 'Advanced'}])
        self._make_task('Build API b', [{'name': 'Python', 'level': 'Advanced'}])
        gaps = calculate_skill_gaps(self.board)
        backend = next((g for g in gaps if g['skill_name'] == 'Backend Development'), None)
        if backend is not None:
            self.assertTrue(backend['has_team_coverage'])
            self.assertGreater(backend['available_count'], 0)

    def test_genuinely_missing_skill_still_flagged(self):
        """A skill no member has must still surface as a gap."""
        self._make_task('OAuth login', [{'name': 'OAuth', 'level': 'Advanced'}])
        self._make_task('OAuth refresh', [{'name': 'OAuth', 'level': 'Advanced'}])
        gaps = calculate_skill_gaps(self.board)
        oauth = next((g for g in gaps if g['skill_name'].lower() == 'oauth'), None)
        self.assertIsNotNone(oauth, f"OAuth gap should be reported: {gaps}")
        self.assertFalse(oauth['has_team_coverage'])

    def test_oauth_variants_collapse_to_one_gap(self):
        """"OAuth" and "OAuth 2.0" are the same competency — they must not
        appear as two separate duplicate gaps in the list."""
        self.assertEqual(_normalize_skill_name('OAuth'), 'oauth')
        self.assertEqual(_normalize_skill_name('OAuth 2.0'), 'oauth')
        self.assertEqual(_normalize_skill_name('OAuth2'), 'oauth')
        self._make_task('Google OAuth 2.0', [{'name': 'OAuth 2.0', 'level': 'Advanced'}])
        self._make_task('GitHub OAuth', [{'name': 'OAuth', 'level': 'Advanced'}])
        gaps = calculate_skill_gaps(self.board)
        oauth_gaps = [g for g in gaps if g['skill_name'].lower().startswith('oauth')]
        self.assertEqual(
            len(oauth_gaps), 1,
            f"OAuth variants must collapse to a single gap, got: {[g['skill_name'] for g in oauth_gaps]}"
        )
        # Both tasks fold into the one gap's affected task count.
        self.assertEqual(oauth_gaps[0]['task_count'], 2)

    def test_system_architecture_covers_software_architecture(self):
        """A member with "System Architecture" covers "Software Architecture"
        tasks — they are the same discipline under different labels."""
        self.assertEqual(
            _normalize_skill_name('System Architecture'),
            _normalize_skill_name('Software Architecture'),
        )

    def test_critical_requires_active_work(self):
        """"Critical – Cannot proceed" must be reserved for skills blocking work
        that is actually in flight. A missing skill needed only by backlog / to-do
        tasks is serious but not "cannot proceed" — it should cap at 'high'."""
        # Two tasks needing a skill nobody has, both sitting in the To Do column.
        self._make_task('Add Redis cache', [{'name': 'Redis', 'level': 'Advanced'}])
        self._make_task('Redis pub/sub', [{'name': 'Redis', 'level': 'Advanced'}])
        gaps = calculate_skill_gaps(self.board)
        redis = next((g for g in gaps if g['skill_name'].lower() == 'redis'), None)
        self.assertIsNotNone(redis, f"Redis gap expected: {gaps}")
        self.assertEqual(redis['active_task_count'], 0)
        self.assertNotEqual(
            redis['severity'], 'critical',
            "A backlog-only zero-coverage gap must not be Critical/Cannot-proceed"
        )

        # Now move the same work into an active (In Progress) column: it becomes
        # a genuine blocker and may escalate to critical.
        active_col = Column.objects.create(
            name='In Progress', board=self.board, column_type='in_progress'
        )
        Task.objects.create(
            title='Redis clustering', column=active_col, created_by=self.user,
            required_skills=[{'name': 'Redis', 'level': 'Advanced'}],
        )
        Task.objects.create(
            title='Redis failover', column=active_col, created_by=self.user,
            required_skills=[{'name': 'Redis', 'level': 'Advanced'}],
        )
        gaps = calculate_skill_gaps(self.board)
        redis = next((g for g in gaps if g['skill_name'].lower() == 'redis'), None)
        self.assertIsNotNone(redis)
        self.assertGreaterEqual(redis['active_task_count'], 2)
        self.assertEqual(
            redis['severity'], 'critical',
            "Zero-coverage skill blocking active work should be Critical"
        )
