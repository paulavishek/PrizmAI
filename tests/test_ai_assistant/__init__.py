"""
Tests for AI Assistant App Models
==================================

Tests coverage:
- AIAssistantSession model
- AIAssistantMessage model
- UserPreference model
- AIAssistantAnalytics model
- ProjectKnowledgeBase model
- AITaskRecommendation model
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from ai_assistant.models import (
    AIAssistantSession, AIAssistantMessage, UserPreference,
    AIAssistantAnalytics, ProjectKnowledgeBase, AITaskRecommendation
)
from kanban.models import Board
from accounts.models import Organization, UserProfile


class AIAssistantSessionTests(TestCase):
    """Test AIAssistantSession model"""
    
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
    
    def test_session_creation(self):
        """Test creating an AI session"""
        session = AIAssistantSession.objects.create(
            user=self.user,
            title='Project Planning Discussion',
            description='Discussing Q1 planning'
        )
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.title, 'Project Planning Discussion')
        self.assertTrue(session.is_active)
    
    def test_session_with_board_context(self):
        """Test session with board context"""
        session = AIAssistantSession.objects.create(
            user=self.user,
            board=self.board,
            title='Board Analysis'
        )
        self.assertEqual(session.board, self.board)
    
    def test_session_message_count(self):
        """Test session message count tracking"""
        session = AIAssistantSession.objects.create(
            user=self.user,
            title='Test Session',
            message_count=5
        )
        self.assertEqual(session.message_count, 5)
    
    def test_session_token_tracking(self):
        """Test token usage tracking"""
        session = AIAssistantSession.objects.create(
            user=self.user,
            title='Test Session',
            total_tokens_used=1500
        )
        self.assertEqual(session.total_tokens_used, 1500)
    
    def test_session_active_status(self):
        """Test session active/inactive status"""
        session = AIAssistantSession.objects.create(
            user=self.user,
            title='Test Session',
            is_active=True
        )
        self.assertTrue(session.is_active)
        
        session.is_active = False
        session.save()
        
        session.refresh_from_db()
        self.assertFalse(session.is_active)
    
    def test_session_ordering(self):
        """Test sessions ordered by updated_at"""
        session1 = AIAssistantSession.objects.create(
            user=self.user,
            title='Old Session'
        )
        session2 = AIAssistantSession.objects.create(
            user=self.user,
            title='New Session'
        )
        sessions = AIAssistantSession.objects.all()
        self.assertEqual(sessions[0], session2)  # Most recent first


class UserPreferenceTests(TestCase):
    """Test UserPreference model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_preference_creation(self):
        """Test creating user preferences"""
        pref = UserPreference.objects.create(
            user=self.user,
            enable_web_search=True,
            enable_task_insights=True
        )
        self.assertEqual(pref.user, self.user)
        self.assertTrue(pref.enable_web_search)
        self.assertTrue(pref.enable_task_insights)
    
    def test_preference_defaults(self):
        """Test preference default values"""
        pref = UserPreference.objects.create(user=self.user)
        self.assertTrue(pref.enable_web_search)
        self.assertTrue(pref.enable_task_insights)
        self.assertTrue(pref.enable_risk_alerts)
        self.assertTrue(pref.enable_resource_recommendations)
    
    def test_notification_preferences(self):
        """Test notification preferences"""
        pref = UserPreference.objects.create(
            user=self.user,
            notify_on_risk=True,
            notify_on_overload=True,
            notify_on_dependency_issues=False
        )
        self.assertTrue(pref.notify_on_risk)
        self.assertTrue(pref.notify_on_overload)
        self.assertFalse(pref.notify_on_dependency_issues)
    
    def test_theme_preference(self):
        """Test theme preference"""
        pref = UserPreference.objects.create(
            user=self.user,
            theme='dark'
        )
        self.assertEqual(pref.theme, 'dark')
    
    def test_messages_per_page(self):
        """Test messages per page setting"""
        pref = UserPreference.objects.create(
            user=self.user,
            messages_per_page=50
        )
        self.assertEqual(pref.messages_per_page, 50)
    
    def test_preference_timestamps(self):
        """Test preference timestamps"""
        pref = UserPreference.objects.create(user=self.user)
        self.assertIsNotNone(pref.created_at)
        self.assertIsNotNone(pref.updated_at)


