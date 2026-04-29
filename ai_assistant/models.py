from django.db import models
from django.contrib.auth.models import User
from kanban.models import Board, Task
from django.utils import timezone
from accounts.models import Organization


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
    question_count = models.IntegerField(default=0, help_text="Number of original user questions (excluding follow-ups in multi-step flows)")
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
        ordering = ['id']
    
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


class SpectraConversationState(models.Model):
    """
    Tracks conversation state for Spectra's action-capable flows.
    One state record per user per board. When a flow completes or is
    cancelled, mode resets to 'normal' and collected_data is cleared.
    """
    MODE_CHOICES = [
        ('normal', 'Normal Q&A'),
        ('collecting_task', 'Collecting task details'),
        ('collecting_board', 'Collecting board details'),
        ('collecting_automation', 'Collecting automation selection'),
        ('collecting_message', 'Collecting message details'),
        ('collecting_time_entry', 'Collecting time entry details'),
        ('collecting_event', 'Collecting event details'),
        ('collecting_retrospective', 'Collecting retrospective details'),
        ('collecting_task_update', 'Collecting task update details'),
        ('collecting_preset', 'Collecting workspace preset preference'),
        ('awaiting_confirmation', 'Awaiting user confirmation'),
    ]
    PENDING_ACTION_CHOICES = [
        ('', 'None'),
        ('create_task', 'Create Task'),
        ('create_board', 'Create Board'),
        ('activate_automation', 'Activate Automation'),
        ('send_message', 'Send Message'),
        ('log_time', 'Log Time'),
        ('schedule_event', 'Schedule Event'),
        ('create_retrospective', 'Create Retrospective'),
        ('create_custom_automation', 'Create Custom Automation'),
        ('create_scheduled_automation', 'Create Scheduled Automation'),
        ('update_task', 'Update Task'),
        ('get_commitment_status', 'Get Commitment Status'),
        ('list_at_risk_commitments', 'List At-Risk Commitments'),
        ('place_commitment_bet', 'Place Commitment Bet'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='spectra_conversation_states',
    )
    board = models.ForeignKey(
        'kanban.Board', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='spectra_conversation_states',
    )
    mode = models.CharField(max_length=50, choices=MODE_CHOICES, default='normal')
    collected_data = models.JSONField(default=dict, blank=True)
    pending_action = models.CharField(
        max_length=50, choices=PENDING_ACTION_CHOICES, blank=True, default='',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'board']

    def __str__(self):
        board_name = self.board.name if self.board else 'No board'
        return f'{self.user.username} | {board_name} | {self.mode}'

    def reset(self):
        """Reset state back to normal Q&A mode."""
        self.mode = 'normal'
        self.collected_data = {}
        self.pending_action = ''
        self.save(update_fields=['mode', 'collected_data', 'pending_action', 'updated_at'])


# ============================================================
# AI PROVIDER SETTINGS — ORGANISATION LEVEL
# ============================================================

# RBAC RULES — AI Provider Settings (Organisation Level)
# - View active provider: All roles (Viewer, Member, Owner, Org Admin)
# - Change org-wide provider: Org Admin only
# - Enter or remove org BYOK key: Org Admin only
# - Change allow_user_provider_override: Org Admin only
# - View key_last_four for display: Org Admin only

PROVIDER_CHOICES = [
    ('gemini', 'Google Gemini'),
    ('openai', 'OpenAI'),
    ('anthropic', 'Anthropic Claude'),
]


class OrganizationAISettings(models.Model):
    """
    Stores the organisation-wide AI provider configuration.

    One record per organisation (OneToOne). Controls which AI provider
    all users in the organisation use by default, whether users may
    override it, and optionally holds an organisation-level BYOK API key
    (stored encrypted — never plain text).

    These settings are managed by an Org Admin. See the RBAC comment
    block above for the full access rules enforced in views and the router.
    """

    organisation = models.OneToOneField(
        Organization,
        on_delete=models.CASCADE,
        related_name='ai_settings',
    )

    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default='gemini',
        help_text=(
            "Organisation-wide active AI provider. Applies to all users "
            "unless overridden (when allow_user_provider_override is True)."
        ),
    )

    allow_user_provider_override = models.BooleanField(
        default=False,
        help_text=(
            "When True, Members and Owners may set their own personal provider "
            "preference. When False, everyone uses the org-wide provider. "
            "Only an Org Admin can change this field."
        ),
    )

    byok_provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        null=True,
        blank=True,
        help_text="Which provider the stored BYOK key belongs to.",
    )

    # ============================================================
    # SECURITY: encrypted_api_key MUST NEVER store a plain-text key.
    # Always encrypt with Fernet (AES-256) via AIRouter._encrypt_key()
    # before saving, and decrypt with AIRouter._decrypt_key() before use.
    # Storing a raw API key here is a critical security violation.
    # ============================================================
    encrypted_api_key = models.TextField(
        null=True,
        blank=True,
        help_text=(
            "Fernet-encrypted organisation BYOK API key. "
            "NEVER store plain text here. Use AIRouter._encrypt_key() to write "
            "and AIRouter._decrypt_key() to read."
        ),
    )

    key_last_four = models.CharField(
        max_length=8,
        null=True,
        blank=True,
        help_text=(
            "Last few visible characters of the BYOK key for safe UI display "
            "(e.g. '••••1a3f'). Never store more than this."
        ),
    )

    key_validated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the BYOK key was last successfully validated.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='org_ai_settings_changes',
        help_text="Org Admin who last changed these settings.",
    )

    class Meta:
        verbose_name = 'Organisation AI Settings'
        verbose_name_plural = 'Organisation AI Settings'

    def __str__(self):
        return f"AI Settings for {self.organisation.name} — {self.provider}"


