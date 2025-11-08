"""
Admin interface for API models
"""
from django.contrib import admin
from api.models import APIToken, APIRequestLog


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
