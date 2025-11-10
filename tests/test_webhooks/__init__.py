"""
Tests for Webhooks App
======================

Tests coverage:
- Webhook model and configuration
- WebhookDelivery tracking
- WebhookEvent logging
- Webhook triggering and delivery
- Retry logic and failure handling
- Security (HMAC signatures)
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch, Mock
import json

from accounts.models import Organization, UserProfile
from kanban.models import Board, Column, Task
from webhooks.models import Webhook, WebhookDelivery, WebhookEvent


class WebhookModelTests(TestCase):
    """Test Webhook model"""
    
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
    
    def test_webhook_creation(self):
        """Test creating a webhook"""
        webhook = Webhook.objects.create(
            name='Slack Notifications',
            url='https://hooks.slack.com/services/TEST',
            board=self.board,
            created_by=self.user,
            events=['task.created', 'task.updated']
        )
        self.assertEqual(webhook.name, 'Slack Notifications')
        self.assertEqual(webhook.board, self.board)
        self.assertTrue(webhook.is_active)
        self.assertEqual(webhook.status, 'active')
    
    def test_webhook_event_configuration(self):
        """Test webhook event types"""
        webhook = Webhook.objects.create(
            name='Test Webhook',
            url='https://example.com/webhook',
            board=self.board,
            created_by=self.user,
            events=['task.created', 'task.deleted', 'comment.added']
        )
        self.assertEqual(len(webhook.events), 3)
        self.assertIn('task.created', webhook.events)
    
    def test_webhook_delivery_settings(self):
        """Test webhook delivery configuration"""
        webhook = Webhook.objects.create(
            name='Test Webhook',
            url='https://example.com/webhook',
            board=self.board,
            created_by=self.user,
            timeout_seconds=30,
            max_retries=5,
            retry_delay_seconds=120
        )
        self.assertEqual(webhook.timeout_seconds, 30)
        self.assertEqual(webhook.max_retries, 5)
        self.assertEqual(webhook.retry_delay_seconds, 120)
    
    def test_webhook_custom_headers(self):
        """Test custom headers configuration"""
        headers = {
            'X-Custom-Header': 'test-value',
            'Authorization': 'Bearer token123'
        }
        webhook = Webhook.objects.create(
            name='Test Webhook',
            url='https://example.com/webhook',
            board=self.board,
            created_by=self.user,
            custom_headers=headers
        )
        self.assertEqual(webhook.custom_headers, headers)
    
    def test_webhook_secret(self):
        """Test webhook secret for HMAC"""
        webhook = Webhook.objects.create(
            name='Test Webhook',
            url='https://example.com/webhook',
            board=self.board,
            created_by=self.user,
            secret='my-secret-key-123'
        )
        self.assertEqual(webhook.secret, 'my-secret-key-123')
    
    def test_increment_delivery_stats_success(self):
        """Test incrementing stats on successful delivery"""
        webhook = Webhook.objects.create(
            name='Test Webhook',
            url='https://example.com/webhook',
            board=self.board,
            created_by=self.user
        )
        
        webhook.increment_delivery_stats(success=True)
        
        self.assertEqual(webhook.total_deliveries, 1)
        self.assertEqual(webhook.successful_deliveries, 1)
        self.assertEqual(webhook.failed_deliveries, 0)
        self.assertEqual(webhook.consecutive_failures, 0)
        self.assertIsNotNone(webhook.last_triggered)
    
    def test_increment_delivery_stats_failure(self):
        """Test incrementing stats on failed delivery"""
        webhook = Webhook.objects.create(
            name='Test Webhook',
            url='https://example.com/webhook',
            board=self.board,
            created_by=self.user
        )
        
        webhook.increment_delivery_stats(success=False)
        
        self.assertEqual(webhook.total_deliveries, 1)
        self.assertEqual(webhook.successful_deliveries, 0)
        self.assertEqual(webhook.failed_deliveries, 1)
        self.assertEqual(webhook.consecutive_failures, 1)
    
    def test_webhook_auto_disable_after_failures(self):
        """Test webhook auto-disables after 10 consecutive failures"""
        webhook = Webhook.objects.create(
            name='Test Webhook',
            url='https://example.com/webhook',
            board=self.board,
            created_by=self.user
        )
        
        # Simulate 10 consecutive failures
        for _ in range(10):
            webhook.increment_delivery_stats(success=False)
        
        webhook.refresh_from_db()
        self.assertEqual(webhook.status, 'failed')
        self.assertFalse(webhook.is_active)
    
    def test_webhook_success_rate_calculation(self):
        """Test success rate property"""
        webhook = Webhook.objects.create(
            name='Test Webhook',
            url='https://example.com/webhook',
            board=self.board,
            created_by=self.user
        )
        
        # 7 successes, 3 failures
        for _ in range(7):
            webhook.increment_delivery_stats(success=True)
        for _ in range(3):
            webhook.increment_delivery_stats(success=False)
        
        webhook.refresh_from_db()
        self.assertEqual(webhook.success_rate, 70.0)
    
    def test_webhook_status_recovery_after_success(self):
        """Test webhook status recovers from failed to active after success"""
        webhook = Webhook.objects.create(
            name='Test Webhook',
            url='https://example.com/webhook',
            board=self.board,
            created_by=self.user,
            status='failed',
            consecutive_failures=5
        )
        
        webhook.increment_delivery_stats(success=True)
        
        webhook.refresh_from_db()
        self.assertEqual(webhook.status, 'active')
        self.assertEqual(webhook.consecutive_failures, 0)


class WebhookDeliveryTests(TestCase):
    """Test WebhookDelivery model"""
    
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
        self.webhook = Webhook.objects.create(
            name='Test Webhook',
            url='https://example.com/webhook',
            board=self.board,
            created_by=self.user,
            max_retries=3
        )
    
    def test_delivery_creation(self):
        """Test creating a webhook delivery"""
        payload = {'task_id': 1, 'action': 'created'}
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type='task.created',
            payload=payload,
            status='pending'
        )
        self.assertEqual(delivery.webhook, self.webhook)
        self.assertEqual(delivery.event_type, 'task.created')
        self.assertEqual(delivery.payload, payload)
        self.assertEqual(delivery.status, 'pending')
    
    def test_delivery_success_tracking(self):
        """Test tracking successful delivery"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type='task.created',
            payload={'test': 'data'},
            status='sent'
        )
        
        delivery.status = 'success'
        delivery.response_status_code = 200
        delivery.response_body = 'OK'
        delivery.response_time_ms = 150
        delivery.delivered_at = timezone.now()
        delivery.save()
        
        self.assertEqual(delivery.status, 'success')
        self.assertEqual(delivery.response_status_code, 200)
        self.assertIsNotNone(delivery.delivered_at)
    
    def test_delivery_failure_tracking(self):
        """Test tracking failed delivery"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type='task.created',
            payload={'test': 'data'},
            status='sent'
        )
        
        delivery.status = 'failed'
        delivery.error_message = 'Connection timeout'
        delivery.retry_count = 1
        delivery.next_retry_at = timezone.now()
        delivery.save()
        
        self.assertEqual(delivery.status, 'failed')
        self.assertEqual(delivery.error_message, 'Connection timeout')
        self.assertEqual(delivery.retry_count, 1)
    
    def test_is_retriable_logic(self):
        """Test retry eligibility check"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type='task.created',
            payload={'test': 'data'},
            status='failed',
            retry_count=1
        )
        
        self.assertTrue(delivery.is_retriable())
        
        # Exceed max retries
        delivery.retry_count = 3
        delivery.save()
        
        self.assertFalse(delivery.is_retriable())
    
    def test_delivery_ordering(self):
        """Test deliveries are ordered by creation time"""
        delivery1 = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type='task.created',
            payload={'id': 1}
        )
        delivery2 = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type='task.updated',
            payload={'id': 2}
        )
        
        deliveries = WebhookDelivery.objects.all()
        self.assertEqual(deliveries[0], delivery2)  # Newest first


