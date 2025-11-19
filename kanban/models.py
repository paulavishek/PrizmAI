from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from colorfield.fields import ColorField
from accounts.models import Organization
from django.core.validators import MinValueValidator, MaxValueValidator

class Board(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='boards')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_boards')
    members = models.ManyToManyField(User, related_name='member_boards', blank=True)
    
    def __str__(self):
        return self.name

class Column(models.Model):
    name = models.CharField(max_length=100)
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='columns')
    position = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['position']
    
    def __str__(self):
        return f"{self.name} - {self.board.name}"

class TaskLabel(models.Model):
    CATEGORY_CHOICES = [
        ('regular', 'Regular'),
        ('lean', 'Lean Six Sigma'),
    ]
    
    name = models.CharField(max_length=50)
    color = ColorField(default='#FF5733')
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='labels')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='regular')
    
    def __str__(self):
        return self.name

class Task(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    column = models.ForeignKey(Column, on_delete=models.CASCADE, related_name='tasks')
    position = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    start_date = models.DateField(blank=True, null=True, help_text="Task start date for Gantt chart")
    due_date = models.DateTimeField(blank=True, null=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='assigned_tasks', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tasks')
    labels = models.ManyToManyField(TaskLabel, related_name='tasks', blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    progress = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
      # AI Analysis Results
    ai_risk_score = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)],
                                      help_text="AI-calculated risk score (0-100)")
    ai_recommendations = models.TextField(blank=True, null=True, help_text="AI-generated recommendations for this task")
    last_ai_analysis = models.DateTimeField(blank=True, null=True, help_text="When AI last analyzed this task")
    
    # Smart Resource Analysis Fields
    required_skills = models.JSONField(
        default=list,
        blank=True,
        help_text="Required skills for this task (e.g., [{'name': 'Python', 'level': 'Intermediate'}])"
    )
    skill_match_score = models.IntegerField(
        blank=True, 
        null=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="AI-calculated skill match score for assigned user (0-100)"
    )
    optimal_assignee_suggestions = models.JSONField(
        default=list,
        blank=True,
        help_text="AI-suggested optimal assignees with match scores"
    )
    workload_impact = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low Impact'),
            ('medium', 'Medium Impact'),
            ('high', 'High Impact'),
            ('critical', 'Critical Impact'),
        ],
        default='medium',
        blank=True,
        null=True,
        help_text="Impact on assignee's workload"
    )
    resource_conflicts = models.JSONField(
        default=list,
        blank=True,
        help_text="Identified resource conflicts and scheduling issues"
    )
    
    # Enhanced Resource Tracking    
    complexity_score = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Task complexity score (1-10)"  
    )
    collaboration_required = models.BooleanField(
        default=False,
        help_text="Does this task require collaboration with others?"
    )
    suggested_team_members = models.JSONField(
        default=list,
        blank=True,
        help_text="AI-suggested team members for collaborative tasks"
    )
    
    # Risk Management Fields
    risk_likelihood = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(3)],
        choices=[(1, 'Low'), (2, 'Medium'), (3, 'High')],
        help_text="Risk likelihood score (1=Low, 2=Medium, 3=High)"
    )
    risk_impact = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(3)],
        choices=[(1, 'Low'), (2, 'Medium'), (3, 'High')],
        help_text="Risk impact score (1=Low, 2=Medium, 3=High)"
    )
    risk_score = models.IntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1), MaxValueValidator(9)],
        help_text="AI-calculated risk score (Likelihood × Impact, range 1-9)"
    )
    risk_level = models.CharField(
        max_length=10,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical'),
        ],
        blank=True,
        null=True,
        help_text="AI-determined risk level classification"
    )
    risk_indicators = models.JSONField(
        default=list,
        blank=True,
        help_text="Key indicators to monitor for this risk (from AI analysis)"
    )
    mitigation_suggestions = models.JSONField(
        default=list,
        blank=True,
        help_text="AI-generated mitigation strategies and action plans"
    )
    risk_analysis = models.JSONField(
        default=dict,
        blank=True,
        help_text="Complete AI risk analysis including reasoning and factors"
    )
    last_risk_assessment = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When AI last performed risk assessment for this task"
    )
    
    # Task Dependency Management (adapted from ReqManager)
    parent_task = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subtasks',
        help_text="Parent task for this subtask"
    )
    related_tasks = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='related_to',
        help_text="Tasks that are related but not parent-child"
    )
    # Gantt Chart Dependencies (blocking tasks)
    dependencies = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name='dependent_tasks',
        help_text="Tasks that must be completed before this task can start"
    )
    dependency_chain = models.JSONField(
        default=list,
        blank=True,
        help_text="Ordered list of task IDs showing complete dependency chain"
    )
    
    # AI-Generated Dependency Suggestions
    suggested_dependencies = models.JSONField(
        default=list,
        blank=True,
        help_text="AI-suggested task dependencies based on description analysis"
    )
    last_dependency_analysis = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When AI last analyzed this task for dependency suggestions"
    )
    
    # Predictive Task Completion Fields
    completed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Actual completion timestamp (when progress reached 100%)"
    )
    actual_duration_days = models.FloatField(
        blank=True,
        null=True,
        help_text="Actual days taken to complete (start_date to completed_at)"
    )
    predicted_completion_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="AI-predicted completion date based on historical data"
    )
    prediction_confidence = models.FloatField(
        blank=True,
        null=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence score for prediction (0.0-1.0)"
    )
    prediction_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Prediction details: confidence_interval, based_on_tasks, factors"
    )
    last_prediction_update = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When prediction was last calculated"
    )
    
    class Meta:
        ordering = ['position']
        indexes = [
            models.Index(fields=['column', 'position']),
            models.Index(fields=['assigned_to']),
            models.Index(fields=['created_by']),
            models.Index(fields=['due_date']),
            models.Index(fields=['progress']),
            models.Index(fields=['priority']),
        ]
    
    def __str__(self):
        return self.title
    
    def duration_days(self):
        """Calculate task duration in days"""
        if self.start_date and self.due_date:
            # Convert due_date to date if it's datetime
            due = self.due_date.date() if hasattr(self.due_date, 'date') else self.due_date
            return (due - self.start_date).days
        return 0
    
    def get_all_subtasks(self):
        """Get all subtasks recursively"""
        subtasks = list(self.subtasks.all())
        for subtask in subtasks:
            subtasks.extend(subtask.get_all_subtasks())
        return subtasks
    
    def get_all_parent_tasks(self):
        """Get all parent tasks up the hierarchy"""
        parents = []
        current = self.parent_task
        while current:
            parents.append(current)
            current = current.parent_task
        return parents
    
    def get_dependency_level(self):
        """Get the nesting level of this task in the hierarchy"""
        level = 0
        current = self.parent_task
        while current:
            level += 1
            current = current.parent_task
        return level
    
    def has_circular_dependency(self, potential_parent):
        """Check if setting a parent would create a circular dependency"""
        if potential_parent is None:
            return False
        if potential_parent == self:
            return True
        return self in potential_parent.get_all_parent_tasks() or potential_parent in self.get_all_subtasks()
    
    def update_dependency_chain(self):
        """Update the dependency chain based on parent relationships"""
        chain = []
        current = self
        while current:
            chain.insert(0, current.id)
            current = current.parent_task
        self.dependency_chain = chain
        self.save()
    
    def save(self, *args, **kwargs):
        """Override save to track completion and update predictions"""
        # Track completion timestamp
        if self.progress == 100 and not self.completed_at:
            self.completed_at = timezone.now()
            
            # Calculate actual duration if start_date exists
            if self.start_date:
                duration = (self.completed_at.date() - self.start_date).days
                self.actual_duration_days = max(0.5, duration)  # Minimum 0.5 days
        
        # Reset completion if progress drops below 100
        elif self.progress < 100 and self.completed_at:
            self.completed_at = None
            self.actual_duration_days = None
        
        super().save(*args, **kwargs)
    
    def get_velocity_factor(self):
        """Calculate team member's velocity factor based on historical data"""
        if not self.assigned_to:
            return 1.0
        
        from django.db.models import Avg
        
        # Get completed tasks by this user with similar complexity
        completed_tasks = Task.objects.filter(
            assigned_to=self.assigned_to,
            progress=100,
            actual_duration_days__isnull=False,
            complexity_score__range=(max(1, self.complexity_score - 2), 
                                    min(10, self.complexity_score + 2))
        ).exclude(id=self.id)
        
        avg_duration = completed_tasks.aggregate(
            avg=Avg('actual_duration_days')
        )['avg']
        
        if avg_duration and avg_duration > 0:
            # Calculate velocity relative to baseline
            baseline = self.complexity_score * 1.5  # Baseline: 1.5 days per complexity point
            return avg_duration / baseline
        
        return 1.0

