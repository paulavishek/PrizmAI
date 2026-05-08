"""
PrizmDiscovery Models — ideas inbox with AI-powered scoring.

Answers "what should we build next?" before work hits a Kanban board.
Org-scoped: ideas live at the organization level; they are optionally linked
to a board only when promoted to a delivery task.

Three models:
  - DiscoveryIdea   — the idea itself with AI scores and lifecycle stage
  - IdeaComment     — discussion thread on an idea
  - IdeaPromotion   — records when an approved idea is promoted to tasks
"""
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from accounts.models import Organization


# ── Stage & source choices ────────────────────────────────────────────────────

IDEA_STAGE_CHOICES = [
    ('new', 'New'),
    ('under_review', 'Under Review'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]

IDEA_SOURCE_CHOICES = [
    ('customer_feedback', 'Customer Feedback'),
    ('internal_brainstorm', 'Internal Brainstorm'),
    ('market_research', 'Market Research'),
    ('user_feedback', 'User Feedback'),
    ('sales_team', 'Sales Team'),
    ('finance_team', 'Finance Team'),
    ('other', 'Other'),
]


# ── Models ────────────────────────────────────────────────────────────────────

class DiscoveryIdea(models.Model):
    """
    A product idea or opportunity awaiting evaluation before becoming a task.

    Lifecycle:  new → under_review → approved (→ promoted) or rejected
    AI scoring: impact, effort, confidence (0–100 each) + free-text reasoning
    """
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='discovery_ideas',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    source = models.CharField(
        max_length=30,
        choices=IDEA_SOURCE_CHOICES,
        default='other',
    )
    stage = models.CharField(
        max_length=20,
        choices=IDEA_STAGE_CHOICES,
        default='new',
        db_index=True,
    )
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='submitted_ideas',
    )

    # AI scoring fields — all nullable until Spectra scores the idea
    ai_score_impact = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Impact score 0–100 (higher = more valuable).",
    )
    ai_score_effort = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Effort score 0–100 (higher = more effort required).",
    )
    ai_score_confidence = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Confidence in the above scores, 0–100.",
    )
    ai_score_recommendation = models.CharField(
        max_length=500, blank=True, default='',
        help_text="Short one-line recommendation from Spectra.",
    )
    ai_score_reasoning = models.TextField(
        blank=True, default='',
        help_text="Full Spectra reasoning shown to the user (Explainable AI).",
    )
    ai_scored_at = models.DateTimeField(null=True, blank=True)

    # Promotion tracking
    promoted_at = models.DateTimeField(null=True, blank=True)
    promoted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='promoted_ideas',
    )

    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Demo flag — set by the demo population command so ideas are not
    # accidentally wiped by user actions during a demo session.
    is_demo = models.BooleanField(default=False)

    class Meta:
        app_label = 'kanban'
        ordering = ['-created_at']
        verbose_name = 'Discovery Idea'
        verbose_name_plural = 'Discovery Ideas'

    def __str__(self):
        return f"[{self.get_stage_display()}] {self.title}"

    @property
    def is_scored(self):
        return self.ai_score_impact is not None

    @property
    def quadrant(self):
        """
        Return the matrix quadrant label based on impact and effort scores.
        Returns None if the idea has not yet been scored.
        """
        if not self.is_scored:
            return None
        high_impact = self.ai_score_impact >= 50
        high_effort = self.ai_score_effort >= 50
        if high_impact and not high_effort:
            return 'quick_win'
        elif high_impact and high_effort:
            return 'strategic_bet'
        elif not high_impact and not high_effort:
            return 'fill_in'
        else:
            return 'deprioritize'

    QUADRANT_LABELS = {
        'quick_win': 'Quick Win',
        'strategic_bet': 'Strategic Bet',
        'fill_in': 'Fill-in',
        'deprioritize': 'Deprioritize',
    }

    @property
    def quadrant_label(self):
        q = self.quadrant
        return self.QUADRANT_LABELS.get(q, '') if q else ''


class IdeaComment(models.Model):
    """A comment or discussion entry on a DiscoveryIdea."""
    idea = models.ForeignKey(
        DiscoveryIdea,
        on_delete=models.CASCADE,
        related_name='comments',
    )
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='idea_comments',
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'kanban'
        ordering = ['created_at']
        verbose_name = 'Idea Comment'
        verbose_name_plural = 'Idea Comments'

    def __str__(self):
        return f"Comment on '{self.idea.title}' by {self.author}"


class IdeaPromotion(models.Model):
    """
    Records when a DiscoveryIdea is approved and promoted to delivery.

    The idea can be linked to an existing Board and to specific Tasks that
    were created as a direct result of the idea being approved.
    """
    idea = models.OneToOneField(
        DiscoveryIdea,
        on_delete=models.CASCADE,
        related_name='promotion',
    )
    # The board the idea was promoted into (optional — user may not know yet)
    board = models.ForeignKey(
        'kanban.Board',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='promoted_ideas',
    )
    # Tasks that were created directly as a result of this idea
    tasks = models.ManyToManyField(
        'kanban.Task',
        blank=True,
        related_name='originated_from_ideas',
    )
    promoted_at = models.DateTimeField(default=timezone.now)
    promoted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='idea_promotions',
    )

    class Meta:
        app_label = 'kanban'
        verbose_name = 'Idea Promotion'
        verbose_name_plural = 'Idea Promotions'

    def __str__(self):
        return f"Promotion of '{self.idea.title}'"
