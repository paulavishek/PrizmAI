from django.contrib import admin

from .models import DecisionCenterBriefing, DecisionCenterSettings, DecisionItem


@admin.register(DecisionItem)
class DecisionItemAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'item_type', 'priority_level', 'status',
        'board', 'created_for', 'created_at',
    )
    list_filter = ('status', 'priority_level', 'item_type')
    search_fields = ('title',)
    raw_id_fields = ('created_for', 'board', 'resolved_by')
    readonly_fields = ('created_at', 'resolved_at')


@admin.register(DecisionCenterBriefing)
class DecisionCenterBriefingAdmin(admin.ModelAdmin):
    list_display = ('user', 'headline', 'estimated_minutes', 'generated_at')
    list_filter = ('generated_at',)
    raw_id_fields = ('user',)
    readonly_fields = ('generated_at',)


@admin.register(DecisionCenterSettings)
class DecisionCenterSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'daily_digest_enabled', 'min_overdue_days', 'min_stale_days')
    raw_id_fields = ('user',)