class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task', '-created_at']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"Comment by {self.user.username} on {self.task.title}"

class TaskActivity(models.Model):
    ACTIVITY_CHOICES = [
        ('created', 'Created'),
        ('moved', 'Moved'),
        ('assigned', 'Assigned'),
        ('updated', 'Updated'),
        ('commented', 'Commented'),
        ('label_added', 'Label Added'),
        ('label_removed', 'Label Removed'),
    ]
    
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='activities')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_CHOICES)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Task Activities'
        indexes = [
            models.Index(fields=['task', '-created_at']),
            models.Index(fields=['user']),
            models.Index(fields=['activity_type']),
        ]
    
    def __str__(self):
        return f"{self.activity_type} by {self.user.username} on {self.task.title}"

class MeetingTranscript(models.Model):
    MEETING_TYPE_CHOICES = [
        ('standup', 'Daily Standup'),
        ('planning', 'Sprint Planning'),
        ('review', 'Review Meeting'),
        ('retrospective', 'Retrospective'),
        ('general', 'General Meeting'),
    ]
    
    PROCESSING_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    title = models.CharField(max_length=200, help_text="Meeting title or topic")
    meeting_type = models.CharField(max_length=20, choices=MEETING_TYPE_CHOICES, default='general')
    meeting_date = models.DateField(help_text="Date when the meeting occurred")
    transcript_text = models.TextField(help_text="Raw meeting transcript")
    transcript_file = models.FileField(upload_to='meeting_transcripts/', blank=True, null=True, 
                                     help_text="Uploaded transcript file")
    
    # Processing information
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='meeting_transcripts')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='meeting_transcripts')
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    processing_status = models.CharField(max_length=20, choices=PROCESSING_STATUS_CHOICES, default='pending')
    
    # AI extraction results
    extraction_results = models.JSONField(default=dict, blank=True, 
                                        help_text="AI extraction results including tasks and metadata")
    tasks_extracted_count = models.IntegerField(default=0)
    tasks_created_count = models.IntegerField(default=0)
    
    # Meeting context
    participants = models.JSONField(default=list, blank=True, 
                                  help_text="List of meeting participants")
    meeting_context = models.JSONField(default=dict, blank=True,
                                     help_text="Additional meeting context and metadata")
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.title} - {self.meeting_date}"


