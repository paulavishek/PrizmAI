"""
Project Stress Test Models

Stores adversarial AI simulation sessions, immunity scores,
attack scenarios, and vaccine (structural fix) recommendations.
"""
from django.db import models
from django.conf import settings


class StressTestSession(models.Model):
    """One complete Red Team AI run against a board."""
    board = models.ForeignKey(
        'Board', on_delete=models.CASCADE, related_name='stress_test_sessions'
    )
    run_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='stress_test_runs'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    score_rationale = models.TextField(blank=True)
    assumptions_made = models.JSONField(default=list)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Stress Test Session'

    def __str__(self):
        return f"Stress Test — {self.board.name} — {self.created_at:%Y-%m-%d}"

    @property
    def scenarios_fail_count(self):
        return self.scenarios.filter(outcome='FAIL').count()

    @property
    def vaccines_applied_count(self):
        return self.vaccines.filter(is_applied=True).count()


class ImmunityScore(models.Model):
    """Composite score and 5 dimension scores for one session."""
    session = models.OneToOneField(
        StressTestSession, on_delete=models.CASCADE, related_name='immunity_score'
    )
    overall = models.IntegerField()
    schedule = models.IntegerField()
    budget = models.IntegerField()
    team = models.IntegerField()
    dependencies = models.IntegerField()
    scope_stability = models.IntegerField()
    # Rationale per dimension
    schedule_rationale = models.TextField(blank=True)
    budget_rationale = models.TextField(blank=True)
    team_rationale = models.TextField(blank=True)
    dependencies_rationale = models.TextField(blank=True)
    scope_stability_rationale = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Immunity Score'

    def get_band(self):
        if self.overall >= 90:
            return 'ANTIFRAGILE'
        elif self.overall >= 70:
            return 'RESILIENT'
        elif self.overall >= 40:
            return 'MODERATE'
        return 'FRAGILE'

    def get_band_colour(self):
        bands = {
            'ANTIFRAGILE': '#0891b2',
            'RESILIENT': '#059669',
            'MODERATE': '#d97706',
            'FRAGILE': '#c0392b',
        }
        return bands[self.get_band()]

    def __str__(self):
        return f"Immunity {self.overall} ({self.get_band()}) — Session #{self.session_id}"


class StressTestScenario(models.Model):
    """One simulated attack within a session."""
    OUTCOME_CHOICES = [
        ('FAIL', 'Critical Fail'),
        ('SURVIVED_BARELY', 'Survived (Barely)'),
        ('SURVIVED', 'Survived'),
    ]

    session = models.ForeignKey(
        StressTestSession, on_delete=models.CASCADE, related_name='scenarios'
    )
    scenario_number = models.IntegerField()
    attack_type = models.CharField(max_length=60)
    title = models.CharField(max_length=120)
    attack_description = models.TextField()
    cascade_effect = models.TextField()
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES)
    severity = models.IntegerField()
    tasks_blocked = models.IntegerField(default=0)
    estimated_delay_weeks = models.IntegerField(null=True, blank=True)
    has_recovery_path = models.BooleanField(default=False)
    early_warning_sign = models.TextField(blank=True)
    tags = models.JSONField(default=list)
    is_addressed = models.BooleanField(default=False)
    addressed_at = models.DateTimeField(null=True, blank=True)
    addressed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='addressed_scenarios'
    )

    class Meta:
        ordering = ['-severity']
        verbose_name = 'Stress Test Scenario'

    def get_outcome_display_label(self):
        labels = {
            'FAIL': 'CRITICAL FAIL',
            'SURVIVED_BARELY': 'SURVIVED (Barely)',
            'SURVIVED': 'SURVIVED',
        }
        return labels.get(self.outcome, self.outcome)

    def get_outcome_css_class(self):
        classes = {
            'FAIL': 'danger',
            'SURVIVED_BARELY': 'warning',
            'SURVIVED': 'success',
        }
        return classes.get(self.outcome, 'secondary')

    def __str__(self):
        return f"#{self.scenario_number} {self.title} ({self.outcome})"


class Vaccine(models.Model):
    """A structural fix recommendation targeting one attack scenario."""
    EFFORT_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
    ]

    session = models.ForeignKey(
        StressTestSession, on_delete=models.CASCADE, related_name='vaccines'
    )
    board = models.ForeignKey(
        'Board', on_delete=models.CASCADE, related_name='vaccines'
    )
    vaccine_number = models.IntegerField()
    targets_scenario_number = models.IntegerField()
    name = models.CharField(max_length=100)
    description = models.TextField()
    effort_level = models.CharField(max_length=10, choices=EFFORT_CHOICES)
    effort_rationale = models.TextField(blank=True)
    projected_score_improvement = models.IntegerField(default=0)
    implementation_hint = models.TextField(blank=True)
    is_applied = models.BooleanField(default=False)
    applied_at = models.DateTimeField(null=True, blank=True)
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='applied_vaccines'
    )

    class Meta:
        ordering = ['-projected_score_improvement']
        verbose_name = 'Vaccine'

    def get_effort_css_class(self):
        classes = {
            'LOW': 'success',
            'MEDIUM': 'warning',
            'HIGH': 'danger',
        }
        return classes.get(self.effort_level, 'secondary')

    def __str__(self):
        return f"Vaccine: {self.name} (Session #{self.session_id})"
