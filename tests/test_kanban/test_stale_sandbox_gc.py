"""
Stale-sandbox garbage collection tests.

cleanup_stale_sandboxes reclaims demo sandboxes for users who stopped using the
demo, so demo storage doesn't grow unbounded in production. It must delete stale
sandboxes (boards + DemoSandbox row, via the comprehensive purge) while leaving
recently-active sandboxes untouched. See kanban/tasks/sandbox_tasks.py.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from accounts.models import Organization, UserProfile
from kanban.models import Board, Column, Task, Workspace, DemoSandbox
from kanban.tasks.sandbox_tasks import cleanup_stale_sandboxes


class StaleSandboxGCTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.creator = User.objects.create_user('creator', password='x')
        cls.demo_org = Organization.objects.create(
            name='Demo Org', is_demo=True, created_by=cls.creator,
        )
        cls.demo_ws = Workspace.objects.create(
            name='Demo Workspace', organization=cls.demo_org,
            is_demo=True, is_active=True, created_by=cls.creator,
        )

    def _make_sandbox(self, username, last_accessed_at):
        user = User.objects.create_user(username, password='x')
        UserProfile.objects.get_or_create(user=user)
        board = Board.objects.create(
            name=f'{username} sandbox', organization=self.demo_org,
            workspace=self.demo_ws, owner=user, created_by=user,
            is_sandbox_copy=True, is_official_demo_board=False,
            is_seed_demo_data=False,
        )
        col = Column.objects.create(name='To Do', board=board, position=0)
        Task.objects.create(title='t', column=col, position=0, created_by=user)
        sandbox = DemoSandbox.objects.create(user=user)
        # auto_now_add sets created_at; override last_accessed_at explicitly.
        DemoSandbox.objects.filter(pk=sandbox.pk).update(last_accessed_at=last_accessed_at)
        return user, board

    def test_stale_sandbox_is_reclaimed_fresh_survives(self):
        now = timezone.now()
        stale_user, stale_board = self._make_sandbox('stale', now - timezone.timedelta(days=120))
        fresh_user, fresh_board = self._make_sandbox('fresh', now - timezone.timedelta(days=3))

        result = cleanup_stale_sandboxes(stale_days=90)

        self.assertEqual(result['reclaimed'], 1)
        self.assertEqual(result['errors'], 0)
        # Stale sandbox fully gone (board + DemoSandbox row).
        self.assertFalse(Board.objects.filter(pk=stale_board.pk).exists())
        self.assertFalse(DemoSandbox.objects.filter(user=stale_user).exists())
        # Fresh sandbox untouched.
        self.assertTrue(Board.objects.filter(pk=fresh_board.pk).exists())
        self.assertTrue(DemoSandbox.objects.filter(user=fresh_user).exists())

    def test_null_last_accessed_falls_back_to_created_at(self):
        # Legacy row: last_accessed_at NULL, created_at old -> treated as stale.
        user = User.objects.create_user('legacy', password='x')
        UserProfile.objects.get_or_create(user=user)
        board = Board.objects.create(
            name='legacy sandbox', organization=self.demo_org, workspace=self.demo_ws,
            owner=user, created_by=user, is_sandbox_copy=True,
            is_official_demo_board=False, is_seed_demo_data=False,
        )
        sandbox = DemoSandbox.objects.create(user=user)
        old = timezone.now() - timezone.timedelta(days=200)
        DemoSandbox.objects.filter(pk=sandbox.pk).update(last_accessed_at=None, created_at=old)

        result = cleanup_stale_sandboxes(stale_days=90)

        self.assertEqual(result['reclaimed'], 1)
        self.assertFalse(Board.objects.filter(pk=board.pk).exists())
        self.assertFalse(DemoSandbox.objects.filter(user=user).exists())
