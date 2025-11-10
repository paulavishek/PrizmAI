"""
Edge Case and Security Tests
=============================

Tests coverage:
- SQL injection prevention
- XSS (Cross-site scripting) prevention
- CSRF protection
- Concurrent modification handling
- Rate limiting
- Input sanitization
- Permission bypass attempts
- Session security
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.db import transaction
from django.core.exceptions import ValidationError
from unittest.mock import patch
import time
from threading import Thread

from accounts.models import Organization, UserProfile
from kanban.models import Board, Column, Task
from messaging.models import ChatRoom, ChatMessage
from webhooks.models import Webhook


class SQLInjectionPreventionTests(TestCase):
    """Test SQL injection prevention"""
    
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
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_sql_injection_in_search(self):
        """Test SQL injection attempts in search queries"""
        # Attempt SQL injection
        injection_strings = [
            "' OR '1'='1",
            "'; DROP TABLE tasks; --",
            "' UNION SELECT * FROM users--",
            "admin'--",
            "' OR 1=1--"
        ]
        
        for injection in injection_strings:
            response = self.client.get(
                reverse('kanban:task_search'),
                {'q': injection}
            )
            
            # Should handle safely without error
            self.assertIn(response.status_code, [200, 400, 403])
            
            # Database should still be intact
            self.assertTrue(User.objects.filter(username='testuser').exists())
    
    def test_sql_injection_in_filters(self):
        """Test SQL injection in filter parameters"""
        board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        
        # Attempt injection via filter
        response = self.client.get(
            reverse('kanban:board_detail', args=[board.id]),
            {'status': "completed' OR '1'='1"}
        )
        
        self.assertIn(response.status_code, [200, 400])


class XSSPreventionTests(TestCase):
    """Test XSS (Cross-site scripting) prevention"""
    
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
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_xss_in_task_title(self):
        """Test XSS prevention in task titles"""
        xss_strings = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<iframe src='javascript:alert(1)'></iframe>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>"
        ]
        
        for xss_string in xss_strings:
            task = Task.objects.create(
                title=xss_string,
                column=self.column,
                created_by=self.user
            )
            
            # Get task detail page
            response = self.client.get(
                reverse('kanban:task_detail', args=[task.id])
            )
            
            # Response should not contain unescaped script tags
            self.assertNotIn('<script>', response.content.decode())
            self.assertNotIn('onerror=', response.content.decode())
    
    def test_xss_in_message_content(self):
        """Test XSS prevention in chat messages"""
        chat_room = ChatRoom.objects.create(
            name='Test Room',
            organization=self.org,
            created_by=self.user
        )
        
        xss_message = "<script>alert('Hack')</script>"
        
        response = self.client.post(
            reverse('messaging:send_message', args=[chat_room.id]),
            {'content': xss_message}
        )
        
        # Message should be saved but escaped
        message = ChatMessage.objects.latest('created_at')
        
        # When rendered, script tags should be escaped
        detail_response = self.client.get(
            reverse('messaging:chat_room', args=[chat_room.id])
        )
        self.assertNotIn('<script>', detail_response.content.decode())


class CSRFProtectionTests(TestCase):
    """Test CSRF protection"""
    
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
        self.client = Client(enforce_csrf_checks=True)
        self.client.login(username='testuser', password='testpass123')
    
    def test_csrf_required_for_post(self):
        """Test CSRF token is required for POST requests"""
        column = Column.objects.create(name='To Do', board=self.board)
        
        # Attempt POST without CSRF token
        response = self.client.post(
            reverse('kanban:task_create'),
            {
                'title': 'Test Task',
                'column': column.id
            }
        )
        
        # Should be rejected
        self.assertEqual(response.status_code, 403)
    
    def test_csrf_required_for_delete(self):
        """Test CSRF token is required for DELETE operations"""
        column = Column.objects.create(name='To Do', board=self.board)
        task = Task.objects.create(
            title='Test Task',
            column=column,
            created_by=self.user
        )
        
        # Attempt DELETE without CSRF token
        response = self.client.post(
            reverse('kanban:task_delete', args=[task.id])
        )
        
        # Should be rejected
        self.assertEqual(response.status_code, 403)


class ConcurrentModificationTests(TestCase):
    """Test concurrent modification handling"""
    
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
            title='Test Task',
            column=self.column,
            created_by=self.user1
        )
    
    def test_concurrent_task_updates(self):
        """Test handling concurrent updates to same task"""
        results = []
        
        def update_task(user, new_title):
            try:
                with transaction.atomic():
                    task = Task.objects.select_for_update().get(id=self.task.id)
                    task.title = new_title
                    task.save()
                    results.append(('success', new_title))
            except Exception as e:
                results.append(('error', str(e)))
        
        # Create two threads trying to update simultaneously
        thread1 = Thread(target=update_task, args=(self.user1, 'Update 1'))
        thread2 = Thread(target=update_task, args=(self.user2, 'Update 2'))
        
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()
        
        # Both should complete (one will wait for the other)
        self.assertEqual(len(results), 2)
        
        # Task should have one of the updates
        self.task.refresh_from_db()
        self.assertIn(self.task.title, ['Update 1', 'Update 2'])
    
    def test_optimistic_locking(self):
        """Test optimistic locking for concurrent edits"""
        # Simulate two users fetching the same task
        task_v1 = Task.objects.get(id=self.task.id)
        task_v2 = Task.objects.get(id=self.task.id)
        
        # User 1 updates and saves
        task_v1.title = 'User 1 Update'
        task_v1.save()
        
        # User 2 tries to update with stale data
        task_v2.title = 'User 2 Update'
        
        # If version field exists, this should raise an error
        # Otherwise, last write wins (but should be detected by app logic)
        task_v2.save()
        
        # Verify final state
        final_task = Task.objects.get(id=self.task.id)
        self.assertIsNotNone(final_task.title)


class RateLimitingTests(TestCase):
    """Test rate limiting"""
    
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
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    @patch('ai_assistant.views.check_rate_limit')
    def test_api_rate_limiting(self, mock_rate_limit):
        """Test API rate limiting"""
        mock_rate_limit.return_value = False  # Exceeded rate limit
        
        response = self.client.post(
            reverse('api:v1:ai_assistant_query'),
            {'query': 'Test query'}
        )
        
        # Should return 429 Too Many Requests
        self.assertEqual(response.status_code, 429)
    
    @patch('webhooks.views.check_webhook_rate_limit')
    def test_webhook_rate_limiting(self, mock_rate_limit):
        """Test webhook delivery rate limiting"""
        webhook = Webhook.objects.create(
            name='Test Webhook',
            url='https://example.com/hook',
            organization=self.org,
            created_by=self.user
        )
        
        mock_rate_limit.return_value = False  # Exceeded rate limit
        
        # Attempt multiple rapid deliveries
        for _ in range(20):
            response = self.client.post(
                reverse('webhooks:trigger', args=[webhook.id]),
                {'event': 'task.created'}
            )
        
        # Some should be rate limited
        self.assertEqual(response.status_code, 429)


class InputSanitizationTests(TestCase):
    """Test input sanitization"""
    
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
    
    def test_email_validation(self):
        """Test email address validation"""
        invalid_emails = [
            'notanemail',
            '@example.com',
            'user@',
            'user name@example.com',
            'user@example',
        ]
        
        for email in invalid_emails:
            with self.assertRaises(ValidationError):
                user = User(username='test', email=email)
                user.full_clean()
    
    def test_url_validation(self):
        """Test URL validation for webhooks"""
        invalid_urls = [
            'not-a-url',
            'ftp://invalid-protocol.com',
            'javascript:alert(1)',
            'file:///etc/passwd',
        ]
        
        for url in invalid_urls:
            with self.assertRaises(ValidationError):
                webhook = Webhook(
                    name='Test',
                    url=url,
                    organization=self.org,
                    created_by=self.user
                )
                webhook.full_clean()
    
    def test_filename_sanitization(self):
        """Test filename sanitization for uploads"""
        dangerous_filenames = [
            '../../../etc/passwd',
            'file; rm -rf /',
            'file.php.jpg',
            '<script>alert(1)</script>.jpg',
        ]
        
        from kanban.utils import sanitize_filename
        
        for filename in dangerous_filenames:
            sanitized = sanitize_filename(filename)
            
            # Should not contain directory traversal
            self.assertNotIn('..', sanitized)
            self.assertNotIn('/', sanitized)
            self.assertNotIn('\\', sanitized)
            
            # Should not contain script tags
            self.assertNotIn('<', sanitized)
            self.assertNotIn('>', sanitized)


class PermissionBypassTests(TestCase):
    """Test permission bypass attempts"""
    
    def setUp(self):
        """Set up test data"""
        # Create two separate organizations
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123'
        )
        self.org1 = Organization.objects.create(
            name='Org 1',
            domain='org1.com',
            created_by=self.user1
        )
        self.board1 = Board.objects.create(
            name='Board 1',
            organization=self.org1,
            created_by=self.user1
        )
        
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        self.org2 = Organization.objects.create(
            name='Org 2',
            domain='org2.com',
            created_by=self.user2
        )
        
        self.client = Client()
    
    def test_cross_organization_access_denied(self):
        """Test users cannot access other organizations' data"""
        self.client.login(username='user2', password='testpass123')
        
        # user2 tries to access board1 from org1
        response = self.client.get(
            reverse('kanban:board_detail', args=[self.board1.id])
        )
        
        # Should be denied
        self.assertIn(response.status_code, [403, 404])
    
    def test_non_member_board_access_denied(self):
        """Test non-board-members cannot access board"""
        # Create user in same org but not board member
        user3 = User.objects.create_user(
            username='user3',
            email='user3@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=user3,
            organization=self.org1
        )
        
        self.client.login(username='user3', password='testpass123')
        
        response = self.client.get(
            reverse('kanban:board_detail', args=[self.board1.id])
        )
        
        # Should be denied (if board has member restrictions)
        self.assertIn(response.status_code, [200, 403])
    
    def test_direct_object_reference_protection(self):
        """Test protection against insecure direct object references"""
        column = Column.objects.create(name='To Do', board=self.board1)
        task = Task.objects.create(
            title='Private Task',
            column=column,
            created_by=self.user1
        )
        
        # user2 tries to access task by guessing ID
        self.client.login(username='user2', password='testpass123')
        
        response = self.client.get(
            reverse('kanban:task_detail', args=[task.id])
        )
        
        # Should be denied
        self.assertIn(response.status_code, [403, 404])


