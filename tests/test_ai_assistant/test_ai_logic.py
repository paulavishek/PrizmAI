"""
Tests for AI Assistant Logic
=============================

Tests coverage:
- AI recommendation generation
- Task risk scoring
- Resource matching algorithms
- Knowledge base queries
- Web search integration (mocked)
- Gemini API integration (mocked)
- Token usage tracking
- Analytics calculations
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import models
from unittest.mock import patch, Mock
from datetime import timedelta

from accounts.models import Organization, UserProfile
from kanban.models import Board, Column, Task
from ai_assistant.models import (
    AIAssistantSession, AIAssistantMessage, UserPreference,
    AIAssistantAnalytics, ProjectKnowledgeBase, AITaskRecommendation
)
from ai_assistant.utils import (
    calculate_task_risk_score, recommend_assignee,
    search_knowledge_base, generate_ai_response
)


class TaskRiskScoringTests(TestCase):
    """Test AI task risk scoring logic"""
    
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
    
    def test_risk_score_for_overdue_task(self):
        """Test risk score increases for overdue tasks"""
        past_date = timezone.now() - timedelta(days=5)
        task = Task.objects.create(
            title='Overdue Task',
            column=self.column,
            due_date=past_date,
            created_by=self.user
        )
        
        risk_score = calculate_task_risk_score(task)
        
        self.assertGreater(risk_score, 50)  # Should be high risk
    
    def test_risk_score_for_unassigned_task(self):
        """Test risk score for unassigned tasks"""
        task = Task.objects.create(
            title='Unassigned Task',
            column=self.column,
            created_by=self.user,
            assigned_to=None
        )
        
        risk_score = calculate_task_risk_score(task)
        
        self.assertGreater(risk_score, 30)  # Should have moderate risk
    
    def test_risk_score_for_complex_task(self):
        """Test risk score for tasks requiring multiple skills"""
        task = Task.objects.create(
            title='Complex Task',
            column=self.column,
            created_by=self.user,
            required_skills=[
                {'name': 'Python', 'level': 'Expert'},
                {'name': 'Django', 'level': 'Expert'},
                {'name': 'React', 'level': 'Intermediate'},
                {'name': 'DevOps', 'level': 'Expert'}
            ]
        )
        
        risk_score = calculate_task_risk_score(task)
        
        self.assertGreater(risk_score, 40)  # Complex task = higher risk
    
    def test_risk_score_for_simple_task(self):
        """Test risk score for simple, well-assigned task"""
        user2 = User.objects.create_user(
            username='skilled',
            email='skilled@example.com',
            password='testpass123'
        )
        profile = UserProfile.objects.create(
            user=user2,
            organization=self.org,
            skills=[{'name': 'Python', 'level': 'Expert'}]
        )
        
        future_date = timezone.now() + timedelta(days=7)
        task = Task.objects.create(
            title='Simple Task',
            column=self.column,
            created_by=self.user,
            assigned_to=user2,
            due_date=future_date,
            required_skills=[{'name': 'Python', 'level': 'Intermediate'}]
        )
        
        risk_score = calculate_task_risk_score(task)
        
        self.assertLess(risk_score, 30)  # Low risk


class AssigneeRecommendationTests(TestCase):
    """Test AI assignee recommendation logic"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='manager',
            email='manager@example.com',
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
        
        # Create developers with different skills
        self.dev1 = User.objects.create_user(
            username='dev1',
            email='dev1@example.com',
            password='testpass123'
        )
        self.profile1 = UserProfile.objects.create(
            user=self.dev1,
            organization=self.org,
            skills=[
                {'name': 'Python', 'level': 'Expert'},
                {'name': 'Django', 'level': 'Expert'}
            ],
            weekly_capacity_hours=40,
            current_workload_hours=10
        )
        
        self.dev2 = User.objects.create_user(
            username='dev2',
            email='dev2@example.com',
            password='testpass123'
        )
        self.profile2 = UserProfile.objects.create(
            user=self.dev2,
            organization=self.org,
            skills=[
                {'name': 'JavaScript', 'level': 'Expert'},
                {'name': 'React', 'level': 'Expert'}
            ],
            weekly_capacity_hours=40,
            current_workload_hours=35
        )
    
    def test_recommend_assignee_based_on_skills(self):
        """Test assignee recommendation prioritizes skill match"""
        task = Task.objects.create(
            title='Python Task',
            column=self.column,
            created_by=self.user,
            required_skills=[
                {'name': 'Python', 'level': 'Expert'},
                {'name': 'Django', 'level': 'Intermediate'}
            ]
        )
        
        recommendations = recommend_assignee(task)
        
        self.assertIsNotNone(recommendations)
        self.assertEqual(recommendations[0]['user'], self.dev1)
        self.assertGreater(recommendations[0]['score'], 80)
    
    def test_recommend_assignee_considers_workload(self):
        """Test recommendation considers current workload"""
        task = Task.objects.create(
            title='Generic Task',
            column=self.column,
            created_by=self.user
        )
        
        recommendations = recommend_assignee(task)
        
        # dev1 has lower workload, should be preferred
        self.assertEqual(recommendations[0]['user'], self.dev1)
    
    def test_recommend_no_qualified_assignees(self):
        """Test recommendation when no one has required skills"""
        task = Task.objects.create(
            title='Specialized Task',
            column=self.column,
            created_by=self.user,
            required_skills=[
                {'name': 'Rust', 'level': 'Expert'},
                {'name': 'WebAssembly', 'level': 'Expert'}
            ]
        )
        
        recommendations = recommend_assignee(task)
        
        # Should still return recommendations but with low scores
        self.assertIsNotNone(recommendations)
        if recommendations:
            self.assertLess(recommendations[0]['score'], 50)


