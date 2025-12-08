"""
Resource Leveling Admin Interface
"""
from django.contrib import admin
from kanban.resource_leveling_models import (
    UserPerformanceProfile,
    TaskAssignmentHistory,
    ResourceLevelingSuggestion
)


@admin.register(UserPerformanceProfile)
class UserPerformanceProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'organization', 'velocity_score', 'utilization_percentage',
        'current_active_tasks', 'total_tasks_completed', 'on_time_completion_rate'
    ]
    list_filter = ['organization', 'last_updated']
    search_fields = ['user__username', 'user__email']
    readonly_fields = [
        'total_tasks_completed', 'avg_completion_time_hours', 'velocity_score',
        'on_time_completion_rate', 'quality_score', 'current_active_tasks',
        'current_workload_hours', 'utilization_percentage', 'last_updated',
        'last_task_completed'
    ]
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'organization')
        }),
        ('Performance Metrics', {
            'fields': (
                'total_tasks_completed', 'avg_completion_time_hours',
                'velocity_score', 'on_time_completion_rate', 'quality_score'
            )
        }),
        ('Current Workload', {
            'fields': (
                'current_active_tasks', 'current_workload_hours',
                'utilization_percentage', 'weekly_capacity_hours'
            )
        }),
        ('Skills', {
            'fields': ('skill_keywords',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('last_updated', 'last_task_completed')
        })
    )
    
    actions = ['update_metrics']
    
    def update_metrics(self, request, queryset):
        """Admin action to update metrics for selected profiles"""
        updated = 0
        for profile in queryset:
            try:
                profile.update_metrics()
                updated += 1
            except Exception as e:
                self.message_user(request, f"Error updating {profile.user.username}: {e}", level='error')
        
        self.message_user(request, f"Updated {updated} performance profiles")
    
    update_metrics.short_description = "Update performance metrics"


@admin.register(TaskAssignmentHistory)
class TaskAssignmentHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'task', 'previous_assignee', 'new_assignee', 'changed_by',
        'changed_at', 'reason', 'was_ai_suggested', 'prediction_accuracy'
    ]
    list_filter = ['reason', 'was_ai_suggested', 'changed_at']
    search_fields = [
        'task__title', 'previous_assignee__username',
        'new_assignee__username', 'changed_by__username'
    ]
    readonly_fields = [
        'task', 'previous_assignee', 'new_assignee', 'changed_by',
        'changed_at', 'predicted_completion_hours', 'predicted_due_date',
        'actual_completion_hours', 'actual_completion_date', 'prediction_accuracy'
    ]
    
    fieldsets = (
        ('Assignment Details', {
            'fields': (
                'task', 'previous_assignee', 'new_assignee',
                'changed_by', 'changed_at', 'reason'
            )
        }),
        ('AI Information', {
            'fields': (
                'was_ai_suggested', 'ai_confidence_score', 'ai_reasoning'
            )
        }),
        ('Predictions', {
            'fields': (
                'predicted_completion_hours', 'predicted_due_date'
            )
        }),
        ('Actual Results', {
            'fields': (
                'actual_completion_hours', 'actual_completion_date',
                'prediction_accuracy'
            )
        })
    )


@admin.register(ResourceLevelingSuggestion)
class ResourceLevelingSuggestionAdmin(admin.ModelAdmin):
    list_display = [
        'task', 'current_assignee', 'suggested_assignee', 'confidence_score',
        'time_savings_percentage', 'status', 'created_at', 'expires_at'
    ]
    list_filter = ['status', 'workload_impact', 'created_at', 'organization']
    search_fields = [
        'task__title', 'current_assignee__username',
        'suggested_assignee__username'
    ]
    readonly_fields = [
        'task', 'organization', 'current_assignee', 'suggested_assignee',
        'confidence_score', 'time_savings_hours', 'time_savings_percentage',
        'skill_match_score', 'workload_impact', 'current_projected_date',
        'suggested_projected_date', 'reasoning', 'created_at', 'expires_at',
        'reviewed_at', 'reviewed_by'
    ]
    
    fieldsets = (
        ('Suggestion Details', {
            'fields': (
                'task', 'organization', 'current_assignee',
                'suggested_assignee', 'status'
            )
        }),
        ('Impact Metrics', {
            'fields': (
                'confidence_score', 'time_savings_hours',
                'time_savings_percentage', 'skill_match_score',
                'workload_impact'
            )
        }),
        ('Projections', {
            'fields': (
                'current_projected_date', 'suggested_projected_date'
            )
        }),
        ('Reasoning', {
            'fields': ('reasoning',)
        }),
        ('Status Information', {
            'fields': (
                'created_at', 'expires_at', 'reviewed_at', 'reviewed_by'
            )
        })
    )
    
    actions = ['mark_expired']
    
    def mark_expired(self, request, queryset):
        """Admin action to mark selected suggestions as expired"""
        updated = queryset.filter(status='pending').update(status='expired')
        self.message_user(request, f"Marked {updated} suggestions as expired")
    
    mark_expired.short_description = "Mark as expired"
