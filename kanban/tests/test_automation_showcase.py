"""
Automation Showcase — build rules across trigger families, fire them, and
capture the resulting audit log.
=========================================================================

Unlike the exhaustive tier batteries (which prove each condition/action/trigger
in isolation), this is a single coherent end-to-end scenario: it builds one real
``AutomationRule`` per trigger *family*, fires each through the live signal
engine, and reads back the ``AutomationLog`` the audit trail records — including
a THEN success, an OTHERWISE fallback, a plain skip, and the linter's
"provably dead" combo landing as a skip.

Its second job is to EMIT the result. When the ``SHOWCASE_OUT`` env var points at
a file, the test writes a JSON snapshot of every rule built and every audit-log
row there, so a human-readable report / artifact can be generated from real data
(not hand-waving). Set it like:

    SHOWCASE_OUT=/path/out.json python -m pytest \
        kanban/tests/test_automation_showcase.py -v

Hermetic — one board / users / tasks, one rolled-back transaction.
"""

import json
import os

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta


class AutomationShowcaseTest(TestCase):

    def setUp(self):
        from kanban.models import Board, Column, TaskLabel
        self.owner = User.objects.create_user(
            username='show_owner', password='x', email='show_owner@example.com')
        self.dev = User.objects.create_user(
            username='show_dev', password='x', email='show_dev@example.com')
        self.board = Board.objects.create(name='Showcase Board', created_by=self.owner)
        self.cols = {}
        for pos, name in enumerate(['Backlog', 'In Progress', 'In Review', 'Done']):
            self.cols[name] = Column.objects.create(
                board=self.board, name=name, position=pos)
        self.hot = TaskLabel.objects.create(
            board=self.board, name='Hot', color='#ef4444')
        # A label that scenario 1's "tag every new task Hot" rule does NOT add,
        # so the label-added trigger in scenario 12 sees a genuinely new label.
        self.review = TaskLabel.objects.create(
            board=self.board, name='NeedsReview', color='#f59e0b')
        self.rules = []       # rule snapshots
        self.audit = []       # audit-log snapshots

    # ── helpers ──────────────────────────────────────────────────────────────

    def _rule(self, name, trigger_type, actions, conditions=None,
              otherwise_actions=None, trigger_config=None, condition_logic='AND'):
        from kanban.automation_models import AutomationRule
        rule = AutomationRule.objects.create(
            board=self.board, created_by=self.owner, name=name,
            trigger_type=trigger_type, trigger_config=trigger_config or {},
            condition_logic=condition_logic, conditions=conditions or [],
            actions=actions, otherwise_actions=otherwise_actions or [],
            is_active=True)
        self.rules.append({
            'name': name, 'trigger_type': trigger_type,
            'trigger_config': rule.trigger_config,
            'condition_logic': condition_logic,
            'conditions': conditions or [],
            'actions': actions, 'otherwise_actions': otherwise_actions or [],
        })
        return rule

    def _task(self, title, **kw):
        from kanban.models import Task
        kw.setdefault('column', self.cols['Backlog'])
        kw.setdefault('created_by', self.owner)
        return Task.objects.create(title=title, **kw)

    def _latest_log(self, rule, task=None):
        from kanban.automation_models import AutomationLog
        qs = AutomationLog.objects.filter(rule=rule)
        if task is not None:
            qs = qs.filter(task_affected=task)
        return qs.order_by('-triggered_at', '-id').first()

    def _capture(self, rule, task=None, expected_outcome=None):
        log = self._latest_log(rule, task)
        self.assertIsNotNone(
            log, f'expected an AutomationLog for rule {rule.name!r}')
        detail = log.execution_detail or {}
        self.audit.append({
            'rule_name': log.rule_name_snapshot or rule.name,
            'trigger_event': log.trigger_event,
            'task': log.task_title_snapshot,
            'outcome': log.outcome,
            'branch': detail.get('branch'),
            'skip_reason': log.skip_reason or '',
            'actions_summary': log.actions_summary or '',
        })
        if expected_outcome is not None:
            self.assertEqual(
                log.outcome, expected_outcome,
                f'{rule.name}: expected outcome {expected_outcome!r}, '
                f'got {log.outcome!r} (skip_reason={log.skip_reason!r})')
        return log

    # ── the showcase ─────────────────────────────────────────────────────────

    def test_showcase(self):
        # 1. task_created → THEN success (add a label to new tasks).
        r = self._rule('New task → tag Hot', 'task_created',
                        actions=[{'type': 'add_label', 'target': 'Hot', 'message': None}])
        t = self._task('Freshly filed bug')
        self._capture(r, t, expected_outcome='success')

        # 2. task_created + condition MET → THEN (comment on urgent new tasks).
        r = self._rule('New urgent task → comment', 'task_created',
                        conditions=[{'attribute': 'priority', 'operator': 'is', 'value': 'urgent'}],
                        actions=[{'type': 'post_comment', 'target': None, 'message': 'Triage now'}])
        t = self._task('Prod outage', priority='urgent')
        self._capture(r, t, expected_outcome='success')

        # 3. task_created + condition NOT met + OTHERWISE → fallback branch.
        r = self._rule('Urgent? else flag', 'task_created',
                        conditions=[{'attribute': 'priority', 'operator': 'is', 'value': 'urgent'}],
                        actions=[{'type': 'post_comment', 'target': None, 'message': 'is urgent'}],
                        otherwise_actions=[{'type': 'post_comment', 'target': None, 'message': 'not urgent'}])
        t = self._task('Minor typo', priority='low')
        self._capture(r, t, expected_outcome='success')  # OTHERWISE ran

        # 4. task_created + condition NOT met + NO otherwise → skipped.
        r = self._rule('New high-priority only', 'task_created',
                        conditions=[{'attribute': 'priority', 'operator': 'is', 'value': 'high'}],
                        actions=[{'type': 'post_comment', 'target': None, 'message': 'hp'}])
        t = self._task('Routine chore', priority='low')
        self._capture(r, t, expected_outcome='skipped')

        # 5. LINTER "dead" combo: task_created + progress>=30 → skipped every time.
        r = self._rule('DEAD: new task + progress>=30', 'task_created',
                        conditions=[{'attribute': 'progress', 'operator': 'gte', 'value': 30}],
                        actions=[{'type': 'post_comment', 'target': None, 'message': 'never'}])
        t = self._task('Cannot ever fire this')
        self._capture(r, t, expected_outcome='skipped')

        # 6. task_assigned → assign notification.
        r = self._rule('On assign → notify', 'task_assigned',
                        actions=[{'type': 'post_comment', 'target': None, 'message': 'assigned {task_title}'}])
        t = self._task('Needs an owner')
        t.assigned_to = self.dev
        t.save()
        self._capture(r, t, expected_outcome='success')

        # 7. task_moved_to_column (to In Review) → set priority high.
        r = self._rule('Moved to Review → high priority', 'task_moved_to_column',
                        trigger_config={'column_name': 'In Review'},
                        actions=[{'type': 'set_priority', 'target': 'high', 'message': None}])
        t = self._task('Feature PR', column=self.cols['In Progress'])
        t.column = self.cols['In Review']
        t.save()
        self._capture(r, t, expected_outcome='success')

        # 8. task_priority_changed → comment.
        r = self._rule('Priority changed → note', 'task_priority_changed',
                        actions=[{'type': 'post_comment', 'target': None, 'message': 'priority now {task_title}'}])
        t = self._task('Escalating item', priority='low')
        t.priority = 'urgent'
        t.save()
        self._capture(r, t, expected_outcome='success')

        # 9. task_completed → comment (move to Done).
        r = self._rule('On complete → log', 'task_completed',
                        actions=[{'type': 'post_comment', 'target': None, 'message': 'done!'}])
        t = self._task('Wrap-up task', column=self.cols['In Progress'], progress=80)
        t.column = self.cols['Done']
        t.progress = 100
        t.save()
        self._capture(r, t, expected_outcome='success')

        # 10. task_completion_threshold (>=50) → comment.
        r = self._rule('Half done → nudge', 'task_completion_threshold',
                        trigger_config={'threshold': 50},
                        actions=[{'type': 'post_comment', 'target': None, 'message': 'halfway'}])
        t = self._task('Long task', column=self.cols['In Progress'], progress=20)
        t.progress = 60
        t.save()
        self._capture(r, t, expected_outcome='success')

        # 11. task_due_date_changed → comment.
        r = self._rule('Due date moved → note', 'task_due_date_changed',
                        actions=[{'type': 'post_comment', 'target': None, 'message': 'date changed'}])
        t = self._task('Deadline task', due_date=timezone.now() + timedelta(days=5))
        t.due_date = timezone.now() + timedelta(days=10)
        t.save()
        self._capture(r, t, expected_outcome='success')

        # 12. task_label_added (m2m receiver) → comment when 'NeedsReview' added.
        r = self._rule('Review label → escalate note', 'task_label_added',
                        trigger_config={'label_name': 'NeedsReview'},
                        actions=[{'type': 'post_comment', 'target': None, 'message': 'needs review'}])
        t = self._task('Getting spicy')
        t.labels.add(self.review)
        self._capture(r, t, expected_outcome='success')

        # ── summary assertions ────────────────────────────────────────────────
        outcomes = [a['outcome'] for a in self.audit]
        self.assertIn('success', outcomes)
        self.assertIn('skipped', outcomes)
        branches = [a['branch'] for a in self.audit]
        self.assertIn('otherwise', branches)   # scenario 3 proved the OTHERWISE label
        self.assertIn('then', branches)
        self.assertEqual(len(self.rules), 12)

        # ── emit the snapshot for the report / artifact ──────────────────────
        out_path = os.environ.get('SHOWCASE_OUT')
        if out_path:
            with open(out_path, 'w', encoding='utf-8') as fh:
                json.dump({'rules': self.rules, 'audit': self.audit}, fh, indent=2)