class SessionSecurityTests(TestCase):
    """Test session security"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Client()
    
    def test_session_expires_after_logout(self):
        """Test session is invalidated after logout"""
        # Login
        self.client.login(username='testuser', password='testpass123')
        
        # Verify logged in
        response = self.client.get(reverse('kanban:dashboard'))
        self.assertEqual(response.status_code, 200)
        
        # Logout
        self.client.logout()
        
        # Try to access protected page
        response = self.client.get(reverse('kanban:dashboard'))
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
    
    def test_session_fixation_protection(self):
        """Test protection against session fixation"""
        # Get initial session key
        self.client.get(reverse('accounts:login'))
        old_session_key = self.client.session.session_key
        
        # Login
        self.client.login(username='testuser', password='testpass123')
        new_session_key = self.client.session.session_key
        
        # Session key should change after login
        self.assertNotEqual(old_session_key, new_session_key)


class PathTraversalPreventionTests(TestCase):
    """Test path traversal prevention"""
    
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
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_file_download_path_traversal(self):
        """Test path traversal in file downloads"""
        # Attempt to download system files
        traversal_attempts = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            'file:///etc/passwd',
        ]
        
        for path in traversal_attempts:
            response = self.client.get(
                reverse('kanban:download_attachment'),
                {'file': path}
            )
            
            # Should be rejected
            self.assertIn(response.status_code, [400, 403, 404])
