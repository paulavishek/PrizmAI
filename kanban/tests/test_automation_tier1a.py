"""
Tier 1a Condition Battery — core task-field conditions (matrix).

Covers Battery 1a (8) + Battery 1b (10) = 18 condition attributes by calling the
registry entry point ``automation_conditions.evaluate(attribute, operator, value,
target)`` directly against real DB fixtures. This is the fast "matrix" layer: it
asserts each operator's TRUE and FALSE outcome without running the full signal
pipeline. Branch logic (AND/OR/OTHERWISE through the live engine) is in
``test_automation_tier1d.py``.

Battery 1a: priority, assignee, column, label, progress, all_subtasks_done,
            due_date, stale_high_priority
Battery 1b: status, created_by, start_date, description, title,
            checklist_progress, has_comments, has_attachments, idle_days,
            time_in_column

Hermetic — every test builds its own board/columns/users/task in a rolled-back
transaction. Run under pytest (``kanban_board.test_settings``):

    python -m pytest kanban/tests/test_automation_tier1a.py -v
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone


class _ConditionTestBase(TestCase):
    """Shared fixtures + a single ``_assert`` helper around the registry."""

    def setUp(self):
        from kanban.models import Board, Column, Task, TaskLabel

        self.tester = User.objects.create_user(
            username='t1_tester', password='x', email='t1_tester@example.com')
        self.priya = User.objects.create_user(
            username='t1_priya', password='x', email='t1_priya@example.com')

        self.board = Board.objects.create(name='T1 Board', created_by=self.tester)
        self.cols = {}
        for pos, name in enumerate(['Backlog', 'To Do', 'In Progress', 'In Review', 'Done']):
            self.cols[name] = Column.objects.create(board=self.board, name=name, position=pos)

        self.bug = TaskLabel.objects.create(board=self.board, name='Bug', color='#ef4444')
        self.feature = TaskLabel.objects.create(board=self.board, name='Feature', color='#3b82f6')

    # ── helpers ──────────────────────────────────────────────────────────────

    def _task(self, **kw):
        from kanban.models import Task
        kw.setdefault('title', 'T1-TASK')
        kw.setdefault('column', self.cols['To Do'])
        kw.setdefault('created_by', self.tester)
        kw.setdefault('assigned_to', self.tester)
        kw.setdefault('priority', 'medium')
        kw.setdefault('progress', 30)
        return Task.objects.create(**kw)

    def _target(self, task):
        from kanban.automation_conditions import TriggerTarget
        return TriggerTarget(target_board=self.board, target_task=task,
                             source=task, source_type='task')

    def _assert(self, attr, operator, value, task, expected):
        from kanban.automation_conditions import evaluate
        got = evaluate(attr, operator, value, self._target(task))
        self.assertEqual(
            got, expected,
            f'{attr} {operator} {value!r}: expected {expected}, got {got}')

    @staticmethod
    def _backdate(task, **fields):
        """Set auto_now/auto_now_add fields via ``.update()`` to bypass auto-stamp."""
        from kanban.models import Task
        Task.objects.filter(pk=task.pk).update(**fields)
        return Task.objects.get(pk=task.pk)


class Tier1aCoreConditionsTest(_ConditionTestBase):
    """Battery 1a — the 8 most-used task-state conditions."""

    def test_priority(self):
        t = self._task(priority='urgent')
        self._assert('priority', 'is', 'urgent', t, True)
        self._assert('priority', 'is', 'Urgent', t, True)          # case-insensitive
        self._assert('priority', 'is', 'low', t, False)
        self._assert('priority', 'is_not', 'low', t, True)
        self._assert('priority', 'is_not', 'urgent', t, False)
        self._assert('priority', 'is_not_empty', None, t, True)
        blank = self._task(priority='')
        self._assert('priority', 'is_empty', None, blank, True)
        self._assert('priority', 'is_not_empty', None, blank, False)

    def test_assignee(self):
        assigned = self._task(assigned_to=self.priya)
        unassigned = self._task(assigned_to=None)
        self._assert('assignee', 'is_not_empty', None, assigned, True)
        self._assert('assignee', 'is_empty', None, assigned, False)
        self._assert('assignee', 'is_empty', None, unassigned, True)
        self._assert('assignee', 'is', str(self.priya.id), assigned, True)
        self._assert('assignee', 'is', str(self.tester.id), assigned, False)
        self._assert('assignee', 'is_not', str(self.tester.id), assigned, True)
        # Sentinel "none" == Unassigned.
        self._assert('assignee', 'is', 'none', unassigned, True)
        self._assert('assignee', 'is', 'none', assigned, False)
        self._assert('assignee', 'is_not', 'none', assigned, True)

    def test_column_and_status(self):
        t = self._task(column=self.cols['In Review'])
        for attr in ('column', 'status'):           # status is an alias of column
            self._assert(attr, 'is', 'In Review', t, True)
            self._assert(attr, 'is', 'in review', t, True)          # case-insensitive
            self._assert(attr, 'is', 'To Do', t, False)
            self._assert(attr, 'is_not', 'To Do', t, True)
            self._assert(attr, 'is_not', 'In Review', t, False)

    def test_label(self):
        t = self._task()
        t.labels.set([self.bug])
        self._assert('label', 'has', 'Bug', t, True)
        self._assert('label', 'has', 'Feature', t, False)
        self._assert('label', 'does_not_have', 'Feature', t, True)
        self._assert('label', 'does_not_have', 'Bug', t, False)
        self._assert('label', 'is_not_empty', None, t, True)
        nolabel = self._task()
        self._assert('label', 'is_empty', None, nolabel, True)
        self._assert('label', 'is_not_empty', None, nolabel, False)

    def test_progress(self):
        t = self._task(progress=50)
        self._assert('progress', 'gte', '50', t, True)
        self._assert('progress', 'gte', '51', t, False)
        self._assert('progress', 'lte', '50', t, True)
        self._assert('progress', 'lte', '49', t, False)
        self._assert('progress', 'equals', '50', t, True)
        self._assert('progress', 'equals', '49', t, False)

    def test_all_subtasks_done(self):
        parent_done = self._task(title='parent-done')
        self._task(title='c1', parent_task=parent_done, progress=100)
        self._task(title='c2', parent_task=parent_done, progress=100)
        self._assert('all_subtasks_done', 'is_true', None, parent_done, True)
        self._assert('all_subtasks_done', 'is_false', None, parent_done, False)

        parent_mixed = self._task(title='parent-mixed')
        self._task(title='c3', parent_task=parent_mixed, progress=100)
        self._task(title='c4', parent_task=parent_mixed, progress=40)
        self._assert('all_subtasks_done', 'is_true', None, parent_mixed, False)
        self._assert('all_subtasks_done', 'is_false', None, parent_mixed, True)

        # No subtasks → handler defines result as False.
        leaf = self._task(title='leaf')
        self._assert('all_subtasks_done', 'is_true', None, leaf, False)
        self._assert('all_subtasks_done', 'is_false', None, leaf, True)

    def test_due_date(self):
        future = self._task(due_date=timezone.now() + timedelta(days=3))
        past = self._task(due_date=timezone.now() - timedelta(days=2))
        nodue = self._task(due_date=None)
        self._assert('due_date', 'is_empty', None, nodue, True)
        self._assert('due_date', 'is_empty', None, future, False)
        self._assert('due_date', 'is_not_empty', None, future, True)
        self._assert('due_date', 'is_overdue', None, past, True)
        self._assert('due_date', 'is_overdue', None, future, False)
        self._assert('due_date', 'within_days', '7', future, True)
        self._assert('due_date', 'within_days', '1', future, False)   # 3 days out
        self._assert('due_date', 'within_days', '7', past, False)     # already overdue

    def test_stale_high_priority(self):
        stale = self._task(priority='high')
        stale = self._backdate(stale, updated_at=timezone.now() - timedelta(days=10))
        self._assert('stale_high_priority', 'is_true', None, stale, True)
        self._assert('stale_high_priority', 'is_false', None, stale, False)

        fresh_high = self._task(priority='high')        # updated just now
        self._assert('stale_high_priority', 'is_true', None, fresh_high, False)
        self._assert('stale_high_priority', 'is_false', None, fresh_high, True)

        stale_low = self._task(priority='low')
        stale_low = self._backdate(stale_low, updated_at=timezone.now() - timedelta(days=10))
        self._assert('stale_high_priority', 'is_true', None, stale_low, False)


class Tier1bCoreFieldConditionsTest(_ConditionTestBase):
    """Battery 1b — the 10 remaining core task-field conditions."""

    def test_created_by(self):
        t = self._task(created_by=self.priya)
        self._assert('created_by', 'is', str(self.priya.id), t, True)
        self._assert('created_by', 'is', str(self.tester.id), t, False)
        self._assert('created_by', 'is_not', str(self.tester.id), t, True)
        self._assert('created_by', 'is_not_empty', None, t, True)

    def test_start_date(self):
        today = timezone.now().date()
        past = self._task(start_date=today - timedelta(days=2))
        soon = self._task(start_date=today + timedelta(days=3))
        none = self._task(start_date=None)
        self._assert('start_date', 'is_empty', None, none, True)
        self._assert('start_date', 'is_not_empty', None, past, True)
        self._assert('start_date', 'is_past', None, past, True)
        self._assert('start_date', 'is_past', None, soon, False)
        today_task = self._task(start_date=today)
        self._assert('start_date', 'is_today', None, today_task, True)
        self._assert('start_date', 'is_today', None, past, False)
        self._assert('start_date', 'within_days', '7', soon, True)
        self._assert('start_date', 'within_days', '1', soon, False)

    def test_description(self):
        t = self._task(description='Implement the spec for login')
        self._assert('description', 'contains', 'spec', t, True)
        self._assert('description', 'contains', 'SPEC', t, True)       # case-insensitive
        self._assert('description', 'contains', 'logout', t, False)
        self._assert('description', 'does_not_contain', 'logout', t, True)
        self._assert('description', 'does_not_contain', 'spec', t, False)
        self._assert('description', 'is_not_empty', None, t, True)
        blank = self._task(description='   ')
        self._assert('description', 'is_empty', None, blank, True)

    def test_title(self):
        t = self._task(title='Fix the login bug')
        self._assert('title', 'contains', 'login', t, True)
        self._assert('title', 'contains', 'LOGIN', t, True)
        self._assert('title', 'contains', 'payment', t, False)
        self._assert('title', 'does_not_contain', 'payment', t, True)
        self._assert('title', 'does_not_contain', 'login', t, False)

    def test_checklist_progress(self):
        from kanban.models import ChecklistItem
        t = self._task()
        ChecklistItem.objects.create(task=t, title='a', is_completed=True)
        ChecklistItem.objects.create(task=t, title='b', is_completed=True)
        ChecklistItem.objects.create(task=t, title='c', is_completed=False)
        # 2/3 → 66%
        self._assert('checklist_progress', 'gte', '60', t, True)
        self._assert('checklist_progress', 'gte', '67', t, False)
        self._assert('checklist_progress', 'lte', '66', t, True)
        self._assert('checklist_progress', 'lte', '65', t, False)
        # No checklist → percentage treated as 0.
        empty = self._task()
        self._assert('checklist_progress', 'lte', '0', empty, True)
        self._assert('checklist_progress', 'gte', '1', empty, False)

    def test_has_comments(self):
        from kanban.models import Comment
        t = self._task()
        self._assert('has_comments', 'is_false', None, t, True)
        self._assert('has_comments', 'is_true', None, t, False)
        Comment.objects.create(task=t, user=self.tester, content='hi')
        Comment.objects.create(task=t, user=self.tester, content='there')
        self._assert('has_comments', 'is_true', None, t, True)
        self._assert('has_comments', 'count_gte', '2', t, True)
        self._assert('has_comments', 'count_gte', '3', t, False)
        self._assert('has_comments', 'count_lte', '2', t, True)
        self._assert('has_comments', 'count_lte', '1', t, False)

    def test_has_attachments(self):
        from kanban.models import TaskFile
        t = self._task()
        self._assert('has_attachments', 'is_false', None, t, True)
        self._assert('has_attachments', 'is_true', None, t, False)
        TaskFile.objects.create(
            task=t, uploaded_by=self.tester, file='tasks/x.pdf',
            filename='x.pdf', file_size=10, file_type='pdf')
        self._assert('has_attachments', 'is_true', None, t, True)
        self._assert('has_attachments', 'is_false', None, t, False)

    def test_idle_days(self):
        t = self._task()
        t = self._backdate(t, updated_at=timezone.now() - timedelta(days=5))
        self._assert('idle_days', 'gte', '5', t, True)
        self._assert('idle_days', 'gte', '6', t, False)
        self._assert('idle_days', 'lte', '5', t, True)
        self._assert('idle_days', 'lte', '4', t, False)

    def test_time_in_column(self):
        t = self._task()
        t = self._backdate(t, column_entered_at=timezone.now() - timedelta(days=4))
        self._assert('time_in_column', 'gte', '4', t, True)
        self._assert('time_in_column', 'gte', '5', t, False)
        self._assert('time_in_column', 'lte', '4', t, True)
        self._assert('time_in_column', 'lte', '3', t, False)
