"""
Project Confidence Service

Computes the auto Project Confidence Score by synthesising scope stability,
budget health, and schedule adherence — no manual setup required.

Also handles applying ProjectSignals to update confidence and triggering
AI Coach renegotiation suggestions when confidence drops below threshold.
"""

import logging
from datetime import timedelta

from django.utils import timezone
from django.db.models import Avg

logger = logging.getLogger(__name__)

# Weights for composite score (must sum to 1.0)
SCOPE_WEIGHT = 0.30
BUDGET_WEIGHT = 0.30
SCHEDULE_WEIGHT = 0.40

# Threshold below which AI Coach fires a renegotiation suggestion
RENEGOTIATION_THRESHOLD = 40.0

# Max adjustment from signals per computation cycle
MAX_SIGNAL_ADJUSTMENT = 30.0


class ProjectConfidenceService:
    """
    Stateless service for computing and updating project confidence scores.
    """

    @staticmethod
    def compute_score(board):
        """
        Compute a fresh ProjectConfidenceScore for the given board.

        Reads current scope, budget, and schedule data to produce a composite
        score (0-100). Saves a new ProjectConfidenceScore record.

        Returns the created ProjectConfidenceScore instance.
        """
        from kanban.project_signals_models import ProjectConfidenceScore, ProjectSignal
        from kanban.models import Task

        scope_score = ProjectConfidenceService._compute_scope_score(board)
        budget_score = ProjectConfidenceService._compute_budget_score(board)
        schedule_score = ProjectConfidenceService._compute_schedule_score(board)

        # Signal adjustment: sum recent signal strengths (last 24 hours)
        since = timezone.now() - timedelta(hours=24)
        recent_signals = ProjectSignal.objects.filter(
            board=board,
            timestamp__gte=since,
        )
        raw_adjustment = sum(s.strength * 10 for s in recent_signals)  # scale to -10..+10 per signal
        signal_adjustment = max(-MAX_SIGNAL_ADJUSTMENT, min(MAX_SIGNAL_ADJUSTMENT, raw_adjustment))

        # Weighted composite
        raw_composite = (
            scope_score * SCOPE_WEIGHT
            + budget_score * BUDGET_WEIGHT
            + schedule_score * SCHEDULE_WEIGHT
            + signal_adjustment
        )
        composite_score = max(0.0, min(100.0, raw_composite))

        # Determine trend from previous score
        previous = ProjectConfidenceScore.objects.filter(
            board=board,
        ).order_by('-computed_at').first()

        previous_score_val = previous.composite_score if previous else None
        if previous_score_val is not None:
            delta = composite_score - previous_score_val
            if delta > 3:
                trend = 'improving'
            elif delta < -3:
                trend = 'declining'
            else:
                trend = 'stable'
        else:
            trend = 'stable'

        computation_data = {
            'scope_score': round(scope_score, 1),
            'budget_score': round(budget_score, 1),
            'schedule_score': round(schedule_score, 1),
            'signal_adjustment': round(signal_adjustment, 1),
            'weights': {
                'scope': SCOPE_WEIGHT,
                'budget': BUDGET_WEIGHT,
                'schedule': SCHEDULE_WEIGHT,
            },
            'recent_signal_count': recent_signals.count(),
        }

        score = ProjectConfidenceScore.objects.create(
            board=board,
            scope_score=round(scope_score, 1),
            budget_score=round(budget_score, 1),
            schedule_score=round(schedule_score, 1),
            signal_adjustment=round(signal_adjustment, 1),
            composite_score=round(composite_score, 1),
            trend=trend,
            previous_score=previous_score_val,
            computation_data=computation_data,
        )

        logger.info(
            'ProjectConfidenceScore computed for board %s: %.0f%% (scope=%.0f, budget=%.0f, schedule=%.0f, signals=%.1f)',
            board.name, composite_score, scope_score, budget_score, schedule_score, signal_adjustment,
        )

        # Check if renegotiation coaching suggestion should fire
        if composite_score < RENEGOTIATION_THRESHOLD:
            ProjectConfidenceService._trigger_renegotiation_coaching(board, score)

        return score

    @staticmethod
    def get_latest_score(board):
        """Return the most recent ProjectConfidenceScore for a board, or None."""
        from kanban.project_signals_models import ProjectConfidenceScore
        return ProjectConfidenceScore.objects.filter(board=board).order_by('-computed_at').first()

    @staticmethod
    def get_confidence_history(board, days=30):
        """Return confidence score history for charting."""
        from kanban.project_signals_models import ProjectConfidenceScore
        since = timezone.now() - timedelta(days=days)
        scores = ProjectConfidenceScore.objects.filter(
            board=board,
            computed_at__gte=since,
        ).order_by('computed_at')
        return [
            {
                'date': s.computed_at.date().isoformat(),
                'score': s.composite_score,
                'scope': s.scope_score,
                'budget': s.budget_score,
                'schedule': s.schedule_score,
                'trend': s.trend,
            }
            for s in scores
        ]

    @staticmethod
    def get_recent_signals(board, limit=20):
        """Return the most recent project signals for display."""
        from kanban.project_signals_models import ProjectSignal
        return ProjectSignal.objects.filter(
            board=board,
        ).select_related('recorded_by', 'related_task').order_by('-timestamp')[:limit]

    @staticmethod
    def record_signal(board, signal_type, strength, description, user=None, task=None, ai_generated=False):
        """
        Create a ProjectSignal and update confidence_before/after from the
        latest score.
        """
        from kanban.project_signals_models import ProjectSignal

        latest = ProjectConfidenceService.get_latest_score(board)
        confidence_before = latest.composite_score if latest else None

        impact = 'positive' if strength > 0 else ('negative' if strength < 0 else 'neutral')

        signal = ProjectSignal.objects.create(
            board=board,
            signal_type=signal_type,
            impact=impact,
            strength=strength,
            description=description,
            related_task=task,
            ai_generated=ai_generated,
            recorded_by=user,
            confidence_before=confidence_before,
            confidence_after=None,  # Will be set on next score computation
        )

        return signal

    # ── Private dimension computations ─────────────────────────────────────

    @staticmethod
    def _compute_scope_score(board):
        """
        Score 0-100 based on scope change from baseline.
        0% change = 100, >40% change = 0.
        """
        scope_status = board.get_current_scope_status()
        if scope_status is None:
            return 85.0  # No baseline — assume slightly below perfect

        change_pct = abs(scope_status.get('scope_change_percentage', 0))
        # Linear scale: 0% change = 100, 40% change = 0
        score = max(0.0, 100.0 - (change_pct * 2.5))
        return score

    @staticmethod
    def _compute_budget_score(board):
        """
        Score 0-100 based on budget utilisation.
        <=70% used = 100, 100% = 30, >120% = 0.
        """
        try:
            from kanban.budget_models import ProjectBudget
            budget = ProjectBudget.objects.get(board=board)
            utilization = budget.get_budget_utilization_percent()
        except Exception:
            return 85.0  # No budget — assume slightly below perfect

        if utilization <= 70:
            return 100.0
        elif utilization <= 100:
            # Linear from 100 to 30 as utilization goes from 70 to 100
            return 100.0 - ((utilization - 70) / 30) * 70
        else:
            # Over budget: linear from 30 to 0 as utilization goes from 100 to 120
            return max(0.0, 30.0 - ((utilization - 100) / 20) * 30)

    @staticmethod
    def _compute_schedule_score(board):
        """
        Score 0-100 based on burndown prediction delay probability.
        0% delay prob = 100, 100% delay prob = 0.
        """
        from kanban.burndown_models import BurndownPrediction

        prediction = BurndownPrediction.objects.filter(
            board=board,
        ).order_by('-prediction_date').first()

        if not prediction:
            return 75.0  # No prediction — moderate assumption

        delay_prob = float(prediction.delay_probability or 0)
        # Direct inversion: 0% delay = 100 score, 100% delay = 0 score
        score = max(0.0, 100.0 - delay_prob)

        # Also factor in risk level
        risk_penalty = {
            'low': 0,
            'medium': -5,
            'high': -15,
            'critical': -25,
        }
        score = max(0.0, score + risk_penalty.get(prediction.risk_level, 0))

        return score

    # ── AI Coach renegotiation ──────────────────────────────────────────────

    @staticmethod
    def _trigger_renegotiation_coaching(board, confidence_score):
        """
        When confidence drops below threshold, create a special AI Coach
        suggestion of type 'confidence_drop' with 3 recovery options.
        Idempotent — won't create duplicates.
        """
        from kanban.coach_models import CoachingSuggestion

        # Check for existing active renegotiation suggestion
        existing = CoachingSuggestion.objects.filter(
            board=board,
            suggestion_type='confidence_drop',
            status__in=['active', 'acknowledged', 'in_progress'],
        ).exists()

        if existing:
            return

        score_val = confidence_score.composite_score
        recovery_options = [
            {
                'title': 'Reduce Scope',
                'description': (
                    f'Consider removing or deferring lower-priority tasks. '
                    f'Scope score is {confidence_score.scope_score:.0f}/100 — '
                    f'reducing scope could improve overall confidence by ~15-20 points.'
                ),
                'impact': 'Fewer deliverables, but hit the deadline reliably.',
            },
            {
                'title': 'Extend Timeline',
                'description': (
                    f'Schedule score is {confidence_score.schedule_score:.0f}/100. '
                    f'Extending the deadline by 1-2 weeks would relieve pressure '
                    f'and improve confidence significantly.'
                ),
                'impact': 'Full scope delivered, later than originally planned.',
            },
            {
                'title': 'Add Resources',
                'description': (
                    f'If budget allows (score: {confidence_score.budget_score:.0f}/100), '
                    f'adding team members could increase velocity. '
                    f'Be cautious of onboarding overhead.'
                ),
                'impact': 'Original scope and timeline, higher cost.',
            },
        ]

        CoachingSuggestion.objects.create(
            board=board,
            suggestion_type='confidence_drop',
            severity='high',
            status='active',
            title=f'Project confidence dropped to {score_val:.0f}% — recovery options available',
            message=(
                f'Project confidence for "{board.name}" has fallen to {score_val:.0f}%, '
                f'which is below the healthy threshold of {RENEGOTIATION_THRESHOLD}%. '
                f'This is based on scope stability ({confidence_score.scope_score:.0f}%), '
                f'budget health ({confidence_score.budget_score:.0f}%), and schedule adherence '
                f'({confidence_score.schedule_score:.0f}%). '
                f'Review the three recovery options below and choose the best path forward.'
            ),
            reasoning=(
                f'Auto-generated by the Project Confidence system. '
                f'Composite score {score_val:.0f}% dropped below '
                f'threshold {RENEGOTIATION_THRESHOLD}%.'
            ),
            recommended_actions=recovery_options,
            expected_impact='Choosing a recovery option can restore confidence to 60-80%.',
            metrics_snapshot=confidence_score.computation_data,
            confidence_score=round(max(0, min(1, score_val / 100)), 2),
            ai_model_used='project-confidence-system',
            generation_method='hybrid',
        )

        logger.info(
            'Renegotiation coaching suggestion created for board %s (confidence=%.0f%%)',
            board.name, score_val,
        )
