"""
What-If Scenario Analyzer Models

Stores persisted what-if scenarios so PMs can save, compare, and revisit
hypothetical project changes and their projected impacts.
"""
from django.db import models
from django.contrib.auth.models import User


class WhatIfScenario(models.Model):
    """A saved what-if scenario with input parameters and computed results."""

    SCENARIO_TYPES = [
        ('scope_change', 'Scope Change'),
        ('team_change', 'Team Change'),
        ('deadline_change', 'Deadline Change'),
        ('combined', 'Combined'),
    ]

    board = models.ForeignKey(
        'kanban.Board',
        on_delete=models.CASCADE,
        related_name='whatif_scenarios',
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=200)
    scenario_type = models.CharField(max_length=20, choices=SCENARIO_TYPES, default='combined')
    input_parameters = models.JSONField(
        default=dict,
        help_text='Slider values: tasks_added, team_size_delta, deadline_shift_days',
    )
    baseline_snapshot = models.JSONField(
        default=dict,
        help_text='Board state at the time of analysis',
    )
    impact_results = models.JSONField(
        default=dict,
        help_text='Computed before/after comparison and deltas',
    )
    ai_analysis = models.JSONField(
        default=dict,
        blank=True,
        help_text='Gemini AI analysis of the scenario',
    )
    is_starred = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'What-If Scenario'
        verbose_name_plural = 'What-If Scenarios'

    def __str__(self):
        return f'{self.name} – {self.board.name} ({self.created_at:%Y-%m-%d})'
