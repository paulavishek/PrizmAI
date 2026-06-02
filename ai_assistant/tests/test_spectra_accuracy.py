"""
test_spectra_accuracy.py — Regression tests locking in the Spectra accuracy pass.

These guard the exact failure modes seen in the May 2026 test transcript:
  • contradictory per-member workload counts (double-sourcing)
  • commitment confidence rendered as "0.38%" instead of "38%"
  • "due in next 7 days" listing tasks due months out
  • Done tasks leaking into high-priority lists
  • overdue counts disagreeing with the dashboard

They exercise the VDF layer and the context providers directly (no LLM / network).

Run with:
    python manage.py test ai_assistant.tests.test_spectra_accuracy
"""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from kanban.models import Board, BoardMembership, Column, Task

from ai_assistant.utils.spectra_data_fetchers import (
    fetch_assignee_workload,
    fetch_board_tasks,
    fetch_overdue_tasks,
)
from ai_assistant.utils.context_providers import registry
from ai_assistant.utils.context_providers.commitment_provider import (
    _pct,
    AT_RISK_THRESHOLD,
    CRITICAL_THRESHOLD,
)


class SpectraAccuracyTests(TestCase):
    def setUp(self):
        # No Redis/broker in the test env. Several Task/Board/membership save
        # signals queue Celery jobs (branch recalculation, debounced summaries);
        # neutralize dispatch so they don't burn minutes on broker-connection
        # retries. They are irrelevant to what these tests assert.
        celery_patcher = patch('celery.app.task.Task.apply_async', return_value=None)
        celery_patcher.start()
        self.addCleanup(celery_patcher.stop)

        self.alice = User.objects.create_user('alice', password='x')
        self.bob = User.objects.create_user('bob', password='x')

        # Board.organization is nullable; omit it to keep the fixture minimal.
        self.board = Board.objects.create(
            name='Software Development',
            created_by=self.alice,
        )
        # Provider get_summary/get_detail enforce RBAC via can_spectra_read_board,
        # so the querying user must be a board member.
        BoardMembership.objects.get_or_create(
            board=self.board, user=self.alice, defaults={'role': 'owner'})

        self.todo = Column.objects.create(board=self.board, name='To Do', position=0)
        self.inprog = Column.objects.create(board=self.board, name='In Progress', position=1)
        self.done = Column.objects.create(board=self.board, name='Done', position=2)

        now = timezone.now()
        # alice: 2 active (one overdue) + 1 done high-priority
        Task.objects.create(column=self.todo, title='A1', created_by=self.alice,
                            assigned_to=self.alice, priority='high',
                            due_date=now + timedelta(days=3))
        Task.objects.create(column=self.inprog, title='A2', created_by=self.alice,
                            assigned_to=self.alice, priority='medium',
                            due_date=now - timedelta(days=2))            # overdue, active
        Task.objects.create(column=self.done, title='A3-done', created_by=self.alice,
                            assigned_to=self.alice, priority='high',
                            due_date=now - timedelta(days=5))            # done (was due in past)
        # bob: 1 active, far-future urgent
        Task.objects.create(column=self.todo, title='B1', created_by=self.alice,
                            assigned_to=self.bob, priority='urgent',
                            due_date=now + timedelta(days=40))
        # unassigned, due tomorrow
        Task.objects.create(column=self.todo, title='U1', created_by=self.alice,
                            assigned_to=None, priority='low',
                            due_date=now + timedelta(days=1))

    # ── Double-sourcing: single, deterministic workload source ──────────────

    def test_workload_is_single_source_and_deterministic(self):
        w1 = fetch_assignee_workload(self.board)
        w2 = fetch_assignee_workload(self.board)

        # Counts include ALL assigned tasks (Done included) — one definition.
        self.assertEqual(w1['alice']['count'], 3)
        self.assertEqual(w1['bob']['count'], 1)
        self.assertEqual(w1['Unassigned']['count'], 1)

        # Identical across calls — no run-to-run drift.
        self.assertEqual(
            {k: v['count'] for k, v in w1.items()},
            {k: v['count'] for k, v in w2.items()},
        )

        # Overdue attribution: only the active overdue task counts (A3 is Done).
        self.assertEqual(w1['alice']['overdue_count'], 1)

    def test_overlapping_legacy_builders_are_removed(self):
        """The builders that recomputed workload/user-info differently are gone."""
        from ai_assistant.utils.chatbot_service import TaskFlowChatbotService
        for gone in (
            '_get_user_info_context', '_get_resource_context',
            '_get_user_tasks_context', '_get_organization_context',
            '_is_user_info_query', '_is_resource_query',
            '_is_user_task_query', '_is_organization_query',
        ):
            self.assertFalse(
                hasattr(TaskFlowChatbotService, gone),
                f'{gone} should have been removed (double-sourcing).',
            )

    # ── Overdue parity with the dashboard (due_date < now, not complete) ────

    def test_overdue_excludes_done_and_future(self):
        titles = {t['title'] for t in fetch_overdue_tasks(self.board)}
        self.assertIn('A2', titles)            # active + overdue
        self.assertNotIn('A3-done', titles)    # Done → not overdue
        self.assertNotIn('B1', titles)         # future
        self.assertNotIn('U1', titles)

    # ── High priority must be literal and Done must be excludable ───────────

    def test_high_priority_filter_and_done_exclusion(self):
        high = {t['title'] for t in
                fetch_board_tasks(self.board, filters={'priority_value': 'high'})}
        # high+urgent retained
        self.assertIn('A1', high)
        self.assertIn('B1', high)              # urgent >= high
        self.assertIn('A3-done', high)         # priority unchanged...
        # ...but Done is flagged so it can be excluded from "high priority" lists
        a3 = next(t for t in
                  fetch_board_tasks(self.board, filters={'priority_value': 'high'})
                  if t['title'] == 'A3-done')
        self.assertTrue(a3['is_complete'])

        active_high = {t['title'] for t in fetch_board_tasks(
            self.board, filters={'priority_value': 'high', 'is_complete': False})}
        self.assertNotIn('A3-done', active_high)
        self.assertIn('A1', active_high)

    # ── "Due in next 7 days" must exclude far-future tasks ──────────────────

    def test_due_soon_section_excludes_far_future(self):
        provider = registry.providers['Board Tasks']
        detail = provider.get_detail(
            self.board, self.alice, 'what is due in the next 7 days?', False)
        self.assertIn('Due in next 7 days', detail)

        # Bound the due-soon section so we don't pick up the full task roster.
        section = detail.split('Due in next 7 days', 1)[1].split('Milestones', 1)[0]
        self.assertIn('A1', section)           # due in 3 days
        self.assertIn('U1', section)           # due tomorrow
        self.assertNotIn('B1', section)        # due in 40 days — must not appear

    # ── Commitment confidence must read as a percent, not a fraction ────────

    def test_confidence_helper_and_thresholds(self):
        self.assertEqual(_pct(0.38), '38%')
        self.assertEqual(_pct(0.85), '85%')
        self.assertEqual(_pct(0.0), '0%')
        self.assertEqual(AT_RISK_THRESHOLD, 0.70)
        self.assertEqual(CRITICAL_THRESHOLD, 0.50)

    def test_commitment_provider_renders_percent(self):
        from kanban.commitment_models import CommitmentProtocol
        CommitmentProtocol.objects.create(
            board=self.board, title='Beta Release',
            target_date=date.today() + timedelta(days=14),
            created_by=self.alice, current_confidence=0.38,
        )
        provider = registry.providers['Commitments']

        summary = provider.get_summary(self.board, self.alice, False)
        self.assertIn('38%', summary)
        self.assertNotIn('0.38%', summary)
        self.assertIn('at risk', summary)      # 0.38 < 0.70

        detail = provider.get_detail(self.board, self.alice, 'commitment confidence', False)
        self.assertIn('38%', detail)
        self.assertNotIn('0.38%', detail)
