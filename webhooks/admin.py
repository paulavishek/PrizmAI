"""
Admin Interface for Webhooks
"""
from django.contrib import admin
from webhooks.models import Webhook, WebhookDelivery, WebhookEvent


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'board', 'is_active', 'status',
        'total_deliveries', 'successful_deliveries', 'failed_deliveries',
        'success_rate', 'last_triggered', 'created_at'
    ]
    list_filter = ['is_active', 'status', 'created_at']
    search_fields = ['name', 'url', 'board__name']
    readonly_fields = [
        'created_at', 'updated_at', 'last_triggered',
        'total_deliveries', 'successful_deliveries', 'failed_deliveries',
        'consecutive_failures', 'success_rate'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'url', 'board', 'created_by', 'events')
        }),
        ('Status', {
            'fields': ('is_active', 'status')
        }),
        ('Delivery Settings', {
            'fields': ('timeout_seconds', 'max_retries', 'retry_delay_seconds')
        }),
        ('Security', {
            'fields': ('secret', 'custom_headers'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': (
                'total_deliveries', 'successful_deliveries', 'failed_deliveries',
                'consecutive_failures', 'success_rate'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_triggered'),
            'classes': ('collapse',)
        }),
    )
    
    def success_rate(self, obj):
        return f"{obj.success_rate}%"
    success_rate.short_description = 'Success Rate'


@admin.register(WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'webhook', 'event_type', 'status',
        'response_status_code', 'response_time_ms',
        'retry_count', 'created_at', 'delivered_at'
    ]
    list_filter = ['status', 'event_type', 'created_at']
    search_fields = ['webhook__name', 'event_type', 'error_message']
    readonly_fields = [
        'webhook', 'event_type', 'payload', 'status',
        'response_status_code', 'response_body', 'response_time_ms',
        'error_message', 'retry_count', 'created_at', 'delivered_at'
    ]
    
    fieldsets = (
        ('Delivery Information', {
            'fields': ('webhook', 'event_type', 'status', 'retry_count')
        }),
        ('Payload', {
            'fields': ('payload',),
            'classes': ('collapse',)
        }),
        ('Response', {
            'fields': (
                'response_status_code', 'response_body',
                'response_time_ms', 'error_message'
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'delivered_at', 'next_retry_at')
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'event_type', 'board', 'object_id',
        'triggered_by', 'webhooks_triggered', 'created_at'
    ]
    list_filter = ['event_type', 'created_at']
    search_fields = ['event_type', 'board__name']
    readonly_fields = [
        'event_type', 'board', 'object_id', 'data',
        'triggered_by', 'created_at', 'webhooks_triggered'
    ]
    
    fieldsets = (
        ('Event Information', {
            'fields': ('event_type', 'board', 'object_id', 'triggered_by')
        }),
        ('Data', {
            'fields': ('data',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('webhooks_triggered', 'created_at')
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
