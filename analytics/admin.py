"""
Admin interface for analytics models.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import UserSession, Feedback, FeedbackPrompt, AnalyticsEvent


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user_display',
        'engagement_badge',
        'duration_minutes',
        'tasks_created',
        'ai_features_used',
        'session_start',
        'device_type'
    ]
    list_filter = [
        'engagement_level',
        'device_type',
        'is_return_visit',
        'registered_during_session',
        'session_start'
    ]
    search_fields = ['user__username', 'user__email', 'session_key', 'ip_address']
    readonly_fields = [
        'session_key',
        'session_start',
        'session_end',
        'engagement_score',
        'engagement_level',
        'duration_minutes',
        'ip_address',
        'user_agent',
        'referrer',
        'previous_session_count'
    ]
    fieldsets = (
        ('Identity', {
            'fields': ('user', 'session_key', 'ip_address', 'device_type')
        }),
        ('Activity Metrics', {
            'fields': (
                'boards_viewed',
                'boards_created',
                'tasks_created',
                'tasks_completed',
                'ai_features_used',
                'pages_visited'
            )
        }),
        ('Engagement', {
            'fields': ('engagement_level', 'engagement_score', 'features_discovered')
        }),
        ('Time Tracking', {
            'fields': ('session_start', 'session_end', 'last_activity', 'duration_minutes')
        }),
        ('Session Info', {
            'fields': ('is_return_visit', 'previous_session_count', 'registered_during_session', 'exit_reason', 'exit_page')
        }),
        ('Technical', {
            'fields': ('user_agent', 'referrer'),
            'classes': ('collapse',)
        }),
    )
    
    def user_display(self, obj):
        if obj.user:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:auth_user_change', args=[obj.user.id]),
                obj.user.username
            )
        return "Anonymous"
    user_display.short_description = "User"
    
    def engagement_badge(self, obj):
        colors = {
            'very_high': '#10b981',
            'high': '#3b82f6',
            'medium': '#f59e0b',
            'low': '#6b7280'
        }
        color = colors.get(obj.engagement_level, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color,
            obj.engagement_level.replace('_', ' ').upper()
        )
    engagement_badge.short_description = "Engagement"
    
    def has_add_permission(self, request):
        return False  # Sessions are created automatically


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'user_display',
        'rating_display',
        'sentiment_badge',
        'feedback_preview',
        'submitted_at',
        'status',
        'hubspot_synced'
    ]
    list_filter = [
        'rating',
        'sentiment',
        'feedback_type',
        'status',
        'synced_to_hubspot',
        'email_consent',
        'submitted_at'
    ]
    search_fields = ['name', 'email', 'organization', 'feedback_text', 'user__username']
    readonly_fields = [
        'user_session',
        'submitted_at',
        'ip_address',
        'sentiment',
        'hubspot_contact_id',
        'hubspot_deal_id',
        'synced_to_hubspot',
        'hubspot_sync_date'
    ]
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'user_session', 'name', 'email', 'organization')
        }),
        ('Feedback Content', {
            'fields': ('feedback_text', 'rating', 'sentiment', 'feedback_type')
        }),
        ('Follow-up', {
            'fields': ('email_consent', 'follow_up_sent', 'follow_up_sent_at', 'follow_up_response')
        }),
        ('Internal', {
            'fields': ('status', 'admin_notes')
        }),
        ('HubSpot Integration', {
            'fields': ('synced_to_hubspot', 'hubspot_contact_id', 'hubspot_deal_id', 'hubspot_sync_date'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('submitted_at', 'ip_address'),
            'classes': ('collapse',)
        }),
    )
    actions = ['sync_to_hubspot', 'mark_as_reviewed', 'mark_as_resolved']
    
    def user_display(self, obj):
        if obj.user:
            return format_html(
                '<a href="{}">{}</a>',
                reverse('admin:auth_user_change', args=[obj.user.id]),
                obj.user.username
            )
        return obj.name or obj.email or "Anonymous"
    user_display.short_description = "User"
    
    def rating_display(self, obj):
        if obj.rating:
            stars = '⭐' * obj.rating
            return format_html('<span title="{}/5">{}</span>', obj.rating, stars)
        return "-"
    rating_display.short_description = "Rating"
    
    def sentiment_badge(self, obj):
        colors = {
            'positive': '#10b981',
            'neutral': '#6b7280',
            'negative': '#ef4444'
        }
        color = colors.get(obj.sentiment, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px;">{}</span>',
            color,
            obj.sentiment.upper() if obj.sentiment else 'N/A'
        )
    sentiment_badge.short_description = "Sentiment"
    
    def feedback_preview(self, obj):
        preview = obj.feedback_text[:100]
        if len(obj.feedback_text) > 100:
            preview += "..."
        return preview
    feedback_preview.short_description = "Feedback"
    
    def hubspot_synced(self, obj):
        if obj.synced_to_hubspot:
            return format_html('<span style="color: green;">✓</span>')
        return format_html('<span style="color: red;">✗</span>')
    hubspot_synced.short_description = "HubSpot"
    hubspot_synced.boolean = True
    
    def sync_to_hubspot(self, request, queryset):
        from .utils import HubSpotIntegration
        hubspot = HubSpotIntegration()
        
        if not hubspot.is_configured():
            self.message_user(request, "HubSpot is not configured.", level='error')
            return
        
        synced_count = 0
        for feedback in queryset:
            if feedback.email:
                try:
                    hubspot.sync_feedback_to_hubspot(feedback)
                    synced_count += 1
                except Exception as e:
                    self.message_user(request, f"Error syncing {feedback.email}: {e}", level='error')
        
        self.message_user(request, f"Successfully synced {synced_count} feedback(s) to HubSpot.")
    sync_to_hubspot.short_description = "Sync selected to HubSpot"
    
    def mark_as_reviewed(self, request, queryset):
        updated = queryset.update(status='reviewed')
        self.message_user(request, f"Marked {updated} feedback(s) as reviewed.")
    mark_as_reviewed.short_description = "Mark as reviewed"
    
    def mark_as_resolved(self, request, queryset):
        updated = queryset.update(status='resolved')
        self.message_user(request, f"Marked {updated} feedback(s) as resolved.")
    mark_as_resolved.short_description = "Mark as resolved"


@admin.register(FeedbackPrompt)
class FeedbackPromptAdmin(admin.ModelAdmin):
    list_display = ['id', 'prompt_type', 'shown_at', 'interacted', 'submitted', 'dismissed']
    list_filter = ['prompt_type', 'interacted', 'submitted', 'dismissed', 'shown_at']
    readonly_fields = ['user_session', 'shown_at']
    
    def has_add_permission(self, request):
        return False


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ['id', 'event_name', 'event_category', 'event_label', 'timestamp']
    list_filter = ['event_name', 'event_category', 'timestamp']
    search_fields = ['event_name', 'event_category', 'event_label']
    readonly_fields = ['user_session', 'timestamp', 'event_data']
    
    def has_add_permission(self, request):
        return False
