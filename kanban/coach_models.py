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
        ('confidence_drop', 'Project Confidence Drop'),
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


class OrganizationLearningProfile(models.Model):
    """
    Organization-level aggregated learning profile.
    Aggregates coaching insights across all boards in an organization
    to enable cross-board collective intelligence and cold-start bootstrapping.
    """
    
    organization = models.ForeignKey(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='learning_profiles'
    )
    
    # Per suggestion type aggregate effectiveness
    suggestion_type = models.CharField(
        max_length=30,
        help_text="Suggestion type this profile covers"
    )
    
    # Aggregated metrics across all boards in org
    total_suggestions = models.IntegerField(default=0)
    total_feedback = models.IntegerField(default=0)
    helpful_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=0,
        help_text="Aggregated helpful rate across all boards (0-1)"
    )
    action_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=0,
        help_text="Aggregated action rate across all boards (0-1)"
    )
    avg_confidence = models.DecimalField(
        max_digits=5, decimal_places=4, default=0,
        help_text="Average confidence score across boards"
    )
    
    # Board coverage
    boards_with_data = models.IntegerField(
        default=0,
        help_text="Number of boards contributing to this profile"
    )
    
    # Learned recommendations
    recommended_confidence = models.DecimalField(
        max_digits=5, decimal_places=4, default=0.75,
        help_text="Recommended confidence for new boards without their own data"
    )
    should_suppress = models.BooleanField(
        default=False,
        help_text="Whether this type should be suppressed org-wide"
    )
    
    # Per-severity effectiveness (JSON: {"high": 0.8, "medium": 0.6, ...})
    severity_effectiveness = models.JSONField(
        default=dict, blank=True,
        help_text="Effectiveness rates by severity level"
    )
    
    # Metadata
    last_aggregated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['organization', 'suggestion_type']
        ordering = ['-helpful_rate', '-total_feedback']
        verbose_name = 'Organization Learning Profile'
        verbose_name_plural = 'Organization Learning Profiles'
    
    def __str__(self):
        return (
            f"{self.organization.name} - {self.suggestion_type}: "
            f"{self.helpful_rate*100:.0f}% helpful ({self.total_feedback} feedback)"
        )


class AIExperimentResult(models.Model):
    """
    A/B testing framework for comparing AI enhancement strategies.
    Tracks effectiveness of rule-based vs AI-enhanced vs hybrid suggestions,
    enabling data-driven decisions about when AI enhancement adds value.
    """
    
    # Experiment scope
    board = models.ForeignKey(
        'Board', on_delete=models.CASCADE,
        related_name='experiment_results',
        null=True, blank=True,
        help_text="Board scope (null = org-wide)"
    )
    organization = models.ForeignKey(
        'accounts.Organization', on_delete=models.CASCADE,
        related_name='experiment_results',
        null=True, blank=True,
    )
    suggestion_type = models.CharField(max_length=30)
    
    # Comparison groups
    generation_method = models.CharField(
        max_length=20,
        choices=[
            ('rule', 'Rule-Based'),
            ('ai', 'AI-Generated'),
            ('hybrid', 'Hybrid (Rule + AI Enhanced)'),
        ]
    )
    
    # Effectiveness metrics
    total_suggestions = models.IntegerField(default=0)
    total_feedback = models.IntegerField(default=0)
    helpful_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    action_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    avg_relevance = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    outcome_success_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=0,
        help_text="Rate of suggestions that actually improved the situation"
    )
    
    # Metadata
    period_start = models.DateField()
    period_end = models.DateField()
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['board', 'suggestion_type', 'generation_method', 'period_start']
        ordering = ['-period_end', '-helpful_rate']
        verbose_name = 'AI Experiment Result'
        verbose_name_plural = 'AI Experiment Results'
    
    def __str__(self):
        scope = self.board.name if self.board else (self.organization.name if self.organization else 'Global')
        return (
            f"{scope} - {self.suggestion_type} ({self.generation_method}): "
            f"{self.helpful_rate*100:.0f}% helpful"
        )
    
    @classmethod
    def calculate_experiment_results(cls, board=None, organization=None, days=30):
        """
        Calculate A/B experiment results comparing generation methods.
        
        Args:
            board: Optional board to scope results
            organization: Optional organization to scope results
            days: Analysis period in days
            
        Returns:
            List of created/updated AIExperimentResult objects
        """
        from django.db.models import Count, Q, Avg
        from datetime import timedelta
        from decimal import Decimal
        
        period_end = timezone.now().date()
        period_start = period_end - timedelta(days=days)
        
        # Build queryset
        qs = CoachingSuggestion.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=days),
            was_helpful__isnull=False,
        )
        
        if board:
            qs = qs.filter(board=board)
        elif organization:
            qs = qs.filter(board__organization=organization)
        
        # Group by suggestion_type + generation_method
        stats = qs.values('suggestion_type', 'generation_method').annotate(
            total=Count('id'),
            helpful=Count('id', filter=Q(was_helpful=True)),
            acted=Count('id', filter=Q(
                action_taken__in=['accepted', 'partially', 'modified']
            )),
            avg_rel=Avg('feedback_entries__relevance_score'),
        )
        
        results = []
        for stat in stats:
            if stat['total'] < 3:
                continue  # Not enough data
            
            helpful_rate = stat['helpful'] / stat['total']
            action_rate = stat['acted'] / stat['total']
            
            # Calculate outcome success rate
            outcome_qs = qs.filter(
                suggestion_type=stat['suggestion_type'],
                generation_method=stat['generation_method'],
                feedback_entries__improved_situation=True,
            ).distinct()
            outcome_total = qs.filter(
                suggestion_type=stat['suggestion_type'],
                generation_method=stat['generation_method'],
                feedback_entries__improved_situation__isnull=False,
            ).distinct().count()
            outcome_rate = outcome_qs.count() / outcome_total if outcome_total > 0 else 0
            
            result, _ = cls.objects.update_or_create(
                board=board,
                suggestion_type=stat['suggestion_type'],
                generation_method=stat['generation_method'],
                period_start=period_start,
                defaults={
                    'organization': organization,
                    'total_suggestions': stat['total'],
                    'total_feedback': stat['total'],
                    'helpful_rate': Decimal(str(round(helpful_rate, 4))),
                    'action_rate': Decimal(str(round(action_rate, 4))),
                    'avg_relevance': Decimal(str(round(float(stat['avg_rel'] or 0), 2))),
                    'outcome_success_rate': Decimal(str(round(outcome_rate, 4))),
                    'period_end': period_end,
                }
            )
            results.append(result)
        
        return results
