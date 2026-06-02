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


class ReentrancyGuardTest(TestCase):
    """X-07, X-09, T-39: a rule's own side effects must not re-trigger
    automation. Without the guard these loop until RecursionError."""

    def test_comment_added_post_comment_fires_exactly_once(self):
        """T-39 / X-09: comment_added → post_comment posts ONE echo, not a storm."""
        from kanban.models import Comment
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(username='echo_user')
        rule = _make_rule(
            board, user, 'comment_added',
            actions=[{'type': 'post_comment', 'target': None, 'message': 'Echo!'}],
        )

        Comment.objects.create(task=task, user=user, content='hello')

        # Original + exactly one automated echo.
        self.assertEqual(Comment.objects.filter(task=task).count(), 2)
        self.assertEqual(
            AutomationLog.objects.filter(rule=rule).count(), 1,
            'comment_added must fire once, not recurse on its own echo',
        )

    def test_task_created_add_subtask_no_explosion(self):
        """X-07: task_created → add_subtask creates ONE subtask, not N²/∞."""
        from kanban.models import Task
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(username='sub_user')
        rule = _make_rule(
            board, user, 'task_created',
            actions=[{'type': 'add_subtask', 'target': None,
                      'message': 'Investigate {task_title}'}],
        )

        parent = Task.objects.create(column=col, title='Parent', created_by=user)

        subtasks = Task.objects.filter(parent_task=parent)
        self.assertEqual(subtasks.count(), 1, 'exactly one subtask, no explosion')
        # The rule fired once (on the parent); the subtask did not re-fire it.
        self.assertEqual(AutomationLog.objects.filter(rule=rule).count(), 1)


class ActionOutcomeSemanticsTest(TestCase):
    """E-05, E-06, E-07, A-11: the audit-log outcome matches the plan's
    'Should happen' (Failed vs Skipped vs Success)."""

    def _outcome_for(self, action, username, task_kwargs=None):
        from kanban.models import Task
        from kanban.automation_models import AutomationLog
        user, board, col, task = _make_board_with_task(
            username=username, task_kwargs=task_kwargs,
        )
        _make_rule(board, user, 'task_created', actions=[action])
        new_task = Task.objects.create(
            column=col, title='Trigger', created_by=user, **(task_kwargs or {}),
        )
        return AutomationLog.objects.filter(task_affected=new_task).latest('triggered_at')

    def test_invalid_priority_is_failed(self):
        log = self._outcome_for(
            {'type': 'set_priority', 'target': 'blue'}, 'badprio_user',
        )
        self.assertEqual(log.outcome, 'failed')
        self.assertIn('blue', log.error_detail.lower())

    def test_missing_column_is_skipped(self):
        log = self._outcome_for(
            {'type': 'move_to_column', 'target': 'Nonexistent'}, 'badcol_user',
        )
        self.assertEqual(log.outcome, 'skipped')

    def test_missing_label_is_skipped(self):
        log = self._outcome_for(
            {'type': 'add_label', 'target': 'Nonexistent'}, 'badlabel_user',
        )
        self.assertEqual(log.outcome, 'skipped')

    def test_assign_default_no_assignee_is_skipped(self):
        # target omitted → defaults to 'task_assignee'; task has no assignee.
        log = self._outcome_for(
            {'type': 'assign_to_user', 'target': ''}, 'noassign_user',
        )
        self.assertEqual(log.outcome, 'skipped')


class PredictionConfidenceConditionTest(TestCase):
    """C-33: a fractional threshold (0.5) must evaluate, not silently fail."""

    def test_fractional_threshold_matches_low_confidence(self):
        from kanban.automation_conditions import evaluate, TriggerTarget

        user, board, col, low = _make_board_with_task(
            username='conf_low', task_kwargs={'prediction_confidence': 0.3},
        )
        high = type(low).objects.create(
            column=col, title='High conf', created_by=user,
            prediction_confidence=0.9,
        )

        def conf_target(t):
            return TriggerTarget(target_board=board, target_task=t, source=t,
                                 source_type='task')

        self.assertTrue(evaluate('prediction_confidence', 'lte', '0.5', conf_target(low)))
        self.assertFalse(evaluate('prediction_confidence', 'lte', '0.5', conf_target(high)))


class DependencyOverdueSweepTest(TestCase):
    """T-25: a blocked task fires when its blocking dependency is overdue."""

    def test_sweep_fires_on_blocked_task(self):
        from datetime import timedelta
        from kanban.models import Task
        from kanban.automation_models import AutomationLog
        from kanban.tasks.automation_tasks import run_dependency_overdue_automations

        user, board, col, blocker = _make_board_with_task(username='dep_user')
        # Blocker is overdue (due yesterday, not complete).
        blocker.due_date = timezone.now() - timedelta(days=1)
        blocker.progress = 50
        blocker.save()

        blocked = Task.objects.create(column=col, title='Blocked A', created_by=user)
        blocked.dependencies.add(blocker)

        rule = _make_rule(board, user, 'dependency_overdue')
        run_dependency_overdue_automations()

        logs = AutomationLog.objects.filter(rule=rule, task_affected=blocked)
        self.assertEqual(logs.count(), 1)


class TaskCompletedDedupeTest(TestCase):
    """T-02: completing → un-completing → re-completing the same day fires once."""

    def test_recomplete_same_day_does_not_refire(self):
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(
            username='complete_user', task_kwargs={'progress': 50},
        )
        rule = _make_rule(board, user, 'task_completed')

        task.progress = 100
        task.save()

        task.progress = 50
        task.save()
        task.progress = 100
        task.save()

        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 1, 'task_completed must dedupe per calendar day')
