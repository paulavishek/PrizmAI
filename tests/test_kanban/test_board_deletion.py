"""
Regression tests for Board deletion
===================================

Guards against a FK-constraint failure when deleting a board:

Deleting a Board cascades to its Tasks, and each Task delete fires the
`record_project_signal_on_task_delete` post_delete handler, which inserts a fresh
ProjectSignal referencing the board.  Created *during* the cascade, those rows
point at a board that is about to vanish — orphaning them and breaking the
COMMIT with "FOREIGN KEY constraint failed".

The fix (kanban/signals.py) tracks boards being deleted in a thread-local set and
skips signal creation for them.  These tests ensure a board with tasks deletes
cleanly and leaves no orphaned ProjectSignal rows.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from django.db import connection

from accounts.models import Organization
from kanban.models import Board, Column, Task
from kanban.project_signals_models import ProjectSignal


class BoardDeletionRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='deluser', email='del@example.com', password='pw123456'
        )
        self.org = Organization.objects.create(
            name='Del Org', domain='del.org', created_by=self.user
        )
        self.board = Board.objects.create(
            name='Board To Delete', organization=self.org, created_by=self.user
        )
        self.column = Column.objects.create(name='To Do', board=self.board)
        # Several tasks so the cascade fires the task-delete signal handler.
        self.tasks = [
            Task.objects.create(title=f'Task {i}', column=self.column, created_by=self.user)
            for i in range(3)
        ]

    def _fk_violations(self):
        """SQLite-only orphan check; returns [] on other backends."""
        if connection.vendor != 'sqlite':
            return []
        with connection.cursor() as c:
            c.execute('PRAGMA foreign_key_check;')
            return c.fetchall()

    def test_delete_board_with_tasks_leaves_no_orphans(self):
        board_id = self.board.id

        # Should not raise, and should remove the board.
        self.board.delete()
        self.assertFalse(Board.objects.filter(id=board_id).exists())

        # The core regression: no ProjectSignal rows may reference the gone board.
        self.assertEqual(
            ProjectSignal.objects.filter(board_id=board_id).count(), 0,
            'Task-delete handler created ProjectSignal rows for a board being deleted',
        )
        self.assertEqual(self._fk_violations(), [], 'Orphaned rows left after board delete')

    def test_deleting_a_single_task_still_records_signal(self):
        """The guard must NOT suppress signals for ordinary (non-cascade) task deletes."""
        before = ProjectSignal.objects.filter(board_id=self.board.id).count()
        self.tasks[0].delete()
        after = ProjectSignal.objects.filter(board_id=self.board.id).count()
        self.assertEqual(
            after, before + 1,
            'Normal task deletion should still record a scope-change ProjectSignal',
        )
        self.assertEqual(self._fk_violations(), [])
