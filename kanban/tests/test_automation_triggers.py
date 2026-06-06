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

    def test_assigned_fires_once_even_if_task_saved_twice(self):
        """A single assignment that triggers two task.save() calls (e.g. the
        update view followed by update_task_prediction) must log exactly one
        task_assigned fire, not a duplicate."""
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(username='assign_user')
        assignee = User.objects.create_user(
            username='assignee_a', password='x', email='a@example.com',
        )
        rule = _make_rule(board, user, 'task_assigned')

        task.assigned_to = assignee
        task.save()
        task.save()  # downstream re-save on the same instance

        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 1, 'task_assigned should fire exactly once')

    def test_assigned_refires_when_reassigned_to_different_user(self):
        """The per-day dedupe is keyed on the assignee, so handing the task to a
        genuinely different person on the same day must fire again. A real
        reassignment arrives in a later request — model that by re-fetching the
        Task so the in-memory per-instance guard starts fresh, exactly as it
        would across two HTTP requests."""
        from kanban.automation_models import AutomationLog
        from kanban.models import Task

        user, board, col, task = _make_board_with_task(username='reassign_user')
        a = User.objects.create_user(username='user_a', password='x', email='a2@example.com')
        b = User.objects.create_user(username='user_b', password='x', email='b2@example.com')
        rule = _make_rule(board, user, 'task_assigned')

        task.assigned_to = a
        task.save()

        # Second request: fresh instance, new assignee.
        task = Task.objects.get(pk=task.pk)
        task.assigned_to = b
        task.save()

        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 2, 'reassignment to a new user should fire again')

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
        # Blocker is overdue (not complete). Use 2 days ago, not 1: the sweep
        # compares due_date__lt=today (date-truncated in the active timezone),
        # so a ~24h-ago timestamp straddles the local midnight boundary and made
        # this test flaky between ~00:00–05:30 IST. 2 days is unambiguously past.
        blocker.due_date = timezone.now() - timedelta(days=2)
        blocker.progress = 50
        blocker.save()

        blocked = Task.objects.create(column=col, title='Blocked A', created_by=user)
        blocked.dependencies.add(blocker)

        rule = _make_rule(board, user, 'dependency_overdue')
        run_dependency_overdue_automations()

        logs = AutomationLog.objects.filter(rule=rule, task_affected=blocked)
        self.assertEqual(logs.count(), 1)


class IdleSweepConfigKeyTest(TestCase):
    """T-13: the idle sweep must honor the builder's ``idle_days`` config.

    The rule builder (and its server-side validation) persist the interval as
    ``trigger_config['idle_days']``, but the sweep originally read ``'days'`` and
    silently fell back to a 7-day default — so the configured N was ignored.
    """

    def _make_idle_task(self, username, idle_for_days):
        from datetime import timedelta
        from kanban.models import Task

        user, board, col, task = _make_board_with_task(
            username=username, task_kwargs={'progress': 50},
        )
        # auto_now stamps updated_at on save; .update() bypasses it so we can
        # backdate the task's last activity deterministically.
        Task.objects.filter(pk=task.pk).update(
            updated_at=timezone.now() - timedelta(days=idle_for_days),
        )
        return user, board, col, task

    def test_idle_days_one_fires_for_two_day_old_task(self):
        """idle_days=1 + a 2-day-stale task must fire (regressed when the sweep
        used the wrong key and defaulted to 7 days)."""
        from kanban.automation_models import AutomationLog
        from kanban.tasks.automation_tasks import run_idle_task_automations

        user, board, col, task = self._make_idle_task('idle_user_fire', idle_for_days=2)
        rule = _make_rule(board, user, 'task_idle', trigger_config={'idle_days': 1})

        run_idle_task_automations()

        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(
            logs.count(), 1,
            'idle sweep must honor idle_days=1, not fall back to the 7-day default',
        )

    def test_idle_days_ten_does_not_fire_for_two_day_old_task(self):
        """idle_days=10 + a 2-day-stale task must stay silent — proves the sweep
        reads the configured value rather than always firing."""
        from kanban.automation_models import AutomationLog
        from kanban.tasks.automation_tasks import run_idle_task_automations

        user, board, col, task = self._make_idle_task('idle_user_quiet', idle_for_days=2)
        rule = _make_rule(board, user, 'task_idle', trigger_config={'idle_days': 10})

        run_idle_task_automations()

        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 0)


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


