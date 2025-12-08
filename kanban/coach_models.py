"""
AI Coach for Project Managers - Data Models

This module contains models for the AI coaching system that provides
proactive suggestions, learns from feedback, and helps PMs make better decisions.
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal


class CoachingSuggestion(models.Model):
    """
    AI-generated coaching suggestions for project managers
    Proactive recommendations based on project metrics and patterns
    """
    
    # Suggestion Types
    SUGGESTION_TYPES = [
        ('velocity_drop', 'Velocity Dropping'),
        ('resource_overload', 'Resource Overloaded'),
        ('risk_convergence', 'Multiple Risks Converging'),
        ('skill_opportunity', 'Skill Development Opportunity'),
        ('scope_creep', 'Scope Creep Detected'),
        ('deadline_risk', 'Deadline at Risk'),
        ('team_burnout', 'Team Burnout Risk'),
        ('quality_issue', 'Quality Issues Detected'),
        ('communication_gap', 'Communication Gap'),
        ('dependency_blocker', 'Dependency Blocking Progress'),
        ('best_practice', 'Best Practice Recommendation'),
    ]
    
    # Severity Levels
    SEVERITY_LEVELS = [
        ('info', 'Information'),
        ('low', 'Low Priority'),
        ('medium', 'Medium Priority'),
        ('high', 'High Priority'),
        ('critical', 'Critical'),
    ]
    
    # Status
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
        ('expired', 'Expired'),
    ]
    
    # Context
    board = models.ForeignKey('Board', on_delete=models.CASCADE, related_name='coaching_suggestions')
    task = models.ForeignKey(
        'Task',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='coaching_suggestions',
        help_text="Specific task this suggestion relates to (if any)"
    )
    
    # Suggestion Details
    suggestion_type = models.CharField(max_length=30, choices=SUGGESTION_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    title = models.CharField(max_length=200, help_text="Brief suggestion title")
    message = models.TextField(help_text="Detailed coaching message")
    
    # AI-Generated Content
    reasoning = models.TextField(
        blank=True,
        help_text="AI explanation of why this suggestion was made"
    )
    recommended_actions = models.JSONField(
        default=list,
        blank=True,
        help_text="List of recommended action steps"
    )
    expected_impact = models.CharField(
        max_length=500,
        blank=True,
        help_text="Expected impact if actions are taken"
    )
    
    # Metrics Context
    metrics_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="Snapshot of relevant metrics when suggestion was generated"
    )
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.75'),
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="AI confidence in this suggestion (0-1)"
    )
    
    # AI Model Info
    ai_model_used = models.CharField(
        max_length=50,
        default='rule-based',
        help_text="AI model/system that generated suggestion"
    )
    generation_method = models.CharField(
        max_length=20,
        choices=[
            ('rule', 'Rule-Based'),
            ('ai', 'AI-Generated'),
            ('hybrid', 'Hybrid (Rule + AI)'),
        ],
        default='rule'
    )
    
    # Timing
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this suggestion becomes irrelevant"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # User Interaction
    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_suggestions'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    
    # Learning Data
    was_helpful = models.BooleanField(
        null=True,
        blank=True,
        help_text="User feedback on helpfulness"
    )
    action_taken = models.CharField(
        max_length=20,
        choices=[
            ('accepted', 'Accepted and Applied'),
            ('partially', 'Partially Applied'),
            ('modified', 'Modified Before Applying'),
            ('ignored', 'Ignored'),
            ('not_applicable', 'Not Applicable'),
        ],
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['board', 'status', '-created_at']),
            models.Index(fields=['suggestion_type', 'severity']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_severity_display()}: {self.title} ({self.board.name})"
    
    @property
    def is_expired(self):
        """Check if suggestion has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    @property
    def days_active(self):
        """Number of days suggestion has been active"""
        if self.resolved_at:
            return (self.resolved_at - self.created_at).days
        return (timezone.now() - self.created_at).days
    
    def acknowledge(self, user):
        """Mark suggestion as acknowledged by user"""
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        if self.status == 'active':
            self.status = 'acknowledged'
        self.save()
    
    def resolve(self, action_taken=None, was_helpful=None):
        """Mark suggestion as resolved"""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        if action_taken:
            self.action_taken = action_taken
        if was_helpful is not None:
            self.was_helpful = was_helpful
        self.save()
    
    def dismiss(self):
        """Dismiss suggestion"""
        self.status = 'dismissed'
        self.resolved_at = timezone.now()
        self.save()


