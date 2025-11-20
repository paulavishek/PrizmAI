"""
Models for Burndown/Burnup Prediction with Confidence Intervals
Statistical forecasting for sprint/project completion with AI-powered insights
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal
import json


class TeamVelocitySnapshot(models.Model):
    """
    Track team velocity over time for statistical forecasting
    Velocity = work completed per time period
    """
    board = models.ForeignKey('Board', on_delete=models.CASCADE, related_name='velocity_snapshots')
    
    # Time period
    period_start = models.DateField(help_text="Start date of velocity measurement period")
    period_end = models.DateField(help_text="End date of velocity measurement period")
    period_type = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('sprint', 'Sprint'),
            ('monthly', 'Monthly'),
        ],
        default='weekly'
    )
    
    # Velocity metrics
    tasks_completed = models.IntegerField(default=0, help_text="Number of tasks completed in period")
    story_points_completed = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Story points/complexity completed"
    )
    hours_completed = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Estimated hours of work completed"
    )
    
    # Team composition
    active_team_members = models.IntegerField(default=0, help_text="Number of active team members in period")
    team_member_list = models.JSONField(default=list, blank=True, help_text="List of team member IDs")
    
    # Quality metrics
    tasks_reopened = models.IntegerField(default=0, help_text="Tasks that were reopened/rejected")
    quality_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Quality score (100 - reopened_percentage)"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    calculated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='calculated_velocities'
    )
    
    class Meta:
        ordering = ['-period_end', '-period_start']
        verbose_name = 'Team Velocity Snapshot'
        verbose_name_plural = 'Team Velocity Snapshots'
        indexes = [
            models.Index(fields=['board', '-period_end']),
            models.Index(fields=['period_start', 'period_end']),
        ]
    
    def __str__(self):
        return f"{self.board.name} Velocity: {self.period_start} to {self.period_end} ({self.tasks_completed} tasks)"
    
    @property
    def velocity_per_member(self):
        """Average velocity per team member"""
        if self.active_team_members > 0:
            return self.tasks_completed / self.active_team_members
        return 0
    
    @property
    def days_in_period(self):
        """Number of days in this velocity period"""
        return (self.period_end - self.period_start).days + 1


class BurndownPrediction(models.Model):
    """
    Statistical burndown/burnup prediction with confidence intervals
    Projects completion date based on historical velocity and variance
    """
    board = models.ForeignKey('Board', on_delete=models.CASCADE, related_name='burndown_predictions')
    
    # Prediction context
    prediction_date = models.DateTimeField(auto_now_add=True, help_text="When this prediction was generated")
    prediction_type = models.CharField(
        max_length=20,
        choices=[
            ('burndown', 'Burndown (work remaining)'),
            ('burnup', 'Burnup (work completed)'),
        ],
        default='burndown'
    )
    
    # Scope
    total_tasks = models.IntegerField(default=0, help_text="Total tasks in scope")
    completed_tasks = models.IntegerField(default=0, help_text="Tasks completed so far")
    remaining_tasks = models.IntegerField(default=0, help_text="Tasks remaining")
    
    total_story_points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Total story points/complexity"
    )
    completed_story_points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Completed story points"
    )
    remaining_story_points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Remaining story points"
    )
    
    # Velocity analysis
    current_velocity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Current team velocity (tasks/week)"
    )
    average_velocity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Historical average velocity"
    )
    velocity_std_dev = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Standard deviation of velocity (measures variance/noise)"
    )
    velocity_trend = models.CharField(
        max_length=20,
        choices=[
            ('increasing', 'Increasing'),
            ('stable', 'Stable'),
            ('decreasing', 'Decreasing'),
            ('insufficient_data', 'Insufficient Data'),
        ],
        default='stable'
    )
    
    # Predictions with confidence intervals
    predicted_completion_date = models.DateField(
        help_text="Most likely completion date (50th percentile)"
    )
    
    # Confidence interval bounds
    completion_date_lower_bound = models.DateField(
        help_text="Early completion date (10th percentile)"
    )
    completion_date_upper_bound = models.DateField(
        help_text="Late completion date (90th percentile)"
    )
    
    days_until_completion_estimate = models.IntegerField(
        default=0,
        help_text="Estimated days until completion"
    )
    days_margin_of_error = models.IntegerField(
        default=0,
        help_text="±days margin of error (half of confidence interval width)"
    )
    
    # Confidence metrics
    confidence_percentage = models.IntegerField(
        default=90,
        validators=[MinValueValidator(50), MaxValueValidator(99)],
        help_text="Confidence level (typically 90%)"
    )
    prediction_confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.5,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Overall confidence in prediction (0-1)"
    )
    
    # Risk assessment
    delay_probability = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Probability of missing target date (%)"
    )
    risk_level = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low Risk - On Track'),
            ('medium', 'Medium Risk - Monitor'),
            ('high', 'High Risk - Action Needed'),
            ('critical', 'Critical Risk - Intervention Required'),
        ],
        default='low'
    )
    
    # Target date comparison
    target_completion_date = models.DateField(
        blank=True,
        null=True,
        help_text="Target/planned completion date (if set)"
    )
    will_meet_target = models.BooleanField(
        default=True,
        null=True,
        blank=True,
        help_text="Will predicted date meet target?"
    )
    days_ahead_behind_target = models.IntegerField(
        default=0,
        help_text="Days ahead (positive) or behind (negative) target"
    )
    
    # Statistical details
    burndown_curve_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Historical and projected burndown data points"
    )
    confidence_bands_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Upper and lower confidence band data for visualization"
    )
    velocity_history_data = models.JSONField(
        default=list,
        blank=True,
        help_text="Historical velocity measurements used in prediction"
    )
    
    # AI-generated suggestions
    actionable_suggestions = models.JSONField(
        default=list,
        blank=True,
        help_text="AI-generated suggestions to improve completion probability"
    )
    
    # Metadata
    based_on_velocity_snapshots = models.ManyToManyField(
        TeamVelocitySnapshot,
        related_name='predictions',
        blank=True,
        help_text="Velocity snapshots used to generate this prediction"
    )
    model_parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Statistical model parameters and assumptions"
    )
    
    class Meta:
        ordering = ['-prediction_date']
        verbose_name = 'Burndown Prediction'
        verbose_name_plural = 'Burndown Predictions'
        indexes = [
            models.Index(fields=['board', '-prediction_date']),
            models.Index(fields=['predicted_completion_date']),
        ]
    
    def __str__(self):
        return (f"{self.board.name} - Completion: {self.predicted_completion_date} "
                f"(±{self.days_margin_of_error} days, {self.confidence_percentage}% confidence)")
    
    @property
    def completion_probability_range(self):
        """Get completion date range as human-readable string"""
        return f"{self.completion_date_lower_bound} to {self.completion_date_upper_bound}"
    
    @property
    def is_high_risk(self):
        """Check if project is high risk"""
        return self.risk_level in ['high', 'critical'] or self.delay_probability >= 30
    
    @property
    def completion_percentage(self):
        """Calculate current completion percentage"""
        if self.total_tasks > 0:
            return (self.completed_tasks / self.total_tasks) * 100
        return 0


class BurndownAlert(models.Model):
    """
    Alerts for burndown/velocity issues that require attention
    """
    ALERT_TYPE_CHOICES = [
        ('velocity_drop', 'Velocity Dropped'),
        ('scope_creep', 'Scope Increased'),
        ('target_risk', 'Target Date at Risk'),
        ('variance_high', 'High Velocity Variance'),
        ('stagnation', 'Progress Stagnated'),
        ('quality_issue', 'Quality Issues Detected'),
    ]
    
    SEVERITY_CHOICES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]
    
    prediction = models.ForeignKey(
        BurndownPrediction,
        on_delete=models.CASCADE,
        related_name='alerts'
    )
    board = models.ForeignKey('Board', on_delete=models.CASCADE, related_name='burndown_alerts')
    
    # Alert details
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='warning')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    title = models.CharField(max_length=200, help_text="Brief alert title")
    message = models.TextField(help_text="Detailed alert message")
    
    # Context
    metric_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Relevant metric value (e.g., velocity, delay probability)"
    )
    threshold_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Threshold that triggered this alert"
    )
    
    # Suggestions
    suggested_actions = models.JSONField(
        default=list,
        blank=True,
        help_text="Suggested actions to address this alert"
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(blank=True, null=True)
    acknowledged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_burndown_alerts'
    )
    resolved_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-severity', '-created_at']
        verbose_name = 'Burndown Alert'
        verbose_name_plural = 'Burndown Alerts'
        indexes = [
            models.Index(fields=['board', 'status', '-created_at']),
            models.Index(fields=['prediction', 'severity']),
        ]
    
    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.title} ({self.severity})"
    
    @property
    def is_active(self):
        """Check if alert is still active"""
        return self.status in ['active', 'acknowledged']


class SprintMilestone(models.Model):
    """
    Track sprint/project milestones for burndown visualization
    """
    board = models.ForeignKey('Board', on_delete=models.CASCADE, related_name='sprint_milestones')
    
    # Milestone info
    name = models.CharField(max_length=200, help_text="Milestone name (e.g., 'Sprint 1 End', 'MVP Release')")
    description = models.TextField(blank=True, help_text="Milestone description")
    
    # Dates
    target_date = models.DateField(help_text="Target completion date")
    actual_date = models.DateField(blank=True, null=True, help_text="Actual completion date")
    
    # Targets
    target_tasks_completed = models.IntegerField(default=0, help_text="Expected tasks completed by this milestone")
    target_story_points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Expected story points by this milestone"
    )
    
    # Status
    is_completed = models.BooleanField(default=False)
    completion_percentage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_milestones'
    )
    
    class Meta:
        ordering = ['target_date']
        verbose_name = 'Sprint Milestone'
        verbose_name_plural = 'Sprint Milestones'
        indexes = [
            models.Index(fields=['board', 'target_date']),
            models.Index(fields=['is_completed']),
        ]
    
    def __str__(self):
        status = "✓" if self.is_completed else "○"
        return f"{status} {self.name} - {self.target_date}"
    
    @property
    def days_until_target(self):
        """Days until target date"""
        if not self.is_completed:
            delta = self.target_date - timezone.now().date()
            return delta.days
        return 0
    
    @property
    def is_overdue(self):
        """Check if milestone is overdue"""
        return not self.is_completed and self.target_date < timezone.now().date()