class MilestoneReachedTest(TestCase):
    """BUG-01: milestone_reached was dead because it required just_completed,
    which is False for tasks created at 100% or typed Milestone while at 100%."""

    def test_milestone_created_at_100_fires(self):
        from kanban.models import Task
        from kanban.automation_models import AutomationLog

        user, board, col, _seed = _make_board_with_task(username='ms_created')
        rule = _make_rule(board, user, 'milestone_reached')

        Task.objects.create(
            column=col, title='Release', created_by=user,
            item_type='milestone', progress=100,
        )

        logs = AutomationLog.objects.filter(rule=rule)
        self.assertEqual(logs.count(), 1, 'milestone created at 100% should fire once')

    def test_existing_complete_task_typed_milestone_fires(self):
        """An existing task already at 100% that is switched to Milestone fires."""
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(
            username='ms_typed', task_kwargs={'progress': 100},
        )
        rule = _make_rule(board, user, 'milestone_reached')

        task.item_type = 'milestone'
        task.save()

        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 1)

    def test_progress_crossing_to_100_on_milestone_fires_once(self):
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(
            username='ms_cross',
            task_kwargs={'item_type': 'milestone', 'progress': 50},
        )
        rule = _make_rule(board, user, 'milestone_reached')

        task.progress = 100
        task.save()
        task.save()  # downstream re-save must not double-fire

        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 1)

    def test_non_milestone_does_not_fire(self):
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(
            username='ms_none', task_kwargs={'progress': 50},
        )
        rule = _make_rule(board, user, 'milestone_reached')

        task.progress = 100  # plain task → not a milestone
        task.save()

        self.assertEqual(
            AutomationLog.objects.filter(rule=rule).count(), 0,
            'a non-milestone task reaching 100% must not fire milestone_reached',
        )


class ScheduleStatusTransitionTest(TestCase):
    """BUG-05: schedule_status_changed must fire only when the computed badge
    actually transitions, not on every progress/due_date save."""

    def test_fires_on_real_transition(self):
        import datetime
        from kanban.automation_models import AutomationLog

        # Due yesterday + progress < 100 → 'late'. Start on-track then drop the
        # due date into the past to transition on_track → late.
        user, board, col, task = _make_board_with_task(
            username='sched_real',
            task_kwargs={
                'progress': 50,
                'due_date': timezone.now() + datetime.timedelta(days=30),
            },
        )
        rule = _make_rule(board, user, 'schedule_status_changed')

        task.due_date = timezone.now() - datetime.timedelta(days=1)
        task.save()

        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 1)

    def test_no_fire_when_status_unchanged(self):
        import datetime
        from kanban.automation_models import AutomationLog

        # Far-future due date: bumping progress 20 → 40 keeps the badge on_track.
        user, board, col, task = _make_board_with_task(
            username='sched_noop',
            task_kwargs={
                'progress': 20,
                'due_date': timezone.now() + datetime.timedelta(days=60),
            },
        )
        rule = _make_rule(board, user, 'schedule_status_changed')

        task.progress = 40
        task.save()

        self.assertEqual(
            AutomationLog.objects.filter(rule=rule).count(), 0,
            'schedule_status_changed must not fire when the badge is unchanged',
        )


