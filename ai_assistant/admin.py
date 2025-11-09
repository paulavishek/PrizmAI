from django.contrib import admin
from .models import (
    AIAssistantSession,
    AIAssistantMessage,
    ProjectKnowledgeBase,
    AIAssistantAnalytics,
    AITaskRecommendation,
    UserPreference,
)


@admin.register(AIAssistantSession)
class AIAssistantSessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'board', 'message_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'board']
    search_fields = ['title', 'user__username', 'board__name']
    readonly_fields = ['created_at', 'updated_at', 'message_count', 'total_tokens_used']


@admin.register(AIAssistantMessage)
class AIAssistantMessageAdmin(admin.ModelAdmin):
    list_display = ['get_session_title', 'role', 'model', 'is_starred', 'used_web_search', 'created_at']
    list_filter = ['role', 'model', 'is_starred', 'used_web_search', 'created_at']
    search_fields = ['content', 'session__title']
    readonly_fields = ['created_at', 'tokens_used']
    
    def get_session_title(self, obj):
        return obj.session.title
    get_session_title.short_description = 'Session'


@admin.register(ProjectKnowledgeBase)
class ProjectKnowledgeBaseAdmin(admin.ModelAdmin):
    list_display = ['title', 'content_type', 'board', 'source_task', 'is_active', 'updated_at']
    list_filter = ['content_type', 'is_active', 'board', 'updated_at']
    search_fields = ['title', 'content', 'board__name']
    readonly_fields = ['created_at', 'updated_at', 'last_indexed']


@admin.register(AIAssistantAnalytics)
class AIAssistantAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['user', 'board', 'date', 'messages_sent', 'total_tokens_used', 'web_searches_performed']
    list_filter = ['date', 'board', 'user']
    search_fields = ['user__username', 'board__name']
    readonly_fields = ['date', 'created_at']


@admin.register(AITaskRecommendation)
class AITaskRecommendationAdmin(admin.ModelAdmin):
    list_display = ['title', 'task', 'recommendation_type', 'potential_impact', 'status', 'created_at']
    list_filter = ['recommendation_type', 'potential_impact', 'status', 'created_at']
    search_fields = ['title', 'description', 'task__title']
    readonly_fields = ['created_at', 'implemented_at']


@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'enable_web_search', 'updated_at']
    list_filter = ['enable_web_search']
    search_fields = ['user__username']
    readonly_fields = ['created_at', 'updated_at']
