"""
AI Coach effectiveness-metric tests
====================================

Coaching Effectiveness = 40% helpful_rate + 40% action_rate + 20% avg_relevance
(see FeedbackLearningSystem.calculate_pm_coaching_effectiveness). Before this
fix, was_helpful was only ever set by the separate, optional "Provide
Feedback" form — Acknowledge (the natural one-click response) set
action_taken='accepted' but left was_helpful null, so a fully-engaged user who
never opens the feedback form was structurally capped near 40-48% effectiveness
regardless of real coaching quality. acknowledge() now defaults was_helpful to
True (a user acting on a suggestion is itself a positive signal), while never
overwriting an explicit Helpful/Not Helpful rating from the feedback form.
"""

from django.test import TestCase
from django.contrib.auth.models import User

from accounts.models import Organization
from kanban.models import Board, Workspace
from kanban.coach_models import CoachingSuggestion
from kanban.utils.feedback_learning import FeedbackLearningSystem


class AcknowledgeSetsHelpfulDefaultTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('pm', password='x')
        cls.org = Organization.objects.create(name='Org', created_by=cls.user)
        cls.ws = Workspace.objects.create(
            name='WS', organization=cls.org, is_active=True, created_by=cls.user,
        )
        cls.board = Board.objects.create(
            name='Board', organization=cls.org, workspace=cls.ws, created_by=cls.user,
        )

    def _suggestion(self):
        return CoachingSuggestion.objects.create(
            board=self.board, suggestion_type='velocity_drop',
            title='Velocity dropping', message='Down 20%', status='active',
        )

    def test_acknowledge_defaults_was_helpful_true(self):
        s = self._suggestion()
        s.acknowledge(self.user)
        s.refresh_from_db()
        self.assertEqual(s.action_taken, 'accepted')
        self.assertIs(s.was_helpful, True)

    def test_acknowledge_does_not_overwrite_explicit_negative_feedback(self):
        s = self._suggestion()
        learning_system = FeedbackLearningSystem()
        learning_system.record_feedback(
            suggestion=s, user=self.user, was_helpful=False,
            relevance_score=2, action_taken='partially',
        )
        s.refresh_from_db()
        s.acknowledge(self.user)
        s.refresh_from_db()
        self.assertIs(s.was_helpful, False)

    def test_acknowledge_does_not_overwrite_explicit_positive_feedback(self):
        s = self._suggestion()
        learning_system = FeedbackLearningSystem()
        learning_system.record_feedback(
            suggestion=s, user=self.user, was_helpful=True,
            relevance_score=5, action_taken='accepted',
        )
        s.refresh_from_db()
        s.acknowledge(self.user)
        s.refresh_from_db()
        self.assertIs(s.was_helpful, True)

    def test_effectiveness_reflects_acknowledge_only_workflow(self):
        """A user who only ever Acknowledges (never opens the optional
        Provide Feedback form) should no longer be capped near ~40-48%."""
        for _ in range(3):
            self._suggestion().acknowledge(self.user)

        learning_system = FeedbackLearningSystem()
        result = learning_system.calculate_pm_coaching_effectiveness(
            self.board, self.user, days=30
        )

        self.assertEqual(result['action_rate'], 100.0)
        self.assertEqual(result['helpful_rate'], 100.0)
        # 40% action_rate + 40% helpful_rate + 0% avg_relevance (acknowledge-only
        # never touches CoachingFeedback.relevance_score) = 80, not the old ~40-48.
        self.assertGreaterEqual(result['effectiveness_score'], 80.0)