class ResourceDemandForecast(models.Model):
    """
    Store predictive analytics for team member demand and workload
    Adapted from ResourcePro for PrizmAI's kanban board
    """
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='forecasts')
    forecast_date = models.DateField(auto_now_add=True, help_text="Date when forecast was generated")
    period_start = models.DateField(help_text="Start date of forecast period")
    period_end = models.DateField(help_text="End date of forecast period")
    
    # Resource info
    resource_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demand_forecasts', 
                                     null=True, blank=True)
    resource_role = models.CharField(max_length=100, help_text="Role/Title of the resource")
    
    # Forecast data
    predicted_workload_hours = models.DecimalField(max_digits=8, decimal_places=2, 
                                                   help_text="Predicted hours of work needed")
    available_capacity_hours = models.DecimalField(max_digits=8, decimal_places=2,
                                                  help_text="Available hours in period")
    confidence_score = models.DecimalField(max_digits=3, decimal_places=2, default=0.5,
                                         help_text="Confidence score (0.00-1.00)")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-forecast_date', 'resource_user']
        verbose_name = 'Resource Demand Forecast'
        verbose_name_plural = 'Resource Demand Forecasts'
    
    def __str__(self):
        resource_name = self.resource_user.username if self.resource_user else self.resource_role
        return f"Forecast for {resource_name} - {self.period_start} to {self.period_end}"
    
    @property
    def is_overloaded(self):
        """Check if workload exceeds capacity"""
        return self.predicted_workload_hours > self.available_capacity_hours
    
    @property
    def utilization_percentage(self):
        """Calculate utilization percentage"""
        if self.available_capacity_hours > 0:
            return (self.predicted_workload_hours / self.available_capacity_hours) * 100
        return 0


