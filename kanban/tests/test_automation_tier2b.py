"""
Tier 2b Action Battery — engine-level regression suite.

Exercises the 15 actions in two automation builder groups:
  - Hierarchy & Dependencies (8): cascade_due_date, cascade_priority,
    assign_subtasks_to, complete_parent_if_all_subtasks_done,
    notify_blocked_tasks, auto_check_checklist, add_checklist_item, add_subtask
  - Resources & Workload (7): set_workload_impact, set_estimated_hours,
    set_estimated_cost, assign_to_best_skill_match, assign_to_lightest_workload,
    add_required_skill, escalate_to_owner

Each test creates a single rule (trigger ``task_assigned``, one action), fires it
by reassigning the relevant task, then asserts (a) exactly ONE ``AutomationLog``
row for that (rule, task) with the expected outcome and (b) the correct effect.
Includes the key ``skipped`` no-op cases the engine encodes.

Hermetic: every test builds its own board/users/scaffolding in a rolled-back
transaction. Run under pytest (``kanban_board.test_settings`` → Celery eager,
in-memory broker/SQLite):

    python -m pytest kanban/tests/test_automation_tier2b.py -v
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone


class Tier2bHierarchyWorkloadActionsTest(TestCase):
    """B-01 … B-15 — Hierarchy & Dependencies + Resources & Workload."""

    def setUp(self):
        from kanban.automation_models import AutomationRule
        from kanban.models import Board, BoardMembership, Column
        from accounts.models import UserProfile

        self.AutomationRule = AutomationRule

        self.tester = User.objects.create_user(
            username='t2b_tester', password='x', email='t2b_tester@example.com')
        self.alice = User.objects.create_user(
            username='t2b_alice', password='x', email='t2b_alice@example.com')
        self.bob = User.objects.create_user(
            username='t2b_bob', password='x', email='t2b_bob@example.com')

        # Profiles + skills (assign_to_best_skill_match). Use the production dict
        # form {'name','level'} so the test guards against name-only matching.
        for user, skills in (
            (self.tester, []),
            (self.alice, [{'name': 'Python', 'level': 'Expert'},
                          {'name': 'Django', 'level': 'Expert'}]),
            (self.bob, [{'name': 'CSS', 'level': 'Intermediate'}]),
        ):
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.skills = skills
            profile.save()

        self.board = Board.objects.create(name='Software Development', created_by=self.tester)
        self.cols = {}
        for pos, name in enumerate(['To Do', 'In Progress', 'In Review', 'Done']):
            self.cols[name] = Column.objects.create(board=self.board, name=name, position=pos)

        # Memberships via bulk_create — skips the branch-recalc post_save signal.
        BoardMembership.objects.bulk_create([
            BoardMembership(board=self.board, user=self.tester, role='owner'),
            BoardMembership(board=self.board, user=self.alice, role='member'),
            BoardMembership(board=self.board, user=self.bob, role='member'),
        ])

    # ── helpers ──────────────────────────────────────────────────────────────

    def _make_rule(self, name, actions):
        return self.AutomationRule.objects.create(
            board=self.board, created_by=self.tester, name=name,
            trigger_type='task_assigned', trigger_config={},
            conditions=[], condition_logic='AND',
            actions=actions, otherwise_actions=[], is_active=True,
        )

    def _fire(self, task, new_assignee):
        """Fire task_assigned on ``task`` by reassigning it. Re-fetch first so the
        per-instance guard starts fresh (as across two HTTP requests)."""
        from kanban.models import Task
        fresh = Task.objects.get(pk=task.pk)
        fresh.assigned_to = new_assignee
        fresh.save()

    def _assert_log(self, rule, task, outcome='success'):
        from kanban.automation_models import AutomationLog
        logs = AutomationLog.objects.filter(rule=rule, task_affected=task)
        self.assertEqual(logs.count(), 1,
                         f'expected 1 log, got {list(logs.values_list("outcome", flat=True))}')
        self.assertEqual(logs.first().outcome, outcome)

    def _task(self, **kw):
        from kanban.models import Task
        kw.setdefault('column', self.cols['To Do'])
        kw.setdefault('created_by', self.tester)
        kw.setdefault('assigned_to', self.tester)
        return Task.objects.create(**kw)

    def _parent_with_subtasks(self, n, parent_kw=None, sub_kw=None):
        parent = self._task(title='Parent', **(parent_kw or {}))
        subs = [self._task(title=f'Sub {i}', parent_task=parent, **(sub_kw or {}))
                for i in range(n)]
        return parent, subs

    def _reload(self, obj):
        return type(obj).objects.get(pk=obj.pk)

    # ─────────────────────── Hierarchy & Dependencies ───────────────────────

    def test_b01a_cascade_due_date_match_parent(self):
        due = timezone.now() + timedelta(days=10)
        parent, subs = self._parent_with_subtasks(2, parent_kw={'due_date': due})
        rule = self._make_rule('TIER2B-B01a: Cascade due (match parent)',
                               [{'type': 'cascade_due_date', 'target': 'match_parent'}])
        self._fire(parent, self.alice)
        self._assert_log(rule, parent)
        for s in subs:
            self.assertEqual(self._reload(s).due_date, parent.due_date)

    def test_b01b_cascade_due_date_shift_days(self):
        base = timezone.now() + timedelta(days=5)
        parent, subs = self._parent_with_subtasks(
            2, parent_kw={'due_date': timezone.now() + timedelta(days=10)},
            sub_kw={'due_date': base})
        rule = self._make_rule('TIER2B-B01b: Cascade due (+7 days)',
                               [{'type': 'cascade_due_date', 'target': '7'}])
        self._fire(parent, self.alice)
        self._assert_log(rule, parent)
        for s in subs:
            self.assertEqual(self._reload(s).due_date.date(), (base + timedelta(days=7)).date())

    def test_b01c_cascade_due_date_no_parent_due_skips(self):
        parent, subs = self._parent_with_subtasks(2)  # parent has no due_date
        rule = self._make_rule('TIER2B-B01c: Cascade due (no parent due)',
                               [{'type': 'cascade_due_date', 'target': 'match_parent'}])
        self._fire(parent, self.alice)
        self._assert_log(rule, parent, outcome='skipped')
        for s in subs:
            self.assertIsNone(self._reload(s).due_date)

    def test_b02_cascade_priority(self):
        parent, subs = self._parent_with_subtasks(
            2, parent_kw={'priority': 'urgent'}, sub_kw={'priority': 'medium'})
        rule = self._make_rule('TIER2B-B02: Cascade priority',
                               [{'type': 'cascade_priority'}])
        self._fire(parent, self.alice)
        self._assert_log(rule, parent)
        for s in subs:
            self.assertEqual(self._reload(s).priority, 'urgent')

    def test_b03_assign_subtasks_to(self):
        parent, subs = self._parent_with_subtasks(2)
        rule = self._make_rule('TIER2B-B03: Assign all subtasks',
                               [{'type': 'assign_subtasks_to', 'target': str(self.alice.id)}])
        self._fire(parent, self.bob)
        self._assert_log(rule, parent)
        for s in subs:
            self.assertEqual(self._reload(s).assigned_to_id, self.alice.id)

    def test_b04a_complete_parent_all_done(self):
        parent, subs = self._parent_with_subtasks(2, sub_kw={'progress': 100})
        rule = self._make_rule('TIER2B-B04a: Complete parent (all done)',
                               [{'type': 'complete_parent_if_all_subtasks_done'}])
        self._fire(subs[0], self.alice)
        self._assert_log(rule, subs[0])
        self.assertEqual(self._reload(parent).progress, 100)

    def test_b04b_complete_parent_sibling_incomplete_skips(self):
        parent = self._task(title='Parent', progress=0)
        s0 = self._task(title='Sub 0', parent_task=parent, progress=100)
        self._task(title='Sub 1', parent_task=parent, progress=40)  # incomplete sibling
        rule = self._make_rule('TIER2B-B04b: Complete parent (sibling incomplete)',
                               [{'type': 'complete_parent_if_all_subtasks_done'}])
        self._fire(s0, self.alice)
        self._assert_log(rule, s0, outcome='skipped')
        self.assertEqual(self._reload(parent).progress, 0)

    def test_b05_notify_blocked_tasks(self):
        from messaging.models import Notification
        blocker = self._task(title='Blocker')
        blocked = self._task(title='Blocked', assigned_to=self.alice)
        blocked.dependencies.add(blocker)
        rule = self._make_rule('TIER2B-B05: Notify blocked tasks',
                               [{'type': 'notify_blocked_tasks', 'message': 'Blocker updated'}])
        self._fire(blocker, self.bob)
        self._assert_log(rule, blocker)
        self.assertTrue(Notification.objects.filter(recipient=self.alice).exists())

    def test_b06_auto_check_checklist(self):
        from kanban.models import ChecklistItem
        task = self._task(title='Has checklist')
        item = ChecklistItem.objects.create(task=task, title='Review code', position=1)
        rule = self._make_rule('TIER2B-B06: Auto-check checklist',
                               [{'type': 'auto_check_checklist', 'target': 'Review'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertTrue(self._reload(item).is_completed)

    def test_b06b_auto_check_checklist_no_match_skips(self):
        from kanban.models import ChecklistItem
        task = self._task(title='Has checklist')
        item = ChecklistItem.objects.create(task=task, title='Review code', position=1)
        rule = self._make_rule('TIER2B-B06b: Auto-check (no match)',
                               [{'type': 'auto_check_checklist', 'target': 'Deploy'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task, outcome='skipped')
        self.assertFalse(self._reload(item).is_completed)

    def test_b07_add_checklist_item(self):
        from kanban.models import ChecklistItem
        task = self._task(title='Needs checklist')
        rule = self._make_rule('TIER2B-B07: Add checklist item',
                               [{'type': 'add_checklist_item', 'message': 'Write unit tests'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertTrue(
            ChecklistItem.objects.filter(task=task, title='Write unit tests').exists())

    def test_b08_add_subtask(self):
        from kanban.models import Task
        task = self._task(title='Parent for subtask')
        rule = self._make_rule('TIER2B-B08: Add subtask',
                               [{'type': 'add_subtask', 'message': 'Generated subtask',
                                 'due_offset_days': 3}])
        base = timezone.now().date()
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        sub = Task.objects.filter(parent_task=task, title='Generated subtask').first()
        self.assertIsNotNone(sub)
        self.assertEqual(sub.column_id, task.column_id)
        # due = now().date()+3 written naive into a DateTimeField; USE_TZ read-back
        # can shift -1 day in UTC, so assert a +3±1 day window (see Tier 2a A-10).
        sub_due = sub.due_date.date() if hasattr(sub.due_date, 'date') else sub.due_date
        self.assertTrue(2 <= (sub_due - base).days <= 3)

    # ─────────────────────── Resources & Workload ───────────────────────────

    def test_b09_set_workload_impact(self):
        task = self._task(title='Workload task')
        rule = self._make_rule('TIER2B-B09: Set workload impact',
                               [{'type': 'set_workload_impact', 'target': 'high'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertEqual(self._reload(task).workload_impact, 'high')

    def test_b10_set_estimated_hours(self):
        from kanban.budget_models import TaskCost
        task = self._task(title='Estimate hours')
        rule = self._make_rule('TIER2B-B10: Set estimated hours',
                               [{'type': 'set_estimated_hours', 'target': '12'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertEqual(float(TaskCost.objects.get(task=task).estimated_hours), 12.0)

    def test_b11_set_estimated_cost(self):
        from kanban.budget_models import TaskCost
        task = self._task(title='Estimate cost')
        rule = self._make_rule('TIER2B-B11: Set estimated cost',
                               [{'type': 'set_estimated_cost', 'target': '5000'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertEqual(float(TaskCost.objects.get(task=task).estimated_cost), 5000.0)

    def test_b12_assign_to_best_skill_match(self):
        # Dict form with a DIFFERENT level than alice's profile ('Intermediate'
        # vs 'Expert') — must still match on name. This is the case that the
        # old stringified-dict comparison silently failed.
        task = self._task(title='Needs Python',
                          required_skills=[{'name': 'Python', 'level': 'Intermediate'}])
        rule = self._make_rule('TIER2B-B12: Assign best skill match',
                               [{'type': 'assign_to_best_skill_match'}])
        self._fire(task, self.bob)  # change assignee off tester so the trigger fires
        self._assert_log(rule, task)
        self.assertEqual(self._reload(task).assigned_to_id, self.alice.id)

    def test_b13_assign_to_lightest_workload(self):
        # tester: 1 incomplete, alice: 2 incomplete, bob: 0 → bob is lightest.
        self._task(title='tester load', assigned_to=self.tester, progress=10)
        self._task(title='alice load 1', assigned_to=self.alice, progress=10)
        self._task(title='alice load 2', assigned_to=self.alice, progress=20)
        task = self._task(title='To distribute')
        rule = self._make_rule('TIER2B-B13: Assign lightest workload',
                               [{'type': 'assign_to_lightest_workload'}])
        self._fire(task, self.alice)  # trigger; action reassigns to lightest
        self._assert_log(rule, task)
        self.assertEqual(self._reload(task).assigned_to_id, self.bob.id)

    def test_b14_add_required_skill(self):
        task = self._task(title='Skill task', required_skills=['Python'])
        rule = self._make_rule('TIER2B-B14: Add required skill',
                               [{'type': 'add_required_skill', 'target': 'Kubernetes'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertIn('Kubernetes', self._reload(task).required_skills)

    def test_b15_escalate_to_owner(self):
        from messaging.models import Notification
        task = self._task(title='Escalate me')
        rule = self._make_rule('TIER2B-B15: Escalate to owner',
                               [{'type': 'escalate_to_owner', 'message': 'Please review'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        # board.created_by == tester (the owner)
        self.assertTrue(Notification.objects.filter(recipient=self.tester).exists())
