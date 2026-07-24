"""
What-If Scenario Engine

Computes cascading project impacts for hypothetical changes (scope, team, deadline)
without writing anything to the database.  Uses existing board metrics, burndown
predictions, budget data, and resource forecasts as the baseline, then applies
pure-math projections and optional Gemini AI analysis.
"""
import json
import logging
import math
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum, Avg

from kanban.models import Board, Task
from kanban.budget_models import ProjectBudget
from kanban.burndown_models import BurndownPrediction, TeamVelocitySnapshot
from kanban_board.ai_cache import get_cached_ai_response

logger = logging.getLogger(__name__)

# Brooks's Law exponent: adding people has diminishing returns on velocity
TEAM_SCALING_EXPONENT = 0.7

# ---------------------------------------------------------------------------
# Single published definition of TEAM UTILIZATION.
#
# utilization% = remaining_tasks / team_size / TASKS_PER_MEMBER_AT_FULL_LOAD * 100
#
# i.e. one member carrying TASKS_PER_MEMBER_AT_FULL_LOAD open tasks is exactly
# 100% utilized.  Every What-If / Shadow Board surface reads this one formula
# (see `compute_utilization_pct`) so the number can't drift between panels.
# Note this is a *workload* measure (open tasks per head), NOT the calendar
# capacity measure used by Skill Gap / AI Coach / profiles — those answer a
# different question (booked hours vs available hours) and are labelled
# differently in the UI.
TASKS_PER_MEMBER_AT_FULL_LOAD = 8

# Displayed utilization saturates here; `utilization_raw` keeps the unclamped
# value as an ordering signal for deeply over-allocated scenarios.
UTILIZATION_DISPLAY_CAP = 200

# Feasibility tier bands (percent).  Raised from 70/50 so a plan the engine
# itself flags as over-allocated can no longer be labelled "High".
FEASIBILITY_HIGH_BAND = 85
FEASIBILITY_MEDIUM_BAND = 60

# Hard ceiling applied to any scenario whose team utilization exceeds 100%.
# A plan that over-allocates the team is, by definition, not a "High
# feasibility" plan — no amount of schedule buffer or budget slack should let
# it read as one.  Anchored just under the top of the Medium band so a plan
# that only just crosses 100% reads Medium (matching its own Medium risk
# level and Medium conflict), then scales down into Low as overload deepens.
OVERALLOCATION_CEILING = (FEASIBILITY_HIGH_BAND - 1) / 100.0   # 0.84
# Total ceiling drop across the 100%→200% utilization range.  At 200%+ the
# ceiling lands at 0.44, i.e. firmly Low.
OVERALLOCATION_CEILING_DROP = 0.40


def compute_utilization_pct(remaining_tasks, team_size):
    """
    The single canonical team-utilization formula (see the constant block above).

    Returns (display_pct, raw_pct):
      * display_pct is clamped to UTILIZATION_DISPLAY_CAP for presentation
      * raw_pct is unclamped, used only as an ordering/severity signal

    Every caller in What-If and Shadow Board must go through this helper —
    utilization previously appeared with three subtly different derivations,
    which is how the same scenario could show two different percentages.
    """
    team_size = team_size or 1
    per_member = remaining_tasks / team_size
    raw = round(per_member / TASKS_PER_MEMBER_AT_FULL_LOAD * 100, 1)
    return min(raw, UTILIZATION_DISPLAY_CAP), raw


def feasibility_tier(score_pct):
    """Map a 0-100 feasibility score onto its High/Medium/Low label."""
    if score_pct >= FEASIBILITY_HIGH_BAND:
        return 'High'
    if score_pct >= FEASIBILITY_MEDIUM_BAND:
        return 'Medium'
    return 'Low'


