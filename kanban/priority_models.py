"""
Priority Decision Tracking Models
Tracks priority assignments and corrections for ML learning
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from kanban.models import Task, Board


class PriorityDecision(models.Model):
    """
    Track priority assignments and corrections to train AI model
    Learns from team's historical priority decisions
    """
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    DECISION_TYPE_CHOICES = [
        ('initial', 'Initial Assignment'),
        ('correction', 'Manual Correction'),
        ('ai_suggestion', 'AI Suggested'),
        ('ai_accepted', 'AI Suggestion Accepted'),
        ('ai_rejected', 'AI Suggestion Rejected'),
    ]
    
    # Core fields
    task = models.ForeignKey(
        Task, 
        on_delete=models.CASCADE, 
        related_name='priority_decisions',
        help_text="Task this decision is for"
    )
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name='priority_decisions',
        help_text="Board for organizational filtering"
    )
    
    # Priority decision
    suggested_priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        null=True,
        blank=True,
        help_text="AI-suggested priority (null for manual decisions)"
    )
    actual_priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        help_text="Priority that was actually assigned"
    )
    previous_priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        null=True,
        blank=True,
        help_text="Previous priority (for corrections)"
    )
    
    # Decision metadata
    decision_type = models.CharField(
        max_length=20,
        choices=DECISION_TYPE_CHOICES,
        default='initial',
        help_text="Type of priority decision"
    )
    decided_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='priority_decisions',
        help_text="User who made this decision"
    )
    decided_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When decision was made"
    )
    
    # Context at time of decision (snapshot for training)
    task_context = models.JSONField(
        default=dict,
        help_text="Task features at decision time: due_date, dependencies, etc."
    )
    
    # AI confidence (if applicable)
    confidence_score = models.FloatField(
        null=True,
        blank=True,
        help_text="AI confidence in suggestion (0.0-1.0)"
    )
    reasoning = models.JSONField(
        default=dict,
        blank=True,
        help_text="AI reasoning for the suggestion"
    )
    
    # Feedback tracking
    was_correct = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether AI suggestion was accepted (null for manual decisions)"
    )
    feedback_notes = models.TextField(
        blank=True,
        help_text="Optional user feedback on why they accepted/rejected"
    )
    
    class Meta:
        ordering = ['-decided_at']
        indexes = [
            models.Index(fields=['task', '-decided_at']),
            models.Index(fields=['board', '-decided_at']),
            models.Index(fields=['decided_by', '-decided_at']),
            models.Index(fields=['decision_type']),
            models.Index(fields=['was_correct']),
        ]
    
    def __str__(self):
        return f"{self.task.title} - {self.actual_priority} ({self.get_decision_type_display()})"
    
    @classmethod
    def log_decision(cls, task, priority, user, decision_type='initial', 
                    suggested_priority=None, confidence=None, reasoning=None,
                    previous_priority=None):
        """
        Convenience method to log a priority decision
        
        Args:
            task: Task object
            priority: Actual priority assigned
            user: User making the decision
            decision_type: Type of decision
            suggested_priority: AI suggested priority (if any)
            confidence: AI confidence score
            reasoning: AI reasoning dict
            previous_priority: Previous priority (for corrections)
        """
        # Capture task context at decision time
        task_context = cls._capture_task_context(task)
        
        # Determine if suggestion was correct
        was_correct = None
        if suggested_priority:
            was_correct = (suggested_priority == priority)
        
        return cls.objects.create(
            task=task,
            board=task.column.board,
            suggested_priority=suggested_priority,
            actual_priority=priority,
            previous_priority=previous_priority,
            decision_type=decision_type,
            decided_by=user,
            task_context=task_context,
            confidence_score=confidence,
            reasoning=reasoning or {},
            was_correct=was_correct
        )
    
    @staticmethod
    def _capture_task_context(task):
        """Capture relevant task features for training"""
        from datetime import datetime
        
        # Calculate days until due
        days_until_due = None
        if task.due_date:
            delta = task.due_date - timezone.now()
            days_until_due = delta.total_seconds() / 86400  # Convert to days
        
        # Count dependencies
        blocking_count = task.dependencies.count()
        blocked_by_count = task.dependent_tasks.count()
        
        # Get assignee workload
        assignee_workload = 0
        if task.assigned_to:
            assignee_workload = Task.objects.filter(
                assigned_to=task.assigned_to,
                progress__lt=100
            ).exclude(
                column__name__icontains='done'
            ).count()
        
        # Get team capacity
        board = task.column.board
        team_size = board.members.count()
        total_open_tasks = Task.objects.filter(
            column__board=board,
            progress__lt=100
        ).exclude(
            column__name__icontains='done'
        ).count()
        
        return {
            'title_length': len(task.title),
            'has_description': bool(task.description),
            'description_length': len(task.description or ''),
            'days_until_due': round(days_until_due, 2) if days_until_due else None,
            'is_overdue': days_until_due < 0 if days_until_due else False,
            'complexity_score': task.complexity_score,
            'blocking_count': blocking_count,
            'blocked_by_count': blocked_by_count,
            'has_assignee': task.assigned_to is not None,
            'assignee_workload': assignee_workload,
            'team_capacity': {
                'team_size': team_size,
                'total_open_tasks': total_open_tasks,
                'tasks_per_member': round(total_open_tasks / team_size, 1) if team_size > 0 else 0
            },
            'collaboration_required': task.collaboration_required,
            'risk_score': task.risk_score,
            'has_subtasks': task.subtasks.exists(),
            'is_subtask': task.parent_task is not None,
            'label_count': task.labels.count(),
            'comment_count': task.comments.count(),
            'created_at': task.created_at.isoformat(),
            'updated_at': task.updated_at.isoformat(),
            'snapshot_time': timezone.now().isoformat()
        }


class PriorityModel(models.Model):
    """
    Store trained priority classification models per board/organization
    """
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name='priority_models',
        help_text="Board this model is trained for"
    )
    
    # Model metadata
    model_version = models.IntegerField(
        default=1,
        help_text="Version number of this model"
    )
    model_type = models.CharField(
        max_length=50,
        default='random_forest',
        help_text="Type of ML model used"
    )
    
    # Model file storage (pickle)
    model_file = models.BinaryField(
        help_text="Serialized model (pickle)"
    )
    feature_importance = models.JSONField(
        default=dict,
        help_text="Feature importance scores for explainability"
    )
    
    # Training metadata
    trained_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When model was trained"
    )
    training_samples = models.IntegerField(
        help_text="Number of samples used for training"
    )
    accuracy_score = models.FloatField(
        help_text="Model accuracy on test set"
    )
    
    # Performance metrics
    precision_scores = models.JSONField(
        default=dict,
        help_text="Precision per priority class"
    )
    recall_scores = models.JSONField(
        default=dict,
        help_text="Recall per priority class"
    )
    f1_scores = models.JSONField(
        default=dict,
        help_text="F1 scores per priority class"
    )
    confusion_matrix = models.JSONField(
        default=list,
        help_text="Confusion matrix for model evaluation"
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Is this the active model for predictions?"
    )
    
    class Meta:
        ordering = ['-trained_at']
        unique_together = ['board', 'model_version']
        indexes = [
            models.Index(fields=['board', 'is_active']),
        ]
    
    def __str__(self):
        return f"Priority Model v{self.model_version} for {self.board.name} - {self.accuracy_score:.2%}"
    
    @classmethod
    def get_active_model(cls, board):
        """Get the active priority model for a board"""
        return cls.objects.filter(board=board, is_active=True).first()


class PrioritySuggestionLog(models.Model):
    """
    Log all priority suggestions made to track usage and effectiveness
    """
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='priority_suggestions'
    )
    model = models.ForeignKey(
        PriorityModel,
        on_delete=models.SET_NULL,
        null=True,
        related_name='suggestions'
    )
    
    # Suggestion details
    suggested_priority = models.CharField(max_length=10)
    confidence_score = models.FloatField()
    reasoning = models.JSONField(default=dict)
    feature_values = models.JSONField(
        default=dict,
        help_text="Feature values used for prediction"
    )
    
    # User interaction
    shown_to_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='priority_suggestions_received'
    )
    shown_at = models.DateTimeField(auto_now_add=True)
    
    user_action = models.CharField(
        max_length=20,
        choices=[
            ('accepted', 'Accepted'),
            ('rejected', 'Rejected'),
            ('modified', 'Modified'),
            ('ignored', 'Ignored'),
        ],
        null=True,
        blank=True,
        help_text="How user responded to suggestion"
    )
    actual_priority = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="Priority user actually chose"
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-shown_at']
        indexes = [
            models.Index(fields=['task', '-shown_at']),
            models.Index(fields=['model', '-shown_at']),
            models.Index(fields=['user_action']),
        ]
    
    def __str__(self):
        return f"Suggestion for {self.task.title}: {self.suggested_priority} ({self.confidence_score:.2%})"
