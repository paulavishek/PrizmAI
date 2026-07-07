"""
Demo Reset regression tests
===========================

Lock in the SYNCHRONOUS Reset Demo path so it cannot silently regress.

Reset Demo was rebuilt to run synchronously in the HTTP request via
``kanban.tasks.sandbox_provisioning.provision_sandbox_sync`` — no Celery task and
no WebSocket — because the old queue/worker/WebSocket path repeatedly hung
(solo-worker/Windows flakiness + ``async_to_sync(group_send)`` deadlocks) and
left the database untouched.

These tests assert the contract that path must keep:
  - it deep-copies the official demo template into a private sandbox copy,
  - it is idempotent across repeated resets (no duplicate sandbox boards),
  - it needs no channel layer / broker (the progress WebSocket sends are
    suppressed via ``_ws_suppress`` when called from the request).

The deferred best-effort extras (``finalize_sandbox_extras``: conflict
detection, KG, ``populate_demo_requirements``, …) are patched out — they
self-heal on next visit and are out of scope for the reset contract.
"""

from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth.models import User
from django.core.cache import caches

from accounts.models import Organization, UserProfile
from kanban.models import Board, Column, Task, Workspace, DemoSandbox


class DemoResetSyncTestCase(TestCase):
    """Behavioural contract for the synchronous Reset Demo (provision_sandbox_sync)."""

    TEMPLATE_TASK_COUNT = 5

    @classmethod
    def setUpTestData(cls):
        # ── Demo infrastructure (shared, pre-existing in real life) ──
        cls.demo_creator = User.objects.create_user('demo_creator', password='x')
        cls.demo_org = Organization.objects.create(
            name='Demo Org', is_demo=True, created_by=cls.demo_creator,
        )
        cls.demo_ws = Workspace.objects.create(
            name='Demo Workspace', organization=cls.demo_org,
            is_demo=True, is_active=True, created_by=cls.demo_creator,
        )
        # Official template board WITH columns + tasks — this is the source the
        # reset clones from (mirrors the real "Software Development" template).
        cls.template_board = Board.objects.create(
            name='Software Development', organization=cls.demo_org,
            workspace=cls.demo_ws, is_official_demo_board=True,
            is_seed_demo_data=True, created_by=cls.demo_creator,
        )
        todo = Column.objects.create(name='To Do', board=cls.template_board, position=0)
        doing = Column.objects.create(name='In Progress', board=cls.template_board, position=1)
        for i in range(cls.TEMPLATE_TASK_COUNT):
            Task.objects.create(
                title=f'Template Task {i}',
                column=todo if i % 2 == 0 else doing,
                position=i,
                created_by=cls.demo_creator,
            )

        # ── Real user who will enter / reset the demo ──
        cls.user = User.objects.create_user('realuser', password='pass123')
        cls.profile, _ = UserProfile.objects.get_or_create(user=cls.user)

    def setUp(self):
        # Defensive: clear the single-flight lock cache so a leaked key from a
        # prior test can't make provisioning short-circuit to 'in_progress'.
        try:
            caches['ai_cache'].clear()
        except Exception:
            pass

    def _provision(self, is_reset):
        """Run the synchronous reset with the deferred extras stubbed out."""
        with patch('kanban.tasks.sandbox_provisioning.finalize_sandbox_extras') as mock_extras:
            mock_extras.delay.return_value = None
            from kanban.tasks.sandbox_provisioning import provision_sandbox_sync
            return provision_sandbox_sync(self.user.id, is_reset=is_reset)

    def test_initial_provision_creates_sandbox_copy(self):
        result = self._provision(is_reset=False)

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get('redirect_url'), '/dashboard/')

        boards = Board.objects.filter(owner=self.user, is_sandbox_copy=True)
        self.assertEqual(boards.count(), 1)
        board = boards.first()
        self.assertEqual(board.cloned_from_id, self.template_board.id)
        self.assertFalse(board.is_official_demo_board)
        self.assertEqual(
            Task.objects.filter(column__board=board).count(),
            self.TEMPLATE_TASK_COUNT,
        )
        self.assertTrue(DemoSandbox.objects.filter(user=self.user).exists())

    def test_reset_is_idempotent_no_duplicate_boards(self):
        # First provision, then a reset — the classic "duplicate boards" bug guard.
        self._provision(is_reset=False)
        first = Board.objects.get(owner=self.user, is_sandbox_copy=True)

        result = self._provision(is_reset=True)
        self.assertEqual(result.get('status'), 'created')

        boards = Board.objects.filter(owner=self.user, is_sandbox_copy=True)
        self.assertEqual(boards.count(), 1, 'reset must purge the old sandbox, not duplicate it')
        new = boards.first()
        self.assertNotEqual(new.id, first.id, 'reset should rebuild a fresh sandbox board')
        self.assertEqual(
            Task.objects.filter(column__board=new).count(),
            self.TEMPLATE_TASK_COUNT,
        )

        sandbox = DemoSandbox.objects.get(user=self.user)
        self.assertIsNotNone(sandbox.last_reset_at)

    def test_reset_needs_no_channel_layer(self):
        # provision_sandbox_sync engages _ws_suppress so the WebSocket helpers are
        # no-ops; this must complete cleanly with no channel layer / broker.
        result = self._provision(is_reset=True)
        self.assertEqual(result.get('redirect_url'), '/dashboard/')
        self.assertEqual(
            Board.objects.filter(owner=self.user, is_sandbox_copy=True).count(),
            1,
        )

    def test_clone_skips_real_user_time_entries_on_template(self):
        """Real-user TimeEntry rows on the template must NOT be cloned.

        Regression for the divergent-timesheet bug: _duplicate_board used to
        copy every template TimeEntry verbatim, so a stray real-user row on the
        official board got replicated into every new sandbox as that user's own,
        inflating their Total Hours on every reset. The clone now copies only
        persona-owned (@demo.prizmai.local) rows, remapping priya.sharma's to the
        sandbox owner.
        """
        from datetime import date
        from decimal import Decimal
        from kanban.budget_models import TimeEntry

        template_task = Task.objects.filter(column__board=self.template_board).first()

        # Primary persona entry — should clone AND remap to the sandbox owner.
        priya = User.objects.create_user(
            'priya.sharma', email='priya.sharma@demo.prizmai.local', password='x',
        )
        UserProfile.objects.get_or_create(user=priya)
        TimeEntry.objects.create(
            task=template_task, user=priya,
            hours_spent=Decimal('4.00'), work_date=date(2026, 7, 1),
        )
        # Real-user pollution on the template — must be skipped by the clone.
        polluter = User.objects.create_user(
            'polluter', email='polluter@gmail.com', password='x',
        )
        UserProfile.objects.get_or_create(user=polluter)
        TimeEntry.objects.create(
            task=template_task, user=polluter,
            hours_spent=Decimal('9.99'), work_date=date(2026, 7, 2),
        )

        self._provision(is_reset=False)
        board = Board.objects.get(owner=self.user, is_sandbox_copy=True)
        sandbox_entries = TimeEntry.objects.filter(task__column__board=board)

        # Owner gets exactly the remapped priya entry; the polluter row is gone.
        self.assertEqual(sandbox_entries.count(), 1)
        entry = sandbox_entries.first()
        self.assertEqual(entry.user_id, self.user.id, 'priya entry must remap to sandbox owner')
        self.assertEqual(entry.hours_spent, Decimal('4.00'))
        self.assertFalse(
            sandbox_entries.filter(user=polluter).exists(),
            'real-user pollution must never be cloned into a sandbox',
        )
