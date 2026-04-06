"""
Workspace Preset models for the progressive feature disclosure system.

Three preset tiers:
  - lean:         Solo / small teams (< 10) — clean, minimal interface
  - professional: Growing teams (10–50) — advanced PM features unlocked
  - enterprise:   Large organisations (50+) — full PrizmAI experience

WorkspacePreset lives on the Organization (global ceiling).
BoardPreset lives on each Board (local override, can only restrict further).
"""
from django.db import models


PRESET_ORDER = ['lean', 'professional', 'enterprise']

PRESET_CHOICES = [
    ('lean', 'Lean / Startup'),
    ('professional', 'Professional / Growth'),
    ('enterprise', 'Enterprise / Heavyweight'),
]


class WorkspacePreset(models.Model):
    """
    Organisation-wide default preset.  All new boards inherit this setting.
    Only Org Admins may change it.
    """
    organization = models.OneToOneField(
        'accounts.Organization',
        on_delete=models.CASCADE,
        related_name='workspace_preset',
    )
    global_preset = models.CharField(
        max_length=20,
        choices=PRESET_CHOICES,
        default='professional',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'kanban'

    def __str__(self):
        return f"{self.organization} — {self.get_global_preset_display()}"


class BoardPreset(models.Model):
    """
    Per-board preset override.  Board Owners can restrict their board to a
    *lower* tier than the global preset, but never exceed it.
    """
    board = models.OneToOneField(
        'kanban.Board',
        on_delete=models.CASCADE,
        related_name='board_preset',
    )
    local_preset = models.CharField(
        max_length=20,
        choices=PRESET_CHOICES,
        null=True,
        blank=True,
        help_text=(
            "If set, overrides the global preset for this board only. "
            "Cannot exceed the global preset tier."
        ),
    )

    class Meta:
        app_label = 'kanban'

    def effective_preset(self):
        """
        Return the effective preset for this board, respecting the rule
        that the local override can never exceed the global ceiling.

        Falls back to 'lean' when:
          - The board has no organization
          - The organization has no WorkspacePreset record
        """
        # Resolve the global ceiling
        global_preset = 'lean'  # safe default
        try:
            org = self.board.organization
            if org is not None:
                global_preset = org.workspace_preset.global_preset
        except (AttributeError, WorkspacePreset.DoesNotExist):
            pass

        if not self.local_preset:
            return global_preset

        global_index = PRESET_ORDER.index(global_preset)
        local_index = PRESET_ORDER.index(self.local_preset)
        # Local can only be equal to or lower than global
        return PRESET_ORDER[min(global_index, local_index)]

    def __str__(self):
        return f"{self.board} — {self.local_preset or 'inherits global'}"


# ── Feature-flag builder ────────────────────────────────────────────

def build_feature_flags(preset):
    """
    Return a dict of boolean feature flags for the given preset string.
    Templates use these via  {% if features.show_gantt %} etc.
    """
    lean = {
        'show_hierarchy': False,
        'show_gantt': False,
        'show_burndown': False,
        'show_advanced_task_form': False,
        'show_ai_coach': False,
        'show_ai_retrospectives': False,
        'show_shadow_board': False,
        'show_premortem': False,
        'show_stress_test': False,
        'show_scope_autopsy': False,
        'show_scope_tracking': False,
        'show_exit_protocol': False,
        'show_commitments': False,
        'show_whatif': False,
        'show_prizm_brief': False,
        'show_budget_roi': False,
        'show_triple_constraint': False,
        'show_automations': False,
        'show_scheduled_automations': False,
        'show_skill_gaps': False,
        'show_resource_optimization': False,
        'show_decision_center': False,
        'show_goals_nav': False,
        'show_missions_nav': False,
        'show_full_analytics': False,
        'spectra_agentic': False,
        # Meta — useful for template logic
        'preset_name': 'lean',
    }

    professional_additions = {
        'show_hierarchy': True,
        'show_gantt': True,
        'show_burndown': True,
        'show_advanced_task_form': True,
        'show_ai_coach': True,
        'show_ai_retrospectives': True,
        'show_automations': True,
        'show_scope_tracking': True,
        'show_skill_gaps': True,
        'show_decision_center': True,
        'show_goals_nav': True,
        'show_missions_nav': True,
        'show_full_analytics': True,
        'spectra_agentic': True,
        'preset_name': 'professional',
    }

    enterprise_additions = {
        'show_shadow_board': True,
        'show_premortem': True,
        'show_stress_test': True,
        'show_scope_autopsy': True,
        'show_exit_protocol': True,
        'show_commitments': True,
        'show_whatif': True,
        'show_prizm_brief': True,
        'show_budget_roi': True,
        'show_triple_constraint': True,
        'show_resource_optimization': True,
        'show_scheduled_automations': True,
        'preset_name': 'enterprise',
    }

    if preset == 'lean':
        return lean
    elif preset == 'professional':
        return {**lean, **professional_additions}
    else:  # enterprise
        return {**lean, **professional_additions, **enterprise_additions}
