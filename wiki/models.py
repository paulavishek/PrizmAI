from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from kanban.models import Board, Task
from accounts.models import Organization
import markdown
from django.utils.safestring import mark_safe


class WikiCategory(models.Model):
    """Categories for organizing wiki pages"""
    
    # AI Assistant Type Choices
    AI_ASSISTANT_CHOICES = [
        ('meeting', 'Meeting Analysis - For meeting notes, standups, sprint planning'),
        ('documentation', 'Documentation Assistant - For guides, references, tutorials'),
        ('none', 'No AI Assistant - Disable AI features for this category'),
    ]
    
    name = models.CharField(max_length=100)
    slug = models.SlugField()
    description = models.TextField(blank=True, null=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='wiki_categories')
    icon = models.CharField(max_length=50, default='folder', help_text='Font Awesome icon name')
    color = models.CharField(max_length=7, default='#3498db', help_text='Hex color code')
    position = models.IntegerField(default=0)
    ai_assistant_type = models.CharField(
        max_length=20, 
        choices=AI_ASSISTANT_CHOICES, 
        default='documentation',
        help_text='Which AI assistant to use for pages in this category'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['position', 'name']
        verbose_name_plural = 'Wiki Categories'
        unique_together = ('organization', 'name', 'slug')
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class WikiPage(models.Model):
    """Main wiki page model"""
    title = models.CharField(max_length=255)
    slug = models.SlugField()
    content = models.TextField(help_text='Markdown supported')
    category = models.ForeignKey(WikiCategory, on_delete=models.CASCADE, related_name='pages')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='wiki_pages')
    
    # Page metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_wiki_pages')
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='updated_wiki_pages')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Page status
    is_published = models.BooleanField(default=True, help_text='Unpublished pages are visible only to editors')
    is_pinned = models.BooleanField(default=False, help_text='Pinned pages appear at the top')
    
    # Content metadata
    tags = models.JSONField(default=list, blank=True, help_text='Tags for search and filtering')
    view_count = models.IntegerField(default=0)
    
    # Version control
    version = models.IntegerField(default=1)
    parent_page = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='child_pages', help_text='Parent page for hierarchical organization')
    
    class Meta:
        ordering = ['-is_pinned', '-updated_at']
        indexes = [
            models.Index(fields=['organization', '-updated_at']),
            models.Index(fields=['slug']),
            models.Index(fields=['category']),
        ]
        unique_together = ('organization', 'slug')
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def get_html_content(self):
        """Convert markdown content to HTML and sanitize to prevent XSS"""
        import bleach
        
        # Convert markdown to HTML
        html = markdown.markdown(
            self.content,
            extensions=[
                'markdown.extensions.fenced_code',
                'markdown.extensions.tables',
                'markdown.extensions.nl2br',
            ]
        )
        
        # Define allowed HTML tags and attributes (security whitelist)
        allowed_tags = [
            'p', 'br', 'strong', 'em', 'u', 's', 'del', 'ins',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li',
            'a', 'code', 'pre', 'blockquote',
            'table', 'thead', 'tbody', 'tr', 'th', 'td',
            'hr', 'img', 'div', 'span'
        ]
        
        allowed_attributes = {
            'a': ['href', 'title', 'rel'],
            'img': ['src', 'alt', 'title', 'width', 'height'],
            'code': ['class'],  # For syntax highlighting
            'pre': ['class'],
            'div': ['class'],
            'span': ['class'],
        }
        
        # Allowed protocols for links (prevent javascript: and data: URLs)
        allowed_protocols = ['http', 'https', 'mailto']
        
        # Sanitize HTML to prevent XSS attacks
        clean_html = bleach.clean(
            html,
            tags=allowed_tags,
            attributes=allowed_attributes,
            protocols=allowed_protocols,
            strip=True
        )
        
        # Linkify URLs (optional - converts plain URLs to clickable links)
        clean_html = bleach.linkify(
            clean_html,
            parse_email=True,
            skip_tags=['pre', 'code']
        )
        
        return mark_safe(clean_html)
    
    def increment_view_count(self):
        """Increment view count for analytics"""
        self.view_count += 1
        self.save(update_fields=['view_count'])
    
    def get_breadcrumb(self):
        """Get breadcrumb navigation path"""
        breadcrumb = []
        page = self
        while page:
            breadcrumb.insert(0, page)
            page = page.parent_page
        return breadcrumb
    
    def get_absolute_url(self):
        """Get absolute URL for the wiki page"""
        from django.urls import reverse
        return reverse('wiki:page_detail', kwargs={'slug': self.slug})


