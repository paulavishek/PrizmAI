"""
AI Coach / Retrospectives cross-surface consistency tests
=========================================================

Four surfaces (Focus Today, the AI Coach cards, the conflict cards and the
briefing) each used to derive "overdue" independently and quoted four different
counts for the same board. The same shape of bug hit "stalled" (the coach read
``updated_at``, everything else read column dwell) and the Improvement Dashboard
(percentages and a "recurring" claim computed from a single retrospective).

These tests pin the reconciled definitions:

* ``Task.overdue_for_boards`` is the single source of truth for overdue.
* ``Task.stalled_for_boards`` is the single source of truth for stalled, and the
  coach's dependency-blocker rule must use it.
* the coach reconciles its own suggestions before returning them.
* "Urgent" action items mean overdue-or-imminent, not merely high-priority.
* recurrence is only asserted when there are 2+ retrospectives to compare.
"""

from datetime import timedelta

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from accounts.models import Organization
from kanban.models import Board, BoardMembership, Column, Task, Workspace
from kanban.retrospective_models import (
    ProjectRetrospective, LessonLearned, RetrospectiveActionItem,
)
from kanban.utils.coaching_rules import CoachingRuleEngine


class OverdueSingleSourceOfTruthTestCase(TestCase):
    """Task.overdue_for_boards — one definition of overdue."""

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
        cls.todo = Column.objects.create(name='To Do', board=cls.board, position=0)
        cls.done = Column.objects.create(name='Done', board=cls.board, position=1)

        past = timezone.now() - timedelta(days=5)
        future = timezone.now() + timedelta(days=5)

        cls.genuinely_overdue = Task.objects.create(
            title='Overdue and unfinished', column=cls.todo, created_by=cls.user,
            due_date=past, progress=40, item_type='task',
        )
        # Past due but finished — the work landed late, it is not outstanding.
        Task.objects.create(
            title='Complete by progress', column=cls.todo, created_by=cls.user,
            due_date=past, progress=100, item_type='task',
        )
        # Past due, progress never updated, but dragged to Done. A card can be
        # moved without its progress field being touched.
        Task.objects.create(
            title='Complete by column', column=cls.done, created_by=cls.user,
            due_date=past, progress=0, item_type='task',
        )
        # Roll-up container: its due date mirrors its children, so counting it
        # would double-count the same slip.
        Task.objects.create(
            title='Epic', column=cls.todo, created_by=cls.user,
            due_date=past, progress=0, item_type='epic',
        )
        Task.objects.create(
            title='Not due yet', column=cls.todo, created_by=cls.user,
            due_date=future, progress=10, item_type='task',
        )
        Task.objects.create(
            title='No due date', column=cls.todo, created_by=cls.user,
            due_date=None, progress=10, item_type='task',
        )

    def test_counts_only_unfinished_past_due_tasks(self):
        overdue = Task.overdue_for_boards([self.board.id])
        self.assertEqual([t.title for t in overdue], ['Overdue and unfinished'])

    def test_annotates_days_overdue(self):
        overdue = Task.overdue_for_boards([self.board.id])
        self.assertEqual(overdue[0].days_overdue, 5)

    def test_done_column_excluded_even_when_progress_is_zero(self):
        titles = [t.title for t in Task.overdue_for_boards([self.board.id])]
        self.assertNotIn('Complete by column', titles)

    def test_epics_excluded_by_default(self):
        titles = [t.title for t in Task.overdue_for_boards([self.board.id])]
        self.assertNotIn('Epic', titles)

    def test_milestones_opt_in(self):
        Task.objects.create(
            title='Missed milestone', column=self.todo, created_by=self.user,
            due_date=timezone.now() - timedelta(days=2), progress=0,
            item_type='milestone',
        )
        without = [t.title for t in Task.overdue_for_boards([self.board.id])]
        self.assertNotIn('Missed milestone', without)

        with_ms = [
            t.title for t in
            Task.overdue_for_boards([self.board.id], include_milestones=True)
        ]
        self.assertIn('Missed milestone', with_ms)

    def test_ordered_most_overdue_first(self):
        Task.objects.create(
            title='Very overdue', column=self.todo, created_by=self.user,
            due_date=timezone.now() - timedelta(days=30), progress=10,
            item_type='task',
        )
        overdue = Task.overdue_for_boards([self.board.id])
        self.assertEqual(overdue[0].title, 'Very overdue')


