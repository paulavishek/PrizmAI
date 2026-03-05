"""
Pre-Mortem AI Analysis Models
Stores AI-generated failure scenario analyses for boards,
and tracks which scenarios have been acknowledged by team members.
"""
from django.db import models
from django.conf import settings


class PreMortemAnalysis(models.Model):
    """
    Stores the result of an AI Pre-Mortem analysis for a board.
    Each run generates 5 failure scenarios with risk assessments.
    """
    RISK_LEVELS = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]

    board = models.ForeignKey('Board', on_delete=models.CASCADE, related_name='pre_mortems')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='pre_mortem_analyses'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    overall_risk_level = models.CharField(max_length=10, choices=RISK_LEVELS)
    analysis_json = models.JSONField(help_text="Full 5-scenario AI output")
    board_snapshot = models.JSONField(help_text="Board data used for the analysis")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Pre-Mortem Analysis'
        verbose_name_plural = 'Pre-Mortem Analyses'

    def __str__(self):
        return f"Pre-Mortem for {self.board.name} ({self.created_at:%Y-%m-%d})"


class PreMortemScenarioAcknowledgment(models.Model):
    """
    Tracks which failure scenarios a team member has acknowledged/addressed.
    """
    pre_mortem = models.ForeignKey(
        PreMortemAnalysis, on_delete=models.CASCADE, related_name='acknowledgments'
    )
    scenario_index = models.IntegerField(help_text="0-4, which of the 5 scenarios")
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='premortem_acknowledgments'
    )
    acknowledged_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-acknowledged_at']
        unique_together = ['pre_mortem', 'scenario_index', 'acknowledged_by']
        verbose_name = 'Pre-Mortem Scenario Acknowledgment'

    def __str__(self):
        return f"Scenario {self.scenario_index} ack by {self.acknowledged_by}"