class KnowledgeBaseSearchTests(TestCase):
    """Test knowledge base search functionality"""
    
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
        
        # Create knowledge base entries
        ProjectKnowledgeBase.objects.create(
            board=self.board,
            title='API Documentation',
            content='REST API endpoints for task management...',
            entry_type='documentation',
            tags=['api', 'rest', 'documentation']
        )
        ProjectKnowledgeBase.objects.create(
            board=self.board,
            title='Deployment Guide',
            content='Steps to deploy the application to production...',
            entry_type='documentation',
            tags=['deployment', 'devops', 'production']
        )
    
    def test_search_knowledge_base_by_keyword(self):
        """Test searching knowledge base by keyword"""
        results = search_knowledge_base(self.board, 'API')
        
        self.assertGreater(len(results), 0)
        self.assertIn('API Documentation', [r.title for r in results])
    
    def test_search_knowledge_base_by_tag(self):
        """Test searching knowledge base by tag"""
        results = search_knowledge_base(self.board, tags=['deployment'])
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, 'Deployment Guide')
    
    def test_search_knowledge_base_no_results(self):
        """Test search with no matching results"""
        results = search_knowledge_base(self.board, 'nonexistent topic')
        
        self.assertEqual(len(results), 0)


class GeminiAPIIntegrationTests(TestCase):
    """Test Gemini API integration (mocked)"""
    
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
        self.session = AIAssistantSession.objects.create(
            user=self.user,
            board=self.board,
            title='Test Session'
        )
    
    @patch('ai_assistant.utils.gemini_api_call')
    def test_generate_ai_response_success(self, mock_gemini):
        """Test successful AI response generation"""
        mock_gemini.return_value = {
            'response': 'This is an AI-generated response',
            'tokens_used': 150
        }
        
        response = generate_ai_response(
            session=self.session,
            prompt='Tell me about this project'
        )
        
        self.assertIsNotNone(response)
        self.assertIn('AI-generated', response['response'])
        self.assertEqual(response['tokens_used'], 150)
    
    @patch('ai_assistant.utils.gemini_api_call')
    def test_generate_ai_response_with_context(self, mock_gemini):
        """Test AI response with board context"""
        mock_gemini.return_value = {
            'response': 'Based on your board context...',
            'tokens_used': 200
        }
        
        response = generate_ai_response(
            session=self.session,
            prompt='Analyze my board',
            include_board_context=True
        )
        
        mock_gemini.assert_called_once()
        call_args = mock_gemini.call_args[0][0]
        self.assertIn('board', call_args.lower())
    
    @patch('ai_assistant.utils.gemini_api_call')
    def test_handle_api_error(self, mock_gemini):
        """Test handling of API errors"""
        mock_gemini.side_effect = Exception('API Error')
        
        response = generate_ai_response(
            session=self.session,
            prompt='Test prompt'
        )
        
        self.assertIn('error', response.lower())
    
    @patch('ai_assistant.utils.gemini_api_call')
    def test_token_usage_tracking(self, mock_gemini):
        """Test token usage is tracked"""
        mock_gemini.return_value = {
            'response': 'Response',
            'tokens_used': 300
        }
        
        initial_tokens = self.session.total_tokens_used
        
        generate_ai_response(
            session=self.session,
            prompt='Test prompt'
        )
        
        self.session.refresh_from_db()
        self.assertEqual(
            self.session.total_tokens_used,
            initial_tokens + 300
        )


