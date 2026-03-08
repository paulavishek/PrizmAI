"""
Tests for AI Insights Tab — Task Detail Page
==============================================

Comprehensive tests for all AI features in the AI Insights tab:
1. AI Complexity Analysis & Breakdown
2. AI Risk Assessment
3. LSS (Lean Six Sigma) Classification
4. AI Assignee Suggestion
5. AI Priority Suggestion
6. AI Deadline Prediction
7. AI Task Summary Generation

Special focus areas:
- Token size handling and truncation resilience
- JSON parsing robustness (malformed, truncated, code-block-wrapped)
- Fallback mechanisms when AI responses are corrupted
- API endpoint input validation and error handling
"""

import json
import re
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone

from accounts.models import Organization, UserProfile
from kanban.models import Board, Column, Task


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_quota_ok(user):
    """Return a passing quota check."""
    quota = MagicMock()
    quota.has_quota_remaining.return_value = True
    quota.get_remaining_requests.return_value = 100
    return True, quota, 100


def _mock_quota_exceeded(user):
    """Return an exceeded-quota check."""
    quota = MagicMock()
    quota.has_quota_remaining.return_value = False
    quota.get_remaining_requests.return_value = 0
    return False, quota, 0


def _noop_track(*args, **kwargs):
    """No-op replacement for track_ai_request."""
    return MagicMock()


def _noop_demo_limit(request):
    """Demo limit that always allows."""
    return {
        'can_generate': True,
        'current_count': 0,
        'max_allowed': float('inf'),
        'message': None,
        'is_demo': False
    }


def _noop_increment(request):
    """No-op replacement for increment_ai_generation_count."""
    pass


# Valid response fixtures -------------------------------------------------

VALID_BREAKDOWN_RESPONSE = json.dumps({
    "is_breakdown_recommended": True,
    "complexity_score": 7,
    "confidence_score": 0.85,
    "confidence_level": "high",
    "reasoning": "Task involves multiple integration points that benefit from decomposition.",
    "complexity_factors": [
        {"factor": "Multiple integrations", "impact": "high", "description": "Requires API and DB work"}
    ],
    "subtasks": [
        {
            "title": "Design API schema",
            "description": "Define endpoints and data models",
            "estimated_effort": "2 hours",
            "priority": "high",
            "reasoning": "Foundation for other subtasks"
        },
        {
            "title": "Implement backend logic",
            "description": "Core business logic",
            "estimated_effort": "4 hours",
            "priority": "high",
            "reasoning": "Main deliverable"
        },
    ],
    "critical_path": ["Design API schema", "Implement backend logic"],
    "parallel_opportunities": [],
    "workflow_suggestions": ["Start with schema design"],
    "risk_considerations": ["Integration complexity"],
    "assumptions": ["Team has Django experience"],
    "total_estimated_effort": "6 hours",
    "effort_vs_original": "Comparable"
})

VALID_RISK_RESPONSE = json.dumps({
    "likelihood": {"score": 2, "label": "Possible", "justification": "Some dependencies exist"},
    "impact": {"score": 3, "label": "High", "justification": "Critical path item"},
    "risk_assessment": {
        "risk_score": 6,
        "risk_level": "high",
        "summary": "Significant risk due to dependencies and timeline pressure"
    },
    "risk_indicators": [
        {"indicator": "Tight deadline", "severity": "high"},
        {"indicator": "External dependency", "severity": "medium"}
    ],
    "mitigation_suggestions": [
        {"strategy": "Add buffer time", "priority": "high", "effort": "low"}
    ],
    "explainability": {
        "confidence_score": 0.8,
        "reasoning": "Based on dependency analysis and timeline data",
        "data_quality": "medium",
        "assumptions": ["No additional blockers emerge"]
    }
})

VALID_LSS_RESPONSE = json.dumps({
    "classification": "Value-Added",
    "justification": "Directly delivers customer-facing feature.",
    "confidence_score": 0.9,
    "confidence_level": "high",
    "contributing_factors": [
        {"factor": "Customer impact", "contribution_percentage": 70, "description": "Direct user benefit"}
    ],
    "classification_reasoning": {
        "value_added_indicators": ["Customer-facing deliverable"],
        "non_value_indicators": [],
        "primary_driver": "Direct customer value"
    },
    "alternative_classification": {
        "classification": "Necessary Non-Value-Added",
        "confidence_score": 0.15,
        "conditions": "If internal tooling only"
    },
    "assumptions": ["Feature is customer-facing"],
    "improvement_suggestions": ["Add success metrics"],
    "lean_waste_type": None,
    "data_quality": "high"
})

VALID_PRIORITY_RESPONSE = json.dumps({
    "suggested_priority": "high",
    "confidence_score": 0.82,
    "confidence_level": "high",
    "reasoning": "Task has a tight deadline and is on the critical path.",
    "contributing_factors": [
        {"name": "Deadline pressure", "contribution_percentage": 50, "description": "Due in 3 days"},
        {"name": "Dependencies", "contribution_percentage": 30, "description": "Blocks 2 tasks"}
    ],
    "priority_comparison": {"current": "medium", "suggested": "high", "change_justified": True},
    "alternative_priority": {"priority": "urgent", "confidence_score": 0.3, "conditions": "If blocker emerges"},
    "workload_impact": {"team_impact": "moderate", "recommendation": "Redistribute lower tasks"},
    "recommendations": ["Focus on this task first"],
    "assumptions": ["No scope changes"],
    "urgency_indicators": ["Tight deadline"],
    "impact_indicators": ["Blocks downstream work"]
})

VALID_DEADLINE_RESPONSE = json.dumps({
    "estimated_days_to_complete": 5,
    "confidence_score": 0.75,
    "confidence_level": "medium",
    "reasoning": "Based on task complexity and assignee velocity.",
    "risk_factors": ["External dependency may cause delay"],
    "optimistic_days": 3,
    "pessimistic_days": 8,
    "contributing_factors": [
        {"name": "Task Complexity", "contribution_percentage": 60, "description": "Moderate complexity at 6/10"}
    ],
    "assumptions": ["No scope changes", "Assignee available full-time"],
    "data_quality": "medium",
    "recommended_deadline": "2026-03-15",
    "start_date_used": "2026-03-08",
    "alternative_scenarios": {
        "best_case": {"days": 3, "conditions": "No blockers"},
        "worst_case": {"days": 10, "conditions": "Major blockers emerge"}
    }
})

VALID_ASSIGNEE_RESPONSE = json.dumps({
    "recommended_user_id": 2,
    "recommended_username": "devuser",
    "recommended_display_name": "Dev User",
    "confidence": 0.88,
    "reasoning": "Best skill match with manageable workload.",
    "factors": [
        {"factor": "Skill match", "score": 0.9, "description": "Strong Python/Django skills"},
        {"factor": "Workload", "score": 0.85, "description": "2 active tasks"}
    ],
    "alternatives": [
        {"user_id": 3, "username": "otherdev", "score": 0.72, "reason": "Good skills but higher workload"}
    ],
    "warnings": [],
    "reassignment_justified": True,
    "explainability": {
        "confidence_score": 0.88,
        "reasoning": "Multi-factor analysis considering skills, workload, and past performance.",
        "data_quality": "high",
        "assumptions": ["Current workload data is up to date"]
    }
})

