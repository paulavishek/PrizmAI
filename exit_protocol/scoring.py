"""
Single source of truth for the Hospice risk-score math.

The dashboard gauge, the per-dimension breakdown bars, and the stored
``ProjectHealthSignal.hospice_risk_score`` must always agree. Historically they
were computed in three different places (the view recomputed a breakdown, the
Celery task summed the live factors, and seed data hard-coded a score), which
let them drift — a seeded signal could store 30% while its own component fields
only added up to 17%. Everything now routes through the helpers below.
"""

# Dimension weights. Re-normalised over whichever dimensions have data so the
# score is always on a 0..1 scale regardless of how many signals are available.
WEIGHTS = {
    'velocity': 0.30,
    'budget': 0.25,
    'deadlines': 0.25,
    'activity': 0.20,
}

# Human-facing labels for each dimension (keeps the view dumb).
# "Velocity Trend" (not just "Velocity") is deliberate: this dimension measures
# whether throughput is *declining* (recent sprints vs the board's own baseline),
# NOT whether the team is hitting a fixed tasks/week target. Commitment Protocol /
# Organizational Memory track target attainment separately, so a board can be
# steady-but-below-target (low Velocity-Trend risk here, flagged there) without
# the two systems contradicting each other.
DIM_LABELS = {
    'velocity': 'Velocity Trend',
    'budget': 'Budget',
    'deadlines': 'Deadlines',
    'activity': 'Activity',
}


def _clamp(value):
    """Clamp a raw factor into the 0.0–1.0 range."""
    return min(max(value, 0.0), 1.0)


def _status_for(factor):
    """Map a 0..1 factor to a bootstrap colour band."""
    if factor >= 0.75:
        return 'danger'
    if factor >= 0.40:
        return 'warning'
    return 'success'


def weighted_score(available_factors):
    """Combine per-dimension factors into an overall 0..1 risk score.

    ``available_factors`` is a dict of ``{dimension: factor}`` containing only
    the dimensions that actually had data. Weights are re-normalised across the
    dimensions present so a board missing (say) budget data is not unfairly
    penalised or rewarded.
    """
    if not available_factors:
        return 0.0
    total_weight = sum(WEIGHTS[k] for k in available_factors) or 1.0
    score = sum(
        (WEIGHTS[dim] / total_weight) * factor
        for dim, factor in available_factors.items()
    )
    return _clamp(score)


def factors_from_signal(signal):
    """Rebuild the ``{dimension: factor}`` dict from a stored signal.

    Mirrors exactly how ``compute_board_health_score`` derives each factor from
    live data, so a breakdown rendered from a stored signal matches the score
    that was computed when the signal was created.
    """
    factors = {}

    if signal.velocity_decline_pct is not None:
        factors['velocity'] = _clamp(signal.velocity_decline_pct / 100)

    if signal.budget_spent_pct is not None and signal.tasks_complete_pct is not None:
        factors['budget'] = _clamp(
            (signal.budget_spent_pct / 100) * (1 - signal.tasks_complete_pct / 100)
        )

    if signal.deadlines_missed_30d is not None:
        factors['deadlines'] = _clamp(signal.deadlines_missed_30d / 10)

    # Activity is always available — every board has a created_at/updated_at.
    factors['activity'] = _clamp(signal.days_since_last_activity / 30)

    return factors


def score_and_breakdown(signal):
    """Return ``(overall_score, breakdown_rows)`` for a stored signal.

    ``overall_score`` is a 0..1 float; ``breakdown_rows`` is the list the
    dashboard template iterates over. Both come from the same factor set, so the
    gauge can never contradict the bars.
    """
    factors = factors_from_signal(signal)
    overall = weighted_score(factors)

    total_weight = sum(WEIGHTS[k] for k in factors) or 1.0
    breakdown = []
    for dim, factor in factors.items():
        adjusted_weight = WEIGHTS[dim] / total_weight
        breakdown.append({
            'label': DIM_LABELS.get(dim, dim.title()),
            # This dimension's own risk level (0–100%).
            'factor_pct': round(factor * 100),
            # The share of the overall score this dimension contributes, after
            # re-normalising weights across the dimensions that had data. Summed
            # across rows this equals the overall score — it is NOT a delta vs a
            # baseline.
            'contribution_pct': round(factor * adjusted_weight * 100),
            # The (re-normalised) weight this dimension carries, so the panel can
            # show its work: base weight × (1 / total available weight).
            'weight_pct': round(adjusted_weight * 100),
            'status': _status_for(factor),
        })
    return overall, breakdown
