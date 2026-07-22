"""Guard test: live auto-capture must NOT create MemoryNodes on demo boards.

The demo's Organizational Memory is a fixed, hand-curated set. Background
auto-capture writers (post_save signals, daily Celery tasks, commitment/autopsy/
automation writers) all consult ``knowledge_graph.demo_guard.is_demo_board``
before creating a node, so per-user sandbox copies don't drift upward and the
demo stays deterministic across Reset Demo.

This test locks that invariant: it verifies the predicate and that the central
task-completion signal is suppressed on demo/sandbox boards but still fires on a
normal board. If a future writer forgets the guard on the signal path, this fails.
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from kanban.tests.test_tenant_isolation import _make_tenant
from kanban.models import Board, Column, Task
from knowledge_graph.models import MemoryNode
from knowledge_graph.demo_guard import is_demo_board


class IsDemoBoardPredicateTest(TestCase):
    def setUp(self):
        self.t = _make_tenant('guard')

    def test_normal_board_is_not_demo(self):
        self.assertFalse(is_demo_board(self.t['board']))

    def test_none_is_not_demo(self):
        self.assertFalse(is_demo_board(None))

    def test_sandbox_copy_is_demo(self):
        board = Board.objects.create(
            name='SB Copy', created_by=self.t['user'], owner=self.t['user'],
            organization=self.t['org'], workspace=self.t['ws'], is_sandbox_copy=True,
        )
        self.assertTrue(is_demo_board(board))

    def test_official_demo_board_is_demo(self):
        board = Board.objects.create(
            name='Official', created_by=self.t['user'], owner=self.t['user'],
            organization=self.t['org'], workspace=self.t['ws'],
            is_official_demo_board=True,
        )
        self.assertTrue(is_demo_board(board))

    def test_board_in_demo_workspace_is_demo(self):
        self.t['ws'].is_demo = True
        self.t['ws'].save(update_fields=['is_demo'])
        self.t['board'].refresh_from_db()
        self.assertTrue(is_demo_board(self.t['board']))


class TaskCompletionAutoCaptureGateTest(TestCase):
    """The capture_task_completed signal must skip demo/sandbox boards."""

    def _completed_task_fires_capture(self, board, col, user):
        """Create an old task on `col`, flip it to 100% complete, and return the
        number of auto-captured MemoryNodes that resulted for `board`."""
        task = Task.objects.create(
            column=col, title='Ship feature', item_type='task', progress=50,
            created_by=user,
        )
        # Signal only captures tasks older than a day.
        Task.objects.filter(pk=task.pk).update(
            created_at=timezone.now() - timedelta(days=3),
        )
        task.refresh_from_db()
        task.progress = 100
        task.save()
        return MemoryNode.objects.filter(board=board, source_object_type='Task').count()

    def test_capture_fires_on_normal_board(self):
        t = _make_tenant('cap_normal')
        count = self._completed_task_fires_capture(t['board'], t['col'], t['user'])
        self.assertEqual(count, 1, 'normal board should auto-capture task completion')

    def test_capture_suppressed_on_sandbox_copy(self):
        t = _make_tenant('cap_demo')
        board = Board.objects.create(
            name='Demo SB', created_by=t['user'], owner=t['user'],
            organization=t['org'], workspace=t['ws'], is_sandbox_copy=True,
        )
        col = Column.objects.create(board=board, name='Backlog', position=0)
        count = self._completed_task_fires_capture(board, col, t['user'])
        self.assertEqual(count, 0, 'demo sandbox board must not auto-capture')
