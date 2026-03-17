from django.db import models
from django.conf import settings
from django.utils import timezone


class ProjectHealthSignal(models.Model):
    """Tracks periodic health metrics that feed into Hospice detection."""
    board = models.ForeignKey(
        'kanban.Board', on_delete=models.CASCADE, related_name='health_signals'
    )
    recorded_at = models.DateTimeField(auto_now_add=True)

    # Velocity metrics (null = data not available for this board)
    velocity_last_sprint = models.FloatField(null=True, blank=True)
    velocity_3sprint_avg = models.FloatField(null=True, blank=True)
    velocity_decline_pct = models.FloatField(null=True, blank=True)

    # Budget metrics (null = no budget configured)
    budget_spent_pct = models.FloatField(null=True, blank=True)
    tasks_complete_pct = models.FloatField(null=True, blank=True)

    # Activity metrics
    deadlines_missed_30d = models.IntegerField(default=0)
    days_since_last_activity = models.IntegerField(default=0)

    # Dimensions with actual data (minimum 2 required for valid score)
    dimensions_available = models.IntegerField(default=0)

    # Computed score — only meaningful when dimensions_available >= 2
    hospice_risk_score = models.FloatField(default=0.0)
    score_is_valid = models.BooleanField(default=False)
    triggered_hospice = models.BooleanField(default=False)

    class Meta:
        ordering = ['-recorded_at']
        indexes = [models.Index(fields=['board', 'recorded_at'])]

    def __str__(self):
        return f"HealthSignal({self.board_id}, score={self.hospice_risk_score:.2f}, valid={self.score_is_valid})"


class HospiceSession(models.Model):
    """Created when a wind-down is initiated (by AI trigger or manually)."""
    STATUS_CHOICES = [
        ('assessment', 'Assessment Phase'),
        ('knowledge_extraction', 'Knowledge Extraction'),
        ('organ_scan', 'Organ Scan'),
        ('team_transition', 'Team Transition'),
        ('burial_pending', 'Burial Pending'),
        ('buried', 'Buried'),
    ]

    TRIGGER_CHOICES = [
        ('ai_detected', 'AI Detected'),
        ('manager_initiated', 'Manager Initiated'),
    ]

    board = models.OneToOneField(
        'kanban.Board', on_delete=models.CASCADE, related_name='hospice_session'
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='initiated_hospice_sessions'
    )
    trigger_type = models.CharField(max_length=20, choices=TRIGGER_CHOICES)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='assessment')

    # AI-generated content (populated async by Celery tasks)
    ai_assessment = models.TextField(blank=True)
    knowledge_checklist = models.JSONField(default=dict)
    team_transition_memos = models.JSONField(default=dict)

    # Progress tracking
    checklist_completed_items = models.JSONField(default=list)

    initiated_at = models.DateTimeField(auto_now_add=True)
    buried_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['board', 'status'])]

    def __str__(self):
        return f"HospiceSession({self.board}, status={self.status})"


class ProjectOrgan(models.Model):
    """A single reusable component extracted from a dying project."""
    ORGAN_TYPE_CHOICES = [
        ('task_template', 'Task Template'),
        ('checklist', 'Checklist'),
        ('automation_rule', 'Automation Rule'),
        ('goal_framework', 'Goal Framework'),
        ('knowledge_entry', 'Knowledge Entry'),
        ('role_definition', 'Role Definition'),
    ]

    STATUS_CHOICES = [
        ('available', 'Available for Transplant'),
        ('transplanted', 'Transplanted'),
        ('rejected', 'Rejected / Archived'),
    ]

    source_board = models.ForeignKey(
        'kanban.Board', on_delete=models.CASCADE, related_name='donated_organs'
    )
    hospice_session = models.ForeignKey(
        HospiceSession, on_delete=models.CASCADE, related_name='organs'
    )

    organ_type = models.CharField(max_length=30, choices=ORGAN_TYPE_CHOICES)
    name = models.CharField(max_length=255)
    description = models.TextField()
    # CRITICAL: payload must be fully self-contained JSON.
    # Do NOT store ForeignKey IDs — the source board will be archived.
    payload = models.JSONField()

    # AI scoring
    reusability_score = models.IntegerField(default=0)
    ai_rationale = models.TextField(blank=True)
    best_suited_for = models.TextField(blank=True)
    cautions = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    extracted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['organ_type', 'status'])]

    def __str__(self):
        return f"Organ({self.name}, type={self.organ_type}, score={self.reusability_score})"


