from django.db import models
from django.contrib.auth.models import User
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
    
    class Meta:
        ordering = ['position']
    
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

class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
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
