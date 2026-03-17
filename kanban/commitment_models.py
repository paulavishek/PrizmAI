"""
Living Commitment Protocol Models

Stores probabilistic, continuously-updating project commitments.
Three sub-features:
  1. Confidence Decay Curves — commitments auto-decay without progress signals
  2. Commitment Markets — team prediction market with credibility tokens
  3. Scope Negotiation Bot — AI-initiated renegotiation when confidence drops
"""
import math
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class CommitmentProtocol(models.Model):
    """
    An official project commitment — a publicly declared deadline with a
    probabilistic confidence level that decays over time without fresh signals.
    """

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('at_risk', 'At Risk'),
        ('critical', 'Critical'),
        ('met', 'Met'),
        ('missed', 'Missed'),
        ('renegotiated', 'Renegotiated'),
    ]

    DECAY_MODEL_CHOICES = [
        ('exponential', 'Exponential'),
        ('linear', 'Linear'),
        ('stepped', 'Stepped'),
    ]

    board = models.ForeignKey(
        'kanban.Board',
        on_delete=models.CASCADE,
        related_name='commitments',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    target_date = models.DateField()
    initial_confidence = models.FloatField(
        default=0.85,
        validators=[MinValueValidator(0.1), MaxValueValidator(1.0)],
    )
    current_confidence = models.FloatField(default=0.85)
    confidence_halflife_days = models.IntegerField(
        default=14,
        help_text='Days for confidence to halve without positive signals',
    )
    decay_model = models.CharField(
        max_length=20,
        choices=DECAY_MODEL_CHOICES,
        default='exponential',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_commitments',
    )
    baseline_snapshot = models.JSONField(
        default=dict,
        help_text='Board state when commitment was created',
    )
    last_signal_date = models.DateTimeField(null=True, blank=True)
    last_decay_calculation = models.DateTimeField(auto_now_add=True)
    ai_reasoning = models.TextField(blank=True)
    negotiation_threshold = models.FloatField(
        default=0.40,
        help_text='Confidence % that triggers Negotiation Bot',
    )
    token_pool_per_member = models.IntegerField(
        default=100,
        help_text='Betting tokens per member per week',
    )
    linked_tasks = models.ManyToManyField(
        'kanban.Task',
        blank=True,
        related_name='commitments',
    )
    stakeholders = models.ManyToManyField(
        User,
        blank=True,
        related_name='watched_commitments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Commitment Protocol'
        verbose_name_plural = 'Commitment Protocols'

    def __str__(self):
        return f'{self.title} – {self.board.name} ({self.target_date})'

    def get_confidence_history(self):
        """Return list of {date, confidence, signal_type, description} dicts from signals."""
        history = []
        signals = self.signals.order_by('timestamp')
        for sig in signals:
            history.append({
                'date': sig.timestamp.isoformat(),
                'confidence': sig.confidence_after,
                'signal_type': sig.signal_type,
                'description': sig.description,
            })
        return history

    def calculate_market_consensus(self):
        """Return credibility-weighted average of active bets."""
        from django.core.cache import cache
        cache_key = f'commitment_market_{self.pk}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        bets = self.bets.filter(resolved=False).select_related('bettor')
        if not bets.exists():
            return None

        weighted_sum = 0.0
        total_weight = 0.0
        for bet in bets:
            try:
                credibility = bet.bettor.betting_credibility.score
            except UserCredibilityScore.DoesNotExist:
                credibility = 50.0
            weight = credibility / 100.0
            weighted_sum += bet.confidence_estimate * weight
            total_weight += weight

        consensus = weighted_sum / total_weight if total_weight > 0 else None
        result = {
            'consensus': consensus,
            'bet_count': bets.count(),
            'divergence': abs(self.current_confidence - consensus) if consensus else 0,
        }
        cache.set(cache_key, result, 300)  # 5-minute cache
        return result

    def days_until_deadline(self):
        """Return integer number of days until target_date (negative if past)."""
        from datetime import date
        return (self.target_date - date.today()).days

    @property
    def confidence_color(self):
        """Return Bootstrap color class based on current_confidence."""
        if self.current_confidence >= 0.70:
            return 'success'
        elif self.current_confidence >= 0.40:
            return 'warning'
        return 'danger'


class ConfidenceSignal(models.Model):
    """
    Records every piece of evidence (positive or negative) that affects
    the confidence level of a CommitmentProtocol.
    """

    SIGNAL_TYPE_CHOICES = [
        ('task_completed', 'Task Completed'),
        ('task_added', 'Task Added (Scope)'),
        ('milestone_hit', 'Milestone Hit'),
        ('milestone_missed', 'Milestone Missed'),
        ('team_member_left', 'Team Member Left'),
        ('team_member_joined', 'Team Member Joined'),
        ('dependency_blocked', 'Dependency Blocked'),
        ('dependency_resolved', 'Dependency Resolved'),
        ('manual_positive', 'Manual Positive Update'),
        ('manual_negative', 'Manual Negative Update'),
        ('external_risk', 'External Risk Detected'),
        ('decay', 'Time Decay'),
    ]

    protocol = models.ForeignKey(
        CommitmentProtocol,
        on_delete=models.CASCADE,
        related_name='signals',
    )
    signal_type = models.CharField(max_length=30, choices=SIGNAL_TYPE_CHOICES)
    signal_value = models.FloatField(
        help_text='Strength from -1.0 (very negative) to +1.0 (very positive)',
    )
    description = models.TextField()
    confidence_before = models.FloatField()
    confidence_after = models.FloatField()
    ai_generated = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_signals',
    )
    related_task = models.ForeignKey(
        'kanban.Task',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='commitment_signals',
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
        verbose_name = 'Confidence Signal'
        verbose_name_plural = 'Confidence Signals'

    def __str__(self):
        direction = '+' if self.signal_value >= 0 else ''
        return (
            f'[{self.get_signal_type_display()}] {direction}{self.signal_value:.2f} '
            f'→ {self.confidence_after:.0%} ({self.protocol.title})'
        )


class CommitmentBet(models.Model):
    """
    A single team member's bet on whether a commitment will be met.
    Anonymous by default; uses credibility tokens.
    """

    protocol = models.ForeignKey(
        CommitmentProtocol,
        on_delete=models.CASCADE,
        related_name='bets',
    )
    bettor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='commitment_bets',
    )
    tokens_wagered = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
    )
    confidence_estimate = models.FloatField(
        validators=[MinValueValidator(0.01), MaxValueValidator(0.99)],
        help_text='Bettor\'s personal confidence estimate 0-1',
    )
    reasoning = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=True)
    placed_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved = models.BooleanField(default=False)
    resolution_correct = models.BooleanField(null=True, blank=True)
    credibility_delta = models.FloatField(
        null=True,
        blank=True,
        help_text='Credibility score change on resolution',
    )

    class Meta:
        unique_together = [('protocol', 'bettor')]
        ordering = ['-placed_at']
        verbose_name = 'Commitment Bet'
        verbose_name_plural = 'Commitment Bets'

    def __str__(self):
        name = 'anonymous' if self.is_anonymous else self.bettor.username
        return f'{name} → {self.confidence_estimate:.0%} ({self.protocol.title})'

    def resolve(self, outcome_met: bool):
        """
        Resolve this bet after the commitment deadline passes.
        A bet is 'correct' if the bettor's confidence direction matched the outcome.
        Bettors who estimated >50% for a met commitment win credibility.
        """
        self.resolved = True
        bettor_predicted_met = self.confidence_estimate >= 0.5
        self.resolution_correct = (bettor_predicted_met == outcome_met)

        # Credibility delta: +5 for correct, -3 for incorrect (weighted by tokens)
        weight = self.tokens_wagered / 100.0
        if self.resolution_correct:
            self.credibility_delta = 5.0 * weight
        else:
            self.credibility_delta = -3.0 * weight

        self.save(update_fields=['resolved', 'resolution_correct', 'credibility_delta'])

        # Update UserCredibilityScore
        try:
            cred, _ = UserCredibilityScore.objects.get_or_create(user=self.bettor)
            cred.score = max(0.0, min(100.0, cred.score + self.credibility_delta))
            cred.total_bets += 1
            if self.resolution_correct:
                cred.correct_bets += 1
            cred.save(update_fields=['score', 'total_bets', 'correct_bets'])
        except Exception:
            pass


