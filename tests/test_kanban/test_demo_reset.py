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


class DemoTimeEntrySeederDeterminismTestCase(TestCase):
    """The template time-entry seeder must be deterministic across reseeds.

    Regression for the "different Time Tracking data on every Reset Demo" bug:
    ``_create_budget_and_time`` used the unseeded GLOBAL ``random`` module, so the
    number of entries, their hours split, and descriptions changed every reset —
    and the clone/remap/date-refresh downstream faithfully propagated that
    variance to each user's sandbox. The seeder now draws from a local
    ``random.Random(1310)`` so repeated reseeds produce byte-for-byte identical
    time entries (aligned with the deterministic budget/estimate/progress data).
    """

    def _seed_once(self):
        """Run just the time-entry seeder against a fresh board and return a
        stable fingerprint of the TimeEntry rows it produced."""
        from datetime import timedelta
        from decimal import Decimal
        from django.utils import timezone
        from kanban.budget_models import TaskCost, TimeEntry
        from kanban.management.commands.populate_all_demo_data import Command

        creator = User.objects.create_user(f'seeder_{TimeEntry.objects.count()}', password='x')
        board = Board.objects.create(name='Seeder Board', created_by=creator)
        done = Column.objects.create(name='Done', board=board, position=0)

        today = timezone.now().date()
        tasks_by_code = {}
        for i in range(4):
            task = Task.objects.create(
                title=f'Done Task {i}', column=done, position=i,
                progress=100, assigned_to=creator, created_by=creator,
                start_date=today - timedelta(days=20),
                completed_at=timezone.now() - timedelta(days=2),
            )
            TaskCost.objects.create(task=task, estimated_hours=Decimal('24.00'))
            tasks_by_code[f'T{i}'] = task

        cmd = Command()
        cmd.TODAY = today
        cmd.priya = creator
        cmd.board = board
        cmd._create_budget_and_time(tasks_by_code, epics=[])

        rows = list(
            TimeEntry.objects.filter(task__column__board=board)
            .order_by('task__title', 'hours_spent', 'work_date', 'description')
            .values_list('task__title', 'hours_spent', 'work_date', 'description')
        )
        return rows

    def test_time_entries_are_identical_across_reseeds(self):
        first = self._seed_once()
        second = self._seed_once()

        # Sanity: the seeder actually produced a non-trivial set to compare.
        self.assertGreaterEqual(len(first), 4 * 3, 'expected several entries per Done task')
        self.assertEqual(
            [r[1:] for r in first], [r[1:] for r in second],
            'template time entries must be identical across reseeds (deterministic RNG)',
        )


class DemoTimeEntryDateRefreshDeterminismTestCase(TestCase):
    """Time-entry work_date refresh must not depend on primary keys.

    Regression for the "Time Tracking DATES shift on every Reset Demo" bug:
    ``_refresh_time_entry_dates`` used ``entry.id % 30`` to place each entry, but
    a Reset re-clones the sandbox and mints fresh PKs, so the same logical entry
    landed on a different day every reset. The refresh now spreads entries within
    their task's window by ordinal position, so it is stable across re-clones.
    """

    def _make_entries(self, task, user, n):
        from decimal import Decimal
        from datetime import date
        from kanban.budget_models import TimeEntry
        for _ in range(n):
            TimeEntry.objects.create(
                task=task, user=user,
                hours_spent=Decimal('2.00'), work_date=date(2026, 1, 1),
            )

    def test_work_dates_are_pk_independent_and_within_window(self):
        from datetime import timedelta
        from django.utils import timezone
        from kanban.budget_models import TimeEntry
        from kanban.utils.demo_date_refresh import _refresh_time_entry_dates

        user = User.objects.create_user('tt_user', password='x')
        board = Board.objects.create(name='SB', is_sandbox_copy=True, created_by=user)
        col = Column.objects.create(name='Done', board=board, position=0)
        start = timezone.now().date() - timedelta(days=20)
        task = Task.objects.create(
            title='T', column=col, position=0, created_by=user,
            start_date=start, completed_at=timezone.now() - timedelta(days=2),
        )
        base = timezone.now().date()

        self._make_entries(task, user, 5)
        _refresh_time_entry_dates(base)
        first = list(
            TimeEntry.objects.filter(task=task).order_by('id')
            .values_list('work_date', flat=True)
        )

        # Simulate a Reset re-clone: destroy + recreate the entries → new PKs.
        TimeEntry.objects.filter(task=task).delete()
        self._make_entries(task, user, 5)
        _refresh_time_entry_dates(base)
        second = list(
            TimeEntry.objects.filter(task=task).order_by('id')
            .values_list('work_date', flat=True)
        )

        # Same dates despite entirely different primary keys.
        self.assertEqual(first, second, 'work_date must not depend on primary keys')
        # Refresh actually moved the entries off their seed placeholder date.
        self.assertNotIn(__import__('datetime').date(2026, 1, 1), first)
        # And every entry landed inside the task's start->completion window.
        end = timezone.localtime(task.completed_at).date()
        for d in first:
            self.assertTrue(start <= d <= end, f'{d} outside task window {start}..{end}')
