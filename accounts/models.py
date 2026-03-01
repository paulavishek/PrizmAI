from django.db import models
from django.contrib.auth.models import User
from django.core.validators import EmailValidator, RegexValidator

class Organization(models.Model):
    name = models.CharField(max_length=100)
    domain = models.CharField(
        max_length=100, 
        validators=[
            RegexValidator(
                regex=r'^[a-zA-Z0-9]+([\-\.]{1}[a-zA-Z0-9]+)*\.[a-zA-Z]{2,}$',
                message='Enter a valid domain (e.g., example.com)'
            )
        ],
        help_text="Domain used for email validation (e.g., example.com)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_organizations')
    
    # Demo Mode Support
    is_demo = models.BooleanField(
        default=False,
        help_text="Whether this is a demo organization (for demo mode)"
    )
    
    def __str__(self):
        return self.name

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    # Organization is now optional - MVP simplification (no multi-org support)
    # All users effectively share the same space with demo users
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.SET_NULL, 
        related_name='members',
        null=True,
        blank=True,
        help_text="Organization (optional - MVP mode does not require organization)"
    )
    is_admin = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    
    # Welcome modal tracking
    has_seen_welcome = models.BooleanField(
        default=False,
        help_text="Whether user has seen the welcome modal explaining demo users"
    )
    
    # AI-Powered Smart Resource Analysis Fields
    skills = models.JSONField(
        default=list, 
        blank=True,
        help_text="List of skills with proficiency levels (e.g., [{'name': 'Python', 'level': 'Expert'}, {'name': 'React', 'level': 'Intermediate'}])"
    )
    weekly_capacity_hours = models.IntegerField(
        default=40,
        help_text="Available working hours per week"
    )
    current_workload_hours = models.IntegerField(
        default=0,
        help_text="Currently assigned hours (auto-calculated)"
    )
    availability_schedule = models.JSONField(
        default=dict,
        blank=True,
        help_text="Weekly availability schedule (e.g., {'monday': {'start': '09:00', 'end': '17:00'}})"
    )
    
    # Performance Metrics (AI-calculated)
    average_task_completion_time = models.FloatField(
        default=0.0,
        help_text="Average time to complete tasks (in hours)"
    )
    quality_score = models.IntegerField(
        default=100,
        help_text="Quality score based on rework rates and reviews (0-100)"
    )
    collaboration_score = models.IntegerField(
        default=100,
        help_text="Collaboration effectiveness score (0-100)"
    )
    productivity_trend = models.CharField(
        max_length=20,
        choices=[
            ('improving', 'Improving'),
            ('stable', 'Stable'),
            ('declining', 'Declining'),
        ],
        default='stable',
        help_text="AI-calculated productivity trend"
    )
    
    # Resource Management
    preferred_task_types = models.JSONField(
        default=list,
        blank=True,
        help_text="Preferred types of tasks based on performance history"
    )
    peak_productivity_hours = models.JSONField(
        default=list,
        blank=True,
        help_text="Hours when user is most productive (e.g., ['09:00-11:00', '14:00-16:00'])"
    )
      # AI Analysis Metadata
    last_resource_analysis = models.DateTimeField(
        blank=True, 
        null=True,
        help_text="When AI last analyzed this user's resource profile"
    )
    resource_risk_factors = models.JSONField(
        default=list,
        blank=True,
        help_text="AI-identified risk factors for this resource"
    )
    
    # Getting Started Wizard
    completed_wizard = models.BooleanField(
        default=False,
        help_text="Whether user has completed the getting started wizard"
    )
    wizard_completed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When user completed the getting started wizard"
    )
    
    # Onboarding v2 — AI-powered workspace setup
    ONBOARDING_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('demo_exploring', 'Exploring Demo'),
        ('goal_submitted', 'Goal Submitted'),
        ('workspace_generated', 'Workspace Generated'),
        ('completed', 'Completed'),
        ('skipped', 'Skipped'),
    ]
    onboarding_version = models.IntegerField(
        default=1,
        help_text="1 = legacy (old welcome modal), 2 = new AI onboarding flow"
    )
    onboarding_status = models.CharField(
        max_length=25,
        choices=ONBOARDING_STATUS_CHOICES,
        default='completed',
        help_text="Current position in the v2 onboarding flow"
    )
    onboarding_goal_text = models.TextField(
        blank=True,
        null=True,
        help_text="Raw organization goal text entered during onboarding"
    )
    is_viewing_demo = models.BooleanField(
        default=False,
        help_text="Whether user is currently viewing the demo workspace"
    )
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    @property
    def utilization_percentage(self):
        """Calculate current utilization percentage"""
        if self.weekly_capacity_hours == 0:
            return 0
        return min(100, (self.current_workload_hours / self.weekly_capacity_hours) * 100)
    
    @property
    def available_hours(self):
        """Calculate available hours this week"""
        return max(0, self.weekly_capacity_hours - self.current_workload_hours)
    
    @property
    def skill_names(self):
        """Get list of skill names for easy searching"""
        return [skill.get('name', '') for skill in self.skills if skill.get('name')]
    
    @property
    def expert_skills(self):
        """Get list of expert-level skills"""
        return [skill.get('name', '') for skill in self.skills if skill.get('level') == 'Expert']
