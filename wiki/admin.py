from django.contrib import admin
from django.utils.html import format_html
from .models import (
    WikiCategory, WikiPage, WikiAttachment, WikiLink,
    MeetingNotes, WikiPageVersion, WikiLinkBetweenPages, WikiPageAccess,
    WikiMeetingAnalysis, WikiMeetingTask
)


@admin.register(WikiCategory)
class WikiCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon_display', 'color_display', 'position', 'organization']
    list_filter = ['organization', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['position', 'name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'organization')
        }),
        ('Display Settings', {
            'fields': ('icon', 'color', 'position')
        }),
        ('Metadata', {
            'fields': ('slug', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def color_display(self, obj):
        return format_html(
            '<div style="width: 30px; height: 30px; background-color: {}; border-radius: 3px;"></div>',
            obj.color
        )
    color_display.short_description = 'Color'
    
    def icon_display(self, obj):
        return format_html('<i class="fas fa-{}"></i> {}', obj.icon, obj.icon)
    icon_display.short_description = 'Icon'
    
    readonly_fields = ['slug', 'created_at', 'updated_at']


@admin.register(WikiPage)
class WikiPageAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'organization', 'created_by', 'view_count', 'published_status', 'updated_at']
    list_filter = ['is_published', 'is_pinned', 'category', 'organization', 'created_at']
    search_fields = ['title', 'content', 'tags']
    ordering = ['-updated_at']
    date_hierarchy = 'updated_at'
    filter_horizontal = []
    
    fieldsets = (
        ('Page Content', {
            'fields': ('title', 'content', 'category')
        }),
        ('Metadata', {
            'fields': ('organization', 'parent_page', 'tags')
        }),
        ('Authors', {
            'fields': ('created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
        ('Publication Status', {
            'fields': ('is_published', 'is_pinned', 'version')
        }),
        ('Statistics', {
            'fields': ('view_count', 'slug', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['slug', 'created_at', 'updated_at', 'created_by', 'view_count', 'version']
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if obj is None:
            form.base_fields['created_by'].initial = request.user
            form.base_fields['updated_by'].initial = request.user
        return form
    
    def published_status(self, obj):
        if obj.is_published:
            return format_html('<span style="color: green;">✓ Published</span>')
        return format_html('<span style="color: orange;">✗ Draft</span>')
    published_status.short_description = 'Status'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(WikiAttachment)
class WikiAttachmentAdmin(admin.ModelAdmin):
    list_display = ['filename', 'page', 'file_type', 'file_size_display', 'uploaded_by', 'uploaded_at']
    list_filter = ['file_type', 'uploaded_at', 'page__organization']
    search_fields = ['filename', 'page__title']
    readonly_fields = ['uploaded_at', 'file_size']
    
    def file_size_display(self, obj):
        """Display file size in human-readable format"""
        size = obj.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    file_size_display.short_description = 'File Size'


@admin.register(WikiLink)
class WikiLinkAdmin(admin.ModelAdmin):
    list_display = ['wiki_page', 'link_type', 'linked_item', 'created_by', 'created_at']
    list_filter = ['link_type', 'created_at', 'wiki_page__organization']
    search_fields = ['wiki_page__title', 'task__title', 'board__name', 'description']
    readonly_fields = ['created_at']
    
    def linked_item(self, obj):
        if obj.task:
            return f"Task: {obj.task.title}"
        elif obj.board:
            return f"Board: {obj.board.name}"
        return "—"
    linked_item.short_description = 'Linked To'


@admin.register(MeetingNotes)
class MeetingNotesAdmin(admin.ModelAdmin):
    list_display = ['title', 'date', 'organization', 'created_by', 'attendee_count', 'related_board']
    list_filter = ['date', 'organization', 'created_at']
    search_fields = ['title', 'content']
    filter_horizontal = ['attendees']
    readonly_fields = ['created_at', 'updated_at', 'created_by']
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Meeting Information', {
            'fields': ('title', 'date', 'duration_minutes', 'organization')
        }),
        ('Content', {
            'fields': ('content', 'decisions')
        }),
        ('Participants', {
            'fields': ('created_by', 'attendees')
        }),
        ('Links', {
            'fields': ('related_board', 'related_wiki_page')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def attendee_count(self, obj):
        return obj.attendees.count()
    attendee_count.short_description = 'Attendees'


@admin.register(WikiPageVersion)
class WikiPageVersionAdmin(admin.ModelAdmin):
    list_display = ['page', 'version_number', 'edited_by', 'created_at', 'change_summary']
    list_filter = ['page', 'created_at', 'page__organization']
    search_fields = ['page__title', 'change_summary']
    readonly_fields = ['created_at', 'content']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Version Info', {
            'fields': ('page', 'version_number', 'edited_by', 'created_at')
        }),
        ('Change Info', {
            'fields': ('title', 'change_summary')
        }),
        ('Content', {
            'fields': ('content',),
            'classes': ('collapse',)
        }),
    )


@admin.register(WikiLinkBetweenPages)
class WikiLinkBetweenPagesAdmin(admin.ModelAdmin):
    list_display = ['source_page', 'target_page', 'created_by', 'created_at']
    list_filter = ['created_at', 'source_page__organization']
    search_fields = ['source_page__title', 'target_page__title']
    readonly_fields = ['created_at']


@admin.register(WikiPageAccess)
class WikiPageAccessAdmin(admin.ModelAdmin):
    list_display = ['page', 'user', 'access_level', 'granted_by', 'granted_at']
    list_filter = ['access_level', 'granted_at', 'page__organization']
    search_fields = ['page__title', 'user__username']
    readonly_fields = ['granted_at']


@admin.register(WikiMeetingAnalysis)
class WikiMeetingAnalysisAdmin(admin.ModelAdmin):
    list_display = ['wiki_page', 'processed_by', 'processing_status', 'action_items_count', 
                   'tasks_created_count', 'confidence_score', 'processed_at']
    list_filter = ['processing_status', 'confidence_score', 'processed_at', 'organization']
    search_fields = ['wiki_page__title', 'processed_by__username']
    readonly_fields = ['processed_at', 'created_at', 'updated_at', 'content_hash']
    date_hierarchy = 'processed_at'
    
    fieldsets = (
        ('Analysis Info', {
            'fields': ('wiki_page', 'organization', 'processed_by', 'processing_status')
        }),
        ('Results Summary', {
            'fields': ('action_items_count', 'decisions_count', 'blockers_count', 
                      'risks_count', 'tasks_created_count', 'confidence_score')
        }),
        ('User Interaction', {
            'fields': ('user_reviewed', 'user_notes')
        }),
        ('Technical Details', {
            'fields': ('analysis_results', 'ai_model_version', 'content_hash', 
                      'processing_error'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('processed_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Prevent manual creation - analyses are created via API
        return False


@admin.register(WikiMeetingTask)
class WikiMeetingTaskAdmin(admin.ModelAdmin):
    list_display = ['task', 'meeting_analysis', 'created_by', 'user_modified', 'created_at']
    list_filter = ['user_modified', 'created_at', 'meeting_analysis__organization']
    search_fields = ['task__title', 'meeting_analysis__wiki_page__title']
    readonly_fields = ['created_at', 'action_item_data']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Task Link', {
            'fields': ('meeting_analysis', 'task', 'action_item_index')
        }),
        ('Creation Info', {
            'fields': ('created_by', 'created_at')
        }),
        ('Modifications', {
            'fields': ('user_modified', 'modifications_note')
        }),
        ('Original AI Data', {
            'fields': ('action_item_data',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        # Prevent manual creation - tasks are created via API
        return False
