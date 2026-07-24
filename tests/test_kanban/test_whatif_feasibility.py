"""
Guard tests for the What-If / Shadow Board feasibility model.

These lock in the coherence invariants fixed after the review that flagged a
125%-utilization plan being labelled "Feasibility: High":

  1. Utilization > 100% caps feasibility below the High band (the plan's own
     "over-allocated" conflict must cost the score something).
  2. A `medium` conflict is never free.
  3. Schedule improvement (fewer remaining tasks) meaningfully moves the score.
  4. Deeper over-allocation scores strictly lower than mild over-allocation.
  5. The tier bands and the utilization formula are exposed as one definition.

The scoring methods are pure functions of plain dicts, so no DB is needed.
"""
from django.test import SimpleTestCase

from kanban.utils.whatif_engine import (
    WhatIfEngine,
    compute_utilization_pct,
    feasibility_tier,
    FEASIBILITY_HIGH_BAND,
    FEASIBILITY_MEDIUM_BAND,
    TASKS_PER_MEMBER_AT_FULL_LOAD,
)


def _projected(**overrides):
    """A healthy projected-state dict; override the fields a test cares about."""
    base = {
        'delay_probability': 5,
        'utilization_pct': 56.0,
        'utilization_raw': 56.0,
        'budget_utilization_pct': 47.0,
        'buffer_days': 80,
        'schedule_overshoot_days': 0,
        'total_tasks': 34,
    }
    base.update(overrides)
    return base


class UtilizationFormulaTests(SimpleTestCase):
    def test_full_load_is_100_percent(self):
        display, raw = compute_utilization_pct(
            TASKS_PER_MEMBER_AT_FULL_LOAD, 1
        )
        self.assertEqual(display, 100.0)
        self.assertEqual(raw, 100.0)

    def test_display_saturates_but_raw_does_not(self):
        display, raw = compute_utilization_pct(1000, 1)
        self.assertLess(display, raw)
        self.assertGreater(raw, 200)


class FeasibilityTierTests(SimpleTestCase):
    def test_bands(self):
        self.assertEqual(feasibility_tier(FEASIBILITY_HIGH_BAND), 'High')
        self.assertEqual(feasibility_tier(FEASIBILITY_HIGH_BAND - 1), 'Medium')
        self.assertEqual(feasibility_tier(FEASIBILITY_MEDIUM_BAND), 'Medium')
        self.assertEqual(feasibility_tier(FEASIBILITY_MEDIUM_BAND - 1), 'Low')


class FeasibilityScoreTests(SimpleTestCase):
    def setUp(self):
        # Board is only used for board.name in AI prompts; scoring never
        # touches the DB, so a bare object with the needed attrs is enough.
        self.engine = WhatIfEngine.__new__(WhatIfEngine)

    def _score(self, projected, conflicts=None, deltas=None):
        return self.engine._compute_feasibility(
            projected, deltas or {'tasks': 0}, conflicts or [],
        )

    def test_over_allocation_cannot_be_high(self):
        """The central bug: 125% utilization must not read as High feasibility."""
        projected = _projected(utilization_pct=125.0, utilization_raw=125.0)
        conflicts = [{'type': 'resource_overload', 'severity': 'medium',
                      'description': 'over-allocated'}]
        score_pct = self._score(projected, conflicts) * 100
        self.assertLess(
            score_pct, FEASIBILITY_HIGH_BAND,
            f'125% utilization scored {score_pct:.1f}% — still in the High band',
        )
        self.assertNotEqual(feasibility_tier(score_pct), 'High')

    def test_medium_conflict_is_not_free(self):
        # A medium conflict only fires alongside a penalty-bearing metric (e.g.
        # utilization just over 100), where `score` is the binding constraint
        # rather than the headroom ceiling — so the conflict penalty is
        # observable there.  Adding a second, standalone medium conflict on top
        # must lower the score: `medium` used to be worth exactly zero.
        base = _projected(utilization_pct=101.0, utilization_raw=101.0,
                          budget_utilization_pct=105.0)
        one = self._score(
            base, [{'type': 'a', 'severity': 'medium', 'description': 'y'}]
        )
        two = self._score(
            base,
            [{'type': 'a', 'severity': 'medium', 'description': 'y'},
             {'type': 'b', 'severity': 'medium', 'description': 'z'}],
        )
        self.assertLess(two, one)

    def test_deeper_overload_scores_strictly_lower(self):
        mild = self._score(_projected(utilization_pct=110.0, utilization_raw=110.0))
        deep = self._score(_projected(utilization_pct=190.0, utilization_raw=190.0))
        self.assertLess(deep, mild)

    def test_schedule_progress_moves_the_score(self):
        """Completing work (bigger buffer, lower utilization) must lift the score
        by a visible margin, not a rounding wobble."""
        earlier = self._score(_projected(buffer_days=54, utilization_pct=104.0,
                                         utilization_raw=104.0))
        later = self._score(_projected(buffer_days=90, utilization_pct=92.0,
                                       utilization_raw=92.0))
        self.assertGreater((later - earlier) * 100, 2.0)
