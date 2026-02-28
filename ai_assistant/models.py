from django.db import models
from django.contrib.auth.models import User
from kanban.models import Board, Task
from django.utils import timezone


class AIAssistantSession(models.Model):
    """
    Represents a conversation session with the AI Project Assistant
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_sessions')
    board = models.ForeignKey(Board, on_delete=models.SET_NULL, null=True, blank=True, 
                             related_name='ai_sessions', help_text="Board context for this session")
    
    title = models.CharField(max_length=200, help_text="Session title/topic")
    description = models.TextField(blank=True, null=True, help_text="Session description")
    
    is_active = models.BooleanField(default=True, help_text="Is this session currently active?")
    is_demo = models.BooleanField(default=False, help_text="Is this a demo/example session visible to all users?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Session metadata
    message_count = models.IntegerField(default=0, help_text="Total messages in this session")
    total_tokens_used = models.IntegerField(default=0, help_text="Total tokens used in this session")
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"


class AIAssistantMessage(models.Model):
    """
    Individual messages in an AI Assistant conversation
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]
    
    MODEL_CHOICES = [
        ('gemini', 'Google Gemini'),
        ('system', 'System'),
    ]
    
    session = models.ForeignKey(AIAssistantSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    
    # Model information
    model = models.CharField(max_length=20, choices=MODEL_CHOICES, null=True, blank=True)
    tokens_used = models.IntegerField(default=0)
    
    # Message metadata
    is_starred = models.BooleanField(default=False, help_text="Is message starred by user?")
    is_helpful = models.BooleanField(null=True, blank=True, help_text="User feedback on helpfulness")
    feedback = models.TextField(blank=True, null=True, help_text="User feedback text")
    
    # Search-related fields
    used_web_search = models.BooleanField(default=False, help_text="Was web search used?")
    search_sources = models.JSONField(default=list, blank=True, help_text="Sources from web search")
    
    # Context tracking
    context_data = models.JSONField(default=dict, blank=True, help_text="Context used to generate response")

    # File attachment reference (optional — set when a file was analysed in this turn)
    attachment = models.ForeignKey(
        'AIAssistantAttachment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='messages',
        help_text='File attachment that was analysed in this message turn',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at', 'id']
    
    def __str__(self):
        preview = self.content[:50] + '...' if len(self.content) > 50 else self.content
        return f"{self.role}: {preview}"


class ProjectKnowledgeBase(models.Model):
    """
    Stores indexed information about projects for RAG system
    """
    CONTENT_TYPE_CHOICES = [
        ('project_overview', 'Project Overview'),
        ('task_description', 'Task Description'),
        ('meeting_notes', 'Meeting Notes'),
        ('documentation', 'Documentation'),
        ('risk_assessment', 'Risk Assessment'),
        ('resource_plan', 'Resource Plan'),
    ]
    
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='knowledge_base')
    content_type = models.CharField(max_length=30, choices=CONTENT_TYPE_CHOICES)
    
    # Content
    title = models.CharField(max_length=300, help_text="Title of the content")
    content = models.TextField(help_text="Full content for indexing")
    summary = models.TextField(blank=True, null=True, help_text="AI-generated summary")
    
    # Source tracking
    source_task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True,
                                   help_text="Related task if applicable")
    source_url = models.URLField(blank=True, null=True, help_text="External source URL if applicable")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_indexed = models.DateTimeField(auto_now=True)
    
    is_active = models.BooleanField(default=True, help_text="Is this KB entry active?")
    
    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'Project Knowledge Base'
        verbose_name_plural = 'Project Knowledge Bases'
    
    def __str__(self):
        return f"{self.title} ({self.get_content_type_display()})"


class AIAssistantAnalytics(models.Model):
    """
    Track usage analytics for AI Assistant
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ai_analytics')
    board = models.ForeignKey(Board, on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='ai_analytics')
    date = models.DateField(auto_now_add=True, help_text="Analytics date")
    
    # Usage metrics
    sessions_created = models.IntegerField(default=0)
    messages_sent = models.IntegerField(default=0)
    gemini_requests = models.IntegerField(default=0)
    
    # Search metrics
    web_searches_performed = models.IntegerField(default=0)
    knowledge_base_queries = models.IntegerField(default=0)
    
    # Token tracking
    total_tokens_used = models.IntegerField(default=0)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    
    # Quality metrics
    helpful_responses = models.IntegerField(default=0)
    unhelpful_responses = models.IntegerField(default=0)
    avg_response_time_ms = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'AI Assistant Analytics'
        verbose_name_plural = 'AI Assistant Analytics'
        unique_together = ['user', 'board', 'date']
    
    def __str__(self):
        return f"Analytics for {self.user.username} - {self.date}"


class AITaskRecommendation(models.Model):
    """
    AI-generated recommendations for project tasks
    """
    RECOMMENDATION_TYPE_CHOICES = [
        ('optimization', 'Optimization Suggestion'),
        ('risk_mitigation', 'Risk Mitigation'),
        ('resource_allocation', 'Resource Allocation'),
        ('dependency', 'Dependency Issue'),
        ('priority', 'Priority Adjustment'),
        ('timeline', 'Timeline Optimization'),
    ]
    
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='task_ai_recommendations')
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='task_recommendations')
    
    recommendation_type = models.CharField(max_length=30, choices=RECOMMENDATION_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Impact assessment
    potential_impact = models.CharField(max_length=20, choices=[
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], default='medium')
    confidence_score = models.DecimalField(max_digits=3, decimal_places=2, default=0.75)
    
    # Action items
    suggested_action = models.TextField(help_text="Recommended action")
    expected_benefit = models.TextField(help_text="Expected benefit if implemented")
    
    # Status
    status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', 'Pending Review'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('implemented', 'Implemented'),
    ])
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    implemented_at = models.DateTimeField(null=True, blank=True)
    implementation_notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_recommendation_type_display()}: {self.title}"


class UserPreference(models.Model):
    """
    Store user preferences for AI Assistant
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='ai_preferences')
    
    # Feature preferences
    enable_web_search = models.BooleanField(default=True)
    enable_task_insights = models.BooleanField(default=True)
    enable_risk_alerts = models.BooleanField(default=True)
    enable_resource_recommendations = models.BooleanField(default=True)
    
    # Notification preferences
    notify_on_risk = models.BooleanField(default=True)
    notify_on_overload = models.BooleanField(default=True)
    notify_on_dependency_issues = models.BooleanField(default=False)
    
    # Display preferences
    messages_per_page = models.IntegerField(default=20)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Preference'
        verbose_name_plural = 'User Preferences'
    
    def __str__(self):
        return f"Preferences for {self.user.username}"


class AIAssistantAttachment(models.Model):
    """
    File attachment uploaded to a Spectra (AI Assistant) session.
    The extracted text is cached at upload time so subsequent questions
    in the same session can reference the document without re-parsing.
    """
    ALLOWED_FILE_TYPES = ['pdf', 'docx', 'doc', 'txt']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    session = models.ForeignKey(
        AIAssistantSession,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ai_assistant_uploads',
    )
    file = models.FileField(upload_to='ai_assistant/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField(help_text='File size in bytes')
    file_type = models.CharField(max_length=10, help_text='File extension without dot')

    # Cached extraction — populated at upload time
    extracted_text = models.TextField(
        blank=True,
        default='',
        help_text='Text extracted from the file at upload time',
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.filename} (session {self.session_id})'

    def is_valid_type(self):
        return self.file_type.lower() in self.ALLOWED_FILE_TYPES