class CoachUsesSharedSignalsTestCase(TestCase):
    """The coach's rules must read the shared aging/overdue signals."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('pm2', password='x')
        cls.org = Organization.objects.create(name='Org2', created_by=cls.user)
        cls.ws = Workspace.objects.create(
            name='WS2', organization=cls.org, is_active=True, created_by=cls.user,
        )
        cls.board = Board.objects.create(
            name='Board2', organization=cls.org, workspace=cls.ws, created_by=cls.user,
        )
        cls.col = Column.objects.create(name='In Progress', board=cls.board, position=0)

    def _stall(self, n, days=10):
        """Create n tasks that have sat in their column for `days` days."""
        entered = timezone.now() - timedelta(days=days)
        for i in range(n):
            t = Task.objects.create(
                title=f'Stalled {i}', column=self.col, progress=50, item_type='task',
                created_by=self.user,
            )
            Task.objects.filter(pk=t.pk).update(column_entered_at=entered)

    def test_stalled_card_matches_stalled_for_boards(self):
        self._stall(4)
        expected = len(Task.stalled_for_boards([self.board.id], tier='warning'))

        engine = CoachingRuleEngine(self.board)
        engine.analyze_and_generate_suggestions()
        card = next(
            s for s in engine.suggestions
            if s['suggestion_type'] == 'dependency_blocker'
        )

        self.assertEqual(card['metrics_snapshot']['stalled_task_count'], expected)
        self.assertEqual(card['metrics_snapshot']['signal'], 'column_dwell')

    def test_stalled_card_says_column_not_progressed(self):
        """The wording must name the signal it actually measures."""
        self._stall(4)
        engine = CoachingRuleEngine(self.board)
        engine.analyze_and_generate_suggestions()
        card = next(
            s for s in engine.suggestions
            if s['suggestion_type'] == 'dependency_blocker'
        )
        self.assertIn('current column', card['title'])
        self.assertIn('not moved column', card['message'])

    def test_stalled_card_ignores_updated_at_churn(self):
        """Editing a task must not make it look unstalled.

        updated_at is auto_now, so the old rule let any edit reset the signal
        while the card sat in the same column — which is why the coach's count
        disagreed with the board badges.
        """
        self._stall(4)
        for t in Task.objects.filter(column=self.col):
            t.title = t.title + ' (edited)'
            t.save()  # bumps updated_at to now

        engine = CoachingRuleEngine(self.board)
        engine.analyze_and_generate_suggestions()
        card = next(
            s for s in engine.suggestions
            if s['suggestion_type'] == 'dependency_blocker'
        )
        self.assertEqual(card['metrics_snapshot']['stalled_task_count'], 4)


class CoachSelfConsistencyTestCase(TestCase):
    """The coach reconciles its suggestions against each other."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('pm3', password='x')
        cls.busy = User.objects.create_user('busy', password='x')
        cls.free = User.objects.create_user('free', password='x')
        cls.org = Organization.objects.create(name='Org3', created_by=cls.owner)
        cls.ws = Workspace.objects.create(
            name='WS3', organization=cls.org, is_active=True, created_by=cls.owner,
        )
        cls.board = Board.objects.create(
            name='Board3', organization=cls.org, workspace=cls.ws, created_by=cls.owner,
        )
        cls.col = Column.objects.create(name='In Progress', board=cls.board, position=0)
        for u in (cls.owner, cls.busy, cls.free):
            BoardMembership.objects.create(board=cls.board, user=u, role='member')

        # 12 active tasks > RECOMMENDED_MAX_TASKS -> overloaded at 120% load.
        for i in range(12):
            Task.objects.create(
                title=f'Busy task {i}', column=cls.col, created_by=cls.owner,
                assigned_to=cls.busy, progress=50, item_type='task',
            )
        Task.objects.create(
            title='Free task', column=cls.col, created_by=cls.owner,
            assigned_to=cls.free, progress=50, item_type='task',
        )

    def _overload_card(self):
        engine = CoachingRuleEngine(self.board)
        engine.analyze_and_generate_suggestions()
        return engine, next(
            s for s in engine.suggestions
            if s['suggestion_type'] == 'resource_overload'
        )

    def test_load_percent_higher_means_busier(self):
        _, card = self._overload_card()
        self.assertEqual(card['metrics_snapshot']['load_percent'], 120)
        self.assertIn('120% load', card['title'])

    def test_relief_candidates_exclude_the_overloaded_member(self):
        _, card = self._overload_card()
        relief = card['metrics_snapshot']['relief_candidates']
        self.assertIn('free', relief)
        self.assertNotIn('busy', relief)

    def test_coordination_block_names_overloaded_and_relief(self):
        engine, _ = self._overload_card()
        for suggestion in engine.suggestions:
            coordination = suggestion['metrics_snapshot']['coordination']
            self.assertIn('busy', coordination['overloaded_members'])
            self.assertIn('free', coordination['relief_members'])

    def test_overload_card_reports_overdue_via_shared_helper(self):
        Task.objects.filter(
            assigned_to=self.busy, title='Busy task 0'
        ).update(due_date=timezone.now() - timedelta(days=6))

        _, card = self._overload_card()
        self.assertEqual(card['metrics_snapshot']['overdue_tasks'], 1)
        self.assertIn('6 days past due', card['message'])


