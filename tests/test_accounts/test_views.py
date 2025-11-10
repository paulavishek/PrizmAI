"""
Tests for Accounts App Views
=============================

Tests coverage:
- User profile views
- Organization management views
- User registration and onboarding
- Profile update views
- Team member management
- Permission checks
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from accounts.models import Organization, UserProfile


class ProfileViewTests(TestCase):
    """Test User Profile views"""
    
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
        self.profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            weekly_capacity_hours=40
        )
    
    def test_profile_view_requires_login(self):
        """Test profile view requires authentication"""
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
    
    def test_profile_view_shows_user_info(self):
        """Test profile view displays user information"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('accounts:profile'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.username)
        self.assertContains(response, self.user.email)
    
    def test_profile_update_view_get(self):
        """Test GET request to profile update"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('accounts:profile_update'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Update Profile')
    
    def test_profile_update_view_post(self):
        """Test updating profile information"""
        self.client.login(username='testuser', password='testpass123')
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'weekly_capacity_hours': 35
        }
        response = self.client.post(
            reverse('accounts:profile_update'),
            data
        )
        
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, 'John')
        self.assertEqual(self.profile.weekly_capacity_hours, 35)
    
    def test_profile_skills_update(self):
        """Test updating user skills"""
        self.client.login(username='testuser', password='testpass123')
        skills = [
            {'name': 'Python', 'level': 'Expert'},
            {'name': 'Django', 'level': 'Intermediate'}
        ]
        data = {
            'skills': skills
        }
        response = self.client.post(
            reverse('accounts:skills_update'),
            data,
            content_type='application/json'
        )
        
        self.profile.refresh_from_db()
        self.assertEqual(len(self.profile.skills), 2)
    
    def test_profile_availability_schedule_update(self):
        """Test updating availability schedule"""
        self.client.login(username='testuser', password='testpass123')
        schedule = {
            'monday': {'start': '09:00', 'end': '17:00'},
            'tuesday': {'start': '09:00', 'end': '17:00'}
        }
        data = {
            'availability_schedule': schedule
        }
        response = self.client.post(
            reverse('accounts:availability_update'),
            data,
            content_type='application/json'
        )
        
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.availability_schedule)


class OrganizationViewTests(TestCase):
    """Test Organization views"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.admin_user
        )
        self.admin_profile = UserProfile.objects.create(
            user=self.admin_user,
            organization=self.org,
            is_admin=True
        )
        
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='testpass123'
        )
        self.regular_profile = UserProfile.objects.create(
            user=self.regular_user,
            organization=self.org,
            is_admin=False
        )
    
    def test_organization_detail_view(self):
        """Test organization detail view"""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(
            reverse('accounts:organization_detail', kwargs={'pk': self.org.id})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Org')
    
    def test_organization_update_requires_admin(self):
        """Test only admins can update organization"""
        self.client.login(username='regular', password='testpass123')
        response = self.client.get(
            reverse('accounts:organization_update', kwargs={'pk': self.org.id})
        )
        
        self.assertEqual(response.status_code, 403)
    
    def test_organization_update_view_admin(self):
        """Test admin can update organization"""
        self.client.login(username='admin', password='testpass123')
        data = {
            'name': 'Updated Org Name',
            'domain': 'updated.org'
        }
        response = self.client.post(
            reverse('accounts:organization_update', kwargs={'pk': self.org.id}),
            data
        )
        
        self.org.refresh_from_db()
        self.assertEqual(self.org.name, 'Updated Org Name')
    
    def test_organization_members_list(self):
        """Test organization members list view"""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(
            reverse('accounts:organization_members', kwargs={'pk': self.org.id})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.admin_user.username)
        self.assertContains(response, self.regular_user.username)
    
    def test_add_member_to_organization(self):
        """Test adding member to organization"""
        new_user = User.objects.create_user(
            username='newuser',
            email='newuser@example.com',
            password='testpass123'
        )
        
        self.client.login(username='admin', password='testpass123')
        data = {
            'user_id': new_user.id,
            'is_admin': False
        }
        response = self.client.post(
            reverse('accounts:add_member', kwargs={'pk': self.org.id}),
            data
        )
        
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            UserProfile.objects.filter(
                user=new_user,
                organization=self.org
            ).exists()
        )
    
    def test_remove_member_from_organization(self):
        """Test removing member from organization"""
        self.client.login(username='admin', password='testpass123')
        response = self.client.post(
            reverse('accounts:remove_member', kwargs={
                'pk': self.org.id,
                'user_id': self.regular_user.id
            })
        )
        
        self.assertEqual(response.status_code, 302)
        # Profile should be deactivated or deleted
    
    def test_promote_member_to_admin(self):
        """Test promoting member to admin"""
        self.client.login(username='admin', password='testpass123')
        response = self.client.post(
            reverse('accounts:promote_member', kwargs={
                'pk': self.org.id,
                'user_id': self.regular_user.id
            })
        )
        
        self.regular_profile.refresh_from_db()
        self.assertTrue(self.regular_profile.is_admin)


