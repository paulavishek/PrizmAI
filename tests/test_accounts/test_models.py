"""
Tests for Accounts App Models
==============================

Tests coverage:
- Organization model
- UserProfile model
- User-Organization relationships
- Profile properties and methods
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from accounts.models import Organization, UserProfile


class OrganizationModelTests(TestCase):
    """Test Organization model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_organization_creation(self):
        """Test creating an organization"""
        org = Organization.objects.create(
            name='Test Corp',
            domain='testcorp.com',
            created_by=self.user
        )
        self.assertEqual(org.name, 'Test Corp')
        self.assertEqual(org.domain, 'testcorp.com')
        self.assertEqual(org.created_by, self.user)
    
    def test_organization_string_representation(self):
        """Test organization __str__ method"""
        org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
        self.assertEqual(str(org), 'Test Org')
    
    def test_organization_domain_validation(self):
        """Test domain validation"""
        # Valid domains
        valid_domains = [
            'example.com',
            'sub.example.com',
            'example-company.org',
            'test123.io',
        ]
        for domain in valid_domains:
            org = Organization(
                name='Test',
                domain=domain,
                created_by=self.user
            )
            try:
                org.full_clean()
                self.assertTrue(True)
            except ValidationError:
                self.fail(f"Domain {domain} should be valid")
    
    def test_organization_invalid_domain(self):
        """Test invalid domain rejection"""
        org = Organization(
            name='Test',
            domain='invalid domain.com',
            created_by=self.user
        )
        with self.assertRaises(ValidationError):
            org.full_clean()
    
    def test_organization_timestamp(self):
        """Test created_at timestamp"""
        org = Organization.objects.create(
            name='Test Org',
            domain='test.org',
            created_by=self.user
        )
        self.assertIsNotNone(org.created_at)


class UserProfileModelTests(TestCase):
    """Test UserProfile model"""
    
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
    
    def test_user_profile_creation(self):
        """Test creating a user profile"""
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            is_admin=False
        )
        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.organization, self.org)
        self.assertFalse(profile.is_admin)
    
    def test_profile_admin_flag(self):
        """Test admin flag functionality"""
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            is_admin=True
        )
        self.assertTrue(profile.is_admin)
    
    def test_skills_field(self):
        """Test skills JSON field"""
        skills = [
            {'name': 'Python', 'level': 'Expert'},
            {'name': 'React', 'level': 'Intermediate'},
        ]
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            skills=skills
        )
        self.assertEqual(profile.skills, skills)
    
    def test_weekly_capacity_hours(self):
        """Test weekly capacity hours"""
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            weekly_capacity_hours=40
        )
        self.assertEqual(profile.weekly_capacity_hours, 40)
    
    def test_utilization_percentage_calculation(self):
        """Test utilization percentage property"""
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            weekly_capacity_hours=40,
            current_workload_hours=20
        )
        self.assertEqual(profile.utilization_percentage, 50.0)
    
    def test_utilization_percentage_over_capacity(self):
        """Test utilization capping at 100%"""
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            weekly_capacity_hours=40,
            current_workload_hours=50
        )
        self.assertEqual(profile.utilization_percentage, 100)
    
    def test_available_hours_calculation(self):
        """Test available hours property"""
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            weekly_capacity_hours=40,
            current_workload_hours=15
        )
        self.assertEqual(profile.available_hours, 25)
    
    def test_available_hours_negative(self):
        """Test available hours doesn't go negative"""
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            weekly_capacity_hours=40,
            current_workload_hours=50
        )
        self.assertEqual(profile.available_hours, 0)
    
    def test_skill_names_property(self):
        """Test skill_names property"""
        skills = [
            {'name': 'Python', 'level': 'Expert'},
            {'name': 'JavaScript', 'level': 'Intermediate'},
        ]
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            skills=skills
        )
        self.assertEqual(profile.skill_names, ['Python', 'JavaScript'])
    
    def test_expert_skills_property(self):
        """Test expert_skills property"""
        skills = [
            {'name': 'Python', 'level': 'Expert'},
            {'name': 'JavaScript', 'level': 'Intermediate'},
            {'name': 'React', 'level': 'Expert'},
        ]
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            skills=skills
        )
        self.assertEqual(set(profile.expert_skills), {'Python', 'React'})
    
    def test_quality_score_defaults(self):
        """Test quality score default value"""
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org
        )
        self.assertEqual(profile.quality_score, 100)
    
    def test_collaboration_score_defaults(self):
        """Test collaboration score default value"""
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org
        )
        self.assertEqual(profile.collaboration_score, 100)
    
    def test_productivity_trend_default(self):
        """Test productivity trend default"""
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org
        )
        self.assertEqual(profile.productivity_trend, 'stable')
    
    def test_availability_schedule(self):
        """Test availability schedule JSON field"""
        schedule = {
            'monday': {'start': '09:00', 'end': '17:00'},
            'friday': {'start': '09:00', 'end': '17:00'},
        }
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            availability_schedule=schedule
        )
        self.assertEqual(profile.availability_schedule, schedule)
    
    def test_profile_string_representation(self):
        """Test profile __str__ method"""
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org
        )
        self.assertEqual(str(profile), f"{self.user.username}'s Profile")
    
    def test_wizard_completion(self):
        """Test getting started wizard completion tracking"""
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            completed_wizard=False
        )
        self.assertFalse(profile.completed_wizard)
        
        profile.completed_wizard = True
        profile.save()
        
        profile.refresh_from_db()
        self.assertTrue(profile.completed_wizard)
    
    def test_resource_risk_factors(self):
        """Test resource risk factors field"""
        risk_factors = [
            'High current workload',
            'Skill mismatch for assigned tasks'
        ]
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org,
            resource_risk_factors=risk_factors
        )
        self.assertEqual(profile.resource_risk_factors, risk_factors)
    
    def test_one_to_one_relationship(self):
        """Test OneToOne relationship with User"""
        profile = UserProfile.objects.create(
            user=self.user,
            organization=self.org
        )
        self.assertEqual(self.user.profile, profile)
    
    def test_multiple_users_same_organization(self):
        """Test multiple users can belong to same organization"""
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        
        profile1 = UserProfile.objects.create(
            user=self.user,
            organization=self.org
        )
        profile2 = UserProfile.objects.create(
            user=user2,
            organization=self.org
        )
        
        self.assertEqual(
            self.org.members.count(), 2
        )
