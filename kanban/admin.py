from django.contrib import admin
from .models import (
    Board, Column, Task, TaskLabel, Comment, TaskActivity,
    TeamSkillProfile, SkillGap, SkillDevelopmentPlan,
    ScopeChangeSnapshot, ScopeCreepAlert, Milestone
)
from .priority_models import PriorityDecision, PriorityModel, PrioritySuggestionLog
from .burndown_models import (
    TeamVelocitySnapshot, BurndownPrediction, BurndownAlert, SprintMilestone
)
from .retrospective_models import (
    ProjectRetrospective, LessonLearned, ImprovementMetric,
    RetrospectiveActionItem, RetrospectiveTrend
)
from .budget_models import (
    ProjectBudget, TaskCost, TimeEntry, ProjectROI,
    BudgetRecommendation, CostPattern
)

# Import resource leveling admin
from .resource_leveling_admin import (
    UserPerformanceProfileAdmin,
    TaskAssignmentHistoryAdmin,
    ResourceLevelingSuggestionAdmin
)

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


# Burndown/Burnup Prediction Admin
@admin.register(TeamVelocitySnapshot)
class TeamVelocitySnapshotAdmin(admin.ModelAdmin):
    list_display = ('board', 'period_start', 'period_end', 'tasks_completed', 'story_points_completed', 
                   'active_team_members', 'velocity_per_member', 'quality_score')
    list_filter = ('board', 'period_type', 'period_end', 'created_at')
    search_fields = ('board__name',)
    readonly_fields = ('created_at', 'velocity_per_member', 'days_in_period')
    
    fieldsets = (
        ('Period Information', {
            'fields': ('board', 'period_start', 'period_end', 'period_type', 'days_in_period')
        }),
        ('Velocity Metrics', {
            'fields': ('tasks_completed', 'story_points_completed', 'hours_completed')
        }),
        ('Team Composition', {
            'fields': ('active_team_members', 'velocity_per_member', 'team_member_list')
        }),
        ('Quality Metrics', {
            'fields': ('tasks_reopened', 'quality_score')
        }),
        ('Metadata', {
            'fields': ('calculated_by', 'created_at'),
            'classes': ('collapse',)
        })
    )


@admin.register(BurndownPrediction)
class BurndownPredictionAdmin(admin.ModelAdmin):
    list_display = ('board', 'prediction_date', 'predicted_completion_date', 'days_margin_of_error',
                   'risk_level', 'delay_probability', 'confidence_percentage', 'completion_percentage')
    list_filter = ('board', 'risk_level', 'prediction_type', 'velocity_trend', 'prediction_date')
    search_fields = ('board__name',)
    readonly_fields = ('prediction_date', 'completion_probability_range', 'is_high_risk', 'completion_percentage')
    filter_horizontal = ('based_on_velocity_snapshots',)
    
    fieldsets = (
        ('Prediction Context', {
            'fields': ('board', 'prediction_type', 'prediction_date', 'target_completion_date')
        }),
        ('Current Scope', {
            'fields': ('total_tasks', 'completed_tasks', 'remaining_tasks', 'completion_percentage',
                      'total_story_points', 'completed_story_points', 'remaining_story_points')
        }),
        ('Velocity Analysis', {
            'fields': ('current_velocity', 'average_velocity', 'velocity_std_dev', 'velocity_trend')
        }),
        ('Prediction Results', {
            'fields': ('predicted_completion_date', 'completion_date_lower_bound', 'completion_date_upper_bound',
                      'days_until_completion_estimate', 'days_margin_of_error', 'completion_probability_range')
        }),
        ('Confidence & Risk', {
            'fields': ('confidence_percentage', 'prediction_confidence_score', 'delay_probability', 
                      'risk_level', 'is_high_risk')
        }),
        ('Target Comparison', {
            'fields': ('will_meet_target', 'days_ahead_behind_target'),
            'classes': ('collapse',)
        }),
        ('Data Visualization', {
            'fields': ('burndown_curve_data', 'confidence_bands_data', 'velocity_history_data'),
            'classes': ('collapse',),
            'description': 'Chart data for visualization'
        }),
        ('AI Suggestions', {
            'fields': ('actionable_suggestions',),
            'classes': ('collapse',)
        }),
        ('Model Details', {
            'fields': ('based_on_velocity_snapshots', 'model_parameters'),
            'classes': ('collapse',)
        })
    )