class WhatIfEngine:
    """Runs what-if scenario simulations against a real board's current state."""

    def __init__(self, board: Board):
        self.board = board

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def simulate(self, params: dict) -> dict:
        """
        Run a what-if simulation.

        Args:
            params: {
                "tasks_added": int,          # +/- task count change
                "team_size_delta": int,       # +/- team member change
                "deadline_shift_days": int,   # +/- days (positive = extend)
            }

        Returns:
            dict with keys: baseline, projected, deltas, new_conflicts,
            feasibility_score, warnings
        """
        tasks_added = int(params.get('tasks_added', 0))
        team_delta = int(params.get('team_size_delta', 0))
        deadline_shift = int(params.get('deadline_shift_days', 0))
        # velocity_health is an optional multiplicative health signal supplied by
        # the live shadow-branch recalculation path: actual_7d_velocity / branch_baseline_velocity.
        # What-If dashboard calls leave this as 1.0 (neutral) so baseline simulations
        # remain deterministic across runs.
        velocity_health = params.get('velocity_health', 1.0)

        baseline = self._capture_baseline()
        projected = self._compute_projected(baseline, tasks_added, team_delta, deadline_shift)
        deltas = self._compute_deltas(baseline, projected)
        conflicts = self._detect_new_conflicts(baseline, projected, tasks_added, team_delta, deadline_shift)
        feasibility = self._compute_feasibility(projected, deltas, conflicts, velocity_health)
        warnings = self._generate_warnings(baseline)

        return {
            'baseline': baseline,
            'projected': projected,
            'deltas': deltas,
            'new_conflicts': conflicts,
            'feasibility_score': feasibility,
            'warnings': warnings,
        }

    def analyze_with_ai(self, params: dict, simulation_results: dict) -> dict:
        """
        Ask AI to evaluate a what-if scenario and provide strategic advice.

        Returns a structured dict or an error dict on failure.
        """
        try:
            from ai_assistant.utils.ai_router import AIRouter

            baseline = simulation_results['baseline']
            projected = simulation_results['projected']
            deltas = simulation_results['deltas']
            conflicts = simulation_results['new_conflicts']
            feasibility = simulation_results['feasibility_score']

            prompt = self._build_ai_prompt(params, baseline, projected, deltas, conflicts, feasibility)

            router = AIRouter()
            raw = get_cached_ai_response(
                prompt=prompt,
                model_call=lambda: router.complete(
                    prompt=prompt,
                    user=None,
                    complexity='complex',
                )['text'],
                operation='whatif_analysis',
                context_id=f"board_{self.board.id}",
            )
            if not raw:
                return {'error': 'AI analysis unavailable. Please try again.'}

            # Strip markdown fences
            if raw.startswith('```'):
                raw = raw.split('```')[1]
                if raw.startswith('json'):
                    raw = raw[4:]
                raw = raw.strip()
            if raw.endswith('```'):
                raw = raw[:-3].strip()

            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                last_brace = raw.rfind('}')
                if last_brace != -1:
                    raw = raw[:last_brace + 1]
                    open_brackets = raw.count('[') - raw.count(']')
                    open_braces = raw.count('{') - raw.count('}')
                    raw += ']' * max(open_brackets, 0) + '}' * max(open_braces, 0)
                result = json.loads(raw)

            return result

        except json.JSONDecodeError as exc:
            logger.warning('What-If AI: JSON parse error: %s', exc)
            return {'error': 'AI returned an unparseable response. Please try again.'}
        except Exception as exc:
            logger.error('What-If AI analysis failed: %s', exc)
            return {'error': f'AI analysis unavailable: {exc}'}

    # ------------------------------------------------------------------
    # Baseline capture (read-only)
    # ------------------------------------------------------------------
    def _capture_baseline(self) -> dict:
        board = self.board
        tasks = Task.objects.filter(column__board=board, item_type='task')
        total_tasks = tasks.count()
        completed = tasks.filter(progress=100).count()
        remaining = total_tasks - completed

        # Scope
        scope_status = board.get_current_scope_status()

        # Budget
        budget_data = self._get_budget_data(total_tasks)

        # Timeline — read latest prediction, don't generate new one
        prediction = BurndownPrediction.objects.filter(
            board=board,
        ).order_by('-prediction_date').first()

        velocity = 0
        predicted_date = None
        delay_probability = 0
        risk_level = 'unknown'
        confidence_pct = None
        if prediction:
            # Use average_velocity to match what the Burndown Prediction dashboard displays.
            # current_velocity is only the most-recent week; average_velocity is the mean
            # across all historical weekly snapshots — the correct baseline for projections.
            velocity = float(prediction.average_velocity or prediction.current_velocity or 0)
            predicted_date = prediction.predicted_completion_date
            delay_probability = float(prediction.delay_probability or 0)
            risk_level = prediction.risk_level or 'unknown'
            confidence_pct = prediction.confidence_percentage

        # Velocity fallback: average recent weekly snapshots (mirrors burndown predictor logic)
        if not velocity:
            recent_snapshots = TeamVelocitySnapshot.objects.filter(
                board=board,
            ).order_by('-period_end')[:8]
            counts = [float(s.tasks_completed or 0) for s in recent_snapshots]
            if counts:
                velocity = sum(counts) / len(counts)

        # Recompute predicted_date from live remaining tasks and velocity so the
        # baseline date uses the same derivation method as `_compute_projected`.
        # Without this, baseline.predicted_date stays pinned to whatever the
        # scheduled BurndownPrediction job last saved (often weeks stale), while
        # projected.predicted_date is recomputed from today on every call — making
        # the timeline delta look implausible (the AI then calls it a "fundamental
        # flaw" even when the math is self-consistent).
        if velocity and velocity >= 0.5 and remaining > 0:
            predicted_date = date.today() + timedelta(weeks=remaining / velocity)

        # Team
        team_size = board.memberships.count() or 1

        # Resource utilization estimate (canonical formula — see module header)
        utilization_pct, _ = compute_utilization_pct(remaining, team_size)

        # Effective deadline
        effective_deadline = self._get_effective_deadline(prediction)

        return {
            'total_tasks': total_tasks,
            'completed_tasks': completed,
            'remaining_tasks': remaining,
            'team_size': team_size,
            'velocity_per_week': round(velocity, 2),
            'avg_cost_per_task': budget_data.get('avg_cost_per_task', 0),
            'budget_allocated': budget_data.get('allocated', 0),
            'budget_spent': budget_data.get('spent', 0),
            'budget_utilization_pct': budget_data.get('utilization_pct', 0),
            'budget_currency': budget_data.get('currency', 'USD'),
            'predicted_date': predicted_date.isoformat() if predicted_date else None,
            'effective_deadline': effective_deadline.isoformat() if effective_deadline else None,
            'delay_probability': round(delay_probability, 1),
            'risk_level': risk_level,
            'confidence_pct': confidence_pct,
            'utilization_pct': utilization_pct,
            'scope_change_pct': (
                scope_status.get('scope_change_percentage', 0) if scope_status else 0
            ),
        }

    # ------------------------------------------------------------------
    # Projected state (pure math, zero DB writes)
    # ------------------------------------------------------------------
    def _compute_projected(self, baseline: dict, tasks_added: int,
                           team_delta: int, deadline_shift: int) -> dict:
        # --- Scope ---
        new_total = baseline['total_tasks'] + tasks_added
        new_remaining = max(baseline['remaining_tasks'] + tasks_added, 0)

        # --- Team ---
        new_team = max(baseline['team_size'] + team_delta, 1)

        # --- Velocity (Brooks's Law) ---
        old_team = baseline['team_size'] or 1
        if new_team != old_team and baseline['velocity_per_week'] > 0:
            ratio = new_team / old_team
            new_velocity = baseline['velocity_per_week'] * (ratio ** TEAM_SCALING_EXPONENT)
        else:
            new_velocity = baseline['velocity_per_week']
        new_velocity = round(max(new_velocity, 0.1), 2)

        # --- Timeline ---
        # Predicted completion is purely a function of remaining work and team
        # velocity.  The deadline shift moves `new_deadline` (below) but never
        # the predicted-completion date itself — conflating the two produced
        # the +207-day projection artefact when scope was reduced.
        VELOCITY_THRESHOLD = 0.5
        low_velocity = new_velocity < VELOCITY_THRESHOLD

        new_predicted_date = None
        if not low_velocity:
            weeks_for_remaining = new_remaining / new_velocity
            new_predicted_date = date.today() + timedelta(weeks=weeks_for_remaining)

        new_deadline = None
        if baseline['effective_deadline']:
            new_deadline = (
                date.fromisoformat(baseline['effective_deadline'])
                + timedelta(days=deadline_shift)
            )

        # --- Schedule overshoot (UNCLAMPED severity signal) ---
        # How many days the projected completion overshoots the deadline.
        # This keeps growing with scope/scenario severity even after
        # delay_probability has saturated at 99, so two deeply-infeasible
        # branches can still be ordered against each other.  Display/conflict
        # logic continues to use the clamped delay_probability below.
        schedule_overshoot_days = 0
        if new_predicted_date and new_deadline and new_predicted_date > new_deadline:
            schedule_overshoot_days = (new_predicted_date - new_deadline).days

        # --- Schedule buffer (signed; None when there isn't enough data) ---
        # Positive = days of slack before the deadline, negative = overshoot.
        # Used only to differentiate penalty-free scenarios (see the headroom
        # ceiling in _compute_feasibility) — never affects the penalty math above.
        buffer_days = None
        if new_predicted_date and new_deadline:
            buffer_days = (new_deadline - new_predicted_date).days

        # --- Delay probability ---
        new_delay_prob = self._estimate_delay_probability(
            new_remaining, new_velocity, new_predicted_date, new_deadline,
            baseline['delay_probability'],
        )

        # --- Budget ---
        additional_cost = tasks_added * baseline['avg_cost_per_task']
        new_budget_spent = baseline['budget_spent'] + max(additional_cost, 0)
        new_budget_util = (
            round(new_budget_spent / baseline['budget_allocated'] * 100, 1)
            if baseline['budget_allocated'] > 0 else 0
        )

        # --- Utilization ---
        # `utilization_raw` is the UNCLAMPED value (can exceed the display cap);
        # kept as a severity signal so over-allocated scenarios stay ordered
        # after the displayed `utilization_pct` saturates.  Both come from the
        # single canonical formula (see module header).
        new_utilization, utilization_raw = compute_utilization_pct(new_remaining, new_team)

        # --- Risk level ---
        # Delay probability sets the baseline band, but a scenario can be
        # low on delay risk while still being dangerous on resourcing or
        # spend (e.g. utilization spiking to 187% with delay probability
        # only at 40%) — escalate risk level to match the worst signal so
        # it doesn't silently disagree with the conflicts/feasibility panel.
        new_risk = self._risk_from_delay(new_delay_prob)
        new_risk = self._escalate_risk(new_risk, utilization_raw, new_budget_util)

        return {
            'total_tasks': new_total,
            'completed_tasks': baseline['completed_tasks'],
            'remaining_tasks': new_remaining,
            'team_size': new_team,
            'velocity_per_week': new_velocity,
            'avg_cost_per_task': baseline['avg_cost_per_task'],
            'budget_allocated': baseline['budget_allocated'],
            'budget_spent': round(new_budget_spent, 2),
            'budget_utilization_pct': new_budget_util,
            'budget_currency': baseline['budget_currency'],
            'predicted_date': new_predicted_date.isoformat() if new_predicted_date else None,
            'low_velocity': low_velocity,
            'effective_deadline': new_deadline.isoformat() if new_deadline else None,
            'delay_probability': round(new_delay_prob, 1),
            'risk_level': new_risk,
            'confidence_pct': baseline['confidence_pct'],
            'utilization_pct': new_utilization,
            'utilization_raw': utilization_raw,
            'schedule_overshoot_days': schedule_overshoot_days,
            'buffer_days': buffer_days,
        }

    # ------------------------------------------------------------------
    # Deltas
    # ------------------------------------------------------------------
    def _compute_deltas(self, baseline: dict, projected: dict) -> dict:
        def _delta(key, fmt='number'):
            b = baseline.get(key, 0) or 0
            p = projected.get(key, 0) or 0
            return round(p - b, 2) if fmt == 'number' else p - b

        timeline_delta = 0
        if baseline.get('predicted_date') and projected.get('predicted_date'):
            bd = date.fromisoformat(baseline['predicted_date'])
            pd = date.fromisoformat(projected['predicted_date'])
            timeline_delta = (pd - bd).days

        return {
            'tasks': _delta('total_tasks'),
            'remaining': _delta('remaining_tasks'),
            'team_size': _delta('team_size'),
            'velocity': _delta('velocity_per_week'),
            'budget_spent': _delta('budget_spent'),
            'budget_utilization_pct': _delta('budget_utilization_pct'),
            'timeline_days': timeline_delta,
            'delay_probability': _delta('delay_probability'),
            'utilization_pct': _delta('utilization_pct'),
        }

    # ------------------------------------------------------------------
    # Conflict detection (hypothetical)
    # ------------------------------------------------------------------
    def _detect_new_conflicts(self, baseline, projected, tasks_added,
                              team_delta, deadline_shift) -> list:
        conflicts = []

        # Resource overload
        if projected['utilization_pct'] > 100 and baseline['utilization_pct'] <= 100:
            conflicts.append({
                'type': 'resource_overload',
                'severity': 'high' if projected['utilization_pct'] > 130 else 'medium',
                'description': (
                    f"Team utilization would jump to {projected['utilization_pct']}%. "
                    f"Members would be over-allocated."
                ),
            })

        # Deadline infeasibility
        if (projected.get('predicted_date') and projected.get('effective_deadline')
                and projected['predicted_date'] > projected['effective_deadline']):
            overshoot = (
                date.fromisoformat(projected['predicted_date'])
                - date.fromisoformat(projected['effective_deadline'])
            ).days
            conflicts.append({
                'type': 'schedule_conflict',
                'severity': 'critical' if overshoot > 14 else 'high',
                'description': (
                    f"Projected completion overshoots the deadline by {overshoot} days."
                ),
            })

        # High delay risk
        if projected['delay_probability'] > 70 and baseline['delay_probability'] <= 70:
            conflicts.append({
                'type': 'deadline_risk',
                'severity': 'high',
                'description': (
                    f"Delay probability would rise to {projected['delay_probability']}% "
                    f"(from {baseline['delay_probability']}%)."
                ),
            })

        # Budget overrun
        if (projected['budget_utilization_pct'] > 100
                and baseline['budget_utilization_pct'] <= 100):
            conflicts.append({
                'type': 'budget_overrun',
                'severity': 'critical' if projected['budget_utilization_pct'] > 120 else 'high',
                'description': (
                    f"Budget utilization would reach {projected['budget_utilization_pct']}%, "
                    f"exceeding the allocated budget."
                ),
            })

        return conflicts

    # ------------------------------------------------------------------
    # Feasibility score  (0.0 – 1.0)
    # ------------------------------------------------------------------
    def _compute_feasibility(self, projected, deltas, conflicts,
                             velocity_health: float = 1.0) -> float:
        """
        Continuous, piecewise-linear penalty curves.  Each curve preserves the
        prior step-function's upper anchor values so existing What-If baselines
        don't shift, but interpolates linearly between anchors so small board
        changes (e.g. a single task completion) produce a small visible score
        movement instead of being clamped to the same step.

        `velocity_health` is `actual_recent_velocity / branch_baseline_velocity`,
        supplied only by the shadow-branch recalc path.  Values > 1.0 (team is
        outperforming the original projection) add up to +0.10; values < 1.0
        subtract up to -0.10.  Capped so the velocity signal never dominates
        the structural penalties.
        """
        score = 1.0

        # --- Delay probability (continuous; anchors preserved at 40/60/80) ---
        # 0–40   →  0
        # 40–60  →  0    → -0.10
        # 60–80  →  -0.10 → -0.20
        # 80–100 →  -0.20 → -0.35  (steeper, matches prior >80 cliff)
        dp = projected.get('delay_probability', 0)
        if dp > 80:
            score -= 0.20 + min(dp - 80, 20) / 20 * 0.15
        elif dp > 60:
            score -= 0.10 + (dp - 60) / 20 * 0.10
        elif dp > 40:
            score -= (dp - 40) / 20 * 0.10

        # --- Resource utilization (continuous; same anchors as before) ---
        # 100–130 →  -0.05 → -0.15  (was a flat -0.15 step; now ramps from -0.05)
        # 130–200 →  -0.15 → -0.25  (preserved from prior linear band)
        util = projected.get('utilization_pct', 0)
        if util > 130:
            excess_pct = min(util - 130, 70) / 70
            score -= 0.15 + excess_pct * 0.10
        elif util > 100:
            score -= 0.05 + (util - 100) / 30 * 0.10

        # --- Budget overrun (continuous) ---
        # 100–120 →  0    → -0.10
        # 120–150 →  -0.10 → -0.20  (extrapolated cap at -0.20)
        bu = projected.get('budget_utilization_pct', 0)
        if bu > 120:
            score -= 0.10 + min(bu - 120, 30) / 30 * 0.10
        elif bu > 100:
            score -= (bu - 100) / 20 * 0.10

        # --- Conflicts ---
        # Computed here but APPLIED AFTER the headroom ceiling clamp (see below),
        # for the same reason the descope penalty is: for a mostly-healthy plan
        # the headroom ceiling is the binding constraint, so a penalty applied
        # to `score` here would be clamped away and cost nothing.  A detected
        # conflict — the thing the UI is showing the user in a warning banner —
        # must always move the number.  `medium` used to be worth exactly zero
        # even before the clamp interaction; every severity now subtracts.
        conflict_penalty = 0.0
        for c in conflicts:
            if c['severity'] == 'critical':
                conflict_penalty += 0.1
            elif c['severity'] == 'high':
                conflict_penalty += 0.05
            elif c['severity'] == 'medium':
                conflict_penalty += 0.03

        # --- Velocity health adjustment (live recalc path only) ---
        # velocity_health = actual_recent_velocity / branch_baseline_velocity.
        # Each 10% deviation moves the feasibility score by ~1 point, capped at
        # +/-10 points so the velocity signal never overwhelms structural penalties.
        # Accept 0.0 as a valid signal (means "no real-board completions in the
        # last 7 days") — that should *penalize*, not be silently skipped.
        if velocity_health is not None and velocity_health >= 0:
            score += max(-0.10, min(0.10, velocity_health - 1.0))

        # --- Saturation differentiation tail ---
        # The structural penalties above stop responding once delay_probability
        # pins at its 99 ceiling and utilization clamps at 200, so two
        # deeply-infeasible scenarios of very different magnitude (e.g. +4 vs
        # +8 tasks) collapse to the *same* score.  This tail keeps subtracting
        # a small, bounded amount that grows with the UNCLAMPED severity
        # signals, restoring strict ordering between such scenarios.
        #
        # It contributes EXACTLY 0 below the clamps (delay_probability < 99 and
        # raw utilization <= 200), so any scenario that isn't already saturated
        # keeps its previous score unchanged.  Combined tail capped at 0.10 so
        # it differentiates without flipping the High/Medium/Low tier.
        tail = 0.0
        if projected.get('delay_probability', 0) >= 99:
            overshoot = projected.get('schedule_overshoot_days', 0) or 0
            if overshoot > 0:
                tail += 0.06 * math.tanh(overshoot / 120.0)
        util_raw = projected.get('utilization_raw', util)
        if util_raw > 200:
            tail += 0.04 * math.tanh((util_raw - 200) / 100.0)
        if tail:
            score -= min(tail, 0.10)

        # --- Headroom ceiling ---
        # The penalty bands above only ever fire once a metric crosses a risk
        # threshold (delay_probability > 40, utilization > 100, budget > 100).
        # Below those thresholds every "healthy" scenario scores identically
        # (score == 1.0, later clamped), even though a scenario with a huge
        # schedule buffer and idle capacity is obviously safer than one that
        # just barely clears the thresholds. `headroom` is a pure function of
        # already-computed `projected` values — it re-uses the same signals
        # that feed the penalties, so it stays deterministic and adds no
        # smoothing/damping across recalcs.
        def _slack(value, full_credit_at, floor_at=0):
            if value is None:
                return 0.5  # no data — neutral, avoids rewarding/punishing missing deadlines
            span = full_credit_at - floor_at
            if span <= 0:
                return 0.5
            return max(0.0, min(1.0, (value - floor_at) / span))

        # Schedule buffer saturates at a 90-day horizon: beyond ~a quarter of
        # runway, extra buffer adds little real feasibility, but within it a
        # bigger buffer (and completing work, which grows it) should still lift
        # the score. Utilization carries the most weight because among healthy
        # scenarios it is the lever that BOTH differentiates scope trade-offs
        # (cut-scope vs add-scope) AND moves as real tasks complete — so it
        # keeps the score responsive to progress instead of flat-lining.
        schedule_slack = _slack(projected.get('buffer_days'), full_credit_at=90, floor_at=0)
        utilization_slack = 1 - _slack(util, full_credit_at=100, floor_at=0)
        budget_slack = 1 - _slack(bu, full_credit_at=100, floor_at=0)
        # Schedule now carries as much weight as utilization.  Previously
        # utilization was weighted 0.50 against schedule's 0.30, so the score
        # was dominated by the resourcing term and barely responded to the
        # schedule: completing four tasks pulled projected completion 18 days
        # earlier and moved feasibility only ~2 points, which reads to a PM as
        # "the score doesn't reward progress".  Equal weighting makes real
        # schedule improvement register while keeping utilization decisive.
        headroom = 0.40 * schedule_slack + 0.40 * utilization_slack + 0.20 * budget_slack

        # Soft ceiling: real projects never have *zero* residual risk —
        # unforeseen scope creep, illness, dependencies — so the maximum
        # displayed score is 0.98, reached only by scenarios with the most
        # headroom (big schedule buffer, idle capacity, budget slack).
        # Scenarios that merely clear the risk thresholds without much margin
        # land well below (down to ~0.68) instead of tying near the top —
        # otherwise a scope-adding scenario that just barely avoids conflicts
        # reads almost identically to a scope-cutting scenario with room to
        # spare, leaving every branch clustered so tightly the user can't tell
        # which to commit to. The floor/span were widened (0.68 + 0.30) so
        # healthy scenarios spread across a ~10-point band and completing tasks
        # produces a visible move. The 0.0 hard floor stays (a project can
        # legitimately be fully blocked).
        HEADROOM_FLOOR = 0.68
        HEADROOM_SPAN = 0.30
        ceiling = min(0.98, HEADROOM_FLOOR + HEADROOM_SPAN * headroom)

        # --- Over-allocation hard ceiling ---
        # The penalty bands alone were far too weak to stop an over-allocated
        # plan reading as "High": at 125% utilization the utilization band
        # subtracted only ~0.13 and the medium conflict subtracted nothing, so
        # a plan whose own AI narrative called it "burnout-inducing" landed at
        # 74% and got the High label.  Utilization above 100% means the team
        # cannot absorb the remaining work — that is a deliverability fact, not
        # a matter of degree to be averaged against schedule buffer.  So any
        # such scenario is capped below the High band outright, and the cap
        # tightens as the overload deepens (100% → 0.60, 200%+ → 0.40).
        if util > 100:
            overload_fraction = min((util - 100) / 100.0, 1.0)
            ceiling = min(
                ceiling,
                OVERALLOCATION_CEILING - OVERALLOCATION_CEILING_DROP * overload_fraction,
            )

        final = max(0.0, min(score, ceiling))

        # --- Conflict penalty (applied AFTER the ceiling clamp) ---
        # See the note where conflict_penalty is accumulated: a detected
        # conflict must always cost the score, even for a plan whose headroom
        # ceiling would otherwise clamp the penalty away to nothing.
        if conflict_penalty:
            final = max(0.0, final - conflict_penalty)

        # --- Descope / value penalty (applied AFTER the ceiling clamp) ---
        # Every other term here is deliverability-only: it rewards a plan for
        # being easy to finish and says nothing about whether the plan still
        # delivers the product.  Removing scope lowers delay probability,
        # utilization AND budget at once — and, crucially, it also MAXES OUT the
        # headroom ceiling (idle capacity + big schedule buffer).  So "cut
        # tasks" wasn't just a near-dominant strategy on the penalty terms; the
        # ceiling actively rewarded it, and any penalty applied to `score`
        # before the clamp was invisible because the ceiling was the binding
        # constraint.  Applying the value penalty to the CLAMPED result is what
        # makes a leaner plan read as "lower risk" without automatically reading
        # as "best".
        #
        # Deliberately asymmetric and zero-anchored:
        #   * Only fires when scope is REDUCED (deltas['tasks'] < 0).  Adding
        #     scope is already penalized structurally above — charging it here
        #     too would double-count.
        #   * Contributes EXACTLY 0 when scope is unchanged or grown, so every
        #     existing What-If baseline and no-op recalc scores identically to
        #     before this term existed (preserves the "baselines don't shift"
        #     invariant documented on the headroom ceiling above).
        # Scaled by the fraction of the project's scope removed and capped at
        # -0.12 so a heavy descope is clearly penalized but the term never
        # overwhelms the structural feasibility signals or flips a genuinely
        # infeasible plan to look good.
        scope_delta = deltas.get('tasks', 0) or 0
        if scope_delta < 0:
            baseline_total = projected.get('total_tasks', 0) - scope_delta
            if baseline_total > 0:
                removed_fraction = min(-scope_delta / baseline_total, 1.0)
                final = max(0.0, final - min(0.12, 0.12 * removed_fraction))

        return round(final, 4)

    # ------------------------------------------------------------------
    # Warnings for missing data
    # ------------------------------------------------------------------
    def _generate_warnings(self, baseline) -> list:
        warnings = []
        if not baseline.get('predicted_date'):
            warnings.append(
                'No burndown prediction available. Timeline projections are estimated '
                'from velocity only.'
            )
        if baseline.get('velocity_per_week', 0) == 0:
            warnings.append(
                'Team velocity is zero or unknown. Complete a few tasks to enable '
                'accurate timeline projections.'
            )
        if baseline.get('budget_allocated', 0) == 0:
            warnings.append(
                'No budget configured for this board. Cost projections are unavailable.'
            )
        if not baseline.get('effective_deadline'):
            warnings.append(
                'No project deadline set. Delay probability cannot be calculated.'
            )
        return warnings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_budget_data(self, total_tasks: int) -> dict:
        try:
            budget = ProjectBudget.objects.get(board=self.board)
            spent = float(budget.get_spent_amount())
            allocated = float(budget.allocated_budget)
            return {
                'allocated': allocated,
                'spent': spent,
                'utilization_pct': round(budget.get_budget_utilization_percent(), 1),
                'currency': budget.currency,
                'avg_cost_per_task': round(spent / total_tasks, 2) if total_tasks else 0,
            }
        except ProjectBudget.DoesNotExist:
            return {
                'allocated': 0,
                'spent': 0,
                'utilization_pct': 0,
                'currency': 'USD',
                'avg_cost_per_task': 0,
            }

    def _get_effective_deadline(self, prediction) -> date | None:
        board = self.board
        if board.project_deadline:
            return board.project_deadline
        if prediction and prediction.target_completion_date:
            return prediction.target_completion_date
        max_due = (
            Task.objects.filter(column__board=board, item_type='task', due_date__isnull=False)
            .order_by('-due_date')
            .values_list('due_date', flat=True)
            .first()
        )
        if max_due:
            return max_due.date() if hasattr(max_due, 'date') else max_due
        return None

    def _estimate_delay_probability(self, remaining, velocity, predicted_date,
                                    deadline, base_delay) -> float:
        """Rough delay probability estimate without running full burndown predictor."""
        if not deadline or not predicted_date:
            # If scope grew, nudge probability up proportionally
            return min(base_delay + max(remaining * 0.5, 0), 99)

        if isinstance(deadline, str):
            deadline = date.fromisoformat(deadline)
        if isinstance(predicted_date, str):
            predicted_date = date.fromisoformat(predicted_date)

        buffer_days = (deadline - predicted_date).days
        if buffer_days >= 14:
            return max(base_delay - 10, 5)
        if buffer_days >= 7:
            return base_delay
        if buffer_days >= 0:
            return min(base_delay + 15, 90)
        # Overshot
        overshoot = abs(buffer_days)
        return min(base_delay + overshoot * 2, 99)

    @staticmethod
    def _risk_from_delay(delay_prob: float) -> str:
        if delay_prob >= 70:
            return 'critical'
        if delay_prob >= 50:
            return 'high'
        if delay_prob >= 30:
            return 'medium'
        return 'low'

    _RISK_ORDER = ('low', 'medium', 'high', 'critical')

    @classmethod
    def _escalate_risk(cls, risk_level: str, utilization_raw: float, budget_util: float) -> str:
        """Bump risk_level up to match utilization/budget severity if worse.

        Mirrors the thresholds used for resource_overload/budget_overrun
        conflicts (100% / 130% utilization, 100% / 120% budget) so the Risk
        card never shows a calmer band than the conflicts it's about to list.
        """
        floor = 'low'
        if utilization_raw > 130 or budget_util > 120:
            floor = 'high'
        elif utilization_raw > 100 or budget_util > 100:
            floor = 'medium'

        if cls._RISK_ORDER.index(floor) > cls._RISK_ORDER.index(risk_level):
            return floor
        return risk_level

    # ------------------------------------------------------------------
    # AI prompt
    # ------------------------------------------------------------------
    def _build_ai_prompt(self, params, baseline, projected, deltas,
                         conflicts, feasibility) -> str:
        conflict_text = '\n'.join(
            f"  - [{c['severity'].upper()}] {c['description']}" for c in conflicts
        ) or '  None detected.'

        # Pre-bind the feasibility tier so the AI's assessment field cannot
        # disagree with the computed score.  Past prompts let the model freely
        # label a 41% scenario "Medium" or even contradict the number with its
        # own narrative ("a critical error", "mathematically inconsistent");
        # locking the tier and explicitly telling the model not to argue with
        # the inputs eliminated that whole class of incoherent recommendations.
        feasibility_pct = round(feasibility * 100, 1)
        forced_tier = feasibility_tier(feasibility_pct)

        return f"""You are a senior program manager and strategic advisor. A project manager is
considering the following hypothetical changes to their project and needs your
expert analysis of the trade-offs.

GROUND RULES (do not violate):
- Treat every number under "Current State", "Projected State After Changes",
  "Key Deltas", and "Feasibility Score" as authoritative inputs computed by a
  deterministic engine.  Do NOT call them "errors", "inconsistent",
  "mathematically impossible", or "implausible" — they are the engine's
  ground truth.  Your job is to interpret and advise, not to audit the math.
- Your "feasibility_assessment" field MUST be exactly "{forced_tier}" because
  the computed feasibility is {feasibility_pct:.1f}% (High >={FEASIBILITY_HIGH_BAND},
  Medium {FEASIBILITY_MEDIUM_BAND}-{FEASIBILITY_HIGH_BAND - 1}, Low <{FEASIBILITY_MEDIUM_BAND}).
  Do not pick a different tier.
- Team utilization above 100% means the team cannot absorb the remaining work.
  When that is the case your risk_summary MUST lead with it, and you must not
  describe the plan as comfortable, safe, or low-risk anywhere in your response.
- Mitigations and trade-offs must be consistent with the sign of each delta
  (e.g., if tasks_added is negative, that's a scope REDUCTION, not an
  expansion; if deadline_shift_days is negative, the deadline got TIGHTER).

**Project:** {self.board.name}

**Proposed Changes:**
- Tasks added/removed: {params.get('tasks_added', 0):+d}
- Team size change: {params.get('team_size_delta', 0):+d} members
- Deadline shift: {params.get('deadline_shift_days', 0):+d} days

**Current State (Baseline):**
- Total tasks: {baseline['total_tasks']} ({baseline['remaining_tasks']} remaining)
- Team size: {baseline['team_size']}
- Velocity: {baseline['velocity_per_week']} tasks/week
- Budget: {baseline['budget_currency']} {baseline['budget_spent']:.0f} / {baseline['budget_allocated']:.0f} ({baseline['budget_utilization_pct']:.0f}%)
- Predicted completion: {baseline.get('predicted_date', 'N/A')}
- Deadline: {baseline.get('effective_deadline', 'N/A')}
- Delay probability: {baseline['delay_probability']}%
- Risk level: {baseline['risk_level']}
- Team utilization: {baseline['utilization_pct']}%

**Projected State After Changes:**
- Total tasks: {projected['total_tasks']} ({projected['remaining_tasks']} remaining)
- Team size: {projected['team_size']}
- Velocity: {projected['velocity_per_week']} tasks/week
- Budget spent: {projected['budget_currency']} {projected['budget_spent']:.0f} ({projected['budget_utilization_pct']:.0f}%)
- Predicted completion: {projected.get('predicted_date', 'N/A')}
- Deadline: {projected.get('effective_deadline', 'N/A')}
- Delay probability: {projected['delay_probability']}%
- Risk level: {projected['risk_level']}
- Team utilization: {projected['utilization_pct']}%

**Key Deltas:**
- Timeline shift: {deltas['timeline_days']:+d} days
- Budget increase: {baseline['budget_currency']} {deltas['budget_spent']:+.0f}
- Delay probability: {deltas['delay_probability']:+.1f}%
- Utilization: {deltas['utilization_pct']:+.1f}%

**New Conflicts Introduced:**
{conflict_text}

**Feasibility Score:** {feasibility:.0%}

Respond with ONLY valid JSON (no markdown fences, no extra text) in this schema:
{{
  "feasibility_assessment": "<High | Medium | Low>",
  "risk_summary": "<2-3 sentences describing the major risks of this change>",
  "recommended_mitigations": [
    "<specific actionable mitigation 1>",
    "<specific actionable mitigation 2>",
    "<specific actionable mitigation 3>"
  ],
  "trade_off_analysis": "<2-3 sentences: what you gain vs what you lose>",
  "alternative_suggestion": "<A better way to achieve the PM's apparent goal, in 2-3 sentences>",
  "confidence": <float 0.0-1.0>
}}"""