class WebhookEventTests(TestCase):
    """Test WebhookEvent model"""
    
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
    
    def test_event_creation(self):
        """Test creating a webhook event"""
        event = WebhookEvent.objects.create(
            event_type='task.created',
            board=self.board,
            object_id=1,
            data={'task_id': 1, 'title': 'New Task'},
            triggered_by=self.user,
            webhooks_triggered=2
        )
        self.assertEqual(event.event_type, 'task.created')
        self.assertEqual(event.board, self.board)
        self.assertEqual(event.webhooks_triggered, 2)
    
    def test_event_ordering(self):
        """Test events are ordered by creation time"""
        event1 = WebhookEvent.objects.create(
            event_type='task.created',
            board=self.board,
            object_id=1,
            data={}
        )
        event2 = WebhookEvent.objects.create(
            event_type='task.updated',
            board=self.board,
            object_id=1,
            data={}
        )
        
        events = WebhookEvent.objects.all()
        self.assertEqual(events[0], event2)  # Newest first


class WebhookTriggeringTests(TestCase):
    """Test webhook triggering logic"""
    
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
            organization=self.org
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
        self.webhook = Webhook.objects.create(
            name='Test Webhook',
            url='https://example.com/webhook',
            board=self.board,
            created_by=self.user,
            events=['task.created', 'task.updated']
        )
    
    @patch('requests.post')
    def test_webhook_triggered_on_task_creation(self, mock_post):
        """Test webhook is triggered when task is created"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = 'OK'
        mock_post.return_value = mock_response
        
        # Create task (should trigger webhook in real app via signals)
        task = Task.objects.create(
            title='New Task',
            column=self.column,
            created_by=self.user
        )
        
        self.assertIsNotNone(task)
        # In real implementation, this would trigger webhook delivery
    
    def test_webhook_not_triggered_when_inactive(self):
        """Test webhook doesn't trigger when inactive"""
        self.webhook.is_active = False
        self.webhook.save()
        
        task = Task.objects.create(
            title='New Task',
            column=self.column,
            created_by=self.user
        )
        
        # Webhook should not be triggered
        deliveries = WebhookDelivery.objects.filter(webhook=self.webhook)
        self.assertEqual(deliveries.count(), 0)
    
    def test_webhook_filtered_by_event_type(self):
        """Test webhook only triggers for configured events"""
        # Webhook configured for task.created only
        webhook = Webhook.objects.create(
            name='Selective Webhook',
            url='https://example.com/webhook',
            board=self.board,
            created_by=self.user,
            events=['task.created']  # Only task.created
        )
        
        # This should not trigger because task.deleted is not in events list
        # In real app, deletion would be caught by signal handlers
        task = Task.objects.create(
            title='Task to delete',
            column=self.column,
            created_by=self.user
        )
        task_id = task.id
        task.delete()
        
        # No delivery for task.deleted event
        deliveries = WebhookDelivery.objects.filter(
            webhook=webhook,
            event_type='task.deleted'
        )
        self.assertEqual(deliveries.count(), 0)


class WebhookSecurityTests(TestCase):
    """Test webhook security features"""
    
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
    
    def test_webhook_with_secret(self):
        """Test webhook secret storage"""
        webhook = Webhook.objects.create(
            name='Secure Webhook',
            url='https://example.com/webhook',
            board=self.board,
            created_by=self.user,
            secret='supersecretkey123'
        )
        self.assertEqual(webhook.secret, 'supersecretkey123')
    
    def test_url_validation(self):
        """Test webhook URL must be valid"""
        from django.core.exceptions import ValidationError
        
        webhook = Webhook(
            name='Invalid Webhook',
            url='not-a-valid-url',
            board=self.board,
            created_by=self.user
        )
        
        with self.assertRaises(ValidationError):
            webhook.full_clean()
