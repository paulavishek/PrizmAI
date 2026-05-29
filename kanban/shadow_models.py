"""
Shadow Board Models — Parallel Universe Simulator

Enables project managers to promote What-If scenarios into living, parallel
execution branches that automatically recalculate as real project changes occur.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ShadowBranch(models.Model):
    """
    A living parallel branch of a project — a "what-if" scenario promoted
    to represent a real alternative timeline.
    
    Unlike a static WhatIfScenario, a ShadowBranch stays alive and auto-recalculates
    whenever real board progress happens.
    """
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('archived', 'Archived'),
        ('committed', 'Committed'),
    ]
    
    board = models.ForeignKey(
        'kanban.Board',
        on_delete=models.CASCADE,
        related_name='shadow_branches',
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
    )
    source_scenario = models.ForeignKey(
        'kanban.WhatIfScenario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shadow_branches',
        help_text='Original What-If scenario this branch was promoted from',
    )
    branch_color = models.CharField(
        max_length=7,
        default='#0d6efd',
        help_text='Hex color code for UI color coding (e.g., #0d6efd, #198754)',
    )
    is_starred = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    baseline_velocity_per_week = models.FloatField(
        null=True,
        blank=True,
        help_text=(
            'Team velocity (tasks/week) the branch projection was created against. '
            'Compared against the live 7-day actual velocity to produce the velocity '
            'health adjustment in feasibility recalculations.'
        ),
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Shadow Branch'
        verbose_name_plural = 'Shadow Branches'
        indexes = [
            models.Index(fields=['board', 'status']),
            models.Index(fields=['board', 'created_at']),
        ]

    def __str__(self):
        return f'{self.name} ({self.get_status_display()}) – {self.board.name}'

    def get_latest_snapshot(self):
        """
        Retrieve the most recent snapshot for this branch.
        Used to get current feasibility score, deltas, and projections.
        """
        return self.snapshots.order_by('-captured_at').first()

    def get_score_history(self, limit=7):
        """
        Get feasibility score history for sparkline rendering.
        Returns list of (captured_at, feasibility_score) tuples, oldest first.
        """
        snapshots = self.snapshots.order_by('-captured_at')[:limit]
        return list(reversed([
            (s.captured_at, s.feasibility_score) for s in snapshots
        ]))


class BranchSnapshot(models.Model):
    """
    A point-in-time capture of a branch's state and projected outcomes.
    
    Snapshots are created whenever the branch is recalculated (triggered by
    real board changes). They record the deltas, feasibility score, and
    AI-generated insights.
    """
    
    branch = models.ForeignKey(
        ShadowBranch,
        on_delete=models.CASCADE,
        related_name='snapshots',
    )
    captured_at = models.DateTimeField(auto_now_add=True)
    
    # Slider values stored in this snapshot (for reproducibility)
    scope_delta = models.IntegerField(
        default=0,
        help_text='Number of tasks added/removed (+/-)',
    )
    team_delta = models.IntegerField(
        default=0,
        help_text='Number of team members added/removed (+/-)',
    )
    deadline_delta_weeks = models.IntegerField(
        default=0,
        help_text='Weeks to extend/reduce deadline (+/-)',
    )
    
    # Computed outcomes — feasibility kept at 2dp so micro-nudges from single
    # task completions actually persist instead of being rounded away.
    feasibility_score = models.DecimalField(
        default=0,
        max_digits=6,
        decimal_places=2,
        help_text='Feasibility score 0-100 (2dp precision retains micro-nudges)',
    )
    projected_completion_date = models.DateField(
        null=True,
        blank=True,
        help_text='AI-predicted project completion date',
    )
    projected_budget_utilization = models.FloatField(
        null=True,
        blank=True,
        help_text='Projected budget utilization percentage',
    )

    # Conflict and recommendation data
    conflicts_detected = models.JSONField(
        default=list,
        blank=True,
        help_text='JSON array of detected conflicts from feasibility analysis',
    )
    gemini_recommendation = models.TextField(
        blank=True,
        null=True,
        help_text='AI recommendation text from Gemini analysis',
    )

    # What produced this snapshot (e.g. 'Task "X" completed', 'Branch restored',
    # 'Manual refresh', 'Periodic branch refresh').  Used to tell real board
    # events apart from baseline corrections / heartbeats so the "How It
    # Affected Your Branches" standup only attributes change to genuine work.
    trigger_event = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Human-readable event that triggered this snapshot',
    )

    class Meta:
        ordering = ['-captured_at']
        verbose_name = 'Branch Snapshot'
        verbose_name_plural = 'Branch Snapshots'
        indexes = [
            models.Index(fields=['branch', '-captured_at']),
        ]

    def __str__(self):
        return f'{self.branch.name} snapshot @ {self.captured_at:%Y-%m-%d %H:%M}'


class BranchDivergenceLog(models.Model):
    """
    Audit trail of significant feasibility score changes.
    
    Logged whenever real board progress causes a branch's feasibility to shift
    by more than 5 points. Helps PMs understand how real-world changes impact
    alternative scenarios.
    """
    
    branch = models.ForeignKey(
        ShadowBranch,
        on_delete=models.CASCADE,
        related_name='divergence_logs',
    )
    logged_at = models.DateTimeField(auto_now_add=True)
    # 2dp precision, matching BranchSnapshot.feasibility_score, so sub-integer
    # divergences (e.g. a 5.4-point shift) don't get truncated to a misleading
    # integer when displayed in the "Significant Score Changes" feed.
    old_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text='Previous feasibility score (0-100, 2dp precision)',
    )
    new_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text='New feasibility score (0-100, 2dp precision)',
    )
    trigger_event = models.TextField(
        help_text='Description of what triggered the recalculation (e.g., "Task XYZ completed")',
    )

    class Meta:
        ordering = ['-logged_at']
        verbose_name = 'Branch Divergence Log'
        verbose_name_plural = 'Branch Divergence Logs'
        indexes = [
            models.Index(fields=['branch', '-logged_at']),
        ]

    def __str__(self):
        delta = self.new_score - self.old_score
        direction = '↑' if delta > 0 else '↓'
        return f'{self.branch.name} {direction}{abs(delta)} pts @ {self.logged_at:%Y-%m-%d %H:%M}'

    @property
    def score_delta(self):
        """Convenience property for template rendering."""
        return self.new_score - self.old_score
