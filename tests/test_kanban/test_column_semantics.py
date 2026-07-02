"""
Column status-semantics tests.

Covers the single source of truth (kanban.column_semantics) plus the end-to-end
behaviour that broke before: renaming the "Done" column to something custom must
NOT silently stop completion tracking. See kanban/column_semantics.py and the
Column.is_done()/resolved_type() resolvers.
"""

from django.test import TestCase
from django.contrib.auth.models import User

from kanban.models import Board, Column, Task
from kanban import column_semantics as cs


class ClassifyColumnNameTests(TestCase):
    def test_done_keywords(self):
        for name in ['Done', 'DONE', 'Completed', 'Finished', 'Achieved',
                     'Closed', 'Resolved', 'Shipped', 'Delivered', 'All Done']:
            self.assertEqual(cs.classify_column_name(name), cs.DONE, name)

    def test_other_categories(self):
        self.assertEqual(cs.classify_column_name('To Do'), cs.TODO)
        self.assertEqual(cs.classify_column_name('Backlog'), cs.TODO)
        self.assertEqual(cs.classify_column_name('In Progress'), cs.IN_PROGRESS)
        self.assertEqual(cs.classify_column_name('Doing'), cs.IN_PROGRESS)
        self.assertEqual(cs.classify_column_name('In Review'), cs.REVIEW)
        self.assertEqual(cs.classify_column_name('QA'), cs.REVIEW)
        self.assertEqual(cs.classify_column_name('Blocked'), cs.BLOCKED)
        self.assertEqual(cs.classify_column_name('On Hold'), cs.BLOCKED)

    def test_precedence_done_beats_review(self):
        # "done" is checked before "review", so this resolves to done.
        self.assertEqual(cs.classify_column_name('Completed reviewed'), cs.DONE)

    def test_unknown_is_other(self):
        self.assertEqual(cs.classify_column_name('Xyzzy'), cs.OTHER)
        self.assertEqual(cs.classify_column_name(''), cs.OTHER)
        self.assertEqual(cs.classify_column_name(None), cs.OTHER)

    def test_predicates_accept_name_string(self):
        self.assertTrue(cs.is_done_column('Finished'))
        self.assertFalse(cs.is_done_column('In Progress'))
        self.assertTrue(cs.is_todo_column('Backlog'))
        self.assertTrue(cs.is_blocked_column('Blocked'))


class ColumnResolverTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('owner', password='x')
        cls.board = Board.objects.create(name='B', created_by=cls.owner)

    def test_auto_derives_from_name(self):
        col = Column.objects.create(name='Done', board=self.board, position=0)
        self.assertEqual(col.column_type, '')  # default auto
        self.assertTrue(col.is_done())
        self.assertEqual(col.resolved_type(), cs.DONE)

    def test_rename_redetects_when_auto(self):
        col = Column.objects.create(name='Done', board=self.board, position=0)
        self.assertTrue(col.is_done())
        col.name = 'Achieved'
        col.save()
        self.assertTrue(col.is_done(), 'renamed auto column must re-derive from the new name')
        col.name = 'In Progress'
        col.save()
        self.assertFalse(col.is_done())
        self.assertTrue(col.is_in_progress())

    def test_explicit_type_overrides_name(self):
        # Arbitrary name pinned as Done — the whole point of the structural marker.
        col = Column.objects.create(
            name='Victory Lap', board=self.board, position=0, column_type=cs.DONE,
        )
        self.assertTrue(col.is_done())
        self.assertEqual(col.resolved_type(), cs.DONE)


class ProgressOnMoveTests(TestCase):
    """End-to-end: the reported bug. Moving a task into a completion column must
    set progress=100 regardless of the column's display name."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('mover', password='x')
        cls.board = Board.objects.create(name='B', created_by=cls.owner)
        cls.todo = Column.objects.create(name='To Do', board=cls.board, position=0)

    def _task(self):
        return Task.objects.create(
            title='T', column=self.todo, position=0, progress=10,
            created_by=self.owner,
        )

    def test_move_to_renamed_done_column_sets_progress_100(self):
        # A Done column renamed to a keyword-recognised name.
        achieved = Column.objects.create(name='Achieved', board=self.board, position=1)
        task = self._task()
        task.column = achieved
        task.save()
        task.refresh_from_db()
        self.assertEqual(task.progress, 100)

    def test_move_to_custom_named_done_typed_column(self):
        # A column with a name that is NOT a keyword, explicitly typed as Done.
        custom = Column.objects.create(
            name='Victory Lap', board=self.board, position=1, column_type=cs.DONE,
        )
        task = self._task()
        task.column = custom
        task.save()
        task.refresh_from_db()
        self.assertEqual(task.progress, 100)

    def test_move_to_non_done_column_leaves_progress(self):
        doing = Column.objects.create(name='In Progress', board=self.board, position=1)
        task = self._task()
        task.column = doing
        task.save()
        task.refresh_from_db()
        self.assertEqual(task.progress, 10)
