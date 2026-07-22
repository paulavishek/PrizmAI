"""
test_feature_guide.py — Tests for the PrizmAI Feature Guide provider.

Covers the Spectra feature-help / onboarding-advisor capability:
  • the always-on summary is a single help line
  • detail returns the all-features index plus the matched entry
  • detail works with no board AND when the user can't read the active board
    (the provider serves static product knowledge, not board data)
  • the context router routes a "which feature?" query to the guide

These exercise the VDF layer directly (no LLM / network).

Run with:
    python manage.py test ai_assistant.tests.test_feature_guide
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from kanban.models import Board
from ai_assistant.utils.context_providers import registry
from ai_assistant.utils.context_providers.help_provider import (
    FeatureGuideContextProvider,
    _ENTRIES,
)
from ai_assistant.utils.context_router import route_query

GUIDE = 'PrizmAI Feature Guide'


class FeatureGuideProviderTests(TestCase):
    def setUp(self):
        celery_patcher = patch('celery.app.task.Task.apply_async', return_value=None)
        celery_patcher.start()
        self.addCleanup(celery_patcher.stop)

        self.alice = User.objects.create_user('alice', password='x')
        self.outsider = User.objects.create_user('outsider', password='x')
        # A board alice owns but outsider is NOT a member of.
        self.board = Board.objects.create(name='Launch Plan', created_by=self.alice)

        self.provider = FeatureGuideContextProvider()

    def test_reference_file_parsed(self):
        """The markdown file parsed into multiple feature entries at import."""
        self.assertGreater(len(_ENTRIES), 10)
        names = [n for n, _ in _ENTRIES]
        self.assertIn('Pre-Mortem', names)
        self.assertIn('Shadow Board', names)

    def test_forms_feature_documented(self):
        """Forms is now a documented feature Spectra can explain."""
        names = [n for n, _ in _ENTRIES]
        self.assertIn('Forms', names)
        detail = self.provider.get_detail(
            self.board, self.alice, query='what does the forms feature do?')
        self.assertIn('Forms', detail)
        self.assertIn('intake', detail.lower())

    def test_situation_playbooks_present(self):
        """Problem->playbook entries were parsed from the guide."""
        names = [n for n, _ in _ENTRIES]
        self.assertTrue(
            any('scope' in n.lower() and 'stakeholder' in n.lower() for n in names),
            f'No stakeholder-scope playbook entry found in: {names}',
        )

    def test_detail_matches_scope_playbook(self):
        """A stakeholder-scope problem statement surfaces the What-If/Scope playbook."""
        detail = self.provider.get_detail(
            self.board, self.alice,
            query='a stakeholder wants to add scope, what do i do?')
        self.assertIn('What-If', detail)
        self.assertIn('Scope', detail)

    def test_summary_is_single_help_line(self):
        summary = self.provider.get_summary(self.board, self.alice)
        self.assertIn('Feature help', summary)
        # Keep it lean — one line so normal queries pay near-zero token cost.
        self.assertLessEqual(len(summary.strip().splitlines()), 1)

    def test_detail_includes_index_and_matched_entry(self):
        detail = self.provider.get_detail(
            self.board, self.alice, query='what does pre-mortem do?')
        self.assertIn('PrizmAI Feature Guide', detail)
        # Index of all features is always present.
        self.assertIn('Shadow Board', detail)
        # The matched entry's body is included.
        self.assertIn('failure simulation', detail.lower())

    def test_detail_no_match_returns_index_and_nudge(self):
        detail = self.provider.get_detail(
            self.board, self.alice, query='hello there')
        self.assertIn('PrizmAI Feature Guide', detail)
        self.assertIn('No specific feature matched', detail)

    def test_works_without_board(self):
        """Welcome-screen case: no active board still yields product knowledge."""
        detail = self.provider.get_detail(
            None, self.alice, query='which feature helps with risk?')
        self.assertIn('PrizmAI Feature Guide', detail)

    def test_works_when_user_lacks_board_access(self):
        """Static product knowledge is not board-scoped — outsider still gets it."""
        summary = self.provider.get_summary(self.board, self.outsider)
        self.assertIn('Feature help', summary)
        detail = self.provider.get_detail(
            self.board, self.outsider, query='what does the gantt chart do?')
        self.assertIn('Gantt', detail)

    def test_unauthenticated_denied(self):
        from django.contrib.auth.models import AnonymousUser
        self.assertEqual(self.provider.get_summary(self.board, AnonymousUser()), '')

    def test_provider_registered(self):
        self.assertIn(GUIDE, registry.providers)


class FeatureGuideRoutingTests(TestCase):
    def test_router_selects_guide_for_advisor_query(self):
        tags = registry.get_all_tags()
        selected = route_query(
            "I'm stuck, which feature helps me plan for risks?",
            tags,
            use_ai=False,  # keyword tier only — no network in tests
        )
        self.assertIn(GUIDE, selected)

    def test_router_selects_guide_for_what_does_query(self):
        tags = registry.get_all_tags()
        selected = route_query(
            'what does the pre-mortem feature do?', tags, use_ai=False)
        self.assertIn(GUIDE, selected)

    def test_router_selects_guide_for_problem_statement(self):
        """A problem statement co-activates the guide (playbook advisor)."""
        tags = registry.get_all_tags()
        selected = route_query(
            'a stakeholder wants to add scope, what should i do?',
            tags,
            use_ai=False,  # keyword tier only — no network in tests
        )
        self.assertIn(GUIDE, selected)