@admin.register(BurndownAlert)
class BurndownAlertAdmin(admin.ModelAdmin):
    list_display = ('board', 'alert_type', 'severity', 'status', 'title', 'created_at', 'is_active')
    list_filter = ('board', 'alert_type', 'severity', 'status', 'created_at')
    search_fields = ('title', 'message', 'board__name')
    readonly_fields = ('created_at', 'is_active')
    
    fieldsets = (
        ('Alert Information', {
            'fields': ('prediction', 'board', 'alert_type', 'severity', 'status')
        }),
        ('Details', {
            'fields': ('title', 'message')
        }),
        ('Metrics', {
            'fields': ('metric_value', 'threshold_value'),
            'classes': ('collapse',)
        }),
        ('Suggestions', {
            'fields': ('suggested_actions',),
            'classes': ('collapse',)
        }),
        ('Tracking', {
            'fields': ('created_at', 'acknowledged_at', 'acknowledged_by', 'resolved_at', 'is_active'),
            'classes': ('collapse',)
        })
    )


@admin.register(SprintMilestone)
class SprintMilestoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'board', 'target_date', 'is_completed', 'completion_percentage', 
                   'days_until_target', 'is_overdue')
    list_filter = ('board', 'is_completed', 'target_date', 'created_at')
    search_fields = ('name', 'description', 'board__name')
    readonly_fields = ('created_at', 'days_until_target', 'is_overdue')
    
    fieldsets = (
        ('Milestone Information', {
            'fields': ('board', 'name', 'description')
        }),
        ('Dates', {
            'fields': ('target_date', 'actual_date', 'days_until_target', 'is_overdue')
        }),
        ('Targets', {
            'fields': ('target_tasks_completed', 'target_story_points')
        }),
        ('Status', {
            'fields': ('is_completed', 'completion_percentage')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        })
    )


# Scope Tracking Admin
@admin.register(ScopeChangeSnapshot)
class ScopeChangeSnapshotAdmin(admin.ModelAdmin):
    list_display = ('board', 'snapshot_date', 'is_baseline', 'total_tasks', 
                   'total_complexity_points', 'scope_change_percentage', 'snapshot_type')
    list_filter = ('board', 'is_baseline', 'snapshot_type', 'snapshot_date')
    search_fields = ('board__name', 'notes')
    readonly_fields = ('snapshot_date', 'scope_change_percentage', 'complexity_change_percentage')
    
    fieldsets = (
        ('Snapshot Information', {
            'fields': ('board', 'snapshot_date', 'snapshot_type', 'is_baseline', 'notes')
        }),
        ('Scope Metrics', {
            'fields': ('total_tasks', 'total_complexity_points', 'avg_complexity', 
                      'high_priority_tasks', 'urgent_priority_tasks')
        }),
        ('Task Breakdown', {
            'fields': ('todo_tasks', 'in_progress_tasks', 'completed_tasks'),
            'classes': ('collapse',)
        }),
        ('Change Analysis', {
            'fields': ('baseline_snapshot', 'scope_change_percentage', 'complexity_change_percentage'),
            'classes': ('collapse',)
        }),
        ('AI Analysis', {
            'fields': ('ai_analysis', 'predicted_delay_days'),
            'classes': ('collapse',),
            'description': 'AI-generated analysis of scope changes'
        }),
        ('Metadata', {
            'fields': ('created_by',),
            'classes': ('collapse',)
        })
    )