class WikiAttachment(models.Model):
    """Files attached to wiki pages"""
    page = models.ForeignKey(WikiPage, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='wiki_attachments/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50, help_text='File type (doc, pdf, image, etc.)')
    file_size = models.IntegerField(help_text='File size in bytes')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.filename} - {self.page.title}"


class WikiLink(models.Model):
    """Link wiki pages to tasks and boards"""
    LINK_TYPE_CHOICES = [
        ('task', 'Task'),
        ('board', 'Board'),
        ('meeting_notes', 'Meeting Notes'),
    ]
    
    wiki_page = models.ForeignKey(WikiPage, on_delete=models.CASCADE, related_name='links_to_items')
    link_type = models.CharField(max_length=20, choices=LINK_TYPE_CHOICES)
    
    # Flexible linking - support both tasks and boards
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True, related_name='wiki_links')
    board = models.ForeignKey(Board, on_delete=models.CASCADE, null=True, blank=True, related_name='wiki_links')
    
    # Link metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=500, blank=True, null=True, 
                                  help_text='Why this wiki page is relevant to this item')
    
    class Meta:
        unique_together = (('wiki_page', 'link_type', 'task'), ('wiki_page', 'link_type', 'board'))
    
    def __str__(self):
        if self.task:
            return f"{self.wiki_page.title} → Task: {self.task.title}"
        elif self.board:
            return f"{self.wiki_page.title} → Board: {self.board.name}"
        return f"{self.wiki_page.title} → {self.link_type}"
    
    def get_linked_item(self):
        """Get the linked item (task or board)"""
        if self.task:
            return self.task
        elif self.board:
            return self.board
        return None


class MeetingNotes(models.Model):
    """Meeting notes and transcript analysis - unified meeting hub"""
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
    
    title = models.CharField(max_length=255)
    meeting_type = models.CharField(max_length=20, choices=MEETING_TYPE_CHOICES, default='general')
    date = models.DateTimeField()
    content = models.TextField(help_text='Markdown supported - manual notes or AI-generated')
    
    # Organization and participants
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='meeting_notes')
    attendees = models.ManyToManyField(User, related_name='meeting_notes_attended')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_meeting_notes')
    
    # Linking - optional board context
    related_board = models.ForeignKey(Board, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='meeting_notes')
    related_wiki_page = models.ForeignKey(WikiPage, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='meeting_notes_references')
    
    # Metadata
    duration_minutes = models.IntegerField(blank=True, null=True, help_text='Meeting duration in minutes')
    action_items = models.JSONField(default=list, blank=True, 
                                   help_text='Action items: [{"task": "...", "assigned_to": "...", "due_date": "..."}]')
    decisions = models.JSONField(default=list, blank=True, help_text='Key decisions made')
    
    # Transcript fields (for AI-powered meetings)
    transcript_text = models.TextField(blank=True, help_text='Raw meeting transcript')
    transcript_file = models.FileField(upload_to='meeting_transcripts/%Y/%m/%d/', blank=True, null=True,
                                     help_text='Uploaded transcript file (txt, pdf, docx)')
    
    # AI extraction results
    extraction_results = models.JSONField(default=dict, blank=True,
                                        help_text='AI extraction results including tasks and metadata')
    tasks_extracted_count = models.IntegerField(default=0)
    tasks_created_count = models.IntegerField(default=0)
    processing_status = models.CharField(max_length=20, choices=PROCESSING_STATUS_CHOICES, default='pending')
    processed_at = models.DateTimeField(blank=True, null=True)
    
    # Meeting context
    meeting_context = models.JSONField(default=dict, blank=True,
                                     help_text='Additional meeting context and metadata')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['organization', '-date']),
            models.Index(fields=['related_board']),
            models.Index(fields=['processing_status']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.date.strftime('%Y-%m-%d %H:%M')}"
    
    def get_html_content(self):
        """Convert markdown content to HTML and sanitize to prevent XSS"""
        import bleach
        
        # Convert markdown to HTML
        html = markdown.markdown(
            self.content,
            extensions=[
                'markdown.extensions.fenced_code',
                'markdown.extensions.tables',
                'markdown.extensions.nl2br',
            ]
        )
        
        # Define allowed HTML tags and attributes (security whitelist)
        allowed_tags = [
            'p', 'br', 'strong', 'em', 'u', 's', 'del', 'ins',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li',
            'a', 'code', 'pre', 'blockquote',
            'table', 'thead', 'tbody', 'tr', 'th', 'td',
            'hr', 'img', 'div', 'span'
        ]
        
        allowed_attributes = {
            'a': ['href', 'title', 'rel'],
            'img': ['src', 'alt', 'title', 'width', 'height'],
            'code': ['class'],
            'pre': ['class'],
            'div': ['class'],
            'span': ['class'],
        }
        
        # Allowed protocols for links (prevent javascript: and data: URLs)
        allowed_protocols = ['http', 'https', 'mailto']
        
        # Sanitize HTML to prevent XSS attacks
        clean_html = bleach.clean(
            html,
            tags=allowed_tags,
            attributes=allowed_attributes,
            protocols=allowed_protocols,
            strip=True
        )
        
        # Linkify URLs
        clean_html = bleach.linkify(
            clean_html,
            parse_email=True,
            skip_tags=['pre', 'code']
        )
        
        return mark_safe(clean_html)


