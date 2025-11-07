# kanban/stakeholder_models.py
"""
Stakeholder Engagement Tracking Models for TaskFlow
Integrated with the kanban board system for project-based stakeholder management
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from .models import Board, Task


class ProjectStakeholder(models.Model):
    """
    Represents a stakeholder associated with a project (Board)
    Supports simple tagging and relationship tracking
    """
    INFLUENCE_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    INTEREST_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    ENGAGEMENT_STRATEGY_CHOICES = [
        ('inform', 'Inform'),
        ('consult', 'Consult'),
        ('involve', 'Involve'),
        ('collaborate', 'Collaborate'),
        ('empower', 'Empower'),
    ]
    
    # Basic information
    name = models.CharField(max_length=100, help_text="Stakeholder name")
    role = models.CharField(max_length=100, help_text="Role/Title of stakeholder")
    organization = models.CharField(max_length=100, blank=True, help_text="Organization/Department")
    email = models.EmailField(blank=True, help_text="Contact email")
    phone = models.CharField(max_length=20, blank=True, help_text="Contact phone")
    
    # Project association
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='stakeholders',
                             help_text="Project/Board this stakeholder is associated with")
    
    # Analysis metrics
    influence_level = models.CharField(max_length=10, choices=INFLUENCE_CHOICES, default='medium',
                                      help_text="Stakeholder's level of influence on project")
    interest_level = models.CharField(max_length=10, choices=INTEREST_CHOICES, default='medium',
                                     help_text="Stakeholder's level of interest in project")
    
    # Engagement tracking
    current_engagement = models.CharField(max_length=20, choices=ENGAGEMENT_STRATEGY_CHOICES, 
                                         default='inform',
                                         help_text="Current engagement level with stakeholder")
    desired_engagement = models.CharField(max_length=20, choices=ENGAGEMENT_STRATEGY_CHOICES,
                                         default='involve',
                                         help_text="Desired engagement level for this stakeholder")
    
    # Metadata
    notes = models.TextField(blank=True, help_text="Additional notes about stakeholder")
    is_active = models.BooleanField(default=True, help_text="Whether stakeholder is still active on project")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_stakeholders')
    
    class Meta:
        ordering = ['name']
        unique_together = [['board', 'email', 'name']]  # Avoid duplicates per board
    
    def __str__(self):
        return f"{self.name} ({self.role}) - {self.board.name}"
    
    def get_quadrant(self):
        """
        Return stakeholder quadrant based on influence and interest levels
        Using power/interest matrix
        """
        influence_value = self.get_influence_value()
        interest_value = self.get_interest_value()
        
        if influence_value >= 2 and interest_value >= 2:
            return "Manage Closely"
        elif influence_value >= 2 and interest_value < 2:
            return "Keep Satisfied"
        elif influence_value < 2 and interest_value >= 2:
            return "Keep Informed"
        else:
            return "Monitor"
    
    def get_influence_value(self):
        """Convert influence level to numeric value"""
        values = {'low': 1, 'medium': 2, 'high': 3}
        return values.get(self.influence_level, 2)
    
    def get_interest_value(self):
        """Convert interest level to numeric value"""
        values = {'low': 1, 'medium': 2, 'high': 3}
        return values.get(self.interest_level, 2)
    
    def get_engagement_level_value(self):
        """Convert current engagement level to numeric value"""
        values = {
            'inform': 1,
            'consult': 2,
            'involve': 3,
            'collaborate': 4,
            'empower': 5
        }
        return values.get(self.current_engagement, 1)
    
    def get_desired_engagement_level_value(self):
        """Convert desired engagement level to numeric value"""
        values = {
            'inform': 1,
            'consult': 2,
            'involve': 3,
            'collaborate': 4,
            'empower': 5
        }
        return values.get(self.desired_engagement, 1)
    
    def get_engagement_gap(self):
        """Calculate engagement gap (desired - current)"""
        return self.get_desired_engagement_level_value() - self.get_engagement_level_value()


class StakeholderTaskInvolvement(models.Model):
    """
    Tracks stakeholder involvement and engagement in specific tasks
    Enables detailed engagement metrics at task level
    """
    INVOLVEMENT_TYPE_CHOICES = [
        ('owner', 'Task Owner'),
        ('contributor', 'Contributor'),
        ('reviewer', 'Reviewer'),
        ('approver', 'Approver/Decision Maker'),
        ('observer', 'Observer/Monitor'),
        ('beneficiary', 'Beneficiary'),
        ('impacted', 'Impacted Party'),
    ]
    
    ENGAGEMENT_STATUS_CHOICES = [
        ('not_engaged', 'Not Engaged'),
        ('informed', 'Informed'),
        ('consulted', 'Consulted'),
        ('involved', 'Involved'),
        ('collaborated', 'Collaborated'),
        ('satisfied', 'Satisfied'),
    ]
    
    # Relationships
    stakeholder = models.ForeignKey(ProjectStakeholder, on_delete=models.CASCADE,
                                   related_name='task_involvements')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='stakeholder_involvements')
    
    # Engagement details
    involvement_type = models.CharField(max_length=20, choices=INVOLVEMENT_TYPE_CHOICES,
                                       default='stakeholder',
                                       help_text="Type of stakeholder involvement in task")
    engagement_status = models.CharField(max_length=20, choices=ENGAGEMENT_STATUS_CHOICES,
                                        default='not_engaged',
                                        help_text="Current engagement status")
    
    # Tracking metrics
    engagement_count = models.IntegerField(default=0, 
                                          help_text="Number of times engaged on this task")
    last_engagement = models.DateTimeField(null=True, blank=True,
                                          help_text="Last engagement timestamp")
    satisfaction_rating = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        choices=[(1, '1 - Very Dissatisfied'), (2, '2 - Dissatisfied'), 
                (3, '3 - Neutral'), (4, '4 - Satisfied'), (5, '5 - Very Satisfied')],
        help_text="Stakeholder satisfaction with task outcome"
    )
    
    # Notes and feedback
    feedback = models.TextField(blank=True, help_text="Stakeholder feedback on task")
    concerns = models.TextField(blank=True, help_text="Any concerns or issues raised")
    
    metadata = models.JSONField(default=dict, blank=True,
                               help_text="Additional tracking data (involvement dates, channels, etc.)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-last_engagement']
        unique_together = [['stakeholder', 'task']]
    
    def __str__(self):
        return f"{self.stakeholder.name} - {self.task.title} ({self.get_involvement_type_display()})"


class StakeholderEngagementRecord(models.Model):
    """
    Records individual engagement events with stakeholders
    Provides detailed history for engagement tracking and analysis
    """
    COMMUNICATION_CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('phone', 'Phone Call'),
        ('meeting', 'In-Person Meeting'),
        ('video', 'Video Call'),
        ('chat', 'Chat/Messaging'),
        ('presentation', 'Presentation'),
        ('survey', 'Survey'),
        ('other', 'Other'),
    ]
    
    # Relationships
    stakeholder = models.ForeignKey(ProjectStakeholder, on_delete=models.CASCADE,
                                   related_name='engagement_records')
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='stakeholder_engagement_records',
                            help_text="Task associated with this engagement (optional)")
    
    # Engagement details
    date = models.DateField(default=timezone.now, help_text="Date of engagement")
    description = models.TextField(help_text="Description of engagement activity")
    communication_channel = models.CharField(max_length=20, choices=COMMUNICATION_CHANNEL_CHOICES,
                                           default='email',
                                           help_text="How stakeholder was engaged")
    
    # Outcome tracking
    outcome = models.TextField(blank=True, help_text="Outcome or results of engagement")
    follow_up_required = models.BooleanField(default=False,
                                            help_text="Whether follow-up is needed")
    follow_up_date = models.DateField(null=True, blank=True,
                                     help_text="Date for follow-up")
    follow_up_completed = models.BooleanField(default=False,
                                             help_text="Whether follow-up was completed")
    
    # Satisfaction
    engagement_sentiment = models.CharField(max_length=20, 
                                           choices=[
                                               ('positive', 'Positive'),
                                               ('neutral', 'Neutral'),
                                               ('negative', 'Negative'),
                                           ],
                                           default='neutral',
                                           help_text="Sentiment of stakeholder after engagement")
    satisfaction_rating = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        choices=[(1, '1 - Very Dissatisfied'), (2, '2 - Dissatisfied'),
                (3, '3 - Neutral'), (4, '4 - Satisfied'), (5, '5 - Very Satisfied')],
        help_text="Engagement satisfaction rating"
    )
    
    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE,
                                  related_name='engagement_records_created')
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text="Additional notes about engagement")
    
    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.stakeholder.name} engagement on {self.date}"


class EngagementMetrics(models.Model):
    """
    Stores aggregated engagement metrics for dashboards and analysis
    Calculated periodically from engagement records
    """
    # Relationships
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='engagement_metrics')
    stakeholder = models.OneToOneField(ProjectStakeholder, on_delete=models.CASCADE,
                                      related_name='metrics')
    
    # Engagement frequency
    total_engagements = models.IntegerField(default=0, help_text="Total number of engagements")
    engagements_this_month = models.IntegerField(default=0, help_text="Engagements in current month")
    engagements_this_quarter = models.IntegerField(default=0, help_text="Engagements in current quarter")
    average_engagements_per_month = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Average engagements per month"
    )
    
    # Communication channels used
    primary_channel = models.CharField(max_length=20, blank=True,
                                      help_text="Most frequently used communication channel")
    channels_used = models.JSONField(default=list, blank=True,
                                    help_text="List of communication channels used with counts")
    
    # Sentiment and satisfaction
    average_satisfaction = models.DecimalField(
        max_digits=3, decimal_places=2, default=0,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Average satisfaction rating (1-5)"
    )
    positive_engagements_count = models.IntegerField(default=0,
                                                    help_text="Number of positive engagements")
    negative_engagements_count = models.IntegerField(default=0,
                                                    help_text="Number of negative engagements")
    
    # Engagement status
    days_since_last_engagement = models.IntegerField(default=0,
                                                    help_text="Days since last engagement")
    pending_follow_ups = models.IntegerField(default=0,
                                            help_text="Number of pending follow-ups")
    
    # Engagement gap metrics
    engagement_gap = models.IntegerField(default=0,
                                        help_text="Gap between desired and current engagement level")
    
    # Calculation metadata
    calculated_at = models.DateTimeField(auto_now=True)
    period_start = models.DateField(help_text="Start date for metrics period")
    period_end = models.DateField(help_text="End date for metrics period")
    
    class Meta:
        ordering = ['-calculated_at']
    
    def __str__(self):
        return f"Metrics for {self.stakeholder.name} ({self.period_start} to {self.period_end})"
    
    def calculate_engagement_health(self):
        """Calculate overall engagement health score (0-100)"""
        score = 0
        
        # Frequency component (0-30)
        if self.average_engagements_per_month > 0:
            frequency_score = min(self.average_engagements_per_month * 5, 30)
            score += frequency_score
        
        # Satisfaction component (0-40)
        if self.average_satisfaction > 0:
            satisfaction_score = (self.average_satisfaction / 5) * 40
            score += satisfaction_score
        
        # Gap component (0-30)
        gap_score = max(30 - (self.engagement_gap * 5), 0)
        score += gap_score
        
        return min(score, 100)


class StakeholderTag(models.Model):
    """
    Simple tags for categorizing and organizing stakeholders
    """
    name = models.CharField(max_length=50, help_text="Tag name")
    color = models.CharField(max_length=7, default='#808080',
                            help_text="Hex color code for tag display")
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='stakeholder_tags')
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE,
                                  related_name='created_stakeholder_tags')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        unique_together = [['board', 'name']]
    
    def __str__(self):
        return self.name


# Add through model to allow many-to-many relationship between ProjectStakeholder and StakeholderTag
class ProjectStakeholderTag(models.Model):
    """
    Through model for many-to-many relationship between ProjectStakeholder and StakeholderTag
    """
    stakeholder = models.ForeignKey(ProjectStakeholder, on_delete=models.CASCADE)
    tag = models.ForeignKey(StakeholderTag, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = [['stakeholder', 'tag']]
    
    def __str__(self):
        return f"{self.stakeholder.name} - {self.tag.name}"
