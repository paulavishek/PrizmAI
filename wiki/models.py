from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from kanban.models import Board, Task
from accounts.models import Organization
import markdown
from django.utils.safestring import mark_safe


class WikiCategory(models.Model):
    """Categories for organizing wiki pages"""
    name = models.CharField(max_length=100)
    slug = models.SlugField()
    description = models.TextField(blank=True, null=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='wiki_categories')
    icon = models.CharField(max_length=50, default='folder', help_text='Font Awesome icon name')
    color = models.CharField(max_length=7, default='#3498db', help_text='Hex color code')
    position = models.IntegerField(default=0)
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
        """Convert markdown content to HTML"""
        return mark_safe(markdown.markdown(self.content))
    
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
        """Convert markdown content to HTML"""
        return mark_safe(markdown.markdown(self.content))


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
