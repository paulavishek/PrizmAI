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

    def test_precedence_review_beats_done(self):
        # Interim states are checked before Done, so a name that mentions
        # both resolves to the interim state, not done.
        self.assertEqual(cs.classify_column_name('Completed reviewed'), cs.REVIEW)
        self.assertEqual(cs.classify_column_name('Done - Needs Review'), cs.REVIEW)

    def test_unknown_is_other(self):
        self.assertEqual(cs.classify_column_name('Xyzzy'), cs.OTHER)
        self.assertEqual(cs.classify_column_name(''), cs.OTHER)
        self.assertEqual(cs.classify_column_name(None), cs.OTHER)

    def test_predicates_accept_name_string(self):
        self.assertTrue(cs.is_done_column('Finished'))
        self.assertFalse(cs.is_done_column('In Progress'))
        self.assertTrue(cs.is_todo_column('Backlog'))
        self.assertTrue(cs.is_blocked_column('Blocked'))

    def test_word_boundary_avoids_partial_matches(self):
        # These contain a keyword as a *substring* but not as a whole word.
        self.assertEqual(cs.classify_column_name('Blockade'), cs.OTHER)
        self.assertEqual(cs.classify_column_name('Unblocked'), cs.OTHER)
        self.assertEqual(cs.classify_column_name('Undone'), cs.OTHER)
        self.assertEqual(cs.classify_column_name('Quarantine'), cs.OTHER)

    def test_negation_cancels_the_matched_keyword(self):
        self.assertEqual(cs.classify_column_name('Not Done Yet'), cs.OTHER)
        self.assertEqual(cs.classify_column_name('Non-Done'), cs.OTHER)
        self.assertEqual(cs.classify_column_name('No Longer Blocked'), cs.OTHER)

    def test_negation_only_cancels_the_negated_keyword(self):
        # "Not Blocked" is neutralized, but "In Progress" still matches.
        self.assertEqual(cs.classify_column_name('In Progress, Not Blocked'), cs.IN_PROGRESS)


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


class ColumnTypeQTests(TestCase):
    """column_type_q() is a separate SQL/ORM implementation used by board
    stats, Spectra column lookups, and other queryset filters — it must stay
    consistent with classify_column_name()/Column.is_done() rather than drift
    back to plain icontains false positives."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('sqlmatcher', password='x')
        cls.board = Board.objects.create(name='B', created_by=cls.owner)

    def test_excludes_negated_and_partial_matches(self):
        undone = Column.objects.create(name='Undone', board=self.board, position=0)
        not_done_yet = Column.objects.create(name='Not Done Yet', board=self.board, position=1)
        achieved = Column.objects.create(name='Achieved', board=self.board, position=2)

        Task.objects.create(title='A', column=undone, position=0, created_by=self.owner)
        Task.objects.create(title='B', column=not_done_yet, position=0, created_by=self.owner)
        Task.objects.create(title='C', column=achieved, position=0, created_by=self.owner)

        done_titles = set(
            Task.objects.filter(cs.column_type_q('done')).values_list('title', flat=True)
        )
        self.assertEqual(done_titles, {'C'})

    def test_explicit_type_still_matches_via_q(self):
        custom = Column.objects.create(
            name='Victory Lap', board=self.board, position=0, column_type=cs.DONE,
        )
        Task.objects.create(title='D', column=custom, position=0, created_by=self.owner)
        done_titles = set(
            Task.objects.filter(cs.column_type_q('done')).values_list('title', flat=True)
        )
        self.assertEqual(done_titles, {'D'})
