"""
Regression tests for automation trigger firing behavior.

Covers the T-04..T-16 manual test scenarios that surfaced bugs:
duplicate notifications, dead triggers (label_added), incomplete condition
forms, missing dedupe on time-based sweeps. The goal: lock in the fixes so
the same regressions don't sneak back.

Each test follows the same shape:
    1. Create a board + column + task.
    2. Create an AutomationRule with the trigger under test.
    3. Trigger the event.
    4. Assert AutomationLog has exactly the expected number of rows.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone


def _make_board_with_task(username='trig_runner', task_kwargs=None):
    """Minimal setup: user, board, column, task."""
    from kanban.models import Board, Column, Task

    user = User.objects.create_user(
        username=username, password='x', email=f'{username}@example.com',
    )
    board = Board.objects.create(name='Trigger Test Board', created_by=user)
    col = Column.objects.create(board=board, name='Backlog', position=0)
    Column.objects.create(board=board, name='In Progress', position=1)
    Column.objects.create(board=board, name='Done', position=2)
    task = Task.objects.create(
        column=col, title='Test task', created_by=user, **(task_kwargs or {}),
    )
    return user, board, col, task


def _make_rule(board, user, trigger_type, actions=None, trigger_config=None,
               conditions=None):
    from kanban.automation_models import AutomationRule
    return AutomationRule.objects.create(
        board=board, created_by=user,
        name=f'Rule: {trigger_type}',
        trigger_type=trigger_type,
        trigger_config=trigger_config or {},
        condition_logic='AND',
        conditions=conditions or [],
        actions=actions or [
            {'type': 'post_comment', 'target': None, 'message': 'fired'},
        ],
        otherwise_actions=[],
        is_active=True,
    )


class DuplicateFirePreventionTest(TestCase):
    """T-04, T-07, T-15: same rule must not fire twice for one user event."""

    def test_unassigned_fires_once_even_if_task_saved_twice(self):
        """Even if a downstream signal handler re-saves the same Task
        instance, run_board_automations must dedupe to a single log row."""
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task()
        task.assigned_to = user
        task.save()
        rule = _make_rule(board, user, 'task_unassigned')

        # Clear the assignee — should fire the rule
        task.assigned_to = None
        task.save()

        # Simulate a downstream second save on the SAME instance (the
        # pattern that previously double-fired the rule).
        task.save()

        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 1, 'task_unassigned should fire exactly once')

    def test_priority_change_fires_once(self):
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(
            username='prio_user', task_kwargs={'priority': 'medium'},
        )
        rule = _make_rule(
            board, user, 'task_priority_changed',
            trigger_config={'priority': 'urgent'},
        )

        task.priority = 'urgent'
        task.save()
        task.save()  # second save (e.g., from update_task_prediction)

        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 1)

    def test_completion_threshold_does_not_refire_above_threshold(self):
        """T-15: once progress crosses the threshold, subsequent bumps above
        the threshold must NOT re-fire the rule."""
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(
            username='thresh_user', task_kwargs={'progress': 30},
        )
        rule = _make_rule(
            board, user, 'task_completion_threshold',
            trigger_config={'threshold': 50},
        )

        # 30 → 60: crosses threshold, should fire
        task.progress = 60
        task.save()

        # 60 → 70: still above threshold, must NOT re-fire
        task.progress = 70
        task.save()

        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 1)


class StatusChangedFilterTest(TestCase):
    """T-06: from/to column filters on task_status_changed actually constrain
    when the rule fires."""

    def test_from_to_filter_only_fires_on_matching_move(self):
        from kanban.models import Column
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(username='status_user')
        in_progress = Column.objects.get(board=board, name='In Progress')
        done = Column.objects.get(board=board, name='Done')

        rule = _make_rule(
            board, user, 'task_status_changed',
            trigger_config={'from': 'Backlog', 'to': 'In Progress'},
        )

        # Backlog → In Progress: matches both filters, should fire
        task.column = in_progress
        task.save()

        # In Progress → Done: from='In Progress' not 'Backlog', should NOT fire
        task.column = done
        task.save()

        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 1)


class LabelAddedTriggerTest(TestCase):
    """T-11: task_label_added must now actually fire (was dead code)."""

    def test_label_added_fires_rule(self):
        from kanban.models import TaskLabel
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(username='label_user')
        label = TaskLabel.objects.create(board=board, name='Important')
        rule = _make_rule(
            board, user, 'task_label_added',
            trigger_config={'label_name': 'Important'},
        )

        task.labels.add(label)

        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 1, 'task_label_added should fire when matching label is attached')

    def test_label_added_filter_skips_non_matching_label(self):
        from kanban.models import TaskLabel
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(username='label_user2')
        TaskLabel.objects.create(board=board, name='Important')
        bug_label = TaskLabel.objects.create(board=board, name='Bug')
        rule = _make_rule(
            board, user, 'task_label_added',
            trigger_config={'label_name': 'Important'},
        )

        task.labels.add(bug_label)

        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 0, 'rule must not fire when a different label is attached')


class ConditionValueValidationTest(TestCase):
    """Phase 2.5: server-side validation must reject conditions whose operator
    requires a value but value is blank."""

    def setUp(self):
        from kanban.models import Board, Column
        self.user = User.objects.create_user(
            username='val_user', password='x', email='val@example.com',
        )
        self.board = Board.objects.create(name='Val Board', created_by=self.user)
        Column.objects.create(board=self.board, name='To Do', position=0)
        from django.test import Client
        self.client = Client()
        self.client.force_login(self.user)

    def test_rejects_contains_with_empty_value(self):
        import json
        payload = {
            'name': 'Bad rule',
            'trigger_type': 'task_description_updated',
            'trigger_config': {},
            'condition_logic': 'AND',
            'conditions': [
                {'attribute': 'description', 'operator': 'contains', 'value': ''},
            ],
            'actions': [
                {'type': 'post_comment', 'target': None, 'message': 'x'},
            ],
            'otherwise_actions': [],
        }
        resp = self.client.post(
            f'/boards/{self.board.id}/automations/rules/create/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 400)
        body = resp.json()
        joined = ' '.join(body.get('errors', []) + [body.get('error', '')])
        self.assertIn('value', joined.lower())

    def test_accepts_is_empty_without_value(self):
        import json
        payload = {
            'name': 'Good rule',
            'trigger_type': 'task_description_updated',
            'trigger_config': {},
            'condition_logic': 'AND',
            'conditions': [
                {'attribute': 'description', 'operator': 'is_empty', 'value': None},
            ],
            'actions': [
                {'type': 'post_comment', 'target': None, 'message': 'x'},
            ],
            'otherwise_actions': [],
        }
        resp = self.client.post(
            f'/boards/{self.board.id}/automations/rules/create/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertIn(resp.status_code, (200, 201))


class IdleTriggerConfigValidationTest(TestCase):
    """Phase 2.5: task_idle rule must require idle_days config."""

    def setUp(self):
        from kanban.models import Board
        self.user = User.objects.create_user(
            username='idle_user', password='x', email='idle@example.com',
        )
        self.board = Board.objects.create(name='Idle Board', created_by=self.user)
        from django.test import Client
        self.client = Client()
        self.client.force_login(self.user)

    def test_rejects_idle_rule_without_days(self):
        import json
        payload = {
            'name': 'Bad idle rule',
            'trigger_type': 'task_idle',
            'trigger_config': {},
            'condition_logic': 'AND',
            'conditions': [],
            'actions': [
                {'type': 'post_comment', 'target': None, 'message': 'idle'},
            ],
            'otherwise_actions': [],
        }
        resp = self.client.post(
            f'/boards/{self.board.id}/automations/rules/create/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(resp.status_code, 400)
