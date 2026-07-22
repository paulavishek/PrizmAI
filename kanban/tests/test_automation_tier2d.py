"""
Tier 2d Action Battery — engine-level regression suite.

Covers the 10 Communications & Memory actions: send_notification, post_comment,
log_time_entry, mention_users_in_comment, start_task_thread, link_wiki_page,
create_wiki_page, capture_decision, capture_lesson, notify_stakeholders.

These all PRODUCE OUTPUT ARTIFACTS (notifications, comments, task threads, wiki
pages, memory nodes, time entries), so each test verifies the artifact's content
/ fields, not just that the rule fired. Includes key skipped no-op cases.

Hermetic: each test builds its own org/board/scaffolding in a rolled-back
transaction. Run under pytest (kanban_board.test_settings):

    python -m pytest kanban/tests/test_automation_tier2d.py -v
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone


class Tier2dCommunicationsMemoryActionsTest(TestCase):
    """D-01 … D-10 — Communications & Memory."""

    def setUp(self):
        from accounts.models import Organization
        from kanban.automation_models import AutomationRule
        from kanban.models import Board, Column

        self.AutomationRule = AutomationRule

        self.tester = User.objects.create_user(
            username='t2d_tester', password='x', email='t2d_tester@example.com')
        self.alice = User.objects.create_user(
            username='t2d_alice', password='x', email='t2d_alice@example.com')

        self.org = Organization.objects.create(name='Tier2d Org', created_by=self.tester)
        self.board = Board.objects.create(
            name='Tier2d Board', organization=self.org, created_by=self.tester)
        self.cols = {}
        for pos, name in enumerate(['To Do', 'In Progress', 'Done']):
            self.cols[name] = Column.objects.create(board=self.board, name=name, position=pos)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _make_rule(self, name, actions, trigger_type='task_assigned'):
        return self.AutomationRule.objects.create(
            board=self.board, created_by=self.tester, name=name,
            trigger_type=trigger_type, trigger_config={},
            conditions=[], condition_logic='AND',
            actions=actions, otherwise_actions=[], is_active=True,
        )

    def _task(self, **kw):
        from kanban.models import Task
        kw.setdefault('column', self.cols['To Do'])
        kw.setdefault('created_by', self.tester)
        kw.setdefault('assigned_to', self.tester)
        kw.setdefault('title', 'TIER2D-TASK')
        return Task.objects.create(**kw)

    def _fire(self, task, new_assignee):
        from kanban.models import Task
        fresh = Task.objects.get(pk=task.pk)
        fresh.assigned_to = new_assignee
        fresh.save()

    def _assert_log(self, rule, task=None, outcome='success'):
        from kanban.automation_models import AutomationLog
        qs = AutomationLog.objects.filter(rule=rule)
        if task is not None:
            qs = qs.filter(task_affected=task)
        self.assertEqual(qs.count(), 1,
                         f'expected 1 log, got {list(qs.values_list("outcome", flat=True))}')
        self.assertEqual(qs.first().outcome, outcome)

    def _wiki_page(self, slug, title):
        from wiki.models import WikiPage, WikiCategory
        cat = WikiCategory.objects.create(
            organization=self.org, name='Docs', slug='docs')
        return WikiPage.objects.create(
            organization=self.org, category=cat, title=title, slug=slug,
            content='body', created_by=self.tester, updated_by=self.tester)

    # ───────────────────────────── D-01..D-10 ───────────────────────────────

    def test_d01_send_notification(self):
        from messaging.models import Notification
        task = self._task()
        rule = self._make_rule('TIER2D-D01: Send notification',
                               [{'type': 'send_notification', 'target': 'task_assignee',
                                 'message': 'Heads up on {task_title}'}])
        self._fire(task, self.alice)  # assignee becomes alice → recipient
        self._assert_log(rule, task)
        note = Notification.objects.filter(recipient=self.alice).first()
        self.assertIsNotNone(note)
        self.assertIn('TIER2D-TASK', note.text)

    def test_d02_post_comment(self):
        from kanban.models import Comment
        task = self._task()
        rule = self._make_rule('TIER2D-D02: Post comment',
                               [{'type': 'post_comment', 'message': 'Auto note for {task_title}'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertTrue(
            Comment.objects.filter(task=task, content='Auto note for TIER2D-TASK').exists())

    def test_d03_log_time_entry(self):
        from kanban.budget_models import TimeEntry
        task = self._task()
        rule = self._make_rule('TIER2D-D03: Log time entry',
                               [{'type': 'log_time_entry', 'target': '2.5'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        entry = TimeEntry.objects.filter(task=task).first()
        self.assertIsNotNone(entry)
        self.assertEqual(float(entry.hours_spent), 2.5)
        self.assertEqual(entry.work_date, timezone.now().date())

    def test_d04_mention_users_in_comment(self):
        from kanban.models import Comment
        task = self._task()
        rule = self._make_rule('TIER2D-D04: Mention users in comment',
                               [{'type': 'mention_users_in_comment',
                                 'message': '@t2d_alice please review'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertTrue(
            Comment.objects.filter(task=task, content__contains='@t2d_alice').exists())

    def test_d05_start_task_thread(self):
        from messaging.models import TaskThreadComment
        task = self._task()
        rule = self._make_rule('TIER2D-D05: Start task thread',
                               [{'type': 'start_task_thread', 'message': 'Kicking off discussion'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertTrue(
            TaskThreadComment.objects.filter(task=task, content='Kicking off discussion').exists())

    def test_d06_link_wiki_page(self):
        from kanban.models import Comment
        self._wiki_page(slug='runbook', title='Deploy Runbook')
        task = self._task()
        rule = self._make_rule('TIER2D-D06: Link wiki page',
                               [{'type': 'link_wiki_page', 'target': 'runbook'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        comment = Comment.objects.filter(task=task, content__contains='Deploy Runbook').first()
        self.assertIsNotNone(comment)
        self.assertIn('/wiki/runbook/', comment.content)

    def test_d06b_link_wiki_page_missing_skips(self):
        task = self._task()
        rule = self._make_rule('TIER2D-D06b: Link wiki page (missing)',
                               [{'type': 'link_wiki_page', 'target': 'does-not-exist'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task, outcome='skipped')

    def test_d07_create_wiki_page(self):
        from wiki.models import WikiPage
        task = self._task()
        rule = self._make_rule('TIER2D-D07: Create wiki page',
                               [{'type': 'create_wiki_page', 'target': 'Release Notes',
                                 'message': 'v1.0 shipped'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        page = WikiPage.objects.filter(organization=self.org, title='Release Notes').first()
        self.assertIsNotNone(page)
        self.assertEqual(page.content, 'v1.0 shipped')
        self.assertIsNotNone(page.category)
        self.assertEqual(page.updated_by_id, self.tester.id)

    def test_d08_capture_decision(self):
        from knowledge_graph.models import MemoryNode
        task = self._task()
        rule = self._make_rule('TIER2D-D08: Capture decision',
                               [{'type': 'capture_decision', 'message': 'Adopt feature flags'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertTrue(MemoryNode.objects.filter(
            node_type='decision', content='Adopt feature flags').exists())

    def test_d09_capture_lesson(self):
        from knowledge_graph.models import MemoryNode
        task = self._task()
        rule = self._make_rule('TIER2D-D09: Capture lesson',
                               [{'type': 'capture_lesson', 'message': 'Cache invalidation is hard'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertTrue(MemoryNode.objects.filter(
            node_type='lesson', content='Cache invalidation is hard').exists())

    def test_d10_notify_stakeholders(self):
        from messaging.models import Notification
        from kanban.stakeholder_models import ProjectStakeholder
        sh_user = User.objects.create_user(
            username='t2d_sponsor', password='x', email='sponsor@example.com')
        ProjectStakeholder.objects.create(
            board=self.board, name='Sponsor', role='Exec Sponsor',
            email='sponsor@example.com', created_by=self.tester, is_active=True)
        task = self._task()
        rule = self._make_rule('TIER2D-D10: Notify stakeholders',
                               [{'type': 'notify_stakeholders', 'message': 'Milestone reached'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task)
        self.assertTrue(
            Notification.objects.filter(recipient=sh_user, text='Milestone reached').exists())

    def test_d10b_notify_stakeholders_no_linked_user_skips(self):
        from kanban.stakeholder_models import ProjectStakeholder
        ProjectStakeholder.objects.create(
            board=self.board, name='Ghost', role='Observer',
            email='nobody@example.com', created_by=self.tester, is_active=True)
        task = self._task()
        rule = self._make_rule('TIER2D-D10b: Notify stakeholders (no user)',
                               [{'type': 'notify_stakeholders', 'message': 'x'}])
        self._fire(task, self.alice)
        self._assert_log(rule, task, outcome='skipped')
