"""
Django Admin for AI Coach Models
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from kanban.coach_models import (
    CoachingSuggestion,
    CoachingFeedback,
    PMMetrics,
    CoachingInsight
)


@admin.register(CoachingSuggestion)
class CoachingSuggestionAdmin(admin.ModelAdmin):
    """Admin for Coaching Suggestions"""
    
    list_display = [
        'id',
        'colored_severity',
        'suggestion_type',
        'title_short',
        'board_link',
        'status',
        'confidence_score',
        'days_active_display',
        'was_helpful',
        'created_at'
    ]
    
    list_filter = [
        'severity',
        'suggestion_type',
        'status',
        'generation_method',
        'was_helpful',
        'created_at',
    ]
    
    search_fields = [
        'title',
        'message',
        'board__name',
    ]
    
    readonly_fields = [
        'created_at',
        'updated_at',
        'resolved_at',
        'acknowledged_at',
        'days_active',
        'is_expired'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': (
                'board',
                'task',
                'suggestion_type',
                'severity',
                'status',
            )
        }),
        ('Content', {
            'fields': (
                'title',
                'message',
                'reasoning',
                'recommended_actions',
                'expected_impact',
            )
        }),
        ('AI Details', {
            'fields': (
                'ai_model_used',
                'generation_method',
                'confidence_score',
                'metrics_snapshot',
            )
        }),
        ('User Interaction', {
            'fields': (
                'acknowledged_by',
                'acknowledged_at',
                'was_helpful',
                'action_taken',
            )
        }),
        ('Timing', {
            'fields': (
                'created_at',
                'updated_at',
                'expires_at',
                'resolved_at',
                'days_active',
                'is_expired',
            )
        }),
    )
    
    def colored_severity(self, obj):
        """Display severity with color"""
        colors = {
            'critical': 'red',
            'high': 'orange',
            'medium': 'blue',
            'low': 'green',
            'info': 'gray',
        }
        color = colors.get(obj.severity, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_severity_display()
        )
    colored_severity.short_description = 'Severity'
    
    def title_short(self, obj):
        """Shortened title"""
        if len(obj.title) > 50:
            return obj.title[:50] + '...'
        return obj.title
    title_short.short_description = 'Title'
    
    def board_link(self, obj):
        """Link to board"""
        url = reverse('admin:kanban_board_change', args=[obj.board.id])
        return format_html('<a href="{}">{}</a>', url, obj.board.name)
    board_link.short_description = 'Board'
    
    def days_active_display(self, obj):
        """Display days active"""
        days = obj.days_active
        if days == 0:
            return 'Today'
        elif days == 1:
            return '1 day'
        else:
            return f'{days} days'
    days_active_display.short_description = 'Active'
    
    actions = ['mark_as_resolved', 'mark_as_dismissed']
    
    def mark_as_resolved(self, request, queryset):
        """Bulk action to resolve suggestions"""
        count = 0
        for suggestion in queryset:
            if suggestion.status != 'resolved':
                suggestion.resolve()
                count += 1
        self.message_user(request, f'{count} suggestion(s) marked as resolved.')
    mark_as_resolved.short_description = 'Mark selected as resolved'
    
    def mark_as_dismissed(self, request, queryset):
        """Bulk action to dismiss suggestions"""
        count = 0
        for suggestion in queryset:
            if suggestion.status != 'dismissed':
                suggestion.dismiss()
                count += 1
        self.message_user(request, f'{count} suggestion(s) dismissed.')
    mark_as_dismissed.short_description = 'Dismiss selected suggestions'


@admin.register(CoachingFeedback)
class CoachingFeedbackAdmin(admin.ModelAdmin):
    """Admin for Coaching Feedback"""
    
    list_display = [
        'id',
        'suggestion_title',
        'user',
        'was_helpful',
        'relevance_score',
        'action_taken',
        'improved_situation',
        'created_at'
    ]
    
    list_filter = [
        'was_helpful',
        'relevance_score',
        'action_taken',
        'improved_situation',
        'created_at',
    ]
    
    search_fields = [
        'suggestion__title',
        'user__username',
        'feedback_text',
        'outcome_description',
    ]
    
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Feedback Details', {
            'fields': (
                'suggestion',
                'user',
                'was_helpful',
                'relevance_score',
                'action_taken',
            )
        }),
        ('Detailed Feedback', {
            'fields': (
                'feedback_text',
                'outcome_description',
                'improved_situation',
            )
        }),
        ('Metadata', {
            'fields': (
                'created_at',
            )
        }),
    )
    
    def suggestion_title(self, obj):
        """Display suggestion title"""
        if len(obj.suggestion.title) > 60:
            return obj.suggestion.title[:60] + '...'
        return obj.suggestion.title
    suggestion_title.short_description = 'Suggestion'


@admin.register(PMMetrics)
class PMMetricsAdmin(admin.ModelAdmin):
    """Admin for PM Metrics"""
    
    list_display = [
        'id',
        'pm_user',
        'board',
        'period_display',
        'action_rate_display',
        'velocity_trend',
        'coaching_effectiveness_score',
        'created_at'
    ]
    
    list_filter = [
        'velocity_trend',
        'period_start',
        'period_end',
        'created_at',
    ]
    
    search_fields = [
        'pm_user__username',
        'board__name',
    ]
    
    readonly_fields = [
        'created_at',
        'action_rate',
    ]
    
    fieldsets = (
        ('Context', {
            'fields': (
                'board',
                'pm_user',
                'period_start',
                'period_end',
            )
        }),
        ('Coaching Engagement', {
            'fields': (
                'suggestions_received',
                'suggestions_acted_on',
                'avg_response_time_hours',
                'action_rate',
            )
        }),
        ('Project Health', {
            'fields': (
                'velocity_trend',
                'risk_mitigation_success_rate',
                'deadline_hit_rate',
                'team_satisfaction_score',
            )
        }),
        ('Learning', {
            'fields': (
                'improvement_areas',
                'struggle_areas',
                'coaching_effectiveness_score',
            )
        }),
        ('Metadata', {
            'fields': (
                'created_at',
                'calculated_by',
            )
        }),
    )
    
    def period_display(self, obj):
        """Display period range"""
        return f'{obj.period_start} to {obj.period_end}'
    period_display.short_description = 'Period'
    
    def action_rate_display(self, obj):
        """Display action rate as percentage"""
        return f'{obj.action_rate:.1f}%'
    action_rate_display.short_description = 'Action Rate'


@admin.register(CoachingInsight)
class CoachingInsightAdmin(admin.ModelAdmin):
    """Admin for Coaching Insights"""
    
    list_display = [
        'id',
        'insight_type',
        'title',
        'confidence_score',
        'sample_size',
        'is_active',
        'discovered_at'
    ]
    
    list_filter = [
        'insight_type',
        'is_active',
        'discovered_at',
    ]
    
    search_fields = [
        'title',
        'description',
    ]
    
    readonly_fields = [
        'discovered_at',
        'last_validated',
    ]
    
    fieldsets = (
        ('Insight Details', {
            'fields': (
                'insight_type',
                'title',
                'description',
            )
        }),
        ('Confidence', {
            'fields': (
                'confidence_score',
                'sample_size',
            )
        }),
        ('Application', {
            'fields': (
                'applicable_to_suggestion_types',
                'rule_adjustments',
                'is_active',
            )
        }),
        ('Metadata', {
            'fields': (
                'discovered_at',
                'last_validated',
            )
        }),
    )
    
    actions = ['activate_insights', 'deactivate_insights']
    
    def activate_insights(self, request, queryset):
        """Bulk activate insights"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} insight(s) activated.')
    activate_insights.short_description = 'Activate selected insights'
    
    def deactivate_insights(self, request, queryset):
        """Bulk deactivate insights"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} insight(s) deactivated.')
    deactivate_insights.short_description = 'Deactivate selected insights'