class TeamCapacityAlert(models.Model):
    """
    Track alerts when team members or team is overloaded
    """
    ALERT_LEVEL_CHOICES = [
        ('warning', 'Warning - 80-100% capacity'),
        ('critical', 'Critical - Over 100% capacity'),
        ('resolved', 'Resolved'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
    ]
    
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='capacity_alerts')
    forecast = models.ForeignKey(ResourceDemandForecast, on_delete=models.CASCADE, 
                                related_name='alerts', null=True, blank=True)
    
    # Alert info
    alert_type = models.CharField(max_length=20, choices=[
        ('individual', 'Individual Overload'),
        ('team', 'Team Overload'),
    ], default='individual')
    alert_level = models.CharField(max_length=20, choices=ALERT_LEVEL_CHOICES, default='warning')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Context
    resource_user = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='capacity_alerts',
                                     null=True, blank=True, help_text="User who is overloaded")
    message = models.TextField(help_text="Alert message with details")
    workload_percentage = models.IntegerField(default=0, help_text="Current utilization percentage")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(blank=True, null=True)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='acknowledged_alerts',
                                       null=True, blank=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        resource_name = self.resource_user.username if self.resource_user else 'Team'
        return f"{self.get_alert_type_display()} Alert for {resource_name} - {self.get_alert_level_display()}"


class WorkloadDistributionRecommendation(models.Model):
    """
    AI-generated recommendations for optimal workload distribution
    """
    RECOMMENDATION_TYPE_CHOICES = [
        ('reassign', 'Task Reassignment'),
        ('defer', 'Defer/Postpone'),
        ('distribute', 'Distribute to Multiple'),
        ('hire', 'Hire/Allocate Resource'),
        ('optimize', 'Optimize Timeline'),
    ]
    
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='distribution_recommendations')
    forecast = models.ForeignKey(ResourceDemandForecast, on_delete=models.CASCADE,
                                related_name='recommendations', null=True, blank=True)
    
    recommendation_type = models.CharField(max_length=20, choices=RECOMMENDATION_TYPE_CHOICES)
    priority = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(10)],
                                  help_text="Priority (1=low, 10=high)")
    
    # Recommendation details
    title = models.CharField(max_length=200, help_text="Short title of recommendation")
    description = models.TextField(help_text="Detailed recommendation description")
    affected_tasks = models.ManyToManyField(Task, related_name='distribution_recommendations', blank=True)
    affected_users = models.ManyToManyField(User, related_name='distribution_recommendations', blank=True)
    
    # Impact metrics
    expected_capacity_savings_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                                                         help_text="Hours this recommendation could save")
    confidence_score = models.DecimalField(max_digits=3, decimal_places=2, default=0.75,
                                         help_text="Confidence in recommendation (0-1)")
    
    # Status
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', 'Pending Review'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('implemented', 'Implemented'),
    ])
    
    created_at = models.DateTimeField(auto_now_add=True)
    implemented_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-priority', '-created_at']
    
    def __str__(self):
        return f"{self.get_recommendation_type_display()}: {self.title}"


class TaskFile(models.Model):
    """File attachments for tasks"""
    ALLOWED_FILE_TYPES = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'jpg', 'jpeg', 'png']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='file_attachments')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_file_uploads')
    file = models.FileField(upload_to='tasks/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField(help_text="File size in bytes")
    file_type = models.CharField(max_length=10, help_text="File extension")
    description = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(blank=True, null=True)  # Soft delete
    
    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['task', 'uploaded_at']),
            models.Index(fields=['uploaded_by', 'uploaded_at']),
        ]
    
    def __str__(self):
        return f"{self.filename} for {self.task.title}"
    
    def is_deleted(self):
        """Check if file is soft-deleted"""
        return self.deleted_at is not None
    
    def get_file_icon(self):
        """Get Bootstrap icon class based on file type"""
        icon_map = {
            'pdf': 'fa-file-pdf',
            'doc': 'fa-file-word',
            'docx': 'fa-file-word',
            'xls': 'fa-file-excel',
            'xlsx': 'fa-file-excel',
            'ppt': 'fa-file-powerpoint',
            'pptx': 'fa-file-powerpoint',
            'jpg': 'fa-file-image',
            'jpeg': 'fa-file-image',
            'png': 'fa-file-image',
        }
        return icon_map.get(self.file_type.lower(), 'fa-file')
    
    @staticmethod
    def is_valid_file_type(filename):
        """Validate file type"""
        ext = filename.split('.')[-1].lower()
        return ext in TaskFile.ALLOWED_FILE_TYPES