@admin.register(ScopeCreepAlert)
class ScopeCreepAlertAdmin(admin.ModelAdmin):
    list_display = ('board', 'severity', 'status', 'scope_increase_percentage', 
                   'timeline_at_risk', 'detected_at', 'is_unresolved')
    list_filter = ('board', 'severity', 'status', 'timeline_at_risk', 'detected_at')
    search_fields = ('board__name', 'ai_summary', 'resolution_notes')
    readonly_fields = ('detected_at', 'days_since_detected', 'is_unresolved')
    
    fieldsets = (
        ('Alert Information', {
            'fields': ('board', 'snapshot', 'severity', 'status')
        }),
        ('Scope Changes', {
            'fields': ('scope_increase_percentage', 'complexity_increase_percentage', 
                      'tasks_added', 'timeline_at_risk')
        }),
        ('Impact Analysis', {
            'fields': ('predicted_delay_days', 'ai_summary'),
        }),
        ('AI Recommendations', {
            'fields': ('recommendations',),
            'classes': ('collapse',),
            'description': 'AI-generated recommendations to manage scope creep'
        }),
        ('Alert Lifecycle', {
            'fields': ('detected_at', 'days_since_detected', 'acknowledged_at', 'acknowledged_by',
                      'resolved_at', 'resolved_by', 'resolution_notes'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['mark_as_acknowledged', 'mark_as_resolved']
    
    def mark_as_acknowledged(self, request, queryset):
        for alert in queryset:
            alert.acknowledge(request.user)
        self.message_user(request, f'{queryset.count()} alert(s) marked as acknowledged.')
    mark_as_acknowledged.short_description = 'Mark selected alerts as acknowledged'
    
    def mark_as_resolved(self, request, queryset):
        for alert in queryset:
            alert.resolve(request.user)
        self.message_user(request, f'{queryset.count()} alert(s) marked as resolved.')
    mark_as_resolved.short_description = 'Mark selected alerts as resolved'


# ============================================================================
# RETROSPECTIVE MODELS ADMIN
# ============================================================================

@admin.register(ProjectRetrospective)
class ProjectRetrospectiveAdmin(admin.ModelAdmin):
    list_display = ('title', 'board', 'retrospective_type', 'status', 'period_start', 
                   'period_end', 'overall_sentiment_score', 'created_at')
    list_filter = ('retrospective_type', 'status', 'board', 'team_morale_indicator', 
                  'performance_trend', 'created_at')
    search_fields = ('title', 'board__name', 'what_went_well', 'what_needs_improvement')
    readonly_fields = ('ai_generated_at', 'ai_confidence_score', 'ai_model_used', 
                      'created_at', 'updated_at', 'metrics_snapshot')
    date_hierarchy = 'period_end'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('board', 'title', 'retrospective_type', 'status')
        }),
        ('Period', {
            'fields': ('period_start', 'period_end')
        }),
        ('AI Analysis', {
            'fields': ('what_went_well', 'what_needs_improvement', 'lessons_learned', 
                      'key_achievements', 'challenges_faced', 'improvement_recommendations')
        }),
        ('Sentiment & Trends', {
            'fields': ('overall_sentiment_score', 'team_morale_indicator', 
                      'performance_trend', 'previous_retrospective')
        }),
        ('Team Input', {
            'fields': ('team_notes', 'team_feedback_on_ai'),
            'classes': ('collapse',)
        }),
        ('AI Metadata', {
            'fields': ('ai_generated_at', 'ai_confidence_score', 'ai_model_used', 
                      'metrics_snapshot'),
            'classes': ('collapse',)
        }),
        ('Tracking', {
            'fields': ('created_by', 'created_at', 'updated_at', 'finalized_by', 'finalized_at')
        })
    )
    
    actions = ['mark_as_reviewed', 'mark_as_finalized']
    
    def mark_as_reviewed(self, request, queryset):
        queryset.update(status='reviewed')
        self.message_user(request, f'{queryset.count()} retrospective(s) marked as reviewed.')
    mark_as_reviewed.short_description = 'Mark as reviewed'
    
    def mark_as_finalized(self, request, queryset):
        for retro in queryset:
            retro.finalize(request.user)
        self.message_user(request, f'{queryset.count()} retrospective(s) finalized.')
    mark_as_finalized.short_description = 'Mark as finalized'


@admin.register(LessonLearned)
class LessonLearnedAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'priority', 'status', 'retrospective', 
                   'board', 'ai_suggested', 'created_at')
    list_filter = ('category', 'priority', 'status', 'ai_suggested', 'is_recurring_issue', 
                  'board', 'created_at')
    search_fields = ('title', 'description', 'recommended_action', 'board__name')
    readonly_fields = ('ai_confidence', 'recurrence_count', 'created_at', 'updated_at')
    filter_horizontal = ('related_lessons',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('retrospective', 'board', 'title', 'description', 'category', 'priority')
        }),
        ('Context', {
            'fields': ('trigger_event', 'impact_description')
        }),
        ('Action', {
            'fields': ('recommended_action', 'action_owner', 'status', 
                      'implementation_date', 'validation_date')
        }),
        ('Impact Measurement', {
            'fields': ('expected_benefit', 'actual_benefit', 'success_metrics'),
            'classes': ('collapse',)
        }),
        ('AI & Recurrence', {
            'fields': ('ai_suggested', 'ai_confidence', 'is_recurring_issue', 
                      'recurrence_count', 'related_lessons'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['mark_implemented', 'mark_validated']
    
    def mark_implemented(self, request, queryset):
        for lesson in queryset:
            lesson.mark_implemented(request.user)
        self.message_user(request, f'{queryset.count()} lesson(s) marked as implemented.')
    mark_implemented.short_description = 'Mark as implemented'
    
    def mark_validated(self, request, queryset):
        for lesson in queryset:
            lesson.mark_validated()
        self.message_user(request, f'{queryset.count()} lesson(s) marked as validated.')
    mark_validated.short_description = 'Mark as validated'


@admin.register(ImprovementMetric)
class ImprovementMetricAdmin(admin.ModelAdmin):
    list_display = ('metric_name', 'metric_type', 'metric_value', 'trend', 
                   'board', 'retrospective', 'measured_at')
    list_filter = ('metric_type', 'trend', 'higher_is_better', 'board', 'measured_at')
    search_fields = ('metric_name', 'description', 'board__name')
    readonly_fields = ('change_amount', 'change_percentage', 'trend', 'created_at')
    date_hierarchy = 'measured_at'
    
    fieldsets = (
        ('Metric Information', {
            'fields': ('board', 'retrospective', 'metric_type', 'metric_name', 'description')
        }),
        ('Values', {
            'fields': ('metric_value', 'previous_value', 'target_value', 
                      'unit_of_measure', 'higher_is_better')
        }),
        ('Change Analysis', {
            'fields': ('change_amount', 'change_percentage', 'trend'),
            'classes': ('collapse',)
        }),
        ('Tracking', {
            'fields': ('measured_at', 'created_at')
        })
    )


@admin.register(RetrospectiveActionItem)
class RetrospectiveActionItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'action_type', 'priority', 'status', 'assigned_to', 
                   'target_completion_date', 'progress_percentage', 'board')
    list_filter = ('action_type', 'priority', 'status', 'ai_suggested', 'board', 
                  'target_completion_date')
    search_fields = ('title', 'description', 'expected_impact', 'board__name')
    readonly_fields = ('ai_confidence', 'created_at', 'updated_at')
    filter_horizontal = ('stakeholders',)
    date_hierarchy = 'target_completion_date'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('retrospective', 'board', 'title', 'description', 
                      'action_type', 'priority')
        }),
        ('Assignment', {
            'fields': ('assigned_to', 'stakeholders')
        }),
        ('Timeline', {
            'fields': ('target_completion_date', 'actual_completion_date', 
                      'progress_percentage', 'status')
        }),
        ('Impact', {
            'fields': ('expected_impact', 'actual_impact'),
            'classes': ('collapse',)
        }),
        ('Blocking', {
            'fields': ('blocked_reason', 'blocked_date', 'progress_notes'),
            'classes': ('collapse',)
        }),
        ('Related Data', {
            'fields': ('related_lesson', 'related_task'),
            'classes': ('collapse',)
        }),
        ('AI Metadata', {
            'fields': ('ai_suggested', 'ai_confidence'),
            'classes': ('collapse',)
        }),
        ('Tracking', {
            'fields': ('created_at', 'updated_at')
        })
    )
    
    actions = ['mark_completed', 'mark_blocked']
    
    def mark_completed(self, request, queryset):
        for action in queryset:
            action.mark_completed()
        self.message_user(request, f'{queryset.count()} action(s) marked as completed.')
    mark_completed.short_description = 'Mark as completed'
    
    def mark_blocked(self, request, queryset):
        queryset.update(status='blocked', blocked_date=admin.models.timezone.now().date())
        self.message_user(request, f'{queryset.count()} action(s) marked as blocked.')
    mark_blocked.short_description = 'Mark as blocked'