class DueDateChangeTest(TestCase):
    """BUG-04: re-saving a task without touching the due date must not fire
    task_due_date_changed (form re-submits all fields)."""

    def test_no_fire_when_due_date_untouched(self):
        import datetime
        from kanban.automation_models import AutomationLog

        due = timezone.now() + datetime.timedelta(days=10)
        user, board, col, task = _make_board_with_task(
            username='due_noop',
            task_kwargs={'progress': 30, 'due_date': due},
        )
        rule = _make_rule(board, user, 'task_due_date_changed')

        # Change a different field; due_date stays the same instant.
        task.progress = 40
        task.save()

        self.assertEqual(
            AutomationLog.objects.filter(rule=rule).count(), 0,
            'task_due_date_changed must not fire when due_date is unchanged',
        )

    def test_fires_when_due_date_changes(self):
        import datetime
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(
            username='due_real',
            task_kwargs={
                'progress': 30,
                'due_date': timezone.now() + datetime.timedelta(days=10),
            },
        )
        rule = _make_rule(board, user, 'task_due_date_changed')

        task.due_date = timezone.now() + datetime.timedelta(days=20)
        task.save()

        self.assertEqual(AutomationLog.objects.filter(rule=rule).count(), 1)


class DerivedSaveSilenceTest(TestCase):
    """BUG-06/02: derived/read-path saves (prediction refresh) must not run
    user automation rules."""

    def test_prediction_refresh_does_not_fire_rules(self):
        import datetime
        from kanban.automation_models import AutomationLog
        from kanban.utils.task_prediction import update_task_prediction

        user, board, col, task = _make_board_with_task(
            username='pred_silent',
            task_kwargs={
                'progress': 40,
                'start_date': (timezone.now() - datetime.timedelta(days=5)).date(),
                'due_date': timezone.now() + datetime.timedelta(days=10),
            },
        )
        # Rules that would otherwise fire on the prediction save's field writes.
        sched = _make_rule(board, user, 'schedule_status_changed')
        due = _make_rule(board, user, 'task_due_date_changed')

        update_task_prediction(task)

        self.assertEqual(
            AutomationLog.objects.filter(rule__in=[sched, due]).count(), 0,
            'a prediction refresh must not fire any automation rule',
        )

    def test_automation_silent_suppresses_rules(self):
        from kanban.automation_models import AutomationLog
        from kanban.signals import automation_silent

        user, board, col, task = _make_board_with_task(
            username='silent_ctx', task_kwargs={'priority': 'medium'},
        )
        rule = _make_rule(
            board, user, 'task_priority_changed',
            trigger_config={'priority': 'urgent'},
        )

        with automation_silent():
            task.priority = 'urgent'
            task.save()

        self.assertEqual(AutomationLog.objects.filter(rule=rule).count(), 0)


class ConcurrentDuplicateEmitTest(TestCase):
    """BUG-02/05 production case: the frontend can double-submit a single user
    action as two near-simultaneous requests (two task.save() on different
    instances). Those slip past the per-instance in-memory guard and can race
    past the 3s window guard. The AutomationLog.dedupe_key unique constraint is
    the race-proof backstop that collapses them to a single rule run."""

    def test_fire_stamps_dedupe_key(self):
        """Every rule run records a non-null dedupe_key built from
        (rule, task, trigger, assignee, time-bucket) so the constraint can
        arbitrate a concurrent duplicate. Covers all triggers uniformly,
        including schedule_status_changed, since the key embeds trigger_event."""
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(username='ddk_stamp')
        assignee = User.objects.create_user(
            username='ddk_assignee', password='x', email='ddk@example.com',
        )
        rule = _make_rule(board, user, 'task_assigned')

        task.assigned_to = assignee
        task.save()

        log = AutomationLog.objects.get(rule=rule, task_affected=task)
        self.assertTrue(log.dedupe_key, 'a fire must stamp a dedupe_key')
        self.assertTrue(
            log.dedupe_key.startswith(f'{rule.pk}:{task.pk}:task_assigned:'),
            f'unexpected dedupe_key format: {log.dedupe_key}',
        )

    def test_duplicate_dedupe_key_rejected_by_db(self):
        """Two log rows with the same dedupe_key cannot coexist — this is what
        prevents a concurrent duplicate emission from firing a rule twice even
        when both requests pass the in-memory and 3s checks."""
        from django.db import IntegrityError, transaction
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(username='ddk_unique')
        assignee = User.objects.create_user(
            username='ddk_unique_a', password='x', email='u@example.com',
        )
        rule = _make_rule(board, user, 'task_assigned')

        task.assigned_to = assignee
        task.save()
        existing = AutomationLog.objects.get(rule=rule, task_affected=task)
        self.assertTrue(existing.dedupe_key)

        # A second emission claiming the same key must be rejected at the DB.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AutomationLog.objects.create(
                    rule=rule, board=board, trigger_event='task_assigned',
                    task_affected=task, outcome='success',
                    dedupe_key=existing.dedupe_key,
                )

    def test_multiple_null_dedupe_keys_allowed(self):
        """The unique constraint is partial (only non-null keys), so legacy /
        fallback rows with a null dedupe_key never collide."""
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(username='ddk_nulls')
        rule = _make_rule(board, user, 'task_created')

        AutomationLog.objects.create(
            rule=rule, board=board, trigger_event='task_created',
            task_affected=task, outcome='success', dedupe_key=None,
        )
        AutomationLog.objects.create(
            rule=rule, board=board, trigger_event='task_created',
            task_affected=task, outcome='success', dedupe_key=None,
        )
        self.assertEqual(
            AutomationLog.objects.filter(rule=rule, dedupe_key__isnull=True).count(),
            2,
        )


