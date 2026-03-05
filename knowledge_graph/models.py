from django.db import models
from django.conf import settings


class MemoryNode(models.Model):
    """A single captured memory — one decision, event, or lesson."""

    NODE_TYPES = [
        ('decision', 'Decision Made'),
        ('lesson', 'Lesson Learned'),
        ('risk_event', 'Risk Event'),
        ('outcome', 'Project Outcome'),
        ('conflict_resolution', 'Conflict Resolution'),
        ('scope_change', 'Scope Change'),
        ('milestone', 'Milestone Reached'),
        ('ai_recommendation', 'AI Recommendation'),
        ('manual_log', 'Manual Decision Log'),
    ]

    board = models.ForeignKey(
        'kanban.Board', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='memory_nodes',
    )
    mission = models.ForeignKey(
        'kanban.Mission', on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    node_type = models.CharField(max_length=30, choices=NODE_TYPES)
    title = models.CharField(max_length=200)
    content = models.TextField()
    context_data = models.JSONField(default=dict, blank=True)
    tags = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_auto_captured = models.BooleanField(default=True)
    source_object_type = models.CharField(max_length=50, blank=True, default='')
    source_object_id = models.IntegerField(null=True, blank=True)
    importance_score = models.FloatField(default=0.5)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['board', '-importance_score']),
            models.Index(fields=['node_type']),
            models.Index(fields=['source_object_type', 'source_object_id']),
        ]

    def __str__(self):
        return f"[{self.get_node_type_display()}] {self.title}"


class MemoryConnection(models.Model):
    """Links between memory nodes — the 'graph' part."""

    CONNECTION_TYPES = [
        ('caused', 'Caused'),
        ('similar_to', 'Similar To'),
        ('led_to', 'Led To'),
        ('prevented', 'Prevented'),
        ('repeated_from', 'Repeated From Past Project'),
    ]

    from_node = models.ForeignKey(
        MemoryNode, on_delete=models.CASCADE, related_name='outgoing_connections',
    )
    to_node = models.ForeignKey(
        MemoryNode, on_delete=models.CASCADE, related_name='incoming_connections',
    )
    connection_type = models.CharField(max_length=30, choices=CONNECTION_TYPES)
    reason = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    ai_generated = models.BooleanField(default=True)

    class Meta:
        unique_together = ('from_node', 'to_node', 'connection_type')

    def __str__(self):
        return f"{self.from_node_id} --[{self.connection_type}]--> {self.to_node_id}"


class OrganizationalMemoryQuery(models.Model):
    """Logs questions asked to the organizational memory search."""

    asked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
    )
    query_text = models.TextField()
    response_json = models.JSONField(default=dict)
    nodes_referenced = models.ManyToManyField(MemoryNode, blank=True)
    asked_at = models.DateTimeField(auto_now_add=True)
    was_helpful = models.BooleanField(null=True)

    class Meta:
        ordering = ['-asked_at']

    def __str__(self):
        return f"Query by {self.asked_by}: {self.query_text[:60]}"