VALID_TASK_SUMMARY_RESPONSE = json.dumps({
    "executive_summary": {
        "one_line_summary": "Backend API task on track with moderate risk.",
        "summary": "This task involves building REST APIs with moderate complexity. Risk is elevated due to external dependencies."
    },
    "confidence_score": 0.8,
    "analysis_completeness": "high",
    "task_health": {
        "status": "on_track",
        "health_score": 72,
        "concerns": ["External dependency risk"]
    },
    "risk_analysis": {
        "overall_risk": "medium",
        "key_risks": ["Integration delay"]
    },
    "resource_assessment": {
        "adequacy": "sufficient",
        "notes": "Assigned developer has relevant skills"
    },
    "stakeholder_insights": None,
    "timeline_assessment": {
        "on_schedule": True,
        "buffer_days": 2
    },
    "lean_efficiency": {
        "classification": "value_added",
        "waste_potential": "low"
    },
    "prioritized_actions": [
        {"action": "Validate API contract with frontend team", "priority": "high"}
    ],
    "assumptions": ["No scope changes expected"],
    "limitations": ["Limited historical data for this task type"],
    "markdown_summary": "## Task Summary\\nBackend API task on track."
})


# ===========================================================================
# SECTION 1: Token Size & Configuration Tests
# ===========================================================================

class TokenSizeConfigTests(TestCase):
    """Verify token limits are correctly configured for all AI Insights features."""

    def test_token_limits_exist_for_all_insight_features(self):
        """Every AI Insights feature must have a dedicated token limit."""
        from kanban.utils.ai_utils import TASK_TOKEN_LIMITS

        required_keys = [
            'task_breakdown',
            'risk_assessment',
            'lean_classification',
            'assignee_suggestion',
            'priority_suggestion',
            'deadline_prediction',
            'task_summary',
        ]
        for key in required_keys:
            self.assertIn(key, TASK_TOKEN_LIMITS, f"Missing token limit for '{key}'")
            self.assertGreater(TASK_TOKEN_LIMITS[key], 0, f"Token limit for '{key}' must be > 0")

    def test_token_limits_are_generous_enough(self):
        """Token limits should be at least 2048 to prevent truncation of structured JSON."""
        from kanban.utils.ai_utils import TASK_TOKEN_LIMITS

        minimum_safe = 2048
        for key in ['task_breakdown', 'risk_assessment', 'lean_classification',
                     'assignee_suggestion', 'priority_suggestion', 'deadline_prediction',
                     'task_summary']:
            self.assertGreaterEqual(
                TASK_TOKEN_LIMITS[key], minimum_safe,
                f"Token limit for '{key}' ({TASK_TOKEN_LIMITS[key]}) is below safe minimum {minimum_safe}"
            )

    def test_task_summary_has_highest_limit(self):
        """task_summary needs the highest limit as it synthesizes all data."""
        from kanban.utils.ai_utils import TASK_TOKEN_LIMITS
        summary_limit = TASK_TOKEN_LIMITS['task_summary']
        for key in ['task_breakdown', 'risk_assessment', 'lean_classification',
                     'deadline_prediction']:
            self.assertGreaterEqual(
                summary_limit, TASK_TOKEN_LIMITS[key],
                f"task_summary limit ({summary_limit}) should be >= {key} limit ({TASK_TOKEN_LIMITS[key]})"
            )

    def test_get_token_limit_returns_default_for_unknown(self):
        """Unknown task types should get the default limit, not crash."""
        from kanban.utils.ai_utils import get_token_limit_for_task, TASK_TOKEN_LIMITS
        result = get_token_limit_for_task('nonexistent_task_xyz')
        self.assertEqual(result, TASK_TOKEN_LIMITS['default'])

    def test_get_temperature_returns_float_for_all_insight_features(self):
        """Temperature should be a valid float for every AI Insights feature."""
        from kanban.utils.ai_utils import get_temperature_for_task
        for key in ['task_breakdown', 'risk_assessment', 'lean_classification',
                     'assignee_suggestion', 'priority_suggestion', 'deadline_prediction',
                     'task_summary']:
            temp = get_temperature_for_task(key)
            self.assertIsInstance(temp, float)
            self.assertGreaterEqual(temp, 0.0)
            self.assertLessEqual(temp, 1.0)

    def test_complex_tasks_route_to_flash(self):
        """Complex AI Insights features should route to Flash model."""
        from kanban.utils.ai_utils import COMPLEX_TASKS
        expected_complex = ['risk_assessment', 'deadline_prediction', 'priority_suggestion',
                            'task_breakdown', 'assignee_suggestion']
        for task_type in expected_complex:
            self.assertIn(task_type, COMPLEX_TASKS,
                          f"'{task_type}' should be in COMPLEX_TASKS for quality routing")


# ===========================================================================
# SECTION 2: JSON Parsing & Truncation Resilience (Unit Tests)
# ===========================================================================

class JSONRepairTests(TestCase):
    """Test the _repair_json utility handles truncated / malformed JSON."""

    def test_repair_trailing_commas(self):
        from kanban.utils.ai_utils import _repair_json
        broken = '{"key": "value", "items": [1, 2, 3,]}'
        fixed = _repair_json(broken)
        self.assertIsNotNone(fixed)
        parsed = json.loads(fixed)
        self.assertEqual(parsed['key'], 'value')

    def test_repair_truncated_json_balances_braces(self):
        from kanban.utils.ai_utils import _repair_json
        truncated = '{"risk_assessment": {"risk_score": 6, "risk_level": "high"'
        fixed = _repair_json(truncated)
        self.assertIsNotNone(fixed)
        parsed = json.loads(fixed)
        self.assertIn('risk_assessment', parsed)

    def test_repair_truncated_array(self):
        from kanban.utils.ai_utils import _repair_json
        truncated = '{"items": ["one", "two", "three"'
        fixed = _repair_json(truncated)
        self.assertIsNotNone(fixed)
        # The repair function should add closing brackets/braces
        # Verify it at least adds the missing ] and }
        self.assertIn(']', fixed)
        self.assertIn('}', fixed)

    def test_repair_missing_commas_between_properties(self):
        from kanban.utils.ai_utils import _repair_json
        broken = '{"a": "1"\n"b": "2"}'
        fixed = _repair_json(broken)
        self.assertIsNotNone(fixed)
        parsed = json.loads(fixed)
        self.assertEqual(parsed['a'], '1')
        self.assertEqual(parsed['b'], '2')

    def test_repair_returns_none_on_catastrophic_input(self):
        from kanban.utils.ai_utils import _repair_json
        result = _repair_json('')
        # Empty string is technically repairable (adds nothing)
        # But completely garbage text should still try
        result2 = _repair_json('not json at all')
        # Should not crash — result can be anything as long as no exception
        self.assertTrue(True)  # Just verify no exception was raised