class MultipleRulesSameTriggerTest(TestCase):
    """When several rules watch the same trigger, one user action must produce
    one audit row PER RULE — not fewer. Regression for the per-(task, assignee,
    day) task_assigned guard that silently dropped any rule which had already
    fired for that assignee earlier the same day (3 rules logged only 2)."""

    def test_three_rules_each_fire_once(self):
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(username='multi_rule')
        assignee = User.objects.create_user(
            username='multi_assignee', password='x', email='m@example.com',
        )
        r1 = _make_rule(board, user, 'task_assigned')
        r2 = _make_rule(board, user, 'task_assigned')
        r3 = _make_rule(board, user, 'task_assigned')

        task.assigned_to = assignee
        task.save()

        for r in (r1, r2, r3):
            self.assertEqual(
                AutomationLog.objects.filter(rule=r, task_affected=task).count(), 1,
                f'rule {r.pk} should fire exactly once',
            )
        self.assertEqual(
            AutomationLog.objects.filter(
                task_affected=task, trigger_event='task_assigned',
            ).count(),
            3, '3 rules x 1 assignment must log 3 rows, not 2',
        )

    def test_reassign_same_assignee_later_same_day_fires_again(self):
        """A rule that already fired for this (task, assignee) earlier today must
        still fire on a later re-assignment to the same person. The old per-day
        guard wrongly suppressed this; the 3s window + dedupe bucket only dedupe
        the burst, not a deliberate re-assignment minutes/hours later."""
        import datetime
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(username='reassign_day')
        assignee = User.objects.create_user(
            username='reassign_a', password='x', email='r@example.com',
        )
        rule = _make_rule(board, user, 'task_assigned')

        # An earlier fire today for the same assignee, well outside the 3s window
        # and the dedupe bucket.
        old = AutomationLog.objects.create(
            rule=rule, board=board, trigger_event='task_assigned',
            task_affected=task, outcome='success',
            execution_detail={'assignee_id': assignee.id},
        )
        AutomationLog.objects.filter(pk=old.pk).update(
            triggered_at=timezone.now() - datetime.timedelta(hours=2),
        )

        task.assigned_to = assignee
        task.save()

        recent = AutomationLog.objects.filter(
            rule=rule, task_affected=task, trigger_event='task_assigned',
            triggered_at__gte=timezone.now() - datetime.timedelta(seconds=30),
        )
        self.assertEqual(
            recent.count(), 1,
            'a same-day re-assignment to the same person must fire again',
        )


