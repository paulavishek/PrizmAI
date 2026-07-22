"""
Tests for the assignee skill-match superlative guardrail.

The candidate factor scores are computed deterministically in Python and fed to
the AI, but the "highest/lowest skill match" phrasing is free-text the model
writes and can invert the ranking. `_correct_skill_match_superlatives` neutralises
any superlative that contradicts the numbers. These are pure-function tests (no DB).
"""

import json
import re
from unittest.mock import patch

from django.test import SimpleTestCase

from kanban.utils.ai_utils import (
    _skill_match_extremes,
    _correct_skill_match_superlatives,
    suggest_task_breakdown,
    generate_task_description,
)


def _candidates():
    # testuser1 has the HIGHEST skill match (40), Priya the LOWEST (37).
    return [
        {'user_id': 1, 'display_name': 'testuser1', 'skill_match': 40.0, 'overall_score': 75.0},
        {'user_id': 2, 'display_name': 'Priya Sharma', 'skill_match': 37.0, 'overall_score': 37.0},
        {'user_id': 3, 'display_name': 'Elena Vasquez', 'skill_match': 38.0, 'overall_score': 40.0},
    ]


class SkillMatchExtremesTests(SimpleTestCase):
    def test_identifies_highest_and_lowest(self):
        highest, lowest = _skill_match_extremes(_candidates())
        self.assertEqual(highest, 'testuser1')
        self.assertEqual(lowest, 'Priya Sharma')

    def test_empty_returns_none(self):
        self.assertEqual(_skill_match_extremes([]), (None, None))

    def test_all_tied_returns_same_name(self):
        tied = [
            {'user_id': 1, 'display_name': 'A', 'skill_match': 50.0},
            {'user_id': 2, 'display_name': 'B', 'skill_match': 50.0},
        ]
        highest, lowest = _skill_match_extremes(tied)
        self.assertEqual(highest, lowest)


class CorrectSuperlativesTests(SimpleTestCase):
    def test_corrects_inverted_lowest_claim_in_reasoning(self):
        # The reproduced bug: AI calls testuser1 (the HIGHEST) the "lowest skill match".
        resp = {
            'reasoning': 'While testuser1 has the lowest skill match score, they are the only '
                         'candidate with sufficient availability.',
            'alternatives': [],
            'factors': [],
        }
        _correct_skill_match_superlatives(resp, _candidates())
        self.assertNotIn('lowest skill match', resp['reasoning'].lower())
        # The correction must NOT surface as a user-facing warning (regression A1).
        self.assertNotIn('Adjusted skill-match wording', ' '.join(resp.get('warnings', [])))

    def test_corrects_wrong_highest_in_alternative(self):
        # Priya is actually the LOWEST but the AI calls her the "highest skill match".
        resp = {
            'reasoning': '',
            'alternatives': [
                {'user_id': 2, 'display_name': 'Priya Sharma',
                 'brief_reason': 'Possesses the highest skill match score.'},
            ],
            'factors': [],
        }
        _correct_skill_match_superlatives(resp, _candidates())
        self.assertNotIn('highest skill match', resp['alternatives'][0]['brief_reason'].lower())

    def test_leaves_correct_claims_untouched(self):
        # testuser1 IS the highest — this claim is accurate and must not be altered.
        original = 'testuser1 has the highest skill match on the team.'
        resp = {'reasoning': original, 'alternatives': [], 'factors': []}
        _correct_skill_match_superlatives(resp, _candidates())
        self.assertEqual(resp['reasoning'], original)
        self.assertNotIn('warnings', resp)

    def test_all_tied_strips_superlatives(self):
        tied = [
            {'user_id': 1, 'display_name': 'A', 'skill_match': 50.0},
            {'user_id': 2, 'display_name': 'B', 'skill_match': 50.0},
        ]
        resp = {'reasoning': 'A has the best skill match.', 'alternatives': [], 'factors': []}
        _correct_skill_match_superlatives(resp, tied)
        self.assertNotIn('best skill match', resp['reasoning'].lower())

    def test_no_candidates_is_noop(self):
        resp = {'reasoning': 'X has the lowest skill match.', 'alternatives': [], 'factors': []}
        _correct_skill_match_superlatives(resp, [])
        self.assertEqual(resp['reasoning'], 'X has the lowest skill match.')

    def test_no_article_stutter_after_correction(self):
        # Elena is NOT the highest (testuser1 is), so "the highest" is corrected.
        # The leading article must be consumed — no "the a notable" stutter.
        resp = {'reasoning': 'Elena Vasquez has the highest skill match on the team.',
                'alternatives': [], 'factors': []}
        _correct_skill_match_superlatives(resp, _candidates())
        self.assertNotIn('the a ', resp['reasoning'])
        self.assertNotIn('highest skill match', resp['reasoning'].lower())

    def test_correction_never_leaks_into_warnings(self):
        # The internal correction note must not surface as a user-facing ⚠️ flag.
        resp = {'reasoning': 'Elena Vasquez has the highest skill match.',
                'alternatives': [], 'factors': [], 'warnings': []}
        _correct_skill_match_superlatives(resp, _candidates())
        self.assertNotIn('Adjusted skill-match wording', ' '.join(resp.get('warnings', [])))