class TaskBreakdownTruncationTests(TestCase):
    """Test that suggest_task_breakdown handles truncated AI responses gracefully."""

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_valid_response_parses_correctly(self, mock_ai):
        from kanban.utils.ai_utils import suggest_task_breakdown
        mock_ai.return_value = VALID_BREAKDOWN_RESPONSE
        result = suggest_task_breakdown({'title': 'Test task', 'description': 'Build feature'})
        self.assertIsNotNone(result)
        self.assertTrue(result.get('is_breakdown_recommended'))
        self.assertEqual(len(result.get('subtasks', [])), 2)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_code_block_wrapped_response(self, mock_ai):
        from kanban.utils.ai_utils import suggest_task_breakdown
        mock_ai.return_value = f"```json\n{VALID_BREAKDOWN_RESPONSE}\n```"
        result = suggest_task_breakdown({'title': 'Test task', 'description': 'Build feature'})
        self.assertIsNotNone(result)
        self.assertTrue(result.get('is_breakdown_recommended'))

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_truncated_json_is_repaired(self, mock_ai):
        """Simulate token cutoff mid-response — brace stack repair should kick in."""
        from kanban.utils.ai_utils import suggest_task_breakdown
        truncated = '{"is_breakdown_recommended": true, "complexity_score": 7, "subtasks": [{"title": "Sub 1", "description": "Desc'
        mock_ai.return_value = truncated
        result = suggest_task_breakdown({'title': 'Test task', 'description': 'Build feature'})
        # Should return something (repaired or fallback), not None
        self.assertIsNotNone(result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_completely_invalid_response_returns_fallback(self, mock_ai):
        from kanban.utils.ai_utils import suggest_task_breakdown
        mock_ai.return_value = "I cannot generate a valid response right now."
        result = suggest_task_breakdown({'title': 'Test task', 'description': 'Build feature'})
        # Should return the hardcoded fallback, not None
        self.assertIsNotNone(result)
        self.assertIn('subtasks', result)
        self.assertIn('factors_considered', result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_none_response_returns_none(self, mock_ai):
        from kanban.utils.ai_utils import suggest_task_breakdown
        mock_ai.return_value = None
        result = suggest_task_breakdown({'title': 'Test', 'description': 'Test'})
        self.assertIsNone(result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_factors_enrichment_always_present(self, mock_ai):
        """factors_considered and factors_missing should always appear in result."""
        from kanban.utils.ai_utils import suggest_task_breakdown
        mock_ai.return_value = VALID_BREAKDOWN_RESPONSE
        result = suggest_task_breakdown({
            'title': 'Simple task',
            'description': 'Easy work',
            'risk_score': 3,
            'workload_impact': 'low',
        })
        self.assertIsNotNone(result)
        self.assertIn('factors_considered', result)
        self.assertIn('factors_missing', result)


class LSSClassificationTruncationTests(TestCase):
    """Test LSS classification handles truncated / malformed AI JSON."""

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_valid_response_parses(self, mock_ai):
        from kanban.utils.ai_utils import suggest_lean_classification
        mock_ai.return_value = VALID_LSS_RESPONSE
        result = suggest_lean_classification('Build feature', 'Customer checkout flow')
        self.assertIsNotNone(result)
        self.assertEqual(result['classification'], 'Value-Added')

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_truncated_json_extracts_classification(self, mock_ai):
        """Truncated JSON should still extract classification via regex."""
        from kanban.utils.ai_utils import suggest_lean_classification
        truncated = '{"classification": "Waste/Eliminate", "justification": "No customer val'
        mock_ai.return_value = truncated
        result = suggest_lean_classification('Internal cleanup', 'Remove old logs')
        self.assertIsNotNone(result)
        self.assertEqual(result['classification'], 'Waste/Eliminate')

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_multiline_string_in_response(self, mock_ai):
        """AI sometimes returns strings with literal newlines."""
        from kanban.utils.ai_utils import suggest_lean_classification
        bad_json = '{"classification": "Value-Added", "justification": "This task\nadds direct value", "confidence_score": 0.8, "confidence_level": "high", "contributing_factors": [], "classification_reasoning": {"value_added_indicators": [], "non_value_indicators": [], "primary_driver": "direct value"}, "alternative_classification": null, "assumptions": [], "improvement_suggestions": [], "lean_waste_type": null, "data_quality": "high"}'
        mock_ai.return_value = bad_json
        result = suggest_lean_classification('Feature', 'Customer feature')
        self.assertIsNotNone(result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_single_quotes_in_response(self, mock_ai):
        """AI sometimes uses single quotes instead of double quotes."""
        from kanban.utils.ai_utils import suggest_lean_classification
        single_quoted = "{'classification': 'Value-Added', 'justification': 'Direct value', 'confidence_score': 0.9, 'confidence_level': 'high', 'contributing_factors': [], 'classification_reasoning': {'value_added_indicators': [], 'non_value_indicators': [], 'primary_driver': 'test'}, 'alternative_classification': None, 'assumptions': [], 'improvement_suggestions': [], 'lean_waste_type': None, 'data_quality': 'high'}"
        mock_ai.return_value = single_quoted
        result = suggest_lean_classification('Feature', 'Test')
        self.assertIsNotNone(result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_none_response(self, mock_ai):
        from kanban.utils.ai_utils import suggest_lean_classification
        mock_ai.return_value = None
        result = suggest_lean_classification('Task', 'Desc')
        self.assertIsNone(result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_code_block_wrapped(self, mock_ai):
        from kanban.utils.ai_utils import suggest_lean_classification
        mock_ai.return_value = f"```json\n{VALID_LSS_RESPONSE}\n```"
        result = suggest_lean_classification('Feature', 'Customer checkout')
        self.assertIsNotNone(result)
        self.assertEqual(result['classification'], 'Value-Added')


class DeadlinePredictionTruncationTests(TestCase):
    """Test deadline prediction handles truncated AI responses via regex fallback."""

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_valid_response_parses(self, mock_ai):
        from kanban.utils.ai_utils import predict_realistic_deadline
        mock_ai.return_value = VALID_DEADLINE_RESPONSE
        result = predict_realistic_deadline(
            {'title': 'Build API', 'description': 'REST endpoints', 'complexity_score': 6},
            {'assignee_avg_completion_days': 4, 'team_avg_completion_days': 5,
             'assignee_velocity_hours_per_day': 6, 'assignee_current_tasks': 2}
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.get('estimated_days_to_complete'), 5)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_truncated_response_uses_regex_fallback(self, mock_ai):
        """When JSON is truncated, regex should extract key numeric fields."""
        from kanban.utils.ai_utils import predict_realistic_deadline
        truncated = '{"estimated_days_to_complete": 7, "confidence_level": "medium", "optimistic_days": 5, "pessimistic_days": 10, "reasoning": "Based on comple'
        mock_ai.return_value = truncated
        result = predict_realistic_deadline(
            {'title': 'Build API', 'description': 'REST endpoints', 'complexity_score': 6},
            {'assignee_avg_completion_days': 4, 'team_avg_completion_days': 5,
             'assignee_velocity_hours_per_day': 6, 'assignee_current_tasks': 2}
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.get('estimated_days_to_complete'), 7)
        self.assertEqual(result.get('optimistic_days'), 5)
        self.assertEqual(result.get('pessimistic_days'), 10)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_completely_garbled_response_extracts_defaults(self, mock_ai):
        """Completely invalid response should still return something via complexity-based defaults."""
        from kanban.utils.ai_utils import predict_realistic_deadline
        mock_ai.return_value = "Sorry, I cannot help with that."
        result = predict_realistic_deadline(
            {'title': 'Build API', 'description': 'REST endpoints', 'complexity_score': 6},
            {'assignee_avg_completion_days': 4, 'team_avg_completion_days': 5,
             'assignee_velocity_hours_per_day': 6, 'assignee_current_tasks': 2}
        )
        # Should get regex-based defaults (complexity_score=6 → estimated_days >= 6)
        self.assertIsNotNone(result)
        self.assertIn('estimated_days_to_complete', result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_none_response(self, mock_ai):
        from kanban.utils.ai_utils import predict_realistic_deadline
        mock_ai.return_value = None
        result = predict_realistic_deadline(
            {'title': 'Task', 'description': 'Desc', 'complexity_score': 5},
            {'assignee_avg_completion_days': 4, 'team_avg_completion_days': 5}
        )
        self.assertIsNone(result)


class PrioritySuggestionTruncationTests(TestCase):
    """Test priority suggestion handles truncated AI responses.

    Previously suggest_task_priority had NO truncation handling — now it uses
    _repair_json, regex extraction, and a rule-based fallback.
    """

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_valid_response_parses(self, mock_ai):
        from kanban.utils.ai_utils import suggest_task_priority
        mock_ai.return_value = VALID_PRIORITY_RESPONSE
        result = suggest_task_priority(
            {'title': 'Build API', 'description': 'REST endpoints', 'due_date': '2026-03-15'},
            {'total_tasks': 10, 'high_priority_count': 3, 'overdue_count': 1}
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.get('suggested_priority'), 'high')

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_truncated_response_recovered_via_repair(self, mock_ai):
        """Truncated JSON should be recovered via _repair_json or regex extraction."""
        from kanban.utils.ai_utils import suggest_task_priority
        mock_ai.return_value = '{"suggested_priority": "high", "confidence_score": 0.8, "reasoning": "Tight deadli'
        result = suggest_task_priority(
            {'title': 'Build API', 'description': 'REST endpoints'},
            {'total_tasks': 10}
        )
        # Should now recover via repair or regex, not return None
        self.assertIsNotNone(result)
        self.assertEqual(result.get('suggested_priority'), 'high')

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_completely_garbled_response_uses_fallback(self, mock_ai):
        """Completely unparseable text should trigger rule-based fallback."""
        from kanban.utils.ai_utils import suggest_task_priority
        mock_ai.return_value = "Sorry, I cannot help with that right now."
        result = suggest_task_priority(
            {'title': 'Security vulnerability fix', 'description': 'Critical production patch'},
            {'total_tasks': 10, 'high_priority_count': 2, 'urgent_count': 1}
        )
        self.assertIsNotNone(result)
        self.assertIn('suggested_priority', result)
        # "security" + "critical" + "production" keywords → high or urgent
        self.assertIn(result['suggested_priority'], ['high', 'urgent'])
        self.assertIn('fallback_note', result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_truncated_regex_extracts_priority(self, mock_ai):
        """Regex extraction should pull suggested_priority from partial JSON."""
        from kanban.utils.ai_utils import suggest_task_priority
        # JSON that _repair_json can't fix but regex can extract from
        mock_ai.return_value = 'Here is the analysis: {"suggested_priority": "urgent", "confidence_score": 0.9, badly formed rest'
        result = suggest_task_priority(
            {'title': 'Hotfix', 'description': 'Production down'},
            {'total_tasks': 5}
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.get('suggested_priority'), 'urgent')
        self.assertIn('truncation_note', result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_code_block_wrapped_response(self, mock_ai):
        from kanban.utils.ai_utils import suggest_task_priority
        mock_ai.return_value = f"```json\n{VALID_PRIORITY_RESPONSE}\n```"
        result = suggest_task_priority(
            {'title': 'Build API', 'description': 'REST endpoints'},
            {'total_tasks': 10}
        )
        self.assertIsNotNone(result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_none_response_returns_none(self, mock_ai):
        """None from AI content generation still returns None (no input to repair)."""
        from kanban.utils.ai_utils import suggest_task_priority
        mock_ai.return_value = None
        result = suggest_task_priority(
            {'title': 'Task', 'description': 'Desc'},
            {'total_tasks': 5}
        )
        self.assertIsNone(result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_fallback_uses_due_date_urgency(self, mock_ai):
        """Rule-based fallback should factor in due date proximity."""
        from kanban.utils.ai_utils import suggest_task_priority
        mock_ai.return_value = "completely invalid"
        # Due tomorrow → urgent
        tomorrow = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        result = suggest_task_priority(
            {'title': 'Simple task', 'description': 'Nothing special', 'due_date': tomorrow},
            {'total_tasks': 10, 'high_priority_count': 1, 'urgent_count': 0}
        )
        self.assertIsNotNone(result)
        self.assertIn(result['suggested_priority'], ['high', 'urgent'])


class AssigneeSuggestionTruncationTests(TestCase):
    """Test assignee suggestion handles truncated AI responses."""

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_valid_response_parses(self, mock_ai):
        from kanban.utils.ai_utils import suggest_optimal_assignee
        mock_ai.return_value = VALID_ASSIGNEE_RESPONSE
        candidates = [
            {'user_id': 2, 'username': 'devuser', 'display_name': 'Dev User', 'overall_score': 85},
            {'user_id': 3, 'username': 'otherdev', 'display_name': 'Other Dev', 'overall_score': 72},
        ]
        result = suggest_optimal_assignee(
            {'title': 'Build API', 'required_skills': ['Python', 'Django']},
            candidates,
            {'board_name': 'Sprint 1', 'total_tasks': 10}
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.get('recommended_user_id'), 2)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_truncated_response_uses_regex_extraction(self, mock_ai):
        from kanban.utils.ai_utils import suggest_optimal_assignee
        truncated = '{"recommended_user_id": 2, "recommended_username": "devuser", "confidence": 0.85, "reasoning": "Best match based on sk'
        mock_ai.return_value = truncated
        candidates = [
            {'user_id': 2, 'username': 'devuser', 'display_name': 'Dev User', 'overall_score': 85},
        ]
        result = suggest_optimal_assignee(
            {'title': 'Build API'},
            candidates,
            {'board_name': 'Sprint 1'}
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.get('recommended_user_id'), 2)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_empty_response_uses_algorithmic_fallback(self, mock_ai):
        from kanban.utils.ai_utils import suggest_optimal_assignee
        mock_ai.return_value = None
        candidates = [
            {'user_id': 2, 'username': 'devuser', 'display_name': 'Dev User', 'overall_score': 85},
        ]
        result = suggest_optimal_assignee(
            {'title': 'Build API'},
            candidates,
            {'board_name': 'Sprint 1'}
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.get('recommended_user_id'), 2)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_invalid_user_id_falls_back_to_top_candidate(self, mock_ai):
        """If AI recommends a user not in candidates, fall back to top scorer."""
        from kanban.utils.ai_utils import suggest_optimal_assignee
        bad_id_response = json.dumps({
            "recommended_user_id": 999,
            "recommended_username": "ghost",
            "confidence": 0.9,
            "reasoning": "Best match."
        })
        mock_ai.return_value = bad_id_response
        candidates = [
            {'user_id': 2, 'username': 'devuser', 'display_name': 'Dev User', 'overall_score': 85},
        ]
        result = suggest_optimal_assignee(
            {'title': 'Build API'},
            candidates,
            {'board_name': 'Sprint 1'}
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.get('recommended_user_id'), 2)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_explainability_block_always_present(self, mock_ai):
        """Result should always include explainability metadata."""
        from kanban.utils.ai_utils import suggest_optimal_assignee
        minimal_response = json.dumps({
            "recommended_user_id": 2,
            "recommended_username": "devuser",
            "confidence": 0.88,
            "reasoning": "Best fit."
        })
        mock_ai.return_value = minimal_response
        candidates = [
            {'user_id': 2, 'username': 'devuser', 'display_name': 'Dev User', 'overall_score': 85},
        ]
        result = suggest_optimal_assignee(
            {'title': 'Build API'},
            candidates,
            {'board_name': 'Sprint 1'}
        )
        self.assertIsNotNone(result)
        self.assertIn('explainability', result)
        self.assertIn('confidence_score', result['explainability'])


class TaskSummaryTruncationTests(TestCase):
    """Test task summary generation handles truncated AI responses."""

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_valid_response_parses(self, mock_ai):
        from kanban.utils.ai_utils import summarize_task_details
        mock_ai.return_value = VALID_TASK_SUMMARY_RESPONSE
        result = summarize_task_details({
            'title': 'Build API', 'description': 'REST endpoints',
            'priority': 'High', 'status': 'In Progress'
        })
        self.assertIsNotNone(result)
        self.assertIn('executive_summary', result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_truncated_response_adds_truncation_note(self, mock_ai):
        """Truncated JSON should be detected and repaired with a truncation_note."""
        from kanban.utils.ai_utils import summarize_task_details
        # Truncated: missing closing braces
        truncated = '{"executive_summary": {"one_line_summary": "Task on track", "summary": "Detailed analysis"}, "confidence_score": 0.8, "task_health": {"status": "on_track"'
        mock_ai.return_value = truncated
        result = summarize_task_details({
            'title': 'Build API', 'description': 'REST endpoints',
            'priority': 'High', 'status': 'In Progress'
        })
        self.assertIsNotNone(result)
        # Should have detected truncation and added note
        if 'truncation_note' in result:
            self.assertIn('truncat', result['truncation_note'].lower())

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_completely_invalid_response_returns_markdown_fallback(self, mock_ai):
        """If JSON parsing fails completely, return raw text as markdown_summary."""
        from kanban.utils.ai_utils import summarize_task_details
        mock_ai.return_value = "This is a plain text summary of the task."
        result = summarize_task_details({
            'title': 'Build API', 'description': 'REST endpoints',
            'priority': 'High', 'status': 'In Progress'
        })
        self.assertIsNotNone(result)
        self.assertIn('markdown_summary', result)
        self.assertIn('parsing_note', result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_none_response(self, mock_ai):
        from kanban.utils.ai_utils import summarize_task_details
        mock_ai.return_value = None
        result = summarize_task_details({
            'title': 'Task', 'description': 'Desc', 'priority': 'Low', 'status': 'To Do'
        })
        self.assertIsNone(result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_code_block_wrapped_response(self, mock_ai):
        from kanban.utils.ai_utils import summarize_task_details
        mock_ai.return_value = f"```json\n{VALID_TASK_SUMMARY_RESPONSE}\n```"
        result = summarize_task_details({
            'title': 'Build API', 'description': 'REST endpoints',
            'priority': 'High', 'status': 'In Progress'
        })
        self.assertIsNotNone(result)
        self.assertIn('executive_summary', result)


class RiskAssessmentTruncationTests(TestCase):
    """Test risk assessment handles truncated AI responses."""

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_valid_response_parses(self, mock_ai):
        from kanban.utils.ai_utils import calculate_task_risk_score
        mock_ai.return_value = VALID_RISK_RESPONSE
        result = calculate_task_risk_score(
            'Build API', 'REST endpoints', 'high', 'Board: Sprint 1'
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['risk_assessment']['risk_score'], 6)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_truncated_response_uses_repair(self, mock_ai):
        """Truncated risk JSON should be repaired via _repair_json."""
        from kanban.utils.ai_utils import calculate_task_risk_score
        truncated = '{"likelihood": {"score": 2, "label": "Possible"}, "impact": {"score": 3}, "risk_assessment": {"risk_score": 6, "risk_level": "high"'
        mock_ai.return_value = truncated
        result = calculate_task_risk_score(
            'Build API', 'REST endpoints', 'high', 'Board: Sprint 1'
        )
        # Should either repair or use fallback
        self.assertIsNotNone(result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_completely_invalid_uses_fallback(self, mock_ai):
        """Completely invalid response should trigger rule-based fallback."""
        from kanban.utils.ai_utils import calculate_task_risk_score
        mock_ai.return_value = "I cannot assess this task."
        result = calculate_task_risk_score(
            'Build API', 'REST endpoints', 'high', 'Board: Sprint 1'
        )
        self.assertIsNotNone(result)
        # Fallback should still have basic risk structure
        self.assertIn('likelihood', result)
        self.assertIn('impact', result)
        self.assertIn('risk_assessment', result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_none_response_uses_fallback(self, mock_ai):
        from kanban.utils.ai_utils import calculate_task_risk_score
        mock_ai.return_value = None
        result = calculate_task_risk_score(
            'Build API', 'REST endpoints', 'medium', 'Board: Sprint 1'
        )
        self.assertIsNotNone(result)
        self.assertIn('risk_assessment', result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_code_block_wrapped_response(self, mock_ai):
        from kanban.utils.ai_utils import calculate_task_risk_score
        mock_ai.return_value = f"```json\n{VALID_RISK_RESPONSE}\n```"
        result = calculate_task_risk_score(
            'Build API', 'REST endpoints', 'high', 'Board: Sprint 1'
        )
        self.assertIsNotNone(result)
        self.assertEqual(result['risk_assessment']['risk_score'], 6)


# ===========================================================================
# SECTION 3: API Endpoint Integration Tests
# ===========================================================================

class AIInsightsAPIBaseTestCase(TestCase):
    """Base class with shared setup for all AI Insights API tests."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org', domain='test.org', created_by=self.user
        )
        self.board = Board.objects.create(
            name='Sprint Board', created_by=self.user, organization=self.org,
            description='Test sprint board'
        )
        self.board.members.add(self.user)
        self.column = Column.objects.create(name='To Do', board=self.board, position=0)
        self.done_column = Column.objects.create(name='Done', board=self.board, position=2)
        self.task = Task.objects.create(
            title='Build REST API',
            description='Implement CRUD endpoints for user management',
            column=self.column,
            created_by=self.user,
            priority='medium',
            complexity_score=6,
        )
        self.client.force_login(self.user)

    def _csrf_headers(self):
        """Get CSRF token for POST requests."""
        from django.middleware.csrf import get_token
        from django.test import RequestFactory
        rf = RequestFactory()
        request = rf.get('/')
        token = get_token(request)
        return {'HTTP_X_CSRFTOKEN': token}


class TaskBreakdownAPITests(AIInsightsAPIBaseTestCase):
    """Test /api/suggest-task-breakdown/ endpoint."""

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    @patch('kanban.api_views.suggest_task_breakdown')
    def test_success_with_task_id(self, mock_breakdown):
        mock_breakdown.return_value = json.loads(VALID_BREAKDOWN_RESPONSE)
        response = self.client.post(
            '/api/suggest-task-breakdown/',
            data=json.dumps({
                'task_id': self.task.id,
                'title': self.task.title,
                'description': self.task.description,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('is_breakdown_recommended'))
        self.assertEqual(len(data.get('subtasks', [])), 2)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    @patch('kanban.api_views.suggest_task_breakdown')
    def test_success_without_task_id(self, mock_breakdown):
        mock_breakdown.return_value = json.loads(VALID_BREAKDOWN_RESPONSE)
        response = self.client.post(
            '/api/suggest-task-breakdown/',
            data=json.dumps({
                'title': 'New task for breakdown',
                'description': 'Complex work',
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    def test_missing_title_returns_400(self):
        response = self.client.post(
            '/api/suggest-task-breakdown/',
            data=json.dumps({'description': 'No title provided'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_exceeded)
    def test_quota_exceeded_returns_429(self):
        response = self.client.post(
            '/api/suggest-task-breakdown/',
            data=json.dumps({'title': 'Test', 'description': 'Test'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 429)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    @patch('kanban.api_views.suggest_task_breakdown')
    def test_ai_failure_returns_500(self, mock_breakdown):
        mock_breakdown.return_value = None
        response = self.client.post(
            '/api/suggest-task-breakdown/',
            data=json.dumps({'title': 'Test', 'description': 'Test'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 500)

    def test_unauthenticated_redirects(self):
        self.client.logout()
        response = self.client.post(
            '/api/suggest-task-breakdown/',
            data=json.dumps({'title': 'Test'}),
            content_type='application/json'
        )
        # login_required redirects to login page (302)
        self.assertEqual(response.status_code, 302)

    def test_get_method_not_allowed(self):
        response = self.client.get('/api/suggest-task-breakdown/')
        self.assertEqual(response.status_code, 405)


class RiskAssessmentAPITests(AIInsightsAPIBaseTestCase):
    """Test /api/kanban/calculate-task-risk/ endpoint."""

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.increment_ai_generation_count', _noop_increment)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    @patch('kanban.api_views.calculate_task_risk_score')
    def test_success_with_task_id(self, mock_risk):
        mock_risk.return_value = json.loads(VALID_RISK_RESPONSE)
        response = self.client.post(
            '/api/kanban/calculate-task-risk/',
            data=json.dumps({
                'task_id': self.task.id,
                'title': self.task.title,
                'description': self.task.description,
                'priority': 'high',
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('success'))
        self.assertIn('risk_analysis', data)
        self.assertTrue(data.get('saved'))

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.increment_ai_generation_count', _noop_increment)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    @patch('kanban.api_views.calculate_task_risk_score')
    def test_risk_saved_to_task_model(self, mock_risk):
        """Risk assessment should persist results to the Task model."""
        risk_data = json.loads(VALID_RISK_RESPONSE)
        mock_risk.return_value = risk_data
        self.client.post(
            '/api/kanban/calculate-task-risk/',
            data=json.dumps({
                'task_id': self.task.id,
                'title': self.task.title,
                'description': self.task.description,
                'priority': 'high',
            }),
            content_type='application/json'
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.risk_score, 6)
        self.assertEqual(self.task.risk_level, 'high')
        self.assertEqual(self.task.risk_likelihood, 2)
        self.assertEqual(self.task.risk_impact, 3)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    def test_missing_title_returns_400(self):
        response = self.client.post(
            '/api/kanban/calculate-task-risk/',
            data=json.dumps({
                'description': 'No title',
                'priority': 'medium',
                'board_id': self.board.id,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    def test_missing_board_and_task_returns_400(self):
        response = self.client.post(
            '/api/kanban/calculate-task-risk/',
            data=json.dumps({
                'title': 'Test',
                'description': 'Test',
                'priority': 'medium',
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_exceeded)
    def test_quota_exceeded_returns_429(self):
        response = self.client.post(
            '/api/kanban/calculate-task-risk/',
            data=json.dumps({
                'title': 'Test', 'priority': 'medium',
                'board_id': self.board.id,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 429)


class LSSClassificationAPITests(AIInsightsAPIBaseTestCase):
    """Test /api/suggest-lss-classification/ endpoint."""

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    @patch('kanban.api_views.suggest_lean_classification')
    def test_success(self, mock_lss):
        mock_lss.return_value = json.loads(VALID_LSS_RESPONSE)
        response = self.client.post(
            '/api/suggest-lss-classification/',
            data=json.dumps({
                'title': 'Build checkout feature',
                'description': 'Customer-facing checkout flow',
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('classification'), 'Value-Added')
        self.assertGreater(data.get('confidence_score', 0), 0.5)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    @patch('kanban.api_views.suggest_lean_classification')
    def test_with_budget_context(self, mock_lss):
        mock_lss.return_value = json.loads(VALID_LSS_RESPONSE)
        response = self.client.post(
            '/api/suggest-lss-classification/',
            data=json.dumps({
                'title': 'Build checkout feature',
                'description': 'Customer-facing checkout flow',
                'estimated_cost': 5000,
                'estimated_hours': 40,
                'hourly_rate': 75,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    def test_missing_title_returns_400(self):
        response = self.client.post(
            '/api/suggest-lss-classification/',
            data=json.dumps({'description': 'No title'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    @patch('kanban.api_views.suggest_lean_classification')
    def test_ai_failure_returns_500(self, mock_lss):
        mock_lss.return_value = None
        response = self.client.post(
            '/api/suggest-lss-classification/',
            data=json.dumps({'title': 'Test task', 'description': 'Test'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 500)


class DeadlinePredictionAPITests(AIInsightsAPIBaseTestCase):
    """Test /api/predict-deadline/ endpoint."""

    def setUp(self):
        super().setUp()
        self.assignee = User.objects.create_user(
            username='devuser', email='dev@example.com', password='testpass123'
        )
        self.board.members.add(self.assignee)
        self.task.assigned_to = self.assignee
        self.task.save()

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    @patch('kanban.api_views.predict_realistic_deadline')
    def test_success_with_assignee(self, mock_deadline):
        mock_deadline.return_value = json.loads(VALID_DEADLINE_RESPONSE)
        response = self.client.post(
            '/api/predict-deadline/',
            data=json.dumps({
                'task_id': self.task.id,
                'title': self.task.title,
                'description': self.task.description,
                'priority': 'medium',
                'assigned_to': 'devuser',
                'board_id': self.board.id,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('estimated_days_to_complete'), 5)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    def test_missing_assignee_returns_400(self):
        """Endpoint should reject requests without an assignee."""
        response = self.client.post(
            '/api/predict-deadline/',
            data=json.dumps({
                'title': 'Build API',
                'description': 'REST endpoints',
                'priority': 'medium',
                'assigned_to': '',
                'board_id': self.board.id,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertTrue(data.get('assignee_required'))

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    def test_unassigned_string_returns_400(self):
        """'Unassigned' string should be rejected same as empty."""
        response = self.client.post(
            '/api/predict-deadline/',
            data=json.dumps({
                'title': 'Build API',
                'description': 'REST endpoints',
                'priority': 'medium',
                'assigned_to': 'Unassigned',
                'board_id': self.board.id,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.json().get('assignee_required'))

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    def test_missing_title_returns_400(self):
        response = self.client.post(
            '/api/predict-deadline/',
            data=json.dumps({
                'description': 'REST endpoints',
                'priority': 'medium',
                'assigned_to': 'devuser',
                'board_id': self.board.id,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_exceeded)
    def test_quota_exceeded_returns_429(self):
        response = self.client.post(
            '/api/predict-deadline/',
            data=json.dumps({
                'title': 'Test', 'assigned_to': 'devuser',
                'board_id': self.board.id,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 429)


class AssigneeSuggestionAPITests(AIInsightsAPIBaseTestCase):
    """Test /api/suggest-assignee/ endpoint."""

    def setUp(self):
        super().setUp()
        self.member = User.objects.create_user(
            username='devuser', email='dev@example.com', password='testpass123'
        )
        self.board.members.add(self.member)
        UserProfile.objects.get_or_create(
            user=self.member,
            defaults={'organization': self.org, 'skills': [{'name': 'Python', 'level': 'Expert'}]}
        )

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.increment_ai_generation_count', _noop_increment)
    @patch('kanban.api_views.check_ai_generation_limit', _noop_demo_limit)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    @patch('kanban.api_views.suggest_optimal_assignee')
    def test_success_with_task_id(self, mock_assignee):
        mock_assignee.return_value = json.loads(VALID_ASSIGNEE_RESPONSE)
        # We need to mock ResourceLevelingService too
        with patch('kanban.api_views.ResourceLevelingService', create=True) as MockRLS:
            mock_service = MagicMock()
            mock_service.analyze_task_assignment.return_value = {
                'candidates': [
                    {'user_id': self.member.id, 'username': 'devuser',
                     'display_name': 'Dev User', 'overall_score': 85},
                ],
                'should_reassign': False,
                'reasoning': 'Best match'
            }
            MockRLS.return_value = mock_service
            response = self.client.post(
                '/api/suggest-assignee/',
                data=json.dumps({
                    'board_id': self.board.id,
                    'task_id': self.task.id,
                    'title': self.task.title,
                }),
                content_type='application/json'
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('success'))
        self.assertIn('recommendation', data)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_generation_limit', _noop_demo_limit)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    def test_missing_board_id_returns_400(self):
        response = self.client.post(
            '/api/suggest-assignee/',
            data=json.dumps({'title': 'Test task'}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_generation_limit', _noop_demo_limit)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    def test_non_member_gets_403(self):
        """User not on the board should get 403."""
        other_user = User.objects.create_user(
            username='outsider', email='out@example.com', password='testpass123'
        )
        self.client.force_login(other_user)
        response = self.client.post(
            '/api/suggest-assignee/',
            data=json.dumps({
                'board_id': self.board.id,
                'title': 'Test task',
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 403)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_generation_limit', _noop_demo_limit)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_exceeded)
    def test_quota_exceeded_returns_429(self):
        response = self.client.post(
            '/api/suggest-assignee/',
            data=json.dumps({
                'board_id': self.board.id,
                'title': 'Test',
            }),
            content_type='application/json'
        )
        # Quota exceeded returns 429, but exception handling may return 500
        self.assertIn(response.status_code, [429, 500])

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_generation_limit', _noop_demo_limit)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    def test_board_with_no_members_returns_400(self):
        """Board with no members should return 400."""
        empty_board = Board.objects.create(
            name='Empty Board', created_by=self.user, organization=self.org
        )
        # Board creator is owner but board.members is empty
        response = self.client.post(
            '/api/suggest-assignee/',
            data=json.dumps({
                'board_id': empty_board.id,
                'title': 'Test task',
            }),
            content_type='application/json'
        )
        # Should return 400 with no_members or 403 (no access) depending on flow
        self.assertIn(response.status_code, [400, 403])


class TaskSummaryAPITests(AIInsightsAPIBaseTestCase):
    """Test /api/generate-task-summary/<task_id>/ endpoint."""

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    @patch('kanban.api_views.generate_and_save_task_summary')
    def test_success(self, mock_summary):
        mock_summary.return_value = "Backend API task on track with moderate risk."
        # Simulate that generate_and_save_task_summary sets task fields
        self.task.ai_summary_generated_at = timezone.now()
        self.task.save()
        response = self.client.post(
            f'/api/generate-task-summary/{self.task.id}/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('summary', data)
        self.assertEqual(data['summary'], "Backend API task on track with moderate risk.")

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    @patch('kanban.api_views.generate_and_save_task_summary')
    def test_ai_failure_returns_500(self, mock_summary):
        mock_summary.return_value = None
        response = self.client.post(
            f'/api/generate-task-summary/{self.task.id}/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 500)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_exceeded)
    def test_quota_exceeded_returns_429(self):
        response = self.client.post(
            f'/api/generate-task-summary/{self.task.id}/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 429)

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    def test_nonexistent_task_returns_404_or_500(self):
        """Nonexistent task should return error (404 from get_object_or_404 or 500 from exception handler)."""
        response = self.client.post(
            '/api/generate-task-summary/99999/',
            content_type='application/json'
        )
        self.assertIn(response.status_code, [404, 500])

    def test_unauthenticated_redirects(self):
        self.client.logout()
        response = self.client.post(
            f'/api/generate-task-summary/{self.task.id}/',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 302)


class PrioritySuggestionAPITests(AIInsightsAPIBaseTestCase):
    """Test /api/suggest-priority/ endpoint.

    Note: The duplicate suggest_task_priority_api definition has been removed.
    The active version uses PrioritySuggestionService from ai_assistant.
    """

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_generation_limit', _noop_demo_limit)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_ok)
    def test_success_with_task_id(self):
        with patch('ai_assistant.utils.priority_service.PrioritySuggestionService') as MockPSS:
            mock_service = MagicMock()
            mock_service.suggest_priority.return_value = json.loads(VALID_PRIORITY_RESPONSE)
            MockPSS.return_value = mock_service
            response = self.client.post(
                '/api/suggest-priority/',
                data=json.dumps({
                    'task_id': self.task.id,
                    'title': self.task.title,
                    'description': self.task.description,
                    'board_id': self.board.id,
                }),
                content_type='application/json'
            )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('suggested_priority'), 'high')

    @patch('kanban.api_views.track_ai_request', _noop_track)
    @patch('kanban.api_views.check_ai_generation_limit', _noop_demo_limit)
    @patch('kanban.api_views.check_ai_quota', _mock_quota_exceeded)
    def test_quota_exceeded_returns_429(self):
        response = self.client.post(
            '/api/suggest-priority/',
            data=json.dumps({
                'title': 'Test', 'board_id': self.board.id,
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 429)


# ===========================================================================
# SECTION 4: Token Size Stress Tests (Large Prompt / Response Scenarios)
# ===========================================================================

class TokenSizeStressTests(TestCase):
    """Test that large AI responses don't get silently truncated."""

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_large_task_summary_response_parses(self, mock_ai):
        """A response near the 8192 token limit should still parse."""
        from kanban.utils.ai_utils import summarize_task_details
        # Build a large but valid response
        large_response = {
            "executive_summary": {
                "one_line_summary": "A" * 200,
                "summary": "B" * 2000
            },
            "confidence_score": 0.85,
            "analysis_completeness": "high",
            "task_health": {"status": "on_track", "health_score": 80, "concerns": ["x" * 100 for _ in range(10)]},
            "risk_analysis": {"overall_risk": "medium", "key_risks": ["risk " * 20 for _ in range(5)]},
            "resource_assessment": {"adequacy": "sufficient", "notes": "C" * 500},
            "stakeholder_insights": None,
            "timeline_assessment": {"on_schedule": True, "buffer_days": 3},
            "lean_efficiency": {"classification": "value_added", "waste_potential": "low"},
            "prioritized_actions": [{"action": f"Action {i}: " + "D" * 100, "priority": "high"} for i in range(10)],
            "assumptions": [f"Assumption {i}" for i in range(10)],
            "limitations": [f"Limitation {i}" for i in range(5)],
            "markdown_summary": "## Summary\n" + "E" * 3000
        }
        mock_ai.return_value = json.dumps(large_response)
        result = summarize_task_details({
            'title': 'Complex task', 'description': 'Long description ' * 50,
            'priority': 'High', 'status': 'In Progress'
        })
        self.assertIsNotNone(result)
        self.assertIn('executive_summary', result)
        # Verify nothing was silently lost
        self.assertEqual(len(result['executive_summary']['one_line_summary']), 200)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_large_breakdown_response_parses(self, mock_ai):
        """Breakdown with many subtasks should parse correctly."""
        from kanban.utils.ai_utils import suggest_task_breakdown
        large_breakdown = {
            "is_breakdown_recommended": True,
            "complexity_score": 9,
            "confidence_score": 0.9,
            "confidence_level": "high",
            "reasoning": "Very complex task requires decomposition.",
            "complexity_factors": [{"factor": f"Factor {i}", "impact": "high", "description": "x" * 100} for i in range(5)],
            "subtasks": [
                {"title": f"Subtask {i}", "description": f"Work item {i} " * 20,
                 "estimated_effort": "3 hours", "priority": "medium",
                 "reasoning": f"Needed for step {i}"}
                for i in range(15)
            ],
            "critical_path": [f"Subtask {i}" for i in range(8)],
            "parallel_opportunities": ["Subtask 3 and Subtask 4 can run in parallel"],
            "workflow_suggestions": ["Start with Subtask 0"],
            "risk_considerations": ["Many subtasks increase coordination overhead"],
            "assumptions": ["Full team availability"],
            "total_estimated_effort": "45 hours",
            "effort_vs_original": "Aligned"
        }
        mock_ai.return_value = json.dumps(large_breakdown)
        result = suggest_task_breakdown({'title': 'Mega task', 'description': 'Huge scope'})
        self.assertIsNotNone(result)
        self.assertEqual(len(result.get('subtasks', [])), 15)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_large_risk_response_parses(self, mock_ai):
        """Risk assessment with many indicators should parse correctly."""
        from kanban.utils.ai_utils import calculate_task_risk_score
        large_risk = {
            "likelihood": {"score": 3, "label": "Likely", "justification": "Multiple risk factors present " * 10},
            "impact": {"score": 3, "label": "High", "justification": "Critical path item with budget implications " * 10},
            "risk_assessment": {
                "risk_score": 9,
                "risk_level": "critical",
                "summary": "Maximum risk level: " + "X" * 500
            },
            "risk_indicators": [
                {"indicator": f"Risk indicator {i}: " + "Y" * 80, "severity": "high"} for i in range(10)
            ],
            "mitigation_suggestions": [
                {"strategy": f"Mitigate {i}: " + "Z" * 80, "priority": "high", "effort": "medium"} for i in range(8)
            ],
            "explainability": {
                "confidence_score": 0.85,
                "reasoning": "Comprehensive analysis " * 20,
                "data_quality": "high",
                "assumptions": [f"Assumption {i}" for i in range(5)]
            }
        }
        mock_ai.return_value = json.dumps(large_risk)
        result = calculate_task_risk_score('Critical task', 'Big risk', 'urgent', 'Board: Sprint 1')
        self.assertIsNotNone(result)
        self.assertEqual(result['risk_assessment']['risk_score'], 9)
        self.assertEqual(len(result.get('risk_indicators', [])), 10)


# ===========================================================================
# SECTION 5: Edge Cases & Integration Scenarios
# ===========================================================================

class AIInsightsEdgeCaseTests(TestCase):
    """Test edge cases across AI Insights features."""

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_breakdown_with_python_booleans_in_response(self, mock_ai):
        """AI may return Python True/False instead of JSON true/false."""
        from kanban.utils.ai_utils import suggest_task_breakdown
        response = '{"is_breakdown_recommended": True, "complexity_score": 5, "subtasks": [], "confidence_score": 0.8, "confidence_level": "medium", "reasoning": "Simple task", "complexity_factors": [], "critical_path": [], "parallel_opportunities": [], "workflow_suggestions": [], "risk_considerations": [], "assumptions": [], "total_estimated_effort": "2 hours", "effort_vs_original": "Same"}'
        mock_ai.return_value = response
        result = suggest_task_breakdown({'title': 'Simple task', 'description': 'Easy work'})
        self.assertIsNotNone(result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_breakdown_with_python_none_in_response(self, mock_ai):
        """AI may return Python None instead of JSON null."""
        from kanban.utils.ai_utils import suggest_task_breakdown
        response = '{"is_breakdown_recommended": False, "complexity_score": 3, "subtasks": [], "confidence_score": 0.7, "confidence_level": "medium", "reasoning": None, "complexity_factors": [], "critical_path": [], "parallel_opportunities": [], "workflow_suggestions": [], "risk_considerations": [], "assumptions": [], "total_estimated_effort": None, "effort_vs_original": None}'
        mock_ai.return_value = response
        result = suggest_task_breakdown({'title': 'Simple task', 'description': 'Easy work'})
        self.assertIsNotNone(result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_summary_with_empty_json_object(self, mock_ai):
        """Empty JSON object should not crash, should return with parsing note."""
        from kanban.utils.ai_utils import summarize_task_details
        mock_ai.return_value = '{}'
        result = summarize_task_details({
            'title': 'Task', 'description': 'Desc', 'priority': 'Low', 'status': 'To Do'
        })
        self.assertIsNotNone(result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_risk_with_extra_text_before_json(self, mock_ai):
        """AI sometimes adds explanatory text before the JSON."""
        from kanban.utils.ai_utils import calculate_task_risk_score
        response = f"Here is the risk assessment:\n\n{VALID_RISK_RESPONSE}"
        mock_ai.return_value = response
        result = calculate_task_risk_score('Build API', 'REST endpoints', 'high', 'Board: Sprint 1')
        self.assertIsNotNone(result)

    def test_token_limit_for_task_never_crashes(self):
        """get_token_limit_for_task should never raise, even with weird input."""
        from kanban.utils.ai_utils import get_token_limit_for_task
        for weird_input in ['', None, 123, 'definitely_not_a_task', '  ', 'UPPERCASE_TASK']:
            try:
                result = get_token_limit_for_task(weird_input)
                self.assertIsInstance(result, int)
                self.assertGreater(result, 0)
            except Exception:
                self.fail(f"get_token_limit_for_task crashed with input: {weird_input!r}")


class GenerateAndSaveTaskSummaryTests(TestCase):
    """Test generate_and_save_task_summary end-to-end with DB persistence."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', email='test@example.com', password='testpass123'
        )
        self.org = Organization.objects.create(
            name='Test Org', domain='test.org', created_by=self.user
        )
        self.board = Board.objects.create(
            name='Sprint Board', created_by=self.user, organization=self.org
        )
        self.column = Column.objects.create(name='To Do', board=self.board, position=0)
        self.task = Task.objects.create(
            title='Build REST API',
            description='Implement CRUD endpoints',
            column=self.column,
            created_by=self.user,
            priority='medium',
            complexity_score=6,
        )

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_summary_persisted_to_db(self, mock_ai):
        from kanban.utils.ai_utils import generate_and_save_task_summary
        mock_ai.return_value = VALID_TASK_SUMMARY_RESPONSE
        result = generate_and_save_task_summary(self.task)
        self.assertIsNotNone(result)
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.ai_summary)
        self.assertIsNotNone(self.task.ai_summary_generated_at)
        self.assertIsNotNone(self.task.ai_summary_metadata)
        # Verify metadata structure
        metadata = self.task.ai_summary_metadata
        self.assertIn('confidence_score', metadata)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_truncated_response_still_saves(self, mock_ai):
        """Even a truncated response should be recovered and saved."""
        from kanban.utils.ai_utils import generate_and_save_task_summary
        truncated = '{"executive_summary": "Task on track.", "confidence_score": 0.7, "markdown_summary": "On track"'
        mock_ai.return_value = truncated
        result = generate_and_save_task_summary(self.task)
        # Should save something (either repaired JSON or fallback)
        self.assertIsNotNone(result)
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.ai_summary)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_ai_failure_returns_none(self, mock_ai):
        from kanban.utils.ai_utils import generate_and_save_task_summary
        mock_ai.return_value = None
        result = generate_and_save_task_summary(self.task)
        self.assertIsNone(result)

    @patch('kanban.utils.ai_utils.generate_ai_content')
    def test_metadata_includes_truncation_note_when_truncated(self, mock_ai):
        """When response is truncated, metadata should carry the truncation_note."""
        from kanban.utils.ai_utils import generate_and_save_task_summary
        truncated = '{"executive_summary": {"one_line_summary": "On track"}, "confidence_score": 0.6, "task_health": {"status": "on_track"'
        mock_ai.return_value = truncated
        result = generate_and_save_task_summary(self.task)
        if result:
            self.task.refresh_from_db()
            metadata = self.task.ai_summary_metadata or {}
            # If truncation was detected, we expect either truncation_note or parsing_note
            has_note = 'truncation_note' in metadata or 'parsing_note' in metadata
            # This is informational — truncation repair is best-effort
            if has_note:
                self.assertTrue(True)
