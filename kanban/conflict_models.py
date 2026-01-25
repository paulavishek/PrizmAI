"""
Conflict Detection and Resolution Models
Tracks resource conflicts, schedule conflicts, dependency conflicts,
and learns from resolution patterns to improve future suggestions.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import datetime


class ConflictDetection(models.Model):
    """
    Represents a detected conflict in task scheduling, resources, or dependencies.
    """
    CONFLICT_TYPES = [
        ('resource', 'Resource Conflict'),
        ('schedule', 'Schedule Conflict'),
        ('dependency', 'Dependency Conflict'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('resolved', 'Resolved'),
        ('ignored', 'Ignored'),
        ('auto_resolved', 'Auto-Resolved'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    # Basic Information
    conflict_type = models.CharField(max_length=20, choices=CONFLICT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Conflict Details
    title = models.CharField(max_length=255, help_text="Short description of the conflict")
    description = models.TextField(help_text="Detailed explanation of the conflict")
    detected_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Related Entities
    board = models.ForeignKey('Board', on_delete=models.CASCADE, related_name='conflicts')
    tasks = models.ManyToManyField('Task', related_name='conflicts', 
                                   help_text="Tasks involved in this conflict")
    affected_users = models.ManyToManyField(User, related_name='affected_conflicts',
                                           help_text="Users affected by this conflict")
    
    # Conflict Metadata
    conflict_data = models.JSONField(
        default=dict,
        help_text="Detailed conflict information (e.g., overlapping time ranges, specific dependency chains)"
    )
    
    # AI Analysis
    ai_confidence_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=80,
        help_text="AI confidence in conflict detection (0-100)"
    )
    suggested_resolutions = models.JSONField(
        default=list,
        help_text="AI-generated resolution suggestions with confidence scores"
    )
    
    # Resolution Tracking
    chosen_resolution = models.ForeignKey(
        'ConflictResolution',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_conflicts'
    )
    resolution_feedback = models.TextField(
        blank=True,
        null=True,
        help_text="User feedback on the resolution"
    )
    resolution_effectiveness = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True,
        blank=True,
        help_text="User rating of resolution effectiveness (1-5 stars)"
    )
    
    # Detection Metadata
    detection_run_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Unique ID for the detection batch run"
    )
    auto_detection = models.BooleanField(
        default=True,
        help_text="Was this detected automatically or manually reported?"
    )
    
    class Meta:
        ordering = ['-detected_at', '-severity']
        indexes = [
            models.Index(fields=['status', 'conflict_type']),
            models.Index(fields=['board', 'status']),
            models.Index(fields=['detected_at']),
        ]
    
    def __str__(self):
        return f"{self.get_conflict_type_display()} - {self.title} ({self.status})"
    
    def resolve(self, resolution, user=None, feedback=None, effectiveness=None):
        """Mark conflict as resolved with chosen resolution."""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.chosen_resolution = resolution
        if feedback:
            self.resolution_feedback = feedback
        if effectiveness:
            self.resolution_effectiveness = effectiveness
        self.save()
        
        # Learn from this resolution
        ResolutionPattern.learn_from_resolution(self, resolution, effectiveness)
    
    def ignore(self, user=None, reason=None):
        """Mark conflict as ignored."""
        self.status = 'ignored'
        self.resolved_at = timezone.now()
        if reason:
            self.resolution_feedback = reason
        self.save()
    
    def get_severity_color(self):
        """Return CSS color class based on severity."""
        colors = {
            'low': 'info',
            'medium': 'warning',
            'high': 'danger',
            'critical': 'critical'
        }
        return colors.get(self.severity, 'secondary')


class ConflictResolution(models.Model):
    """
    Represents a possible resolution for a conflict.
    Can be AI-suggested or manually created.
    """
    RESOLUTION_TYPES = [
        ('reassign', 'Reassign Task'),
        ('reschedule', 'Reschedule Task'),
        ('adjust_dates', 'Adjust Dates'),
        ('remove_dependency', 'Remove Dependency'),
        ('modify_dependency', 'Modify Dependency'),
        ('split_task', 'Split Task'),
        ('reduce_scope', 'Reduce Scope'),
        ('add_resources', 'Add Resources'),
        ('custom', 'Custom Resolution'),
    ]
    
    # Basic Information
    conflict = models.ForeignKey(
        ConflictDetection,
        on_delete=models.CASCADE,
        related_name='resolutions'
    )
    resolution_type = models.CharField(max_length=30, choices=RESOLUTION_TYPES)
    title = models.CharField(max_length=255)
    description = models.TextField()
    
    # Resolution Details
    action_steps = models.JSONField(
        default=list,
        help_text="Specific steps to implement this resolution"
    )
    estimated_impact = models.CharField(
        max_length=255,
        blank=True,
        help_text="Expected impact of this resolution"
    )
    
    # AI Scoring
    ai_confidence = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=50,
        help_text="AI confidence in this resolution (0-100)"
    )
    ai_reasoning = models.TextField(
        blank=True,
        help_text="AI explanation for why this resolution was suggested"
    )
    
    # Implementation
    auto_applicable = models.BooleanField(
        default=False,
        help_text="Can this resolution be applied automatically?"
    )
    implementation_data = models.JSONField(
        default=dict,
        help_text="Data needed to auto-apply this resolution"
    )
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    applied_at = models.DateTimeField(null=True, blank=True)
    applied_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='applied_resolutions'
    )
    
    # Success Metrics
    times_suggested = models.IntegerField(default=1)
    times_accepted = models.IntegerField(default=0)
    avg_effectiveness_rating = models.FloatField(
        null=True,
        blank=True,
        help_text="Average user rating when this type was chosen"
    )
    
    class Meta:
        ordering = ['-ai_confidence', '-created_at']
        indexes = [
            models.Index(fields=['conflict', 'resolution_type']),
            models.Index(fields=['-ai_confidence']),
        ]
    
    def __str__(self):
        return f"{self.get_resolution_type_display()}: {self.title}"
    
    def apply(self, user):
        """Apply this resolution to resolve the conflict."""
        if self.auto_applicable:
            self._auto_apply()
        
        self.applied_at = timezone.now()
        self.applied_by = user
        self.times_accepted += 1
        self.save()
        
        # Mark conflict as resolved
        self.conflict.resolve(self, user)
    
    def _auto_apply(self):
        """Automatically apply the resolution based on implementation_data."""
        data = self.implementation_data
        resolution_type = self.resolution_type
        
        # Import here to avoid circular imports
        from kanban.models import Task
        
        # Helper function to parse date strings
        def parse_date(date_str):
            """Convert date string to date object if needed."""
            if isinstance(date_str, str):
                try:
                    # Try parsing ISO format date
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
                except (ValueError, AttributeError):
                    try:
                        # Try parsing YYYY-MM-DD format
                        return datetime.strptime(date_str, '%Y-%m-%d').date()
                    except ValueError:
                        return None
            return date_str
        
        if resolution_type == 'reassign' and 'task_id' in data and 'new_assignee_id' in data:
            task = Task.objects.get(id=data['task_id'])
            new_assignee = User.objects.get(id=data['new_assignee_id'])
            task.assigned_to = new_assignee
            task.save()
        
        elif resolution_type == 'reschedule' and 'task_id' in data:
            task = Task.objects.get(id=data['task_id'])
            if 'new_start_date' in data:
                task.start_date = parse_date(data['new_start_date'])
            if 'new_due_date' in data:
                task.due_date = parse_date(data['new_due_date'])
            task.save()
        
        elif resolution_type == 'adjust_dates' and 'task_id' in data:
            task = Task.objects.get(id=data['task_id'])
            if 'new_start_date' in data:
                task.start_date = parse_date(data['new_start_date'])
            if 'new_due_date' in data:
                task.due_date = parse_date(data['new_due_date'])
            task.save()
        
        # Add more auto-apply logic for other resolution types as needed


class ResolutionPattern(models.Model):
    """
    Learns from historical conflict resolutions to improve future suggestions.
    This model stores patterns about what resolutions work best for different conflict types.
    """
    # Pattern Identification
    conflict_type = models.CharField(
        max_length=20,
        choices=ConflictDetection.CONFLICT_TYPES
    )
    resolution_type = models.CharField(
        max_length=30,
        choices=ConflictResolution.RESOLUTION_TYPES
    )
    
    # Context
    board = models.ForeignKey(
        'Board',
        on_delete=models.CASCADE,
        related_name='resolution_patterns',
        null=True,
        blank=True,
        help_text="Board-specific pattern (null = global pattern)"
    )
    pattern_context = models.JSONField(
        default=dict,
        help_text="Context conditions when this pattern applies (e.g., team size, project type)"
    )
    
    # Success Metrics
    times_used = models.IntegerField(default=0)
    times_successful = models.IntegerField(default=0)
    success_rate = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Ratio of successful resolutions (0.0 - 1.0)"
    )
    avg_effectiveness_rating = models.FloatField(
        default=0.0,
        help_text="Average user effectiveness rating for this pattern"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    # AI Learning
    confidence_boost = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(-50.0), MaxValueValidator(50.0)],
        help_text="Confidence adjustment for AI suggestions based on learning (-50 to +50)"
    )
    
    class Meta:
        unique_together = [['conflict_type', 'resolution_type', 'board']]
        ordering = ['-success_rate', '-times_used']
        indexes = [
            models.Index(fields=['conflict_type', 'resolution_type']),
            models.Index(fields=['-success_rate']),
        ]
    
    def __str__(self):
        board_str = f" on {self.board.name}" if self.board else " (global)"
        return f"{self.get_conflict_type_display()} → {self.get_resolution_type_display()}{board_str} ({self.success_rate:.1%})"
    
    @classmethod
    def learn_from_resolution(cls, conflict, resolution, effectiveness_rating=None):
        """
        Update or create a pattern based on a resolved conflict.
        This is the learning mechanism.
        """
        # Get or create pattern
        pattern, created = cls.objects.get_or_create(
            conflict_type=conflict.conflict_type,
            resolution_type=resolution.resolution_type,
            board=conflict.board,
            defaults={
                'pattern_context': {},
                'times_used': 0,
                'times_successful': 0,
            }
        )
        
        # Update usage count
        pattern.times_used += 1
        pattern.last_used_at = timezone.now()
        
        # Update success metrics
        if effectiveness_rating and effectiveness_rating >= 4:  # 4-5 stars = successful
            pattern.times_successful += 1
        
        # Recalculate success rate
        pattern.success_rate = pattern.times_successful / pattern.times_used if pattern.times_used > 0 else 0.0
        
        # Update average effectiveness rating
        if effectiveness_rating:
            if pattern.avg_effectiveness_rating == 0:
                pattern.avg_effectiveness_rating = effectiveness_rating
            else:
                # Running average
                pattern.avg_effectiveness_rating = (
                    (pattern.avg_effectiveness_rating * (pattern.times_used - 1) + effectiveness_rating)
                    / pattern.times_used
                )
        
        # Calculate confidence boost based on success rate and sample size
        if pattern.times_used >= 5:  # Need minimum data before boosting
            if pattern.success_rate >= 0.8:
                pattern.confidence_boost = min(20.0 + (pattern.times_used * 2), 50.0)
            elif pattern.success_rate >= 0.6:
                pattern.confidence_boost = min(10.0 + pattern.times_used, 30.0)
            elif pattern.success_rate < 0.3:
                pattern.confidence_boost = max(-20.0 - (pattern.times_used * 2), -50.0)
        
        pattern.save()
        return pattern
    
    @classmethod
    def get_confidence_boost(cls, conflict_type, resolution_type, board=None):
        """
        Get the learned confidence boost for a specific resolution type.
        Checks board-specific first, then falls back to global patterns.
        """
        # Try board-specific pattern first
        if board:
            pattern = cls.objects.filter(
                conflict_type=conflict_type,
                resolution_type=resolution_type,
                board=board
            ).first()
            if pattern and pattern.times_used >= 3:
                return pattern.confidence_boost
        
        # Fall back to global pattern
        global_pattern = cls.objects.filter(
            conflict_type=conflict_type,
            resolution_type=resolution_type,
            board__isnull=True
        ).first()
        
        if global_pattern and global_pattern.times_used >= 5:
            return global_pattern.confidence_boost
        
        return 0.0  # No learned pattern yet


class ConflictNotification(models.Model):
    """
    Tracks notifications sent to users about conflicts.
    Prevents spam and ensures users are informed.
    """
    conflict = models.ForeignKey(
        ConflictDetection,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='conflict_notifications'
    )
    
    # Notification Details
    sent_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    acknowledged = models.BooleanField(default=False)
    
    # Notification Channel
    notification_type = models.CharField(
        max_length=20,
        choices=[
            ('in_app', 'In-App Notification'),
            ('email', 'Email'),
            ('both', 'Both'),
        ],
        default='in_app'
    )
    
    class Meta:
        unique_together = [['conflict', 'user']]
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['user', '-sent_at']),
            models.Index(fields=['conflict', 'acknowledged']),
        ]
    
    def __str__(self):
        return f"Notification for {self.user.username} about {self.conflict.title}"
    
    def mark_read(self):
        """Mark notification as read."""
        if not self.read_at:
            self.read_at = timezone.now()
            self.save()
    
    def acknowledge(self):
        """Mark notification as acknowledged."""
        self.acknowledged = True
        self.read_at = timezone.now()
        self.save()
