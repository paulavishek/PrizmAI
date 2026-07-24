"""
Requirement.identifier auto-generation must be a per-board sequence.

Regression test for a bug where the next identifier was derived from
Max('id') — the requirement table's global auto-increment primary key,
shared across every board — instead of the highest existing identifier on
that specific board. A board's first requirement got REQ-001 (explicitly
assigned), but every later one picked up whatever the global id counter
happened to be, producing boards with REQ-001 followed by REQ-14766,
REQ-18910, etc. instead of a clean REQ-002, REQ-003, ...
"""
from django.contrib.auth.models import User
from django.test import TestCase

from kanban.models import Board
from requirements.models import Requirement


class RequirementIdentifierGenerationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('owner', password='x')
        cls.board_a = Board.objects.create(name='Board A', created_by=cls.owner)
        cls.board_b = Board.objects.create(name='Board B', created_by=cls.owner)

    def test_sequential_numbering_per_board(self):
        r1 = Requirement.objects.create(board=self.board_a, title='First', description='')
        r2 = Requirement.objects.create(board=self.board_a, title='Second', description='')
        r3 = Requirement.objects.create(board=self.board_a, title='Third', description='')
        self.assertEqual(r1.identifier, 'REQ-001')
        self.assertEqual(r2.identifier, 'REQ-002')
        self.assertEqual(r3.identifier, 'REQ-003')

    def test_numbering_is_independent_per_board(self):
        # Inflate Board A's global-id footprint first — this is what exposed
        # the original bug: Board B's first requirement must still be
        # REQ-001, not derived from Board A's higher primary keys.
        for i in range(20):
            Requirement.objects.create(board=self.board_a, title=f'Filler {i}', description='')

        b_first = Requirement.objects.create(board=self.board_b, title='B First', description='')
        b_second = Requirement.objects.create(board=self.board_b, title='B Second', description='')
        self.assertEqual(b_first.identifier, 'REQ-001')
        self.assertEqual(b_second.identifier, 'REQ-002')

    def test_explicit_identifier_is_respected(self):
        req = Requirement.objects.create(
            board=self.board_a, title='Explicit', description='', identifier='REQ-099',
        )
        self.assertEqual(req.identifier, 'REQ-099')
        # The next auto-generated one continues from the highest existing
        # number regardless of gaps.
        nxt = Requirement.objects.create(board=self.board_a, title='Next', description='')
        self.assertEqual(nxt.identifier, 'REQ-100')