class UrgentActionSemanticsTestCase(TestCase):
    """'Urgent' means overdue or due within 48 hours — not just high priority."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('pm4', password='x')
        cls.org = Organization.objects.create(name='Org4', created_by=cls.user)
        cls.ws = Workspace.objects.create(
            name='WS4', organization=cls.org, is_active=True, created_by=cls.user,
        )
        cls.board = Board.objects.create(
            name='Board4', organization=cls.org, workspace=cls.ws, created_by=cls.user,
        )
        BoardMembership.objects.create(board=cls.board, user=cls.user, role='owner')
        cls.retro = ProjectRetrospective.objects.create(
            board=cls.board, title='R1', retrospective_type='milestone',
            status='finalized',
            period_start=timezone.localdate() - timedelta(days=20),
            period_end=timezone.localdate() - timedelta(days=5),
            created_by=cls.user,
        )
        today = timezone.localdate()
        cls.overdue = RetrospectiveActionItem.objects.create(
            retrospective=cls.retro, board=cls.board,
            title='Overdue action', description='d', action_type='process_change',
            priority='medium', status='pending',
            target_completion_date=today - timedelta(days=3),
        )
        cls.imminent = RetrospectiveActionItem.objects.create(
            retrospective=cls.retro, board=cls.board,
            title='Due tomorrow', description='d', action_type='process_change',
            priority='medium', status='pending',
            target_completion_date=today + timedelta(days=1),
        )
        cls.later = RetrospectiveActionItem.objects.create(
            retrospective=cls.retro, board=cls.board,
            title='Critical but due next week', description='d',
            action_type='process_change', priority='critical', status='in_progress',
            target_completion_date=today + timedelta(days=8),
        )

    def _dashboard(self):
        self.client.force_login(self.user)
        return self.client.get(f'/board/{self.board.id}/retrospectives/dashboard/')

    def test_urgent_contains_overdue_and_imminent_only(self):
        response = self._dashboard()
        self.assertEqual(response.status_code, 200)
        titles = [a.title for a in response.context['urgent_actions']]
        self.assertIn('Overdue action', titles)
        self.assertIn('Due tomorrow', titles)
        self.assertNotIn('Critical but due next week', titles)

    def test_not_yet_due_high_priority_moves_to_upcoming(self):
        response = self._dashboard()
        titles = [a.title for a in response.context['upcoming_actions']]
        self.assertIn('Critical but due next week', titles)


class RecurrenceRequiresTwoRetrospectivesTestCase(TestCase):
    """A "seen 2+ times" claim needs 2+ retrospectives to compare."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('pm5', password='x')
        cls.org = Organization.objects.create(name='Org5', created_by=cls.user)
        cls.ws = Workspace.objects.create(
            name='WS5', organization=cls.org, is_active=True, created_by=cls.user,
        )
        cls.board = Board.objects.create(
            name='Board5', organization=cls.org, workspace=cls.ws, created_by=cls.user,
        )
        BoardMembership.objects.create(board=cls.board, user=cls.user, role='owner')

    def _make_retro(self, title):
        return ProjectRetrospective.objects.create(
            board=self.board, title=title, retrospective_type='milestone',
            status='finalized',
            period_start=timezone.localdate() - timedelta(days=20),
            period_end=timezone.localdate() - timedelta(days=5),
            created_by=self.user,
        )

    def _lesson(self, retro):
        return LessonLearned.objects.create(
            retrospective=retro, board=self.board,
            title='Recurring thing', description='d',
            category='planning', priority='high',
            is_recurring_issue=True, recurrence_count=2,
        )

    def _dashboard(self):
        self.client.force_login(self.user)
        return self.client.get(f'/board/{self.board.id}/retrospectives/dashboard/')

    def test_single_retrospective_suppresses_recurrence(self):
        retro = self._make_retro('Only one')
        self._lesson(retro)

        response = self._dashboard()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['recurring_lessons']), 0)
        self.assertEqual(response.context['stats']['recurring_issues'], 0)

    def test_two_retrospectives_allow_recurrence(self):
        retro = self._make_retro('First')
        self._make_retro('Second')
        self._lesson(retro)

        response = self._dashboard()
        self.assertEqual(len(response.context['recurring_lessons']), 1)
        self.assertEqual(response.context['stats']['recurring_issues'], 1)
