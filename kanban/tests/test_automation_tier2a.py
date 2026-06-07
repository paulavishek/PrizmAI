"""
Tier 2a Action Battery — engine-level regression suite.

Exercises all 13 "Task State" automation actions through the real engine:
each test creates a single rule (trigger ``task_assigned``, no conditions, one
action), fires it by reassigning the task, then asserts (a) exactly ONE
``AutomationLog`` success row — the plan's core "no duplicates" invariant — and
(b) the task field changed to the expected value.

Hermetic: every test builds its own board/columns/task/users in a rolled-back
transaction, so it never touches the seeded live demo board. Run under pytest
(``kanban_board.test_settings`` → Celery eager, in-memory broker):

    python -m pytest kanban/tests/test_automation_tier2a.py -v

Mirrors the shape of ``test_automation_triggers.py``.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

ORIGINAL_DESCRIPTION = 'Original description text — Tier 2a test task'


class Tier2aTaskStateActionsTest(TestCase):
    """A-01 … A-13 — one action per test, one Audit Log row expected each."""

    def setUp(self):
        from kanban.automation_models import AutomationRule
        from kanban.models import Board, Column, Task, TaskLabel

        self.AutomationRule = AutomationRule

        self.tester = User.objects.create_user(
            username='t2a_tester', password='x', email='t2a_tester@example.com')
        self.priya = User.objects.create_user(
            username='priya.sharma', password='x', email='priya@example.com')
        self.marcus = User.objects.create_user(
            username='marcus.chen', password='x', email='marcus@example.com')

        self.board = Board.objects.create(name='Software Development', created_by=self.tester)
        cols = {}
        for pos, name in enumerate(['Backlog', 'To Do', 'In Progress', 'In Review', 'Done']):
            cols[name] = Column.objects.create(board=self.board, name=name, position=pos)
        self.cols = cols

        self.bug = TaskLabel.objects.create(board=self.board, name='Bug', color='#ef4444')
        self.feature = TaskLabel.objects.create(board=self.board, name='Feature', color='#3b82f6')

        self.task = Task.objects.create(
            title='TIER2A-TEST',
            column=cols['To Do'],
            created_by=self.tester,
            assigned_to=self.tester,
            priority='medium',
            progress=30,
            description=ORIGINAL_DESCRIPTION,
            due_date=timezone.now() + timedelta(days=7),
            start_date=None,
        )
        self.task.labels.set([self.bug])

    # ── helpers ──────────────────────────────────────────────────────────────

    def _make_rule(self, name, actions):
        return self.AutomationRule.objects.create(
            board=self.board, created_by=self.tester, name=name,
            trigger_type='task_assigned', trigger_config={},
            conditions=[], condition_logic='AND',
            actions=actions, otherwise_actions=[], is_active=True,
        )

    def _fire(self, new_assignee):
        """Fire ``task_assigned`` by reassigning the task. Re-fetch first so the
        per-instance ``_automation_rules_fired`` guard starts fresh, exactly as
        it would across two HTTP requests."""
        from kanban.models import Task
        task = Task.objects.get(pk=self.task.pk)
        task.assigned_to = new_assignee
        task.save()

    def _assert_one_success(self, rule):
        from kanban.automation_models import AutomationLog
        logs = AutomationLog.objects.filter(rule=rule, task_affected=self.task)
        self.assertEqual(logs.count(), 1,
                         f'expected exactly 1 log, got {list(logs.values_list("outcome", flat=True))}')
        self.assertEqual(logs.first().outcome, 'success')

    def _reload(self):
        from kanban.models import Task
        return Task.objects.get(pk=self.task.pk)

    # ── A-01 Set priority ────────────────────────────────────────────────────

    def test_a01_set_priority(self):
        rule = self._make_rule('TIER2A-A01: Set priority',
                               [{'type': 'set_priority', 'target': 'urgent'}])
        self._fire(self.priya)
        self._assert_one_success(rule)
        self.assertEqual(self._reload().priority, 'urgent')

    # ── A-02 Set progress % ──────────────────────────────────────────────────

    def test_a02_set_progress(self):
        rule = self._make_rule('TIER2A-A02: Set progress',
                               [{'type': 'set_progress', 'target': '75'}])
        self._fire(self.priya)
        self._assert_one_success(rule)
        self.assertEqual(self._reload().progress, 75)

    # ── A-03 Set description (replace) ────────────────────────────────────────

    def test_a03_set_description(self):
        new_text = 'AUTOMATED: This description was set by Tier 2a rule A-03'
        rule = self._make_rule('TIER2A-A03: Set description',
                               [{'type': 'set_description', 'message': new_text}])
        self._fire(self.priya)
        self._assert_one_success(rule)
        desc = self._reload().description
        self.assertEqual(desc, new_text)
        self.assertNotIn('Original description text', desc)

    # ── A-04 Append to description ────────────────────────────────────────────

    def test_a04_append_to_description(self):
        addition = '[APPENDED by A-04 rule]'
        rule = self._make_rule('TIER2A-A04: Append description',
                               [{'type': 'append_to_description', 'message': addition}])
        self._fire(self.priya)
        self._assert_one_success(rule)
        desc = self._reload().description
        self.assertIn('Original description text', desc)  # original preserved
        self.assertIn(addition, desc)                     # appended below

    # ── A-05 Add label ───────────────────────────────────────────────────────

    def test_a05_add_label(self):
        rule = self._make_rule('TIER2A-A05: Add label',
                               [{'type': 'add_label', 'target': 'Feature'}])
        self._fire(self.priya)
        self._assert_one_success(rule)
        names = set(self._reload().labels.values_list('name', flat=True))
        self.assertEqual(names, {'Bug', 'Feature'})  # Bug NOT removed

    # ── A-06 Remove label ────────────────────────────────────────────────────

    def test_a06_remove_label(self):
        rule = self._make_rule('TIER2A-A06: Remove label',
                               [{'type': 'remove_label', 'target': 'Bug'}])
        self._fire(self.priya)
        self._assert_one_success(rule)
        names = set(self._reload().labels.values_list('name', flat=True))
        self.assertEqual(names, set())

    # ── A-07 Assign to user (overwrites the trigger assignee) ────────────────

    def test_a07_assign_to_user(self):
        rule = self._make_rule('TIER2A-A07: Assign to user',
                               [{'type': 'assign_to_user', 'target': str(self.priya.id)}])
        self._fire(self.marcus)            # trigger sets marcus; action must overwrite to priya
        self._assert_one_success(rule)     # and must NOT loop into a 2nd log
        self.assertEqual(self._reload().assigned_to_id, self.priya.id)

    # ── A-08 Clear assignee ──────────────────────────────────────────────────

    def test_a08_clear_assignee(self):
        rule = self._make_rule('TIER2A-A08: Clear assignee',
                               [{'type': 'clear_assignee'}])
        self._fire(self.priya)             # trigger sets priya; action clears it
        self._assert_one_success(rule)
        self.assertIsNone(self._reload().assigned_to_id)

    # ── A-09 Move to column ──────────────────────────────────────────────────

    def test_a09_move_to_column(self):
        rule = self._make_rule('TIER2A-A09: Move to column',
                               [{'type': 'move_to_column', 'target': 'In Review'}])
        self._fire(self.priya)
        self._assert_one_success(rule)
        self.assertEqual(self._reload().column.name, 'In Review')

    # ── A-10 Set due date ────────────────────────────────────────────────────

    def test_a10_set_due_date(self):
        rule = self._make_rule('TIER2A-A10: Set due date',
                               [{'type': 'set_due_date', 'target': 'in_14_days'}])
        base = timezone.now().date()  # capture just before firing
        self._fire(self.priya)
        self._assert_one_success(rule)
        due = self._reload().due_date
        actual = due.date() if hasattr(due, 'date') else due
        # Intent: due date moved to ~+14 days. The handler writes a naive
        # local-midnight value; under USE_TZ this can land ±1 day in UTC on
        # read-back, so assert a 14±1 day delta rather than an exact date.
        delta = (actual - base).days
        self.assertTrue(13 <= delta <= 15, f'due date delta was {delta} days, expected ~14')

    # ── A-11 Set start date ──────────────────────────────────────────────────

    def test_a11_set_start_date(self):
        rule = self._make_rule('TIER2A-A11: Set start date',
                               [{'type': 'set_start_date', 'target': 'today'}])
        base = timezone.now().date()  # capture just before firing
        self._fire(self.priya)
        self._assert_one_success(rule)
        start = self._reload().start_date
        actual = start.date() if hasattr(start, 'date') else start
        # Intent: start date set to ~today (was blank). Allow ±1 day for the
        # same naive-midnight / USE_TZ read-back shift as A-10.
        delta = (actual - base).days
        self.assertTrue(-1 <= delta <= 1, f'start date delta was {delta} days, expected ~0')

    # ── A-12 Clear due date ──────────────────────────────────────────────────

    def test_a12_clear_due_date(self):
        rule = self._make_rule('TIER2A-A12: Clear due date',
                               [{'type': 'clear_due_date'}])
        self._fire(self.priya)
        self._assert_one_success(rule)
        self.assertIsNone(self._reload().due_date)

    # ── A-13 Close task (progress→100; column unchanged) ─────────────────────

    def test_a13_close_task(self):
        rule = self._make_rule('TIER2A-A13: Close task',
                               [{'type': 'close_task'}])
        self._fire(self.priya)
        self._assert_one_success(rule)
        task = self._reload()
        self.assertEqual(task.progress, 100)
        # close_task writes via .update() — it does NOT move the column.
        self.assertEqual(task.column.name, 'To Do')
