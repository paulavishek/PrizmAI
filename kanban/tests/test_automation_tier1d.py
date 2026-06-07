"""
Tier 1d — Branch logic (condition gating) through the live engine.

Where tier1a–c verify each condition's truth value in isolation (the matrix),
this battery fires *real* rules with conditions through the automation engine
(``task_assigned`` trigger) and asserts the end-to-end outcome:

  * condition met            → THEN actions run, AutomationLog outcome 'success'
  * condition not met, no else→ outcome 'skipped' (skip_reason "Condition not met")
  * condition not met + else  → OTHERWISE actions run, outcome 'success'
  * AND logic                → all conditions must hold
  * OR logic                 → any condition holds
  * empty conditions         → always runs

The effect of each branch is distinguished by the value it writes (THEN sets
progress 90, OTHERWISE sets progress 10), so we can prove *which* branch ran.

Run under pytest (``kanban_board.test_settings``):

    python -m pytest kanban/tests/test_automation_tier1d.py -v
"""

from django.contrib.auth.models import User
from django.test import TestCase


class Tier1dBranchLogicTest(TestCase):
    """Condition gating + AND/OR + OTHERWISE fallback, end-to-end."""

    def setUp(self):
        from kanban.automation_models import AutomationRule
        from kanban.models import Board, Column, Task

        self.AutomationRule = AutomationRule
        self.tester = User.objects.create_user(
            username='t1d_tester', password='x', email='t1d_tester@example.com')
        self.priya = User.objects.create_user(
            username='t1d_priya', password='x', email='t1d_priya@example.com')
        self.marcus = User.objects.create_user(
            username='t1d_marcus', password='x', email='t1d_marcus@example.com')

        self.board = Board.objects.create(name='T1D Board', created_by=self.tester)
        self.cols = {}
        for pos, name in enumerate(['To Do', 'In Progress', 'Done']):
            self.cols[name] = Column.objects.create(board=self.board, name=name, position=pos)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _task(self, **kw):
        from kanban.models import Task
        kw.setdefault('title', 'T1D-TASK')
        kw.setdefault('column', self.cols['To Do'])
        kw.setdefault('created_by', self.tester)
        kw.setdefault('assigned_to', self.tester)
        kw.setdefault('priority', 'medium')
        kw.setdefault('progress', 30)
        return Task.objects.create(**kw)

    def _make_rule(self, name, conditions, actions, otherwise_actions=None,
                   condition_logic='AND'):
        return self.AutomationRule.objects.create(
            board=self.board, created_by=self.tester, name=name,
            trigger_type='task_assigned', trigger_config={},
            conditions=conditions, condition_logic=condition_logic,
            actions=actions, otherwise_actions=otherwise_actions or [],
            is_active=True,
        )

    def _fire(self, task, new_assignee):
        from kanban.models import Task
        fresh = Task.objects.get(pk=task.pk)
        fresh.assigned_to = new_assignee
        fresh.save()

    def _log(self, rule, task):
        from kanban.automation_models import AutomationLog
        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(
            logs.count(), 1,
            f'expected exactly 1 log, got {list(logs.values_list("outcome", flat=True))}')
        return logs.first()

    def _reload(self, task):
        from kanban.models import Task
        return Task.objects.get(pk=task.pk)

    THEN = [{'type': 'set_progress', 'target': '90'}]
    OTHERWISE = [{'type': 'set_progress', 'target': '10'}]

    # ── condition met → THEN ──────────────────────────────────────────────────

    def test_condition_met_runs_then(self):
        task = self._task(priority='urgent', progress=30)
        rule = self._make_rule(
            'T1D-01: met → THEN',
            conditions=[{'attribute': 'priority', 'operator': 'is', 'value': 'urgent'}],
            actions=self.THEN)
        self._fire(task, self.priya)
        self.assertEqual(self._log(rule, task).outcome, 'success')
        self.assertEqual(self._reload(task).progress, 90)

    # ── condition not met, no otherwise → skipped ─────────────────────────────

    def test_condition_not_met_no_otherwise_skips(self):
        task = self._task(priority='low', progress=30)
        rule = self._make_rule(
            'T1D-02: not met → skipped',
            conditions=[{'attribute': 'priority', 'operator': 'is', 'value': 'urgent'}],
            actions=self.THEN)
        self._fire(task, self.priya)
        log = self._log(rule, task)
        self.assertEqual(log.outcome, 'skipped')
        self.assertIn('condition not met', log.skip_reason.lower())
        self.assertEqual(log.execution_detail.get('branch'), 'skipped')
        self.assertEqual(self._reload(task).progress, 30)   # untouched

    # ── condition not met + otherwise → OTHERWISE ─────────────────────────────

    def test_otherwise_runs_when_condition_not_met(self):
        task = self._task(priority='low', progress=30)
        rule = self._make_rule(
            'T1D-03: not met → OTHERWISE',
            conditions=[{'attribute': 'priority', 'operator': 'is', 'value': 'urgent'}],
            actions=self.THEN, otherwise_actions=self.OTHERWISE)
        self._fire(task, self.priya)
        log = self._log(rule, task)
        self.assertEqual(log.outcome, 'success')
        self.assertEqual(self._reload(task).progress, 10)   # OTHERWISE branch ran
        # NOTE-1D-01 fix: the audit log records the real branch, not always 'then'.
        self.assertEqual(log.execution_detail.get('branch'), 'otherwise')

    def test_otherwise_skipped_when_condition_met(self):
        task = self._task(priority='urgent', progress=30)
        rule = self._make_rule(
            'T1D-04: met → THEN (otherwise present but unused)',
            conditions=[{'attribute': 'priority', 'operator': 'is', 'value': 'urgent'}],
            actions=self.THEN, otherwise_actions=self.OTHERWISE)
        self._fire(task, self.priya)
        log = self._log(rule, task)
        self.assertEqual(log.outcome, 'success')
        self.assertEqual(self._reload(task).progress, 90)   # THEN branch ran
        self.assertEqual(log.execution_detail.get('branch'), 'then')

    # ── AND logic ─────────────────────────────────────────────────────────────

    def test_and_logic_all_true_runs_then(self):
        task = self._task(priority='urgent', progress=60)
        rule = self._make_rule(
            'T1D-05: AND all true',
            conditions=[
                {'attribute': 'priority', 'operator': 'is', 'value': 'urgent'},
                {'attribute': 'progress', 'operator': 'gte', 'value': '50'},
            ],
            actions=self.THEN, condition_logic='AND')
        self._fire(task, self.priya)
        self.assertEqual(self._log(rule, task).outcome, 'success')
        self.assertEqual(self._reload(task).progress, 90)

    def test_and_logic_one_false_skips(self):
        task = self._task(priority='urgent', progress=40)   # second cond fails
        rule = self._make_rule(
            'T1D-06: AND one false',
            conditions=[
                {'attribute': 'priority', 'operator': 'is', 'value': 'urgent'},
                {'attribute': 'progress', 'operator': 'gte', 'value': '50'},
            ],
            actions=self.THEN, condition_logic='AND')
        self._fire(task, self.priya)
        self.assertEqual(self._log(rule, task).outcome, 'skipped')
        self.assertEqual(self._reload(task).progress, 40)

    # ── OR logic ──────────────────────────────────────────────────────────────

    def test_or_logic_one_true_runs_then(self):
        task = self._task(priority='low', progress=60)      # only second cond true
        rule = self._make_rule(
            'T1D-07: OR one true',
            conditions=[
                {'attribute': 'priority', 'operator': 'is', 'value': 'urgent'},
                {'attribute': 'progress', 'operator': 'gte', 'value': '50'},
            ],
            actions=self.THEN, condition_logic='OR')
        self._fire(task, self.priya)
        self.assertEqual(self._log(rule, task).outcome, 'success')
        self.assertEqual(self._reload(task).progress, 90)

    def test_or_logic_all_false_skips(self):
        task = self._task(priority='low', progress=40)      # both conds false
        rule = self._make_rule(
            'T1D-08: OR all false',
            conditions=[
                {'attribute': 'priority', 'operator': 'is', 'value': 'urgent'},
                {'attribute': 'progress', 'operator': 'gte', 'value': '50'},
            ],
            actions=self.THEN, condition_logic='OR')
        self._fire(task, self.priya)
        self.assertEqual(self._log(rule, task).outcome, 'skipped')
        self.assertEqual(self._reload(task).progress, 40)

    # ── empty conditions → always runs (baseline) ─────────────────────────────

    def test_empty_conditions_always_runs(self):
        task = self._task(priority='low', progress=30)
        rule = self._make_rule(
            'T1D-09: no conditions',
            conditions=[], actions=self.THEN)
        self._fire(task, self.priya)
        self.assertEqual(self._log(rule, task).outcome, 'success')
        self.assertEqual(self._reload(task).progress, 90)
