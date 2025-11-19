"""
Tests for Priority Suggestion Feature
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from kanban.models import Board, Column, Task
from kanban.priority_models import PriorityDecision, PriorityModel
from ai_assistant.utils.priority_service import PrioritySuggestionService, PriorityModelTrainer
from accounts.models import Organization, UserProfile


class PrioritySuggestionServiceTest(TestCase):
    def setUp(self):
        # Create organization
        self.org = Organization.objects.create(name='Test Org')
        
        # Create users
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.profile = UserProfile.objects.create(user=self.user, organization=self.org)
        
        # Create board
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        self.board.members.add(self.user)
        
        # Create column
        self.column = Column.objects.create(
            name='To Do',
            board=self.board,
            position=0
        )
        
        self.service = PrioritySuggestionService()
    
    def test_rule_based_suggestion_urgent(self):
        """Test rule-based suggestion for urgent task"""
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
    
    def test_feature_extraction(self):
        """Test feature extraction from task"""
        task = Task.objects.create(
            title='Test Task',
            description='Test description',
            column=self.column,
            created_by=self.user,
            due_date=timezone.now() + timedelta(days=3),
            complexity_score=6,
            collaboration_required=True
        )
        
        features = self.service._extract_features(task)
        
        self.assertEqual(len(features), 14)  # Should have 14 features
        self.assertIsInstance(features[0], (int, float))  # days_until_due


class PriorityDecisionTest(TestCase):
    def setUp(self):
        # Create organization
        self.org = Organization.objects.create(name='Test Org')
        
        # Create users
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.profile = UserProfile.objects.create(user=self.user, organization=self.org)
        
        # Create board
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        
        # Create column
        self.column = Column.objects.create(
            name='To Do',
            board=self.board,
            position=0
        )
        
        # Create task
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


class PriorityAPITest(TestCase):
    def setUp(self):
        # Create organization
        self.org = Organization.objects.create(name='Test Org')
        
        # Create users
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.profile = UserProfile.objects.create(user=self.user, organization=self.org)
        
        # Create board
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        self.board.members.add(self.user)
        
        # Create column
        self.column = Column.objects.create(
            name='To Do',
            board=self.board,
            position=0
        )
        
        self.client = Client()
        self.client.login(username='testuser', password='12345')
    
    def test_suggest_priority_api_new_task(self):
        """Test priority suggestion API for new task"""
        response = self.client.post(
            '/api/suggest-priority/',
            data={
                'board_id': self.board.id,
                'title': 'New Task',
                'complexity_score': 7,
                'due_date': (timezone.now() + timedelta(days=2)).isoformat()
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('suggested_priority', data)
        self.assertIn('confidence', data)
        self.assertIn('reasoning', data)
    
    def test_log_priority_decision_api(self):
        """Test logging priority decision via API"""
        task = Task.objects.create(
            title='Test Task',
            column=self.column,
            created_by=self.user,
            priority='medium'
        )
        
        response = self.client.post(
            '/api/log-priority-decision/',
            data={
                'task_id': task.id,
                'priority': 'high',
                'decision_type': 'correction',
                'suggested_priority': 'medium',
                'confidence': 0.75
            },
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertTrue(data['success'])
        
        # Verify decision was logged
        decisions = PriorityDecision.objects.filter(task=task)
        self.assertEqual(decisions.count(), 1)
        self.assertEqual(decisions.first().actual_priority, 'high')
    
    def test_get_priority_model_info_api(self):
        """Test getting priority model info"""
        response = self.client.get(f'/api/board/{self.board.id}/priority-model-info/')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('has_model', data)
        self.assertFalse(data['has_model'])  # No model trained yet
        self.assertIn('decision_count', data)
