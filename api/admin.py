"""
Admin interface for API models
"""
from django.contrib import admin
from api.models import APIToken, APIRequestLog, AIUsageQuota, AIRequestLog as AILog
from api.ai_usage_models import AIUsageQuota, AIRequestLog as AILog


@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'user', 'is_active', 'created_at', 'last_used',
        'request_count_current_hour', 'rate_limit_per_hour'
    ]
    list_filter = ['is_active', 'created_at', 'last_used']
    search_fields = ['name', 'user__username', 'user__email', 'token']
    readonly_fields = [
        'token', 'created_at', 'last_used', 'request_count_current_hour',
        'rate_limit_reset_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'name', 'token', 'is_active')
        }),
        ('Permissions', {
            'fields': ('scopes', 'ip_whitelist')
        }),
        ('Rate Limiting', {
            'fields': (
                'rate_limit_per_hour',
                'request_count_current_hour',
                'rate_limit_reset_at'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_used', 'expires_at')
        }),
        ('Metadata', {
            'fields': ('user_agent',),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing object
            return self.readonly_fields + ('user',)
        return self.readonly_fields


@admin.register(APIRequestLog)
class APIRequestLogAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp', 'token', 'method', 'endpoint',
        'status_code', 'response_time_ms', 'ip_address'
    ]
    list_filter = ['method', 'status_code', 'timestamp']
    search_fields = ['endpoint', 'ip_address', 'token__name']
    readonly_fields = [
        'token', 'endpoint', 'method', 'status_code',
        'response_time_ms', 'ip_address', 'user_agent',
        'timestamp', 'error_message'
    ]
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AIUsageQuota)
class AIUsageQuotaAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'requests_used', 'monthly_quota', 'get_usage_percent',
        'get_remaining_requests', 'period_end', 'last_request_at'
    ]
    list_filter = ['period_start', 'period_end']
    search_fields = ['user__username', 'user__email']
    readonly_fields = [
        'requests_used', 'total_requests_all_time', 'last_request_at',
        'created_at', 'updated_at', 'period_start', 'period_end'
    ]
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Quota', {
            'fields': ('monthly_quota', 'requests_used', 'total_requests_all_time')
        }),
        ('Period', {
            'fields': ('period_start', 'period_end', 'last_request_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing object
            return self.readonly_fields + ('user',)
        return self.readonly_fields


@admin.register(AILog)
class AIRequestLogAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp', 'user', 'feature', 'request_type',
        'success', 'response_time_ms', 'ai_model'
    ]
    list_filter = ['feature', 'success', 'ai_model', 'timestamp']
    search_fields = ['user__username', 'feature', 'request_type']
    readonly_fields = [
        'user', 'feature', 'request_type', 'ai_model',
        'tokens_used', 'success', 'error_message',
        'response_time_ms', 'board_id', 'timestamp'
    ]
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