class NegotiationSession(models.Model):
    """
    Tracks each AI-initiated renegotiation conversation triggered when
    commitment confidence falls below the negotiation threshold.
    """

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent to Stakeholders'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]

    OPTION_CHOICES = [
        ('a', 'Option A: Reduce Scope'),
        ('b', 'Option B: Extend Deadline'),
        ('c', 'Option C: Add Resources'),
        ('custom', 'Custom Agreement'),
    ]

    protocol = models.ForeignKey(
        CommitmentProtocol,
        on_delete=models.CASCADE,
        related_name='negotiations',
    )
    trigger_confidence = models.FloatField()
    trigger_reason = models.TextField()
    ai_drafted_message = models.TextField()
    # Option A — Reduce Scope
    option_a_description = models.TextField(
        help_text='Reduce scope option',
        blank=True,
    )
    option_a_impact = models.JSONField(default=dict)
    # Option B — Extend Deadline
    option_b_description = models.TextField(
        help_text='Extend deadline option',
        blank=True,
    )
    option_b_impact = models.JSONField(default=dict)
    # Option C — Add Resources
    option_c_description = models.TextField(
        help_text='Add resources option',
        blank=True,
    )
    option_c_impact = models.JSONField(default=dict)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
    )
    chosen_option = models.CharField(
        max_length=10,
        choices=OPTION_CHOICES,
        null=True,
        blank=True,
    )
    new_target_date = models.DateField(null=True, blank=True)
    new_scope_tasks = models.IntegerField(null=True, blank=True)
    stakeholder_notes = models.TextField(blank=True)
    initiated_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    initiated_by_ai = models.BooleanField(default=True)

    class Meta:
        ordering = ['-initiated_at']
        verbose_name = 'Negotiation Session'
        verbose_name_plural = 'Negotiation Sessions'

    def __str__(self):
        return f'Negotiation for "{self.protocol.title}" at {self.trigger_confidence:.0%}'


class UserCredibilityScore(models.Model):
    """
    Tracks a user's prediction market credibility score and weekly token balance.
    Score ranges 0–100, starts at 50. Tokens reset weekly.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='betting_credibility',
    )
    score = models.FloatField(
        default=50.0,
        help_text='0-100, starts at 50',
    )
    total_bets = models.IntegerField(default=0)
    correct_bets = models.IntegerField(default=0)
    tokens_remaining = models.IntegerField(default=100)
    tokens_reset_date = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = 'User Credibility Score'
        verbose_name_plural = 'User Credibility Scores'

    def __str__(self):
        return f'{self.user.username} — credibility {self.score:.1f}/100'

    @property
    def accuracy_pct(self):
        if self.total_bets == 0:
            return None
        return round((self.correct_bets / self.total_bets) * 100, 1)