class PriorityRuleEngineTests(SimpleTestCase):
    """The create-task priority path is deterministic Python (_rule_based_suggestion)."""

    def _suggest(self, task):
        from ai_assistant.utils.priority_service import PrioritySuggestionService
        return PrioritySuggestionService()._rule_based_suggestion(task)

    def _task(self, **ctx):
        from kanban.models import Task
        title = ctx.pop('title', 'A task')
        description = ctx.pop('description', '')
        t = Task(title=title, description=description)
        t._advanced_context = ctx
        return t

    def _factor_texts(self, result):
        return [f['description'] for f in result['reasoning']['top_factors']]

    def test_incident_keyword_detected(self):
        task = self._task(title='Resolve OOM crashes in Cloud Run',
                          description='memory leak during velocity recalculation')
        joined = ' '.join(self._factor_texts(self._suggest(task))).lower()
        self.assertIn('oom', joined)

    def test_dependency_relabeled_and_informational(self):
        task = self._task(title='Normal task', dependencies_count=2)
        result = self._suggest(task)
        blocked = [f for f in result['reasoning']['top_factors']
                   if 'Blocked by' in f['description']]
        self.assertTrue(blocked, "expected a 'Blocked by' factor")
        self.assertIn('Blocked by 2 tasks', blocked[0]['description'])
        # Informational only — contributes 0% and no urgency points.
        self.assertEqual(blocked[0]['contribution_percentage'], 0)

    def test_confidence_derived_from_score(self):
        task = self._task(title='Critical security breach in production database')
        result = self._suggest(task)
        m = re.search(r'(\d+)/(\d+)', result['reasoning']['analysis_score'])
        score, mx = int(m.group(1)), int(m.group(2))
        expected = round(min(0.95, max(0.40, 0.45 + 0.50 * score / mx)), 2)
        expected = max(0.40, round(expected - 0.10, 2))  # no due date penalty
        self.assertAlmostEqual(result['confidence'], expected, places=2)

    def test_bullet_percentages_are_real_shares(self):
        # Positive-contribution factors' percentages should sum to ~100 (not a ramp).
        task = self._task(title='Critical production database migration')
        result = self._suggest(task)
        positives = [f['contribution_percentage'] for f in result['reasoning']['top_factors']
                     if f['contribution_percentage'] > 0]
        self.assertTrue(positives)
        self.assertAlmostEqual(sum(positives), 100, delta=2)

    def test_api_no_longer_false_positive_substring(self):
        # "capital" must NOT trigger the 'api' keyword (word-boundary matching).
        task = self._task(title='Update capital expenditure spreadsheet')
        joined = ' '.join(self._factor_texts(self._suggest(task))).lower()
        self.assertNotIn('high-impact keywords', joined)