class TeamSkillProfile(models.Model):
    """
    Aggregated skill inventory for a team/board
    Provides high-level view of available skills and capacity
    """
    board = models.OneToOneField(Board, on_delete=models.CASCADE, related_name='skill_profile')
    
    # Aggregate skill data
    skill_inventory = models.JSONField(
        default=dict,
        help_text="Dictionary of available skills: {'Python': {'expert': 2, 'intermediate': 3, 'beginner': 1}}"
    )
    total_capacity_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Total team capacity in hours per week"
    )
    utilized_capacity_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Currently utilized hours"
    )
    
    # Metadata
    last_updated = models.DateTimeField(auto_now=True)
    last_analysis = models.DateTimeField(blank=True, null=True, help_text="Last AI skill analysis timestamp")
    
    class Meta:
        verbose_name = 'Team Skill Profile'
        verbose_name_plural = 'Team Skill Profiles'
    
    def __str__(self):
        return f"Skill Profile for {self.board.name}"
    
    @property
    def utilization_percentage(self):
        """Calculate team utilization"""
        if self.total_capacity_hours == 0:
            return 0
        return min(100, (self.utilized_capacity_hours / self.total_capacity_hours) * 100)
    
    @property
    def available_skills(self):
        """Get list of all available skill names"""
        return list(self.skill_inventory.keys())


class SkillGap(models.Model):
    """
    Identified skill gaps between required and available skills
    AI-calculated with recommendations for remediation
    """
    GAP_SEVERITY_CHOICES = [
        ('low', 'Low - Can work around'),
        ('medium', 'Medium - May cause delays'),
        ('high', 'High - Blocking work'),
        ('critical', 'Critical - Cannot proceed'),
    ]
    
    GAP_STATUS_CHOICES = [
        ('identified', 'Identified'),
        ('acknowledged', 'Acknowledged'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('accepted', 'Accepted Risk'),
    ]
    
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='skill_gaps')
    
    # Gap details
    skill_name = models.CharField(max_length=100, help_text="Name of the missing/insufficient skill")
    proficiency_level = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('expert', 'Expert'),
        ],
        help_text="Required proficiency level"
    )
    required_count = models.IntegerField(default=1, help_text="Number of team members needed with this skill")
    available_count = models.IntegerField(default=0, help_text="Number of team members currently with this skill")
    gap_count = models.IntegerField(help_text="Difference between required and available (auto-calculated)")
    
    # Context
    severity = models.CharField(max_length=20, choices=GAP_SEVERITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=GAP_STATUS_CHOICES, default='identified')
    
    # Associated data
    affected_tasks = models.ManyToManyField(Task, related_name='skill_gaps', blank=True,
                                           help_text="Tasks that require this skill")
    sprint_period_start = models.DateField(blank=True, null=True, help_text="Sprint/period when gap was identified")
    sprint_period_end = models.DateField(blank=True, null=True)
    
    # AI Analysis
    ai_recommendations = models.JSONField(
        default=list,
        help_text="AI-generated recommendations: [{'type': 'hire', 'details': '...', 'priority': 1}]"
    )
    estimated_impact_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Estimated hours of delay/impact if not addressed"
    )
    confidence_score = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.75,
        help_text="AI confidence in this gap analysis (0-1)"
    )
    
    # Tracking
    identified_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='acknowledged_skill_gaps')
    
    class Meta:
        ordering = ['-severity', '-identified_at']
        verbose_name = 'Skill Gap'
        verbose_name_plural = 'Skill Gaps'
        indexes = [
            models.Index(fields=['board', 'status']),
            models.Index(fields=['skill_name', 'proficiency_level']),
        ]
    
    def __str__(self):
        return f"{self.skill_name} ({self.proficiency_level}) - Gap: {self.gap_count} - {self.board.name}"
    
    def save(self, *args, **kwargs):
        """Auto-calculate gap_count on save"""
        self.gap_count = max(0, self.required_count - self.available_count)
        super().save(*args, **kwargs)
    
    @property
    def is_critical(self):
        """Check if this is a critical gap"""
        return self.severity in ['high', 'critical'] or self.gap_count >= 2
    
    @property
    def gap_percentage(self):
        """Calculate gap as percentage of requirement"""
        if self.required_count == 0:
            return 0
        return (self.gap_count / self.required_count) * 100


