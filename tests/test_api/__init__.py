"""
Tests for REST API Endpoints
=============================

Tests coverage:
- Serializers for all models
- API viewsets and views
- Filtering and searching
- Pagination
- Authentication and permissions
- Error handling and validation
"""

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from accounts.models import Organization, UserProfile
from kanban.models import Board, Column, Task
from wiki.models import WikiCategory, WikiPage


class BoardAPITests(APITestCase):
    """Test Board API endpoints"""
    
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
            is_admin=True
        )
        self.board = Board.objects.create(
            name='Test Board',
            organization=self.org,
            created_by=self.user
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_list_boards(self):
        """Test listing boards"""
        response = self.client.get('/api/v1/boards/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_board(self):
        """Test creating a board via API"""
        data = {
            'name': 'New Board',
            'description': 'Test board',
            'organization': self.org.id
        }
        response = self.client.post('/api/v1/boards/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_update_board(self):
        """Test updating a board"""
        data = {'name': 'Updated Board'}
        response = self.client.patch(
            f'/api/v1/boards/{self.board.id}/',
            data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_delete_board(self):
        """Test deleting a board"""
        response = self.client.delete(f'/api/v1/boards/{self.board.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class TaskAPITests(APITestCase):
    """Test Task API endpoints"""
    
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
            board=self.board,
            position=0
        )
        self.task = Task.objects.create(
            title='Test Task',
            column=self.column,
            created_by=self.user
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_list_tasks(self):
        """Test listing tasks"""
        response = self.client.get('/api/v1/tasks/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_task(self):
        """Test creating a task via API"""
        data = {
            'title': 'New Task',
            'column': self.column.id,
            'priority': 'high'
        }
        response = self.client.post('/api/v1/tasks/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_task_filtering_by_priority(self):
        """Test filtering tasks by priority"""
        response = self.client.get('/api/v1/tasks/?priority=high')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_task_filtering_by_assignee(self):
        """Test filtering tasks by assignee"""
        response = self.client.get(f'/api/v1/tasks/?assigned_to={self.user.id}')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class WikiPageAPITests(APITestCase):
    """Test Wiki Page API endpoints"""
    
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
        self.category = WikiCategory.objects.create(
            name='Docs',
            slug='docs',
            organization=self.org
        )
        self.page = WikiPage.objects.create(
            title='Test Page',
            slug='test-page',
            content='Content',
            category=self.category,
            organization=self.org,
            created_by=self.user,
            updated_by=self.user
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_list_wiki_pages(self):
        """Test listing wiki pages"""
        response = self.client.get('/api/v1/wiki/pages/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_wiki_page(self):
        """Test creating a wiki page"""
        data = {
            'title': 'New Page',
            'content': 'Page content',
            'category': self.category.id,
            'organization': self.org.id
        }
        response = self.client.post('/api/v1/wiki/pages/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_search_wiki_pages(self):
        """Test searching wiki pages"""
        response = self.client.get('/api/v1/wiki/pages/?search=test')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class APIAuthenticationTests(APITestCase):
    """Test API authentication"""
    
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
        self.client = APIClient()
    
    def test_unauthenticated_access_denied(self):
        """Test unauthenticated requests are denied"""
        response = self.client.get('/api/v1/boards/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_authenticated_access_allowed(self):
        """Test authenticated access is allowed"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/v1/boards/')
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_404_NOT_FOUND
        ])


class APIPaginationTests(APITestCase):
    """Test API pagination"""
    
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
        
        # Create multiple boards
        for i in range(15):
            Board.objects.create(
                name=f'Board {i}',
                organization=self.org,
                created_by=self.user
            )
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_pagination_default_page_size(self):
        """Test default page size"""
        response = self.client.get('/api/v1/boards/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
    
    def test_pagination_custom_page_size(self):
        """Test custom page size"""
        response = self.client.get('/api/v1/boards/?page_size=5')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_pagination_page_navigation(self):
        """Test navigating pages"""
        response1 = self.client.get('/api/v1/boards/?page=1')
        response2 = self.client.get('/api/v1/boards/?page=2')
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)


class APIErrorHandlingTests(APITestCase):
    """Test API error handling"""
    
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
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_404_not_found(self):
        """Test 404 error for non-existent resource"""
        response = self.client.get('/api/v1/boards/99999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_validation_error(self):
        """Test validation errors"""
        data = {'name': ''}  # Empty name
        response = self.client.post('/api/v1/boards/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_permission_denied(self):
        """Test permission denied errors"""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )
        other_org = Organization.objects.create(
            name='Other Org',
            domain='other.org',
            created_by=other_user
        )
        UserProfile.objects.create(
            user=other_user,
            organization=other_org
        )
        other_board = Board.objects.create(
            name='Other Board',
            organization=other_org,
            created_by=other_user
        )
        
        response = self.client.patch(
            f'/api/v1/boards/{other_board.id}/',
            {'name': 'Hacked'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