class UserRegistrationViewTests(TestCase):
    """Test user registration and onboarding"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
    
    def test_registration_view_get(self):
        """Test GET request to registration page"""
        response = self.client.get(reverse('accounts:register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Register')
    
    def test_registration_view_post_success(self):
        """Test successful user registration"""
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!'
        }
        response = self.client.post(reverse('accounts:register'), data)
        
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            User.objects.filter(username='newuser').exists()
        )
    
    def test_registration_view_password_mismatch(self):
        """Test registration with mismatched passwords"""
        data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password1': 'ComplexPass123!',
            'password2': 'DifferentPass456!'
        }
        response = self.client.post(reverse('accounts:register'), data)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'password')
        self.assertFalse(
            User.objects.filter(username='newuser').exists()
        )
    
    def test_registration_duplicate_username(self):
        """Test registration with existing username"""
        User.objects.create_user(
            username='existing',
            email='existing@example.com',
            password='testpass123'
        )
        
        data = {
            'username': 'existing',
            'email': 'new@example.com',
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!'
        }
        response = self.client.post(reverse('accounts:register'), data)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')


class OnboardingWizardViewTests(TestCase):
    """Test onboarding wizard for new users"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='newuser',
            email='newuser@example.com',
            password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            completed_wizard=False
        )
    
    def test_wizard_redirects_incomplete_users(self):
        """Test wizard redirect for users who haven't completed setup"""
        self.client.login(username='newuser', password='testpass123')
        response = self.client.get(reverse('kanban:board_list'))
        
        # Should redirect to wizard if not completed
        if not self.profile.completed_wizard:
            self.assertEqual(response.status_code, 302)
            self.assertIn('wizard', response.url)
    
    def test_wizard_step_1_organization_setup(self):
        """Test wizard step 1: organization setup"""
        self.client.login(username='newuser', password='testpass123')
        data = {
            'organization_name': 'My Company',
            'domain': 'mycompany.com'
        }
        response = self.client.post(
            reverse('accounts:wizard_step1'),
            data
        )
        
        self.assertEqual(response.status_code, 302)
    
    def test_wizard_step_2_profile_setup(self):
        """Test wizard step 2: profile setup"""
        self.client.login(username='newuser', password='testpass123')
        data = {
            'weekly_capacity_hours': 40,
            'skills': [{'name': 'Python', 'level': 'Intermediate'}]
        }
        response = self.client.post(
            reverse('accounts:wizard_step2'),
            data
        )
        
        self.assertEqual(response.status_code, 302)
    
    def test_wizard_completion(self):
        """Test wizard completion marks profile as complete"""
        self.client.login(username='newuser', password='testpass123')
        response = self.client.post(reverse('accounts:wizard_complete'))
        
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.completed_wizard)


class UserSearchViewTests(TestCase):
    """Test user search and filtering"""
    
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
        self.profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org
        )
    
    def test_user_search_by_username(self):
        """Test searching users by username"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('accounts:user_search'),
            {'q': 'test'}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'testuser')
    
    def test_user_search_by_skills(self):
        """Test searching users by skills"""
        self.profile.skills = [
            {'name': 'Python', 'level': 'Expert'}
        ]
        self.profile.save()
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(
            reverse('accounts:user_search'),
            {'skill': 'Python'}
        )
        
        self.assertEqual(response.status_code, 200)