# ============================================================
# AI PROVIDER SETTINGS — USER LEVEL
# ============================================================

# RBAC RULES — AI Provider Settings (User Level)
# - Set provider_override: Member, Owner, Org Admin
#   BUT this is only respected by the router if org.allow_user_provider_override is True.
#   Org Admins can always override regardless of the flag.
# - Enter or remove personal BYOK key: Member, Owner, Org Admin (always permitted —
#   personal BYOK is the user's own key and their own cost).
# - Viewers cannot change any AI settings.

USER_PROVIDER_CHOICES = [
    ('inherit', 'Inherit from Organisation'),
    ('gemini', 'Google Gemini'),
    ('openai', 'OpenAI'),
    ('anthropic', 'Anthropic Claude'),
]


class UserAISettings(models.Model):
    """
    Stores an individual user's personal AI provider preference.

    One record per user (OneToOne). A user may choose a different provider
    from the organisation default — but only when the organisation's
    allow_user_provider_override is True (or the user is an Org Admin).

    Users may always store their own personal BYOK key regardless of the
    override flag — it is their own key on their own bill.

    NOTE: Records in this table start empty (no record = use org/Gemini defaults).
    The AIRouter handles UserAISettings.DoesNotExist gracefully at every point.
    See the RBAC comment block above for the full access rules.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='ai_settings',
    )

    provider_override = models.CharField(
        max_length=20,
        choices=USER_PROVIDER_CHOICES,
        default='inherit',
        help_text=(
            "User's preferred provider. 'inherit' means follow the org-wide setting. "
            "Other values are respected only if org.allow_user_provider_override is True, "
            "or this user is an Org Admin."
        ),
    )

    byok_provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        null=True,
        blank=True,
        help_text="Which provider the user's personal BYOK key belongs to.",
    )

    # ============================================================
    # SECURITY: encrypted_api_key MUST NEVER store a plain-text key.
    # Always encrypt with Fernet (AES-256) via AIRouter._encrypt_key()
    # before saving, and decrypt with AIRouter._decrypt_key() before use.
    # Storing a raw API key here is a critical security violation.
    # ============================================================
    encrypted_api_key = models.TextField(
        null=True,
        blank=True,
        help_text=(
            "Fernet-encrypted personal BYOK API key. "
            "NEVER store plain text here. Use AIRouter._encrypt_key() to write "
            "and AIRouter._decrypt_key() to read."
        ),
    )

    key_last_four = models.CharField(
        max_length=8,
        null=True,
        blank=True,
        help_text=(
            "Last few visible characters of the personal BYOK key for safe UI display "
            "(e.g. '••••1a3f'). Never store more than this."
        ),
    )

    key_validated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the personal BYOK key was last successfully validated.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User AI Settings'
        verbose_name_plural = 'User AI Settings'

    def __str__(self):
        return f"AI Settings for {self.user.username} — {self.provider_override}"
