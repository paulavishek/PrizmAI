from django.contrib import admin
from .models import Board, Column, Task, TaskLabel, Comment, TaskActivity
from .priority_models import PriorityDecision, PriorityModel, PrioritySuggestionLog

@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ('name', 'organization', 'created_by', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('organization', 'created_at')

@admin.register(Column)
class ColumnAdmin(admin.ModelAdmin):
    list_display = ('name', 'board', 'position')
    list_filter = ('board',)
    search_fields = ('name', 'board__name')

@admin.register(TaskLabel)
class TaskLabelAdmin(admin.ModelAdmin):
    list_display = ('name', 'color', 'board')
    list_filter = ('board',)
    search_fields = ('name', 'board__name')

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'column', 'priority', 'due_date', 'assigned_to', 'created_by', 'parent_task')
    list_filter = ('column', 'priority', 'due_date', 'created_at')
    search_fields = ('title', 'description')
    filter_horizontal = ('labels', 'related_tasks')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'column', 'assigned_to', 'priority', 'progress', 'labels')
        }),
        ('Timeline', {
            'fields': ('due_date',),
        }),
        ('Task Dependencies', {
            'fields': ('parent_task', 'related_tasks', 'dependency_chain'),
            'classes': ('collapse',),
            'description': 'Manage task relationships and dependencies'
        }),
        ('AI-Suggested Dependencies', {
            'fields': ('suggested_dependencies', 'last_dependency_analysis'),
            'classes': ('collapse',),
            'description': 'AI analysis results for task dependencies'
        }),
        ('AI Analysis Results', {
            'fields': ('ai_risk_score', 'ai_recommendations', 'last_ai_analysis'),
            'classes': ('collapse',),
            'description': 'These fields are related to AI analysis'
        }),
    )
    
    readonly_fields = ('last_ai_analysis', 'last_dependency_analysis', 'dependency_chain')

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('task', 'user', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('content', 'task__title', 'user__username')

@admin.register(TaskActivity)
class TaskActivityAdmin(admin.ModelAdmin):
    list_display = ('task', 'user', 'activity_type', 'created_at')
    list_filter = ('activity_type', 'created_at')
    search_fields = ('description', 'task__title', 'user__username')


@admin.register(PriorityDecision)
class PriorityDecisionAdmin(admin.ModelAdmin):
    list_display = ('task', 'actual_priority', 'suggested_priority', 'decision_type', 'was_correct', 'decided_by', 'decided_at')
    list_filter = ('decision_type', 'actual_priority', 'was_correct', 'decided_at', 'board')
    search_fields = ('task__title', 'decided_by__username')
    readonly_fields = ('task_context', 'reasoning', 'decided_at')
    
    fieldsets = (
        ('Decision Information', {
            'fields': ('task', 'board', 'decision_type', 'decided_by', 'decided_at')
        }),
        ('Priority Details', {
            'fields': ('previous_priority', 'suggested_priority', 'actual_priority', 'was_correct')
        }),
        ('AI Context', {
            'fields': ('confidence_score', 'reasoning', 'task_context'),
            'classes': ('collapse',)
        }),
        ('Feedback', {
            'fields': ('feedback_notes',),
            'classes': ('collapse',)
        })
    )


@admin.register(PriorityModel)
class PriorityModelAdmin(admin.ModelAdmin):
    list_display = ('board', 'model_version', 'accuracy_score', 'training_samples', 'is_active', 'trained_at')
    list_filter = ('is_active', 'trained_at', 'board')
    readonly_fields = ('model_file', 'feature_importance', 'trained_at', 'precision_scores', 'recall_scores', 'f1_scores', 'confusion_matrix')
    
    fieldsets = (
        ('Model Information', {
            'fields': ('board', 'model_version', 'model_type', 'is_active', 'trained_at')
        }),
        ('Training Metrics', {
            'fields': ('training_samples', 'accuracy_score')
        }),
        ('Performance Details', {
            'fields': ('precision_scores', 'recall_scores', 'f1_scores', 'confusion_matrix'),
            'classes': ('collapse',)
        }),
        ('Model Data', {
            'fields': ('feature_importance',),
            'classes': ('collapse',)
        })
    )


@admin.register(PrioritySuggestionLog)
class PrioritySuggestionLogAdmin(admin.ModelAdmin):
    list_display = ('task', 'suggested_priority', 'confidence_score', 'user_action', 'shown_to_user', 'shown_at')
    list_filter = ('user_action', 'suggested_priority', 'shown_at')
    search_fields = ('task__title', 'shown_to_user__username')
    readonly_fields = ('reasoning', 'feature_values', 'shown_at', 'responded_at')
    
    fieldsets = (
        ('Suggestion Information', {
            'fields': ('task', 'model', 'shown_to_user', 'shown_at')
        }),
        ('AI Suggestion', {
            'fields': ('suggested_priority', 'confidence_score', 'reasoning', 'feature_values'),
        }),
        ('User Response', {
            'fields': ('user_action', 'actual_priority', 'responded_at'),
            'classes': ('collapse',)
        })
    )

