"""
Tests for the deterministic number-guard on the AI Analytics Summary.

`_reconcile_summary_numbers` reconciles the summary's narrative numbers against the
authoritative metrics it was given: it auto-corrects unambiguous integer counts (overdue,
per-column, total, completed) and flags percentages without rewriting them. It must never
touch legitimate recommendation numbers and must never raise.

These are pure dict-in / dict-out tests — no database needed.
"""
from django.test import SimpleTestCase

from kanban.utils.ai_utils import _reconcile_summary_numbers


def _analytics(**overrides):
    data = {
        'board_name': 'Software Development',
        'total_tasks': 29,
        'completed_count': 8,
        'productivity': 27.6,
        'overdue_count': 3,
        'value_added_percentage': 0,
        'tasks_by_column': [
            {'name': 'Backlog', 'count': 9},
            {'name': 'To Do', 'count': 6},
            {'name': 'In Progress', 'count': 4},
            {'name': 'In Review', 'count': 2},
            {'name': 'Done', 'count': 8},
        ],
    }
    data.update(overrides)
    return data


class NumberGuardTests(SimpleTestCase):
    def test_overdue_drift_is_corrected(self):
        summary = {'executive_summary': 'There are 2 overdue tasks blocking delivery.'}
        out = _reconcile_summary_numbers(summary, _analytics())
        self.assertIn('3 overdue tasks', out['executive_summary'])
        self.assertNotIn('2 overdue', out['executive_summary'])
        self.assertEqual(out['_number_reconciliation']['corrections'], 1)

    def test_overdue_correct_value_untouched(self):
        summary = {'executive_summary': '3 overdue tasks remain.'}
        out = _reconcile_summary_numbers(summary, _analytics())
        self.assertEqual(out['executive_summary'], '3 overdue tasks remain.')
        self.assertNotIn('_number_reconciliation', out)

    def test_column_count_corrected_when_wrong(self):
        summary = {
            'key_insights': [
                {'insight': 'Bottleneck', 'evidence': '7 tasks in Backlog versus 8 done'},
            ]
        }
        out = _reconcile_summary_numbers(summary, _analytics())
        self.assertIn('9 tasks in Backlog', out['key_insights'][0]['evidence'])

    def test_column_count_untouched_when_right(self):
        summary = {
            'key_insights': [
                {'insight': 'Bottleneck', 'evidence': '9 tasks in Backlog compared to 4 in progress'},
            ]
        }
        out = _reconcile_summary_numbers(summary, _analytics())
        self.assertEqual(
            out['key_insights'][0]['evidence'],
            '9 tasks in Backlog compared to 4 in progress',
        )

    def test_recommendation_numbers_are_not_touched(self):
        # "transition 5 tasks" / "WIP limit of 3" are advice, not data claims.
        text = 'Transition 5 tasks from the backlog and set a WIP limit of 3 items.'
        summary = {
            'process_improvement_recommendations': [
                {'recommendation': text, 'expected_impact': 'Higher throughput'},
            ]
        }
        out = _reconcile_summary_numbers(summary, _analytics())
        self.assertEqual(
            out['process_improvement_recommendations'][0]['recommendation'], text,
        )
        self.assertNotIn('_number_reconciliation', out)

    def test_total_and_completed_counts(self):
        summary = {'executive_summary': '7 tasks completed out of 30 total tasks.'}
        out = _reconcile_summary_numbers(summary, _analytics())
        self.assertIn('8 tasks completed', out['executive_summary'])
        self.assertIn('29 total tasks', out['executive_summary'])

    def test_percentage_within_tolerance_not_rewritten(self):
        # 27 vs 27.6 is legitimate rounding -> flag-only, never rewritten.
        summary = {'health_assessment': {'score_reasoning': 'Only 27 percent complete.'}}
        out = _reconcile_summary_numbers(summary, _analytics())
        self.assertEqual(
            out['health_assessment']['score_reasoning'], 'Only 27 percent complete.',
        )

    def test_percentage_completion_not_corrected_as_count(self):
        # "27 percent complete" must not be mistaken for the completed *count* (8).
        summary = {'executive_summary': 'The board is 27 percent complete.'}
        out = _reconcile_summary_numbers(summary, _analytics())
        self.assertEqual(out['executive_summary'], 'The board is 27 percent complete.')

    def test_missing_metric_key_is_safe(self):
        summary = {'executive_summary': '2 overdue tasks remain.'}
        data = _analytics()
        data.pop('overdue_count')  # rule simply skipped
        out = _reconcile_summary_numbers(summary, data)
        self.assertEqual(out['executive_summary'], '2 overdue tasks remain.')

    def test_malformed_inputs_never_raise(self):
        self.assertEqual(_reconcile_summary_numbers(None, _analytics()), None)
        self.assertEqual(_reconcile_summary_numbers({'x': 1}, None), {'x': 1})
        # Non-string fields are ignored, not crashed on.
        summary = {'executive_summary': 123, 'key_insights': ['not-a-dict']}
        self.assertEqual(_reconcile_summary_numbers(summary, _analytics()), summary)
