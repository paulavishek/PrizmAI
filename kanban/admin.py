from django.contrib import admin
from .models import (
    Board, Column, Task, TaskLabel, Comment, TaskActivity,
    TeamSkillProfile, SkillGap, SkillDevelopmentPlan
)
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


@admin.register(TeamSkillProfile)
class TeamSkillProfileAdmin(admin.ModelAdmin):
    list_display = ('board', 'total_capacity_hours', 'utilized_capacity_hours', 'utilization_percentage', 'last_updated')
    list_filter = ('last_updated', 'last_analysis')
    search_fields = ('board__name',)
    readonly_fields = ('last_updated', 'utilization_percentage', 'available_skills')
    
    fieldsets = (
        ('Board Information', {
            'fields': ('board',)
        }),
        ('Capacity Metrics', {
            'fields': ('total_capacity_hours', 'utilized_capacity_hours', 'utilization_percentage')
        }),
        ('Skill Inventory', {
            'fields': ('skill_inventory', 'available_skills'),
            'classes': ('collapse',),
            'description': 'Team-wide skill inventory and availability'
        }),
        ('Analysis Metadata', {
            'fields': ('last_updated', 'last_analysis'),
            'classes': ('collapse',)
        })
    )


@admin.register(SkillGap)
class SkillGapAdmin(admin.ModelAdmin):
    list_display = ('skill_name', 'proficiency_level', 'gap_count', 'severity', 'status', 'board', 'identified_at')
    list_filter = ('severity', 'status', 'proficiency_level', 'identified_at', 'board')
    search_fields = ('skill_name', 'board__name')
    readonly_fields = ('gap_count', 'identified_at', 'is_critical', 'gap_percentage')
    filter_horizontal = ('affected_tasks',)
    
    fieldsets = (
        ('Gap Information', {
            'fields': ('board', 'skill_name', 'proficiency_level', 'severity', 'status')
        }),
        ('Gap Metrics', {
            'fields': ('required_count', 'available_count', 'gap_count', 'gap_percentage', 'is_critical')
        }),
        ('Sprint Context', {
            'fields': ('sprint_period_start', 'sprint_period_end', 'affected_tasks'),
            'classes': ('collapse',)
        }),
        ('AI Analysis', {
            'fields': ('ai_recommendations', 'estimated_impact_hours', 'confidence_score'),
            'classes': ('collapse',),
            'description': 'AI-generated recommendations and impact analysis'
        }),
        ('Tracking', {
            'fields': ('identified_at', 'resolved_at', 'acknowledged_by'),
            'classes': ('collapse',)
        })
    )
    
    def save_model(self, request, obj, form, change):
        """Auto-calculate gap_count before saving"""
        obj.gap_count = max(0, obj.required_count - obj.available_count)
        super().save_model(request, obj, form, change)


@admin.register(SkillDevelopmentPlan)
class SkillDevelopmentPlanAdmin(admin.ModelAdmin):
    list_display = ('title', 'plan_type', 'target_skill', 'status', 'progress_percentage', 'board', 'created_at')
    list_filter = ('plan_type', 'status', 'target_proficiency', 'ai_suggested', 'created_at', 'board')
    search_fields = ('title', 'description', 'target_skill', 'board__name')
    readonly_fields = ('created_at', 'updated_at', 'is_overdue', 'days_until_target')
    filter_horizontal = ('target_users',)
    
    fieldsets = (
        ('Plan Information', {
            'fields': ('board', 'skill_gap', 'plan_type', 'title', 'description')
        }),
        ('Target & Goals', {
            'fields': ('target_skill', 'target_proficiency', 'target_users')
        }),
        ('Timeline & Budget', {
            'fields': ('start_date', 'target_completion_date', 'actual_completion_date', 
                      'estimated_cost', 'estimated_hours', 'is_overdue', 'days_until_target')
        }),
        ('Status & Progress', {
            'fields': ('status', 'progress_percentage')
        }),
        ('Impact Tracking', {
            'fields': ('expected_impact', 'actual_impact', 'success_metrics'),
            'classes': ('collapse',),
            'description': 'Track the impact and success of this development plan'
        }),
        ('Ownership', {
            'fields': ('created_by', 'assigned_to', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('AI Metadata', {
            'fields': ('ai_suggested', 'ai_confidence'),
            'classes': ('collapse',),
            'description': 'AI-related metadata for this plan'
        })
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make created_by read-only after creation"""
        if obj:  # Editing existing object
            return self.readonly_fields + ('created_by',)
        return self.readonly_fields