class SkillDevelopmentPlan(models.Model):
    """
    Track training and skill development initiatives to address gaps
    Includes hiring, training, and work redistribution plans
    """
    PLAN_TYPE_CHOICES = [
        ('training', 'Training/Upskilling'),
        ('hiring', 'Hire New Resource'),
        ('contractor', 'Contract Resource'),
        ('redistribute', 'Redistribute Work'),
        ('mentorship', 'Mentorship Program'),
        ('cross_training', 'Cross Training'),
    ]
    
    PLAN_STATUS_CHOICES = [
        ('proposed', 'Proposed'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    skill_gap = models.ForeignKey(SkillGap, on_delete=models.CASCADE, related_name='development_plans')
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='skill_development_plans')
    
    # Plan details
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPE_CHOICES)
    title = models.CharField(max_length=200, help_text="Brief title of the development plan")
    description = models.TextField(help_text="Detailed plan description and action steps")
    
    # Targets
    target_users = models.ManyToManyField(User, related_name='skill_development_plans', blank=True,
                                         help_text="Team members involved in this plan")
    target_skill = models.CharField(max_length=100, help_text="Skill being developed")
    target_proficiency = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('expert', 'Expert'),
        ]
    )
    
    # Timeline and budget
    start_date = models.DateField(blank=True, null=True)
    target_completion_date = models.DateField(blank=True, null=True)
    actual_completion_date = models.DateField(blank=True, null=True)
    estimated_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True,
                                        help_text="Estimated cost (training fees, hiring budget, etc.)")
    estimated_hours = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True,
                                         help_text="Estimated hours investment")
    
    # Status and progress
    status = models.CharField(max_length=20, choices=PLAN_STATUS_CHOICES, default='proposed')
    progress_percentage = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Impact tracking
    expected_impact = models.TextField(blank=True, help_text="Expected impact on team capability")
    actual_impact = models.TextField(blank=True, help_text="Measured impact after completion")
    success_metrics = models.JSONField(
        default=list,
        blank=True,
        help_text="Metrics to track success: [{'metric': 'Tasks completed', 'target': 5, 'actual': 3}]"
    )
    
    # Ownership
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_development_plans')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='owned_development_plans',
                                   help_text="Person responsible for executing this plan")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # AI-generated recommendations
    ai_suggested = models.BooleanField(default=False, help_text="Was this plan AI-generated?")
    ai_confidence = models.DecimalField(max_digits=3, decimal_places=2, blank=True, null=True,
                                       help_text="AI confidence in this recommendation (0-1)")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Skill Development Plan'
        verbose_name_plural = 'Skill Development Plans'
        indexes = [
            models.Index(fields=['board', 'status']),
            models.Index(fields=['skill_gap']),
        ]
    
    def __str__(self):
        return f"{self.get_plan_type_display()}: {self.title}"
    
    @property
    def is_overdue(self):
        """Check if plan is overdue"""
        if self.target_completion_date and self.status not in ['completed', 'cancelled']:
            from django.utils import timezone
            return timezone.now().date() > self.target_completion_date
        return False
    
    @property
    def days_until_target(self):
        """Calculate days until target completion"""
        if self.target_completion_date:
            from django.utils import timezone
            delta = self.target_completion_date - timezone.now().date()
            return delta.days
        return None


# Import security and permission models to register them with Django
from .audit_models import SystemAuditLog, SecurityEvent, DataAccessLog
from .permission_models import Role, BoardMembership, PermissionOverride, ColumnPermission
