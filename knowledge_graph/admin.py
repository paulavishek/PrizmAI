from django.contrib import admin
from knowledge_graph.models import MemoryNode, MemoryConnection, OrganizationalMemoryQuery


@admin.register(MemoryNode)
class MemoryNodeAdmin(admin.ModelAdmin):
    list_display = ('title', 'node_type', 'board', 'importance_score', 'is_auto_captured', 'created_at')
    list_filter = ('node_type', 'is_auto_captured', 'created_at')
    search_fields = ('title', 'content')
    raw_id_fields = ('board', 'mission', 'created_by')
    readonly_fields = ('created_at',)


@admin.register(MemoryConnection)
class MemoryConnectionAdmin(admin.ModelAdmin):
    list_display = ('from_node', 'connection_type', 'to_node', 'ai_generated', 'created_at')
    list_filter = ('connection_type', 'ai_generated')
    raw_id_fields = ('from_node', 'to_node')


@admin.register(OrganizationalMemoryQuery)
class OrganizationalMemoryQueryAdmin(admin.ModelAdmin):
    list_display = ('asked_by', 'query_text_short', 'was_helpful', 'asked_at')
    list_filter = ('was_helpful', 'asked_at')
    raw_id_fields = ('asked_by',)

    def query_text_short(self, obj):
        return obj.query_text[:80]
    query_text_short.short_description = 'Query'
