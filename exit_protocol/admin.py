from django.contrib import admin
from .models import (
    ProjectHealthSignal, HospiceSession, ProjectOrgan,
    OrganTransplant, CemeteryEntry, HospiceDismissal
)


@admin.register(CemeteryEntry)
class CemeteryEntryAdmin(admin.ModelAdmin):
    list_display = ['project_name', 'cause_of_death', 'team_size',
                    'completion_pct_display', 'buried_at', 'is_resurrected']
    list_filter = ['cause_of_death', 'is_resurrected']
    search_fields = ['project_name', 'autopsy_summary']
    readonly_fields = ['buried_at', 'board', 'hospice_session', 'board_id_snapshot']


@admin.register(HospiceSession)
class HospiceSessionAdmin(admin.ModelAdmin):
    list_display = ['board', 'status', 'trigger_type', 'initiated_at', 'buried_at']
    list_filter = ['status', 'trigger_type']


@admin.register(ProjectOrgan)
class ProjectOrganAdmin(admin.ModelAdmin):
    list_display = ['name', 'organ_type', 'reusability_score', 'status', 'source_board']
    list_filter = ['organ_type', 'status']
    search_fields = ['name', 'description']


@admin.register(ProjectHealthSignal)
class ProjectHealthSignalAdmin(admin.ModelAdmin):
    list_display = ['board', 'hospice_risk_score', 'score_is_valid',
                    'dimensions_available', 'triggered_hospice', 'recorded_at']
    list_filter = ['score_is_valid', 'triggered_hospice']


@admin.register(OrganTransplant)
class OrganTransplantAdmin(admin.ModelAdmin):
    list_display = ['organ', 'target_board', 'compatibility_score',
                    'transplanted_at', 'approved_by']


@admin.register(HospiceDismissal)
class HospiceDismissalAdmin(admin.ModelAdmin):
    list_display = ['board', 'user', 'dismissed_at', 'expires_at']