class OrganTransplant(models.Model):
    """Records when an organ is transplanted into a target project."""
    organ = models.ForeignKey(
        ProjectOrgan, on_delete=models.CASCADE, related_name='transplants'
    )
    target_board = models.ForeignKey(
        'kanban.Board', on_delete=models.CASCADE, related_name='received_organs'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='approved_transplants'
    )

    compatibility_score = models.IntegerField(default=0)
    ai_match_rationale = models.TextField(blank=True)
    adaptation_needed = models.TextField(blank=True)

    transplanted_at = models.DateTimeField(auto_now_add=True)
    created_object_type = models.CharField(max_length=50, blank=True)
    created_object_id = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"Transplant({self.organ.name} → {self.target_board})"


class CemeteryEntry(models.Model):
    """The permanent gravestone record for every buried project."""
    CAUSE_OF_DEATH_CHOICES = [
        ('natural_completion', '✅ Natural Completion'),
        ('budget_exhaustion', '💸 Budget Exhaustion'),
        ('deadline_collapse', '⏰ Deadline Collapse'),
        ('scope_creep_spiral', '🔄 Scope Creep Spiral'),
        ('team_dissolution', '👥 Team Dissolution'),
        ('strategic_pivot', '🔀 Strategic Pivot'),
        ('zombie_death', '🧟 Zombie Death'),
        ('merger', '🔗 Merger / Absorbed'),
    ]

    board = models.OneToOneField(
        'kanban.Board', on_delete=models.CASCADE, related_name='cemetery_entry'
    )
    hospice_session = models.OneToOneField(
        HospiceSession, on_delete=models.CASCADE, null=True, blank=True,
        related_name='cemetery_entry'
    )

    # Metadata snapshot — captured at burial time
    project_name = models.CharField(max_length=255)
    project_description = models.TextField(blank=True)
    board_id_snapshot = models.IntegerField()
    team_size = models.IntegerField(default=0)
    total_tasks = models.IntegerField(default=0)
    completed_tasks = models.IntegerField(default=0)
    budget_allocated = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    budget_spent = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # Cause of death
    cause_of_death = models.CharField(max_length=30, choices=CAUSE_OF_DEATH_CHOICES)
    ai_cause_rationale = models.TextField(blank=True)
    contributing_factors = models.JSONField(default=list)

    # Full autopsy report
    autopsy_report = models.JSONField(default=dict)
    autopsy_summary = models.TextField(blank=True)

    # Lessons learned
    lessons_to_repeat = models.JSONField(default=list)
    lessons_to_avoid = models.JSONField(default=list)
    open_questions = models.JSONField(default=list)

    # Timeline of decline (for Chart.js rendering)
    decline_timeline = models.JSONField(default=list)

    # Search tags
    tags = models.JSONField(default=list)

    buried_at = models.DateTimeField(auto_now_add=True)

    # Resurrection tracking
    is_resurrected = models.BooleanField(default=False)
    resurrected_as = models.ForeignKey(
        'kanban.Board', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resurrected_from'
    )

    class Meta:
        ordering = ['-buried_at']
        indexes = [
            models.Index(fields=['cause_of_death']),
            models.Index(fields=['buried_at']),
        ]
        verbose_name_plural = 'Cemetery Entries'

    def __str__(self):
        return f"Cemetery({self.project_name}, {self.get_cause_of_death_display()})"

    def completion_pct_display(self):
        if self.total_tasks == 0:
            return '0%'
        return f'{round(self.completed_tasks / self.total_tasks * 100)}%'


class HospiceDismissal(models.Model):
    """Persists 7-day banner dismissals. Do not use Django sessions for this."""
    board = models.ForeignKey(
        'kanban.Board', on_delete=models.CASCADE, related_name='hospice_dismissals'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hospice_dismissals'
    )
    dismissed_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        unique_together = [('board', 'user')]
        indexes = [models.Index(fields=['board', 'user', 'expires_at'])]

    def __str__(self):
        return f"Dismissal({self.board_id}, user={self.user_id}, expires={self.expires_at})"

    def is_active(self):
        return self.expires_at > timezone.now()