class WikiPageVersion(models.Model):
    """Track wiki page version history"""
    page = models.ForeignKey(WikiPage, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField()
    title = models.CharField(max_length=255)
    content = models.TextField()
    edited_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    change_summary = models.CharField(max_length=500, blank=True, null=True,
                                     help_text='Summary of changes made in this version')
    
    class Meta:
        ordering = ['-version_number']
        unique_together = ('page', 'version_number')
    
    def __str__(self):
        return f"{self.page.title} - v{self.version_number}"


class WikiLinkBetweenPages(models.Model):
    """Link between wiki pages (cross-references)"""
    source_page = models.ForeignKey(WikiPage, on_delete=models.CASCADE, related_name='outgoing_links')
    target_page = models.ForeignKey(WikiPage, on_delete=models.CASCADE, related_name='incoming_links')
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('source_page', 'target_page')
    
    def __str__(self):
        return f"{self.source_page.title} → {self.target_page.title}"


class WikiPageAccess(models.Model):
    """Track who has access to wiki pages for analytics and permissions"""
    ACCESS_LEVEL_CHOICES = [
        ('view', 'View Only'),
        ('edit', 'Edit'),
        ('admin', 'Admin'),
    ]
    
    page = models.ForeignKey(WikiPage, on_delete=models.CASCADE, related_name='access_records')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    access_level = models.CharField(max_length=20, choices=ACCESS_LEVEL_CHOICES, default='view')
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='wiki_access_granted')
    granted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('page', 'user')
    
    def __str__(self):
        return f"{self.user.username} - {self.page.title} ({self.access_level})"