class AIAssistantAnalyticsTests(TestCase):
    """Test AIAssistantAnalytics model"""
    
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
    
    def test_analytics_creation(self):
        """Test creating analytics record"""
        analytics = AIAssistantAnalytics.objects.create(
            user=self.user,
            board=self.board,
            sessions_created=5,
            messages_sent=50,
            gemini_requests=40
        )
        self.assertEqual(analytics.user, self.user)
        self.assertEqual(analytics.sessions_created, 5)
        self.assertEqual(analytics.messages_sent, 50)
    
    def test_search_metrics(self):
        """Test search-related metrics"""
        analytics = AIAssistantAnalytics.objects.create(
            user=self.user,
            web_searches_performed=10,
            knowledge_base_queries=20
        )
        self.assertEqual(analytics.web_searches_performed, 10)
        self.assertEqual(analytics.knowledge_base_queries, 20)
    
    def test_token_tracking(self):
        """Test token usage tracking"""
        analytics = AIAssistantAnalytics.objects.create(
            user=self.user,
            total_tokens_used=5000,
            input_tokens=2000,
            output_tokens=3000
        )
        self.assertEqual(analytics.total_tokens_used, 5000)
        self.assertEqual(analytics.input_tokens, 2000)
        self.assertEqual(analytics.output_tokens, 3000)
    
    def test_quality_metrics(self):
        """Test quality metrics"""
        analytics = AIAssistantAnalytics.objects.create(
            user=self.user,
            helpful_responses=45,
            unhelpful_responses=5,
            avg_response_time_ms=500
        )
        self.assertEqual(analytics.helpful_responses, 45)
        self.assertEqual(analytics.unhelpful_responses, 5)
        self.assertEqual(analytics.avg_response_time_ms, 500)
    
    def test_date_tracking(self):
        """Test date field for daily analytics"""
        analytics = AIAssistantAnalytics.objects.create(user=self.user)
        self.assertIsNotNone(analytics.date)
    
    def test_created_at_timestamp(self):
        """Test created_at timestamp"""
        analytics = AIAssistantAnalytics.objects.create(user=self.user)
        self.assertIsNotNone(analytics.created_at)


class ProjectKnowledgeBaseTests(TestCase):
    """Test ProjectKnowledgeBase model"""
    
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
    
    def test_knowledge_base_creation(self):
        """Test creating knowledge base entry"""
        kb = ProjectKnowledgeBase.objects.create(
            board=self.board,
            title='API Documentation',
            content='REST API endpoints...'
        )
        self.assertEqual(kb.board, self.board)
        self.assertEqual(kb.title, 'API Documentation')
    
    def test_knowledge_base_type(self):
        """Test knowledge base entry types"""
        types = ['documentation', 'decision', 'lesson', 'template']
        for entry_type in types:
            kb = ProjectKnowledgeBase.objects.create(
                board=self.board,
                title=f'Entry-{entry_type}',
                content='Content',
                entry_type=entry_type
            )
            self.assertEqual(kb.entry_type, entry_type)
    
    def test_knowledge_base_tags(self):
        """Test tagging knowledge base entries"""
        tags = ['api', 'backend', 'documentation']
        kb = ProjectKnowledgeBase.objects.create(
            board=self.board,
            title='API Docs',
            content='Content',
            tags=tags
        )
        self.assertEqual(kb.tags, tags)


class AITaskRecommendationTests(TestCase):
    """Test AITaskRecommendation model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_recommendation_creation(self):
        """Test creating AI recommendation"""
        rec = AITaskRecommendation.objects.create(
            user=self.user,
            recommendation_type='skill_match',
            title='Skill Improvement',
            description='Consider learning Python'
        )
        self.assertEqual(rec.user, self.user)
        self.assertEqual(rec.recommendation_type, 'skill_match')
    
    def test_recommendation_confidence_score(self):
        """Test confidence score"""
        rec = AITaskRecommendation.objects.create(
            user=self.user,
            recommendation_type='workload',
            title='Reduce workload',
            confidence_score=85
        )
        self.assertEqual(rec.confidence_score, 85)
    
    def test_recommendation_action_items(self):
        """Test action items in recommendation"""
        actions = [
            'Assign fewer high-priority tasks',
            'Redistribute existing load',
            'Schedule learning time'
        ]
        rec = AITaskRecommendation.objects.create(
            user=self.user,
            recommendation_type='workload',
            title='Optimize workload',
            action_items=actions
        )
        self.assertEqual(rec.action_items, actions)
    
    def test_recommendation_accepted(self):
        """Test marking recommendation as accepted"""
        rec = AITaskRecommendation.objects.create(
            user=self.user,
            recommendation_type='skill_match',
            title='Test'
        )
        self.assertFalse(rec.is_accepted)
        
        rec.is_accepted = True
        rec.save()
        
        rec.refresh_from_db()
        self.assertTrue(rec.is_accepted)