class MultiFieldSaveTest(TestCase):
    """The quick-view 'Save' button posts every staged edit as ONE task.save().
    Trigger evaluation diffs each field independently, so a single save that
    changed several fields must fire EVERY applicable trigger — not just one."""

    def test_one_save_fires_assigned_and_priority_and_progress(self):
        from kanban.automation_models import AutomationLog

        user, board, col, task = _make_board_with_task(
            username='multifield', task_kwargs={'priority': 'low', 'progress': 20},
        )
        assignee = User.objects.create_user(
            username='mf_assignee', password='x', email='mf@example.com',
        )
        r_assign = _make_rule(board, user, 'task_assigned')                       # T-03
        r_prio = _make_rule(                                                      # T-07
            board, user, 'task_priority_changed', trigger_config={'priority': 'urgent'},
        )
        r_prog = _make_rule(board, user, 'task_progress_changed')                 # T-08

        # One save, three field changes — exactly what the Save button sends.
        task.assigned_to = assignee
        task.priority = 'urgent'
        task.progress = 60
        task.save()

        self.assertEqual(
            AutomationLog.objects.filter(rule=r_assign).count(), 1,
            'task_assigned must fire from the combined save',
        )
        self.assertEqual(
            AutomationLog.objects.filter(rule=r_prio).count(), 1,
            'task_priority_changed must fire from the same save',
        )
        self.assertEqual(
            AutomationLog.objects.filter(rule=r_prog).count(), 1,
            'task_progress_changed must fire from the same save',
        )


class ComputeProgressStatusTest(TestCase):
    """Unit tests for the extracted pure status computation (BUG-05 support)."""

    def test_none_without_due_date(self):
        from kanban.models import Task
        self.assertIsNone(Task.compute_progress_status(50, None, None))

    def test_complete_is_on_track(self):
        import datetime
        from kanban.models import Task
        past = timezone.now() - datetime.timedelta(days=1)
        self.assertEqual(Task.compute_progress_status(100, past, None), 'on_track')

    def test_overdue_incomplete_is_late(self):
        import datetime
        from kanban.models import Task
        past = timezone.now() - datetime.timedelta(days=1)
        self.assertEqual(Task.compute_progress_status(50, past, None), 'late')

    def test_due_soon_low_progress_is_at_risk(self):
        import datetime
        from kanban.models import Task
        soon = timezone.now() + datetime.timedelta(days=2)
        self.assertEqual(Task.compute_progress_status(10, soon, None), 'at_risk')

    def test_far_future_is_on_track(self):
        import datetime
        from kanban.models import Task
        far = timezone.now() + datetime.timedelta(days=60)
        self.assertEqual(Task.compute_progress_status(20, far, None), 'on_track')


class ScheduledRuleCronWiringTest(TestCase):
    """T-43/44/45: a scheduled rule must encode its day restriction into the
    linked PeriodicTask's crontab. The builder sends weekly as a weekday *name*
    ('Saturday') and monthly as an int under 'day_of_month'; the setup helper
    originally read only int(config['day']), so weekly/monthly silently kept
    day_of_week/day_of_month '*' and fired every day.
    """

    def _setup(self, trigger_type, trigger_config):
        from kanban.automation_views import _setup_scheduled_rule
        user, board, col, _ = _make_board_with_task(username=f'sched_{trigger_type}')
        rule = _make_rule(board, user, trigger_type, trigger_config=trigger_config)
        _setup_scheduled_rule(rule, trigger_type, trigger_config)
        rule.refresh_from_db()
        return rule.periodic_task.crontab

    def test_daily_runs_every_day(self):
        c = self._setup('scheduled_daily', {'time': '09:00'})
        self.assertEqual((c.hour, c.minute), ('9', '0'))
        self.assertEqual(c.day_of_week, '*')
        self.assertEqual(c.day_of_month, '*')

    def test_weekly_name_maps_to_cron_day_of_week(self):
        # Saturday -> cron 6 (Sun=0..Sat=6); day_of_month stays '*'.
        c = self._setup('scheduled_weekly', {'day': 'Saturday', 'time': '13:00'})
        self.assertEqual(c.day_of_week, '6')
        self.assertEqual(c.day_of_month, '*')

    def test_weekly_sunday_maps_to_zero(self):
        c = self._setup('scheduled_weekly', {'day': 'Sunday', 'time': '08:00'})
        self.assertEqual(c.day_of_week, '0')

    def test_monthly_day_of_month_key_is_honored(self):
        c = self._setup('scheduled_monthly', {'day_of_month': 6, 'time': '10:00'})
        self.assertEqual(c.day_of_month, '6')
        self.assertEqual(c.day_of_week, '*')
