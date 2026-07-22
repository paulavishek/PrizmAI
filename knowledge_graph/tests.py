"""
Regression tests for organizational-memory visibility scoping.

Locks in the fix for the cross-tenant workspace-wide memory leak: an
``is_org_wide=True`` memory must be visible only to the FORMAL workspace member
roster (WorkspaceMembership), not to anyone who merely shares a single board
that happens to live in that workspace.
"""

from django.test import TestCase

from kanban.tests.test_tenant_isolation import _make_tenant
from kanban.models import Board, Column, BoardMembership
from knowledge_graph.models import MemoryNode, MemoryConnection
from knowledge_graph.views import _accessible_memory_qs, build_node_connections_map


class WorkspaceWideMemoryVisibilityTest(TestCase):
    def setUp(self):
        # Two fully independent tenants.
        self.a = _make_tenant('mem_a')
        self.b = _make_tenant('mem_b')

        # A SECOND board inside tenant A's workspace — this is the board that
        # gets shared cross-workspace to user B (board-level only).
        self.board_a2 = Board.objects.create(
            name='mem_a Shared Board', created_by=self.a['user'], owner=self.a['user'],
            organization=self.a['org'], workspace=self.a['ws'],
        )
        Column.objects.create(board=self.board_a2, name='Backlog', position=0)

        # User B is a board member of board_a2 ONLY — no WorkspaceMembership in
        # tenant A's workspace. This is the exact foothold that caused the leak.
        BoardMembership.objects.create(
            board=self.board_a2, user=self.b['user'], role='member',
        )

        # Org-wide + private memory on the UNSHARED board (board A).
        self.mem_global = MemoryNode.objects.create(
            board=self.a['board'], node_type='note', title='Global',
            content='workspace-wide', is_org_wide=True, is_auto_captured=False,
            created_by=self.a['user'],
        )
        self.mem_private = MemoryNode.objects.create(
            board=self.a['board'], node_type='note', title='Private',
            content='board-only', is_org_wide=False, is_auto_captured=False,
            created_by=self.a['user'],
        )
        # Org-wide memory on the SHARED board (board_a2) — B may open this board,
        # so this one SHOULD remain visible via the board-level clause.
        self.mem_shared_board = MemoryNode.objects.create(
            board=self.board_a2, node_type='note', title='SharedBoard',
            content='on shared board', is_org_wide=True, is_auto_captured=False,
            created_by=self.a['user'],
        )

    def _ids(self, tenant):
        return set(_accessible_memory_qs(tenant['user']).values_list('id', flat=True))

    def test_owner_sees_own_workspace_wide_memory(self):
        ids = self._ids(self.a)
        self.assertIn(self.mem_global.id, ids)
        self.assertIn(self.mem_private.id, ids)

    def test_cross_workspace_board_member_cannot_see_org_wide_memory(self):
        """The core fix: a board-only foothold in WS-A must NOT expose org-wide
        memories on OTHER boards in WS-A."""
        ids = self._ids(self.b)
        self.assertNotIn(self.mem_global.id, ids)
        self.assertNotIn(self.mem_private.id, ids)

    def test_org_wide_memory_on_a_shared_board_is_still_visible(self):
        """Board-level sharing still works — B can open board_a2, so its memory
        is reachable via the board clause (no over-restriction)."""
        self.assertIn(self.mem_shared_board.id, self._ids(self.b))


class BuildNodeConnectionsMapTest(TestCase):
    """Guards the shared connection serializer that powers AI-Discovered
    Connections — ported from the retired board knowledge page onto the
    Organizational Memory detail endpoint (memory_node_detail)."""

    def setUp(self):
        self.t = _make_tenant('conn')
        self.src = MemoryNode.objects.create(
            board=self.t['board'], node_type='decision', title='Source',
            content='from', created_by=self.t['user'],
        )
        self.dst = MemoryNode.objects.create(
            board=self.t['board'], node_type='lesson', title='Target',
            content='to', created_by=self.t['user'],
        )
        self.conn = MemoryConnection.objects.create(
            from_node=self.src, to_node=self.dst, connection_type='led_to',
            reason='because', ai_generated=True,
        )

    def test_outgoing_and_incoming_are_mirrored(self):
        cmap = build_node_connections_map([self.src.pk, self.dst.pk])

        out = cmap[str(self.src.pk)]
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['direction'], 'outgoing')
        self.assertEqual(out[0]['type'], 'led_to')
        self.assertEqual(out[0]['other_title'], 'Target')
        self.assertTrue(out[0]['ai_generated'])

        inc = cmap[str(self.dst.pk)]
        self.assertEqual(len(inc), 1)
        self.assertEqual(inc[0]['direction'], 'incoming')
        self.assertEqual(inc[0]['other_title'], 'Source')

    def test_empty_input_returns_empty_map(self):
        self.assertEqual(build_node_connections_map([]), {})

    def test_unconnected_node_absent_from_map(self):
        lonely = MemoryNode.objects.create(
            board=self.t['board'], node_type='note', title='Lonely',
            content='x', created_by=self.t['user'],
        )
        cmap = build_node_connections_map([lonely.pk])
        self.assertNotIn(str(lonely.pk), cmap)