@admin.register(RetrospectiveTrend)
class RetrospectiveTrendAdmin(admin.ModelAdmin):
    list_display = ('board', 'period_type', 'analysis_date', 'retrospectives_analyzed',
                   'implementation_rate', 'completion_rate', 'velocity_trend')
    list_filter = ('period_type', 'velocity_trend', 'quality_trend', 'board', 'analysis_date')
    search_fields = ('board__name', 'ai_insights')
    readonly_fields = ('implementation_rate', 'completion_rate', 'created_at')
    date_hierarchy = 'analysis_date'
    
    fieldsets = (
        ('Analysis Context', {
            'fields': ('board', 'period_type', 'analysis_date', 'retrospectives_analyzed')
        }),
        ('Lessons Learned Metrics', {
            'fields': ('total_lessons_learned', 'lessons_implemented', 
                      'lessons_validated', 'implementation_rate')
        }),
        ('Action Items Metrics', {
            'fields': ('total_action_items', 'action_items_completed', 'completion_rate')
        }),
        ('Patterns', {
            'fields': ('recurring_issues', 'top_improvement_categories')
        }),
        ('Trends', {
            'fields': ('velocity_trend', 'quality_trend')
        }),
        ('AI Insights', {
            'fields': ('ai_insights', 'key_recommendations'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',)
        })
    )



@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ('title', 'board', 'target_date', 'milestone_type', 'is_completed', 
                   'completion_percentage', 'status', 'created_by')
    list_filter = ('board', 'milestone_type', 'is_completed', 'target_date', 'created_at')
    search_fields = ('title', 'description', 'board__name')
    readonly_fields = ('created_at', 'updated_at', 'is_overdue', 'completion_percentage', 'status')
    filter_horizontal = ('related_tasks',)
    date_hierarchy = 'target_date'
    
    fieldsets = (
        ('Milestone Information', {
            'fields': ('board', 'title', 'description', 'milestone_type')
        }),
        ('Timeline', {
            'fields': ('target_date', 'is_completed', 'completed_date', 'is_overdue', 'status')
        }),
        ('Related Tasks', {
            'fields': ('related_tasks', 'completion_percentage'),
            'classes': ('collapse',),
            'description': 'Tasks that must be completed for this milestone'
        }),
        ('Visual', {
            'fields': ('color',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['mark_as_completed', 'mark_as_incomplete']
    
    def mark_as_completed(self, request, queryset):
        for milestone in queryset:
            milestone.mark_complete(request.user)
        self.message_user(request, f'{queryset.count()} milestone(s) marked as completed.')
    mark_as_completed.short_description = 'Mark selected milestones as completed'
    
    def mark_as_incomplete(self, request, queryset):
        for milestone in queryset:
            milestone.mark_incomplete()
        self.message_user(request, f'{queryset.count()} milestone(s) marked as incomplete.')
    mark_as_incomplete.short_description = 'Mark selected milestones as incomplete'


# Budget & ROI Tracking Admin
@admin.register(ProjectBudget)
class ProjectBudgetAdmin(admin.ModelAdmin):
    list_display = ('board', 'allocated_budget', 'currency', 'get_utilization', 'get_status', 'created_at')
    list_filter = ('currency', 'ai_optimization_enabled', 'created_at')
    search_fields = ('board__name',)
    readonly_fields = ('created_at', 'updated_at', 'last_ai_analysis')
    
    def get_utilization(self, obj):
        return f"{obj.get_budget_utilization_percent():.1f}%"
    get_utilization.short_description = 'Utilization'
    
    def get_status(self, obj):
        return obj.get_status()
    get_status.short_description = 'Status'


@admin.register(TaskCost)
class TaskCostAdmin(admin.ModelAdmin):
    list_display = ('task', 'estimated_cost', 'actual_cost', 'get_total_cost', 'is_over_budget', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('task__title',)
    readonly_fields = ('created_at', 'updated_at')
    
    def get_total_cost(self, obj):
        return f"{obj.get_total_actual_cost():.2f}"
    get_total_cost.short_description = 'Total Cost'


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ('task', 'user', 'hours_spent', 'work_date', 'created_at')
    list_filter = ('work_date', 'user', 'created_at')
    search_fields = ('task__title', 'user__username', 'description')
    date_hierarchy = 'work_date'
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ProjectROI)
class ProjectROIAdmin(admin.ModelAdmin):
    list_display = ('board', 'snapshot_date', 'roi_percentage', 'total_cost', 'expected_value', 'completed_tasks')
    list_filter = ('snapshot_date', 'created_at')
    search_fields = ('board__name',)
    readonly_fields = ('created_at', 'snapshot_date')


@admin.register(BudgetRecommendation)
class BudgetRecommendationAdmin(admin.ModelAdmin):
    list_display = ('title', 'board', 'recommendation_type', 'priority', 'status', 'confidence_score', 'created_at')
    list_filter = ('recommendation_type', 'priority', 'status', 'created_at')
    search_fields = ('title', 'description', 'board__name')
    readonly_fields = ('created_at', 'reviewed_at')
    
    actions = ['mark_as_accepted', 'mark_as_rejected']
    
    def mark_as_accepted(self, request, queryset):
        queryset.update(status='accepted', reviewed_by=request.user, reviewed_at=admin.models.timezone.now())
        self.message_user(request, f'{queryset.count()} recommendation(s) accepted.')
    mark_as_accepted.short_description = 'Mark selected as accepted'
    
    def mark_as_rejected(self, request, queryset):
        queryset.update(status='rejected', reviewed_by=request.user, reviewed_at=admin.models.timezone.now())
        self.message_user(request, f'{queryset.count()} recommendation(s) rejected.')
    mark_as_rejected.short_description = 'Mark selected as rejected'


@admin.register(CostPattern)
class CostPatternAdmin(admin.ModelAdmin):
    list_display = ('pattern_name', 'board', 'pattern_type', 'confidence', 'occurrence_count', 'last_occurred')
    list_filter = ('pattern_type', 'last_occurred', 'created_at')
    search_fields = ('pattern_name', 'board__name')
    readonly_fields = ('created_at', 'updated_at')