class WikiMeetingAnalysis(models.Model):
    """
    AI-powered analysis of wiki pages containing meeting notes
    Stores extracted action items, decisions, blockers, risks, and suggestions
    """
    PROCESSING_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    # Link to wiki page
    wiki_page = models.ForeignKey(WikiPage, on_delete=models.CASCADE, related_name='meeting_analyses')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='wiki_meeting_analyses')
    
    # Processing metadata
    processed_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='processed_meeting_analyses')
    processed_at = models.DateTimeField(auto_now_add=True)
    processing_status = models.CharField(max_length=20, choices=PROCESSING_STATUS_CHOICES, default='pending')
    processing_error = models.TextField(blank=True, null=True, help_text='Error message if processing failed')
    
    # AI Analysis Results (comprehensive JSON structure)
    analysis_results = models.JSONField(default=dict, blank=True, help_text="""
        Complete AI analysis including:
        - meeting_summary: {title, summary, date_detected, participants, meeting_type, confidence}
        - action_items: [{title, description, priority, assignee, due_date, etc.}]
        - decisions: [{decision, context, impact, requires_action}]
        - blockers: [{blocker, severity, resolution, owner}]
        - risks: [{risk, impact, probability, mitigation}]
        - key_topics: [list of main topics]
        - follow_ups: [{type, description, timeframe, participants}]
        - metadata: {counts, sentiment, notes}
    """)
    
    # Quick access counts (denormalized for performance)
    action_items_count = models.IntegerField(default=0, help_text='Number of action items extracted')
    decisions_count = models.IntegerField(default=0, help_text='Number of decisions identified')
    blockers_count = models.IntegerField(default=0, help_text='Number of blockers found')
    risks_count = models.IntegerField(default=0, help_text='Number of risks identified')
    tasks_created_count = models.IntegerField(default=0, help_text='Number of tasks created from this analysis')
    
    # Analysis metadata
    content_hash = models.CharField(max_length=64, help_text='Hash of content analyzed (to detect changes)')
    ai_model_version = models.CharField(max_length=50, default='gemini-2.0-flash-exp', help_text='AI model used (Flash or Flash-Lite)')
    confidence_score = models.CharField(max_length=20, blank=True, null=True, help_text='Overall confidence: high/medium/low')
    
    # User actions
    user_reviewed = models.BooleanField(default=False, help_text='Has user reviewed the analysis?')
    user_notes = models.TextField(blank=True, null=True, help_text='User notes about the analysis')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-processed_at']
        indexes = [
            models.Index(fields=['wiki_page', '-processed_at']),
            models.Index(fields=['organization', 'processing_status']),
            models.Index(fields=['processing_status']),
        ]
        verbose_name = 'Wiki Meeting Analysis'
        verbose_name_plural = 'Wiki Meeting Analyses'
    
    def __str__(self):
        return f"Analysis of {self.wiki_page.title} - {self.processed_at.strftime('%Y-%m-%d %H:%M')}"
    
    def get_action_items(self):
        """Get list of action items from analysis results"""
        return self.analysis_results.get('action_items', [])
    
    def get_decisions(self):
        """Get list of decisions from analysis results"""
        return self.analysis_results.get('decisions', [])
    
    def get_blockers(self):
        """Get list of blockers from analysis results"""
        return self.analysis_results.get('blockers', [])
    
    def get_risks(self):
        """Get list of risks from analysis results"""
        return self.analysis_results.get('risks', [])
    
    def get_meeting_summary(self):
        """Get meeting summary from analysis results"""
        return self.analysis_results.get('meeting_summary', {})
    
    def get_metadata(self):
        """Get analysis metadata"""
        return self.analysis_results.get('metadata', {})
    
    def has_urgent_items(self):
        """Check if there are any urgent action items"""
        action_items = self.get_action_items()
        return any(item.get('priority') == 'urgent' for item in action_items)
    
    def has_critical_blockers(self):
        """Check if there are any critical blockers"""
        blockers = self.get_blockers()
        return any(blocker.get('severity') == 'critical' for blocker in blockers)
    
    def update_counts(self):
        """Update denormalized counts from analysis results"""
        self.action_items_count = len(self.get_action_items())
        self.decisions_count = len(self.get_decisions())
        self.blockers_count = len(self.get_blockers())
        self.risks_count = len(self.get_risks())
        
        metadata = self.get_metadata()
        self.confidence_score = metadata.get('confidence', 'medium')


class WikiMeetingTask(models.Model):
    """
    Tracks tasks created from wiki meeting analysis
    Links AI-extracted action items to actual created tasks
    """
    # Link to analysis and task
    meeting_analysis = models.ForeignKey(WikiMeetingAnalysis, on_delete=models.CASCADE, 
                                        related_name='created_tasks')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='wiki_meeting_source')
    
    # Action item details from AI analysis
    action_item_index = models.IntegerField(help_text='Index in the action_items array')
    action_item_data = models.JSONField(default=dict, help_text='Original AI-extracted action item data')
    
    # Creation metadata
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_meeting_tasks')
    created_at = models.DateTimeField(auto_now_add=True)
    
    # User modifications
    user_modified = models.BooleanField(default=False, help_text='Did user modify before creating?')
    modifications_note = models.TextField(blank=True, null=True, help_text='What was changed from AI suggestion')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['meeting_analysis', 'task']),
            models.Index(fields=['task']),
        ]
        unique_together = ('meeting_analysis', 'action_item_index')
    
    def __str__(self):
        return f"Task '{self.task.title}' from {self.meeting_analysis.wiki_page.title}"