class WebSearchIntegrationTests(TestCase):
    """Test web search integration (mocked)"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        UserPreference.objects.create(
            user=self.user,
            enable_web_search=True
        )
    
    @patch('ai_assistant.utils.web_search_api')
    def test_web_search_enabled(self, mock_search):
        """Test web search when enabled"""
        mock_search.return_value = [
            {
                'title': 'Django Documentation',
                'url': 'https://docs.djangoproject.com',
                'snippet': 'Django is a Python web framework...'
            }
        ]
        
        from ai_assistant.utils import perform_web_search
        results = perform_web_search('Django best practices')
        
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]['title'], 'Django Documentation')
    
    @patch('ai_assistant.utils.web_search_api')
    def test_web_search_disabled(self, mock_search):
        """Test web search respects user preferences"""
        pref = UserPreference.objects.get(user=self.user)
        pref.enable_web_search = False
        pref.save()
        
        from ai_assistant.utils import perform_web_search
        results = perform_web_search('query', user=self.user)
        
        self.assertEqual(len(results), 0)
        mock_search.assert_not_called()


class AIAnalyticsTests(TestCase):
    """Test AI analytics calculations"""
    
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
    
    def test_analytics_calculation(self):
        """Test analytics metrics calculation"""
        analytics = AIAssistantAnalytics.objects.create(
            user=self.user,
            board=self.board,
            sessions_created=10,
            messages_sent=100,
            gemini_requests=80,
            helpful_responses=70,
            unhelpful_responses=10
        )
        
        # Calculate success rate
        success_rate = (analytics.helpful_responses / 
                       (analytics.helpful_responses + analytics.unhelpful_responses)) * 100
        
        self.assertEqual(success_rate, 87.5)
    
    def test_analytics_aggregation(self):
        """Test aggregating analytics over time"""
        # Create multiple analytics entries
        for i in range(5):
            AIAssistantAnalytics.objects.create(
                user=self.user,
                board=self.board,
                sessions_created=2,
                messages_sent=20,
                date=timezone.now().date()
            )
        
        # Aggregate totals
        total_sessions = AIAssistantAnalytics.objects.filter(
            user=self.user
        ).aggregate(total=models.Sum('sessions_created'))['total']
        
        self.assertEqual(total_sessions, 10)


class TaskRecommendationGenerationTests(TestCase):
    """Test AI task recommendation generation"""
    
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
            weekly_capacity_hours=40,
            current_workload_hours=35,
            skills=[{'name': 'Python', 'level': 'Intermediate'}]
        )
    
    def test_generate_skill_improvement_recommendation(self):
        """Test generating skill improvement recommendations"""
        from ai_assistant.utils import generate_recommendations
        
        recommendations = generate_recommendations(self.user)
        
        # Should recommend skill improvements
        skill_recs = [r for r in recommendations if r.recommendation_type == 'skill_match']
        self.assertGreater(len(skill_recs), 0)
    
    def test_generate_workload_recommendation(self):
        """Test generating workload recommendations"""
        # User is overloaded
        profile = UserProfile.objects.get(user=self.user)
        profile.current_workload_hours = 50
        profile.save()
        
        from ai_assistant.utils import generate_recommendations
        
        recommendations = generate_recommendations(self.user)
        
        # Should recommend workload reduction
        workload_recs = [r for r in recommendations if r.recommendation_type == 'workload']
        self.assertGreater(len(workload_recs), 0)
