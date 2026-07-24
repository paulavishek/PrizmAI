"""
Gap Analysis must never surface a made-up requirement identifier.

The LLM occasionally free-styles a plausible-looking REQ-XXXXX id in its gap
recommendation text even though no such requirement was ever created (the
prompt only asks for narrative area/recommendation strings, no id field).
_strip_invented_ids is the defensive backstop that removes any such id
regardless of what the model returns.
"""
from django.test import TestCase

from kanban.models import Board
from requirements.ai_analysis import RequirementsAIAnalyzer


class StripInventedIdsTests(TestCase):
    def setUp(self):
        self.analyzer = RequirementsAIAnalyzer(board=Board())

    def test_strips_fake_id_from_area_and_recommendation(self):
        gaps = [
            {
                'area': 'REQ-18924: Observability and Monitoring',
                'severity': 'high',
                'recommendation': 'Create REQ-18925 for backup and disaster recovery.',
            },
        ]
        cleaned = self.analyzer._strip_invented_ids(gaps)
        self.assertNotIn('REQ-18924', cleaned[0]['area'])
        self.assertNotIn('REQ-18925', cleaned[0]['recommendation'])

    def test_leaves_text_without_ids_untouched(self):
        gaps = [{'area': 'Legal and Compliance', 'severity': 'medium', 'recommendation': 'Add GDPR requirements.'}]
        cleaned = self.analyzer._strip_invented_ids(gaps)
        self.assertEqual(cleaned, gaps)