class CoachingFeedback(models.Model):
    """
    User feedback on coaching suggestions
    Used to train and improve the AI coach
    """
    
    suggestion = models.ForeignKey(
        CoachingSuggestion,
        on_delete=models.CASCADE,
        related_name='feedback_entries'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coaching_feedback')
    
    # Feedback
    was_helpful = models.BooleanField(help_text="Was this suggestion helpful?")
    relevance_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="How relevant was this suggestion? (1-5)"
    )
    
    # Detailed Feedback
    feedback_text = models.TextField(
        blank=True,
        help_text="Detailed feedback from user"
    )
    action_taken = models.CharField(
        max_length=20,
        choices=[
            ('accepted', 'Accepted and Applied'),
            ('partially', 'Partially Applied'),
            ('modified', 'Modified Before Applying'),
            ('ignored', 'Ignored'),
            ('not_applicable', 'Not Applicable'),
        ]
    )
    
    # Outcome
    outcome_description = models.TextField(
        blank=True,
        help_text="What happened after applying (or not) the suggestion?"
    )
    improved_situation = models.BooleanField(
        null=True,
        blank=True,
        help_text="Did the situation improve?"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Coaching Feedback'
        verbose_name_plural = 'Coaching Feedback'
    
    def __str__(self):
        return f"Feedback on '{self.suggestion.title}' by {self.user.username}"


class PMMetrics(models.Model):
    """
    Project Manager performance metrics
    Tracks patterns to improve coaching suggestions
    """
    
    board = models.ForeignKey('Board', on_delete=models.CASCADE, related_name='pm_metrics')
    pm_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='pm_metrics',
        help_text="Project manager being tracked"
    )
    
    # Time Period
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Performance Metrics
    suggestions_received = models.IntegerField(
        default=0,
        help_text="Number of suggestions received"
    )
    suggestions_acted_on = models.IntegerField(
        default=0,
        help_text="Number of suggestions acted on"
    )
    avg_response_time_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Average time to respond to suggestions (hours)"
    )
    
    # Project Health Indicators
    velocity_trend = models.CharField(
        max_length=20,
        choices=[
            ('improving', 'Improving'),
            ('stable', 'Stable'),
            ('declining', 'Declining'),
        ],
        default='stable'
    )
    risk_mitigation_success_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of risks successfully mitigated"
    )
    deadline_hit_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of deadlines met"
    )
    team_satisfaction_score = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
        help_text="Team satisfaction score (0-5)"
    )
    
    # Learning Indicators
    improvement_areas = models.JSONField(
        default=list,
        blank=True,
        help_text="Areas where PM is improving"
    )
    struggle_areas = models.JSONField(
        default=list,
        blank=True,
        help_text="Areas where PM needs more support"
    )
    
    # Coaching Effectiveness
    coaching_effectiveness_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="How effective coaching has been (0-100)"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    calculated_by = models.CharField(
        max_length=50,
        default='system',
        help_text="How metrics were calculated"
    )
    
    class Meta:
        ordering = ['-period_end']
        verbose_name = 'PM Metrics'
        verbose_name_plural = 'PM Metrics'
        unique_together = [['board', 'pm_user', 'period_start', 'period_end']]
    
    def __str__(self):
        return f"{self.pm_user.username} - {self.board.name} ({self.period_start} to {self.period_end})"
    
    @property
    def action_rate(self):
        """Percentage of suggestions acted on"""
        if self.suggestions_received > 0:
            return (self.suggestions_acted_on / self.suggestions_received) * 100
        return 0


class CoachingInsight(models.Model):
    """
    Learned insights from coaching patterns
    Used to improve future suggestions
    """
    
    insight_type = models.CharField(
        max_length=30,
        choices=[
            ('pattern', 'Pattern Recognition'),
            ('effectiveness', 'Suggestion Effectiveness'),
            ('pm_behavior', 'PM Behavior Pattern'),
            ('team_dynamics', 'Team Dynamics'),
            ('context_factor', 'Context Factor'),
        ]
    )
    
    # Insight Content
    title = models.CharField(max_length=200)
    description = models.TextField(help_text="What was learned")
    
    # Confidence
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Confidence in this insight (0-1)"
    )
    sample_size = models.IntegerField(
        default=0,
        help_text="Number of data points supporting this insight"
    )
    
    # Application
    applicable_to_suggestion_types = models.JSONField(
        default=list,
        help_text="Which suggestion types this insight applies to"
    )
    rule_adjustments = models.JSONField(
        default=dict,
        blank=True,
        help_text="How rules should be adjusted based on this insight"
    )
    
    # Metadata
    discovered_at = models.DateTimeField(auto_now_add=True)
    last_validated = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Is this insight currently being applied?"
    )
    
    class Meta:
        ordering = ['-confidence_score', '-sample_size']
    
    def __str__(self):
        return f"{self.title} (confidence: {self.confidence_score})"
