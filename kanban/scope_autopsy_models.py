"""
Scope Creep Autopsy Models

Forensic post-mortem analysis of how a project's scope grew —
tracing every expansion to its exact cause, person, date, and cost impact.
"""
from django.db import models
from django.conf import settings


class ScopeAutopsyReport(models.Model):
    """A complete scope creep forensic report for a board."""

    STATUS_CHOICES = [
        ('generating', 'Generating'),
        ('complete', 'Complete'),
        ('failed', 'Failed'),
    ]

    board = models.ForeignKey(
        'kanban.Board', on_delete=models.CASCADE,
        related_name='scope_autopsies',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='generating',
    )

    # Baseline snapshot at project start
    baseline_task_count = models.IntegerField(default=0)
    baseline_date = models.DateTimeField(null=True, blank=True)

    # Final numbers
    final_task_count = models.IntegerField(default=0)
    total_scope_growth_percentage = models.FloatField(default=0.0)
    total_delay_days = models.IntegerField(default=0)
    total_budget_impact = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
    )

    # Full AI analysis stored as JSON
    timeline_json = models.JSONField(default=list)
    pattern_analysis = models.TextField(blank=True)
    ai_summary = models.TextField(blank=True)
    recommendations = models.JSONField(default=list)

    # Board snapshot used for analysis
    board_snapshot = models.JSONField(default=dict)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['board', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Scope Autopsy: {self.board.name} ({self.get_status_display()})"


class ScopeTimelineEvent(models.Model):
    """A single scope change event within an autopsy report."""

    SOURCE_TYPES = [
        ('task_added', 'Task Added Manually'),
        ('scope_alert', 'Scope Creep Alert'),
        ('conflict', 'Conflict Resolution'),
        ('meeting', 'Meeting Transcript'),
        ('ai_suggestion', 'AI Suggestion Accepted'),
        ('bulk_import', 'Bulk Task Import'),
        ('unknown', 'Unknown Source'),
    ]

    report = models.ForeignKey(
        ScopeAutopsyReport,
        on_delete=models.CASCADE,
        related_name='timeline_events',
    )
    event_date = models.DateTimeField()
    title = models.CharField(max_length=200)
    description = models.TextField()
    source_type = models.CharField(max_length=30, choices=SOURCE_TYPES)
    source_object_type = models.CharField(max_length=50, blank=True)
    source_object_id = models.IntegerField(null=True, blank=True)
    tasks_added = models.IntegerField(default=0)
    tasks_removed = models.IntegerField(default=0)
    net_task_change = models.IntegerField(default=0)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='scope_autopsy_events',
    )
    estimated_delay_days = models.IntegerField(default=0)
    estimated_budget_impact = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
    )
    cumulative_task_count = models.IntegerField(default=0)
    is_major_event = models.BooleanField(default=False)

    class Meta:
        ordering = ['event_date']
        indexes = [
            models.Index(fields=['report', 'event_date']),
        ]

    def __str__(self):
        return f"{self.event_date:%Y-%m-%d}: {self.title} (+{self.net_task_change})"
