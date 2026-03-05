"""
Decision Center Models
Unified decision queue that batches conflicts, risks, overdue tasks,
over-allocations, scope alerts, budget warnings, and quick wins into
one prioritised morning review for each PM.
"""
from datetime import time

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class DecisionItem(models.Model):
    """A single item requiring PM attention, collected for batch review."""

    ITEM_TYPES = [
        ('conflict', 'Unresolved Conflict'),
        ('premortem_risk', 'Pre-Mortem Risk Unacknowledged'),
        ('overdue_task', 'Overdue Tasks'),
        ('overallocated', 'Team Member Over-Allocated'),
        ('scope_change', 'Scope Change Detected'),
        ('budget_threshold', 'Budget Threshold Crossed'),
        ('deadline_approaching', 'Deadline Approaching'),
        ('unassigned_task', 'Unassigned Tasks'),
        ('stale_task', 'Stale Tasks'),
        ('ai_recommendation', 'AI Recommendation Pending'),
        ('memory_captured', 'New Knowledge Memory Captured'),
    ]

    PRIORITY_LEVELS = [
        ('action_required', 'Action Required'),
        ('awareness', 'Awareness Only'),
        ('quick_win', 'Quick Win'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('resolved', 'Resolved'),
        ('snoozed', 'Snoozed'),
        ('dismissed', 'Dismissed'),
    ]

    created_for = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='decision_items',
    )
    board = models.ForeignKey(
        'kanban.Board',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='decision_items',
    )
    item_type = models.CharField(max_length=30, choices=ITEM_TYPES)
    priority_level = models.CharField(max_length=20, choices=PRIORITY_LEVELS)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    suggested_action = models.TextField(blank=True)

    # Generic FK to the source object (ConflictDetection, ScopeCreepAlert, …)
    source_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    source_object_id = models.PositiveIntegerField(null=True, blank=True)
    source_object = GenericForeignKey('source_content_type', 'source_object_id')

    context_data = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_decisions',
    )
    snoozed_until = models.DateTimeField(null=True, blank=True)
    estimated_minutes = models.PositiveSmallIntegerField(default=2)

    class Meta:
        ordering = ['status', 'priority_level', '-created_at']
        indexes = [
            models.Index(fields=['created_for', 'status']),
            models.Index(fields=['created_for', 'status', 'priority_level']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_priority_level_display()})"


class DecisionCenterBriefing(models.Model):
    """AI-generated morning summary for a user's decision queue."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='decision_briefings',
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    headline = models.CharField(max_length=300)
    briefing = models.TextField()
    estimated_minutes = models.PositiveSmallIntegerField(default=0)
    top_priority_board = models.CharField(max_length=200, blank=True)
    item_counts = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"Briefing for {self.user} @ {self.generated_at:%Y-%m-%d %H:%M}"


class DecisionCenterSettings(models.Model):
    """Per-user preferences for the Decision Center."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='decision_center_settings',
    )
    daily_digest_enabled = models.BooleanField(default=True)
    digest_time = models.TimeField(default=time(8, 0))
    show_awareness_items = models.BooleanField(default=True)
    show_quick_wins = models.BooleanField(default=True)
    min_overdue_days = models.PositiveSmallIntegerField(default=2)
    min_stale_days = models.PositiveSmallIntegerField(default=14)
    budget_alert_threshold = models.PositiveSmallIntegerField(default=80)
    deadline_warning_days = models.PositiveSmallIntegerField(default=7)

    class Meta:
        verbose_name = 'Decision Center Settings'
        verbose_name_plural = 'Decision Center Settings'

    def __str__(self):
        return f"Decision Center Settings for {self.user}"