class DescriptionFidelityTests(SimpleTestCase):
    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_fidelity_constraint_and_context_in_prompt(self, mock_ai):
        mock_ai.return_value = json.dumps({
            "objective": "x", "key_deliverables": ["a"],
            "action_steps": ["s"], "success_criteria": "done",
        })
        generate_task_description(
            "Fix OOM crashes",
            context={'mitigation_strategies': 'Add a Redis-based debouncer and a Celery queue'},
        )
        prompt = mock_ai.call_args[0][0]
        self.assertIn('TECHNOLOGY FIDELITY', prompt)
        self.assertIn('Redis-based debouncer', prompt)  # context forwarded verbatim


class EstimateContradictionTests(SimpleTestCase):
    """A tiny manual estimate that contradicts the AI's own multi-day subtask
    breakdown should be flagged, not silently used to lower the complexity score."""

    def _ai_breakdown(self):
        return json.dumps({
            "is_breakdown_recommended": True,
            "complexity_score": 6,
            "reasoning": "Base 6.",
            "subtasks": [
                {"title": "A", "estimated_effort": "1 day", "order": 1},
                {"title": "B", "estimated_effort": "1 day", "order": 2},
                {"title": "C", "estimated_effort": "1 day", "order": 3},
            ],
            "factors_considered": [
                {"name": "Estimated Hours", "value": "3.0 hrs",
                 "direction": "lowers", "note": "Short effort estimate"},
            ],
        })

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_flags_contradiction_and_neutralises_factor(self, mock_ai):
        mock_ai.return_value = self._ai_breakdown()
        result = suggest_task_breakdown({'title': 'Big task', 'estimated_hours': 3})
        # 3 days of subtasks vs a 3-hour estimate → contradiction surfaced.
        self.assertIn('estimate_contradiction', result)
        self.assertEqual(result['estimate_contradiction']['decomposed_effort_days'], 3.0)
        # The "Estimated Hours -> lowers" factor must be neutralised.
        est = [f for f in result['factors_considered'] if f['name'] == 'Estimated Hours'][0]
        self.assertEqual(est['direction'], 'neutral')

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_no_flag_when_estimate_matches(self, mock_ai):
        mock_ai.return_value = self._ai_breakdown()
        # 24h estimate ≈ 3 days, consistent with the breakdown → no contradiction.
        result = suggest_task_breakdown({'title': 'Big task', 'estimated_hours': 24})
        self.assertNotIn('estimate_contradiction', result)


class DescriptionIncidentContextTests(SimpleTestCase):
    """Security/incident titles must steer the description prompt toward immediate
    mitigation, and provided form context must reach the prompt."""

    def _valid_desc(self):
        return json.dumps({
            "objective": "x", "key_deliverables": ["a"],
            "action_steps": ["s"], "success_criteria": "done",
        })

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_incident_signal_adds_mitigation_rule(self, mock_ai):
        mock_ai.return_value = self._valid_desc()
        generate_task_description("Resolve Multi-Tenancy Data Bleed in Spectra AI Context")
        prompt = mock_ai.call_args[0][0]
        self.assertIn("SECURITY/INCIDENT SIGNAL", prompt)
        self.assertIn("immediate_mitigation", prompt)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_non_incident_has_no_mitigation_rule(self, mock_ai):
        mock_ai.return_value = self._valid_desc()
        generate_task_description("Add a date picker to the settings page")
        prompt = mock_ai.call_args[0][0]
        self.assertNotIn("SECURITY/INCIDENT SIGNAL", prompt)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_form_context_reaches_prompt(self, mock_ai):
        mock_ai.return_value = self._valid_desc()
        generate_task_description(
            "Refactor pooling",
            context={'required_skills': ['Django ORM', 'PostgreSQL'], 'tags': ['Security']},
        )
        prompt = mock_ai.call_args[0][0]
        self.assertIn("Django ORM", prompt)
        self.assertIn("Security", prompt)
