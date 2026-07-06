"""
Rule-Linter Parity + End-to-End Tests
=====================================

The rule builder ships a *client-side* "linter" (``TRIGGER_FIELD_CONSTRAINTS`` in
``static/js/unified_rule_builder.js``) that warns when a chosen trigger and
condition can never align — e.g. ``task_created`` + ``progress >= 30`` can never
fire because a brand-new task always has ``progress = 0``. Each warning is either:

    * ``dead``      — the condition can never be true at that trigger's fire
                      moment, so the rule's THEN would skip every time; or
    * ``pointless`` — the condition is always true at that moment, so it adds
                      nothing.

That linter is JavaScript with no test runner, and a false "dead" warning (on a
rule that *could* fire) is worse than a missing one. These tests are the safety
net: they PROVE every linter verdict against the real Python runtime.

Two layers:
    1. Parity — build the exact task/trigger state the linter reasons about and
       assert ``automation_conditions.evaluate(...)`` returns the constant the
       linter claims (``False`` for ``dead``, ``True`` for ``pointless``). If the
       JS mapping and the Python engine ever diverge, this goes red.
    2. End-to-end — fire a real ``AutomationRule`` through the live engine and
       assert the ``AutomationLog`` outcome, proving the linter's "this rule will
       skip every time" promise is literally true (and that a *pointless* rule
       still fires — the linter never mislabels a working rule as dead).

Hermetic — every test builds its own board/columns/users/task in a rolled-back
transaction. Run under pytest (``kanban_board.test_settings``):

    python -m pytest kanban/tests/test_automation_linter_parity.py -v

NOTE: This file is the Python source of truth for the JS mapping. When you add a
combo to ``TRIGGER_FIELD_CONSTRAINTS``, add its parity assertion here (and vice
versa) so the two can never silently drift.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone


class _LinterTestBase(TestCase):
    """Shared fixtures around the condition registry + the live engine."""

    def setUp(self):
        from kanban.models import Board, Column, Task, TaskLabel

        self.owner = User.objects.create_user(
            username='lint_owner', password='x', email='lint_owner@example.com')
        self.other = User.objects.create_user(
            username='lint_other', password='x', email='lint_other@example.com')

        self.board = Board.objects.create(name='Linter Board', created_by=self.owner)
        self.cols = {}
        for pos, name in enumerate(['Backlog', 'In Progress', 'Done']):
            self.cols[name] = Column.objects.create(
                board=self.board, name=name, position=pos)

    # ── fixtures mirroring each trigger's fire-moment state ──────────────────

    def _fresh_created_task(self, **kw):
        """A task exactly as ``task_created`` sees it: no relations, progress=0.

        ``Task.objects.create`` with defaults reproduces the create-form state
        (the form has no progress/subtask/comment inputs), and the pre_save
        signal stamps ``column_entered_at = now`` on first save — so age,
        idle-days and time-in-column are all 0 at this instant.
        """
        from kanban.models import Task
        kw.setdefault('title', 'Freshly created')
        kw.setdefault('column', self.cols['Backlog'])
        kw.setdefault('created_by', self.owner)
        return Task.objects.create(**kw)

    def _overdue_task(self):
        """A task in the state ``task_overdue`` fires on: past due, incomplete."""
        from kanban.models import Task
        t = Task.objects.create(
            title='Overdue', column=self.cols['In Progress'],
            created_by=self.owner, progress=40,
            due_date=timezone.now() - timedelta(days=3))
        return t

    def _assigned_task(self):
        """A task in the state ``task_assigned`` fires on: assignee present."""
        from kanban.models import Task
        return Task.objects.create(
            title='Assigned', column=self.cols['In Progress'],
            created_by=self.owner, assigned_to=self.other)

    def _target(self, task):
        from kanban.automation_conditions import TriggerTarget
        return TriggerTarget(target_board=self.board, target_task=task,
                             source=task, source_type='task')

    def _eval(self, attr, operator, value, task):
        from kanban.automation_conditions import evaluate
        return evaluate(attr, operator, value, self._target(task))

    def _assert_dead(self, task, attr, operator, value):
        """A ``dead`` linter verdict means the runtime returns False here."""
        got = self._eval(attr, operator, value, task)
        self.assertFalse(
            got, f"linter marks {attr} {operator} {value!r} as DEAD for this "
                 f"trigger, but runtime returned {got!r} (expected False)")

    def _assert_pointless(self, task, attr, operator, value):
        """A ``pointless`` linter verdict means the runtime returns True here."""
        got = self._eval(attr, operator, value, task)
        self.assertTrue(
            got, f"linter marks {attr} {operator} {value!r} as POINTLESS "
                 f"(always-true) for this trigger, but runtime returned {got!r} "
                 f"(expected True)")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2a — parity for the two combos the linter shipped with
# ─────────────────────────────────────────────────────────────────────────────

class ExistingLinterParityTest(_LinterTestBase):
    """The original mapping: task_created x {progress, all_subtasks_done}."""

    def test_task_created_progress_dead_cases(self):
        t = self._fresh_created_task()
        self.assertEqual(t.progress, 0)  # premise: born at 0%
        # "Progress >= N" (N>0) / "= N" (N!=0) / "<= N" (N<0) can never be true.
        self._assert_dead(t, 'progress', 'gte', 30)
        self._assert_dead(t, 'progress', 'gte', 1)
        self._assert_dead(t, 'progress', 'equals', 30)
        self._assert_dead(t, 'progress', 'lte', -1)

    def test_task_created_progress_pointless_cases(self):
        t = self._fresh_created_task()
        # "Progress >= 0" / "= 0" / "<= N" (N>=0) are always true → adds nothing.
        self._assert_pointless(t, 'progress', 'gte', 0)
        self._assert_pointless(t, 'progress', 'equals', 0)
        self._assert_pointless(t, 'progress', 'lte', 0)
        self._assert_pointless(t, 'progress', 'lte', 30)

    def test_task_created_all_subtasks_done_parity(self):
        t = self._fresh_created_task()
        self._assert_dead(t, 'all_subtasks_done', 'is_true', None)      # no subtasks
        self._assert_pointless(t, 'all_subtasks_done', 'is_false', None)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 — parity for the EXPANSION combos before/after they go into the JS
# ─────────────────────────────────────────────────────────────────────────────

class ExpansionLinterParityTest(_LinterTestBase):
    """Every combo added to TRIGGER_FIELD_CONSTRAINTS must be proven here.

    task_created — a related object (subtask/comment/attachment/dependency/time
    entry) cannot exist at the instant of creation, and age/idle/time-in-column
    are all 0, so these conditions reduce to a constant.
    """

    def test_task_created_subtask_count(self):
        t = self._fresh_created_task()
        self._assert_dead(t, 'subtask_count', 'gte', 1)
        self._assert_dead(t, 'subtask_count', 'equals', 1)
        self._assert_pointless(t, 'subtask_count', 'equals', 0)
        self._assert_pointless(t, 'subtask_count', 'lte', 0)
        self._assert_pointless(t, 'subtask_count', 'gte', 0)

    def test_task_created_subtask_completion_pct(self):
        t = self._fresh_created_task()  # no subtasks → pct == 0
        self._assert_dead(t, 'subtask_completion_pct', 'gte', 1)
        self._assert_pointless(t, 'subtask_completion_pct', 'lte', 0)
        self._assert_pointless(t, 'subtask_completion_pct', 'gte', 0)

    def test_task_created_checklist_progress(self):
        t = self._fresh_created_task()  # no checklist → pct == 0
        self._assert_dead(t, 'checklist_progress', 'gte', 1)
        self._assert_pointless(t, 'checklist_progress', 'lte', 0)
        self._assert_pointless(t, 'checklist_progress', 'gte', 0)

    def test_task_created_has_comments(self):
        t = self._fresh_created_task()
        self._assert_dead(t, 'has_comments', 'is_true', None)
        self._assert_dead(t, 'has_comments', 'count_gte', 1)
        self._assert_pointless(t, 'has_comments', 'is_false', None)
        self._assert_pointless(t, 'has_comments', 'count_gte', 0)
        self._assert_pointless(t, 'has_comments', 'count_lte', 0)

    def test_task_created_has_attachments(self):
        t = self._fresh_created_task()
        self._assert_dead(t, 'has_attachments', 'is_true', None)
        self._assert_pointless(t, 'has_attachments', 'is_false', None)

    def test_task_created_has_dependencies(self):
        t = self._fresh_created_task()
        self._assert_dead(t, 'has_dependencies', 'is_true', None)
        self._assert_pointless(t, 'has_dependencies', 'is_false', None)

    def test_task_created_has_blocked_tasks(self):
        t = self._fresh_created_task()
        self._assert_dead(t, 'has_blocked_tasks', 'is_true', None)
        self._assert_pointless(t, 'has_blocked_tasks', 'is_false', None)

    def test_task_created_idle_days(self):
        t = self._fresh_created_task()  # updated_at == now → 0 days idle
        self._assert_dead(t, 'idle_days', 'gte', 1)
        self._assert_pointless(t, 'idle_days', 'lte', 0)
        self._assert_pointless(t, 'idle_days', 'gte', 0)

    def test_task_created_time_in_column(self):
        t = self._fresh_created_task()  # column_entered_at stamped to now → 0 days
        self._assert_dead(t, 'time_in_column', 'gte', 1)
        self._assert_pointless(t, 'time_in_column', 'lte', 0)
        self._assert_pointless(t, 'time_in_column', 'gte', 0)

    def test_task_created_hours_logged(self):
        t = self._fresh_created_task()  # no TimeEntry → 0 hours
        self._assert_dead(t, 'hours_logged', 'gte', 1)
        self._assert_pointless(t, 'hours_logged', 'lte', 0)
        self._assert_pointless(t, 'hours_logged', 'gte', 0)

    # ── trigger-implied field state (other triggers) ─────────────────────────

    def test_task_overdue_due_date(self):
        """An overdue task must HAVE a past due date."""
        t = self._overdue_task()
        self._assert_dead(t, 'due_date', 'is_empty', None)
        self._assert_dead(t, 'due_date', 'within_days', 7)   # due is in the past
        self._assert_pointless(t, 'due_date', 'is_not_empty', None)
        self._assert_pointless(t, 'due_date', 'is_overdue', None)

    def test_task_assigned_assignee(self):
        """A task_assigned event always has an assignee."""
        t = self._assigned_task()
        self._assert_dead(t, 'assignee', 'is_empty', None)
        self._assert_dead(t, 'assignee', 'is', 'none')       # "Unassigned" sentinel
        self._assert_pointless(t, 'assignee', 'is_not_empty', None)

    # ── guardrail: an EXCLUDED field must NOT be treated as constant ─────────

    def test_task_created_form_settable_fields_are_not_dead(self):
        """priority/assignee/due_date/title ARE settable on the create form, so
        the linter must NOT flag them. Prove they can be true at creation."""
        t = self._fresh_created_task(
            priority='urgent', assigned_to=self.other,
            due_date=timezone.now() + timedelta(days=5), title='Ship it')
        self.assertTrue(self._eval('priority', 'is', 'urgent', t))
        self.assertTrue(self._eval('assignee', 'is_not_empty', None, t))
        self.assertTrue(self._eval('due_date', 'is_not_empty', None, t))
        self.assertTrue(self._eval('title', 'contains', 'Ship', t))


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2b — end-to-end: the linter's promise, proven through the live engine
# ─────────────────────────────────────────────────────────────────────────────

class LinterEndToEndTest(_LinterTestBase):
    """Fire real rules and read the AutomationLog the audit trail records."""

    def _make_rule(self, conditions, name='E2E rule'):
        from kanban.automation_models import AutomationRule
        return AutomationRule.objects.create(
            board=self.board, created_by=self.owner, name=name,
            trigger_type='task_created', trigger_config={},
            condition_logic='AND', conditions=conditions,
            actions=[{'type': 'post_comment', 'target': None, 'message': 'fired'}],
            otherwise_actions=[], is_active=True)

    def test_dead_rule_skips_every_time(self):
        """task_created + progress>=30 is 'dead' → engine logs outcome=skipped."""
        from kanban.automation_models import AutomationLog
        rule = self._make_rule(
            [{'attribute': 'progress', 'operator': 'gte', 'value': 30}],
            name='DEAD: created + progress>=30')
        task = self._fresh_created_task(title='Should not fire')
        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 1, 'expected exactly one audit entry')
        self.assertEqual(logs.first().outcome, 'skipped')

    def test_pointless_rule_still_fires(self):
        """task_created + progress>=0 is 'pointless' (always true) but MUST still
        fire — the linter never turns a working rule into a dead one."""
        from kanban.automation_models import AutomationLog
        rule = self._make_rule(
            [{'attribute': 'progress', 'operator': 'gte', 'value': 0}],
            name='POINTLESS: created + progress>=0')
        task = self._fresh_created_task(title='Should fire')
        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().outcome, 'success')

    def test_expansion_dead_rule_skips(self):
        """A newly-covered combo (created + has_comments is_true) also skips."""
        from kanban.automation_models import AutomationLog
        rule = self._make_rule(
            [{'attribute': 'has_comments', 'operator': 'is_true', 'value': None}],
            name='DEAD: created + has_comments')
        task = self._fresh_created_task(title='No comments yet')
        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().outcome, 'skipped')
