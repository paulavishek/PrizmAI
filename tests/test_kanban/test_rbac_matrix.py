"""
RBAC Matrix & Cross-Board Authorization Tests
=============================================

Locks in the role-based access-control contract and guards against the
cross-board IDOR class of bugs fixed in the RBAC hardening sweep.

Two layers are exercised:

  1. **Permission matrix** — direct ``user.has_perm(...)`` / simple_access
     assertions for owner / member / viewer / org-admin / stranger across
     view_board, edit_board, delete_board and invite_board_member.

  2. **Endpoint authorization** — HTTP client checks that strangers (and, where
     relevant, viewers) are rejected from per-board feature endpoints and the
     strategic/portfolio API that previously fetched objects by id with no
     permission check.

Roles under test (BoardMembership.role):
  owner_u   — board creator + 'owner' membership   (full control)
  owner2_u  — 'owner' membership, NOT the creator   (manage members, NOT delete)
  member_u  — 'member' membership                   (edit, no manage/delete)
  viewer_u  — 'viewer' membership                   (read-only)
  org_admin_u — OrgAdmin of the board's org         (full control)
  stranger_u — legitimate user in a different org   (no access)
"""

from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.urls import reverse

from accounts.models import Organization, UserProfile
from kanban.models import (
    Board, BoardMembership, Column, Task, Mission, Strategy,
    OrganizationGoal, Workspace,
)
from kanban.simple_access import (
    can_access_board, can_modify_board_content, can_manage_board,
)
from kanban.invitation_views import _can_manage_invites


def _mk_profile(user, org, ws):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.organization = org
    profile.active_workspace = ws
    profile.is_viewing_demo = False
    profile.onboarding_version = 2
    profile.onboarding_status = 'completed'
    profile.save()
    return profile


class RBACMatrixTests(TestCase):
    """Role-based permission matrix on a single real-workspace board."""

    @classmethod
    def setUpTestData(cls):
        # ── Org / workspace (real, not demo) ──
        cls.owner_u = User.objects.create_user('owner_u', password='x')
        cls.org = Organization.objects.create(
            name='RBAC Org', is_demo=False, created_by=cls.owner_u,
        )
        cls.ws = Workspace.objects.create(
            name='RBAC WS', organization=cls.org, is_demo=False,
            is_active=True, created_by=cls.owner_u,
        )

        # ── Strategic chain: Goal → Mission → Strategy → Board ──
        cls.goal = OrganizationGoal.objects.create(
            name='Goal', organization=cls.org, workspace=cls.ws,
            created_by=cls.owner_u,
        )
        cls.mission = Mission.objects.create(
            name='Mission', organization_goal=cls.goal, workspace=cls.ws,
            created_by=cls.owner_u,
        )
        cls.strategy = Strategy.objects.create(
            name='Strategy', mission=cls.mission, workspace=cls.ws,
            status='active', created_by=cls.owner_u,
        )
        cls.board = Board.objects.create(
            name='Board', organization=cls.org, workspace=cls.ws,
            strategy=cls.strategy, created_by=cls.owner_u,
        )
        col = Column.objects.create(name='To Do', board=cls.board, position=0)
        Task.objects.create(title='T1', column=col, created_by=cls.owner_u)

        # ── Users + memberships ──
        cls.owner2_u = User.objects.create_user('owner2_u', password='x')
        cls.member_u = User.objects.create_user('member_u', password='x')
        cls.viewer_u = User.objects.create_user('viewer_u', password='x')
        cls.org_admin_u = User.objects.create_user('org_admin_u', password='x')
        cls.stranger_u = User.objects.create_user('stranger_u', password='x')

        BoardMembership.objects.create(board=cls.board, user=cls.owner_u, role='owner')
        BoardMembership.objects.create(board=cls.board, user=cls.owner2_u, role='owner')
        BoardMembership.objects.create(board=cls.board, user=cls.member_u, role='member')
        BoardMembership.objects.create(board=cls.board, user=cls.viewer_u, role='viewer')

        for u in (cls.owner_u, cls.owner2_u, cls.member_u, cls.viewer_u, cls.org_admin_u):
            _mk_profile(u, cls.org, cls.ws)

        # Org admin: in OrgAdmin group + same org as the board
        org_admin_group, _ = Group.objects.get_or_create(name='OrgAdmin')
        cls.org_admin_u.groups.add(org_admin_group)

        # Stranger lives in a separate real org/workspace
        cls.other_org = Organization.objects.create(
            name='Other Org', is_demo=False, created_by=cls.stranger_u,
        )
        cls.other_ws = Workspace.objects.create(
            name='Other WS', organization=cls.other_org, is_demo=False,
            is_active=True, created_by=cls.stranger_u,
        )
        _mk_profile(cls.stranger_u, cls.other_org, cls.other_ws)

    # ── view_board ───────────────────────────────────────────────────────────
    def test_view_board_allowed_for_members_and_admin(self):
        for u in (self.owner_u, self.owner2_u, self.member_u, self.viewer_u, self.org_admin_u):
            self.assertTrue(u.has_perm('prizmai.view_board', self.board), u.username)

    def test_view_board_denied_for_stranger(self):
        self.assertFalse(self.stranger_u.has_perm('prizmai.view_board', self.board))

    # ── edit_board ───────────────────────────────────────────────────────────
    def test_edit_board_allowed_for_owner_member_admin(self):
        for u in (self.owner_u, self.owner2_u, self.member_u, self.org_admin_u):
            self.assertTrue(u.has_perm('prizmai.edit_board', self.board), u.username)

    def test_edit_board_denied_for_viewer_and_stranger(self):
        self.assertFalse(self.viewer_u.has_perm('prizmai.edit_board', self.board))
        self.assertFalse(self.stranger_u.has_perm('prizmai.edit_board', self.board))

    # ── delete_board ─────────────────────────────────────────────────────────
    def test_delete_board_for_creator_and_admin_only(self):
        self.assertTrue(self.owner_u.has_perm('prizmai.delete_board', self.board))
        self.assertTrue(self.org_admin_u.has_perm('prizmai.delete_board', self.board))

    def test_delete_board_denied_for_owner_role_member_viewer(self):
        # An 'owner' BoardMembership that isn't the creator must NOT delete.
        self.assertFalse(self.owner2_u.has_perm('prizmai.delete_board', self.board))
        self.assertFalse(self.member_u.has_perm('prizmai.delete_board', self.board))
        self.assertFalse(self.viewer_u.has_perm('prizmai.delete_board', self.board))
        self.assertFalse(self.stranger_u.has_perm('prizmai.delete_board', self.board))

    # ── invite_board_member / _can_manage_invites (B2 regression) ────────────
    def test_invite_permission_includes_owner_role_and_admin(self):
        for u in (self.owner_u, self.owner2_u, self.org_admin_u):
            self.assertTrue(u.has_perm('prizmai.invite_board_member', self.board), u.username)

    def test_invite_permission_denied_for_member_viewer_stranger(self):
        for u in (self.member_u, self.viewer_u, self.stranger_u):
            self.assertFalse(u.has_perm('prizmai.invite_board_member', self.board), u.username)

    def test_can_manage_invites_honors_owner_role(self):
        # Regression: an 'owner'-role user who is NOT the creator was previously
        # denied member management. They must now be allowed.
        self.assertTrue(_can_manage_invites(self.owner2_u, self.board))
        self.assertTrue(_can_manage_invites(self.org_admin_u, self.board))
        self.assertFalse(_can_manage_invites(self.member_u, self.board))
        self.assertFalse(_can_manage_invites(self.viewer_u, self.board))

    # ── simple_access helpers ────────────────────────────────────────────────
    def test_simple_access_modify_denies_viewer(self):
        self.assertTrue(can_access_board(self.viewer_u, self.board))
        self.assertFalse(can_modify_board_content(self.viewer_u, self.board))
        self.assertTrue(can_modify_board_content(self.member_u, self.board))

    def test_simple_access_manage_for_owner_only(self):
        self.assertTrue(can_manage_board(self.owner2_u, self.board))   # owner role
        self.assertFalse(can_manage_board(self.member_u, self.board))
        self.assertFalse(can_manage_board(self.viewer_u, self.board))


class CrossBoardEndpointTests(TestCase):
    """A stranger must not reach another board's feature/API endpoints."""

    @classmethod
    def setUpTestData(cls):
        cls.owner_u = User.objects.create_user('cb_owner', password='x')
        cls.org = Organization.objects.create(
            name='CB Org', is_demo=False, created_by=cls.owner_u,
        )
        cls.ws = Workspace.objects.create(
            name='CB WS', organization=cls.org, is_demo=False,
            is_active=True, created_by=cls.owner_u,
        )
        cls.goal = OrganizationGoal.objects.create(
            name='CB Goal', organization=cls.org, workspace=cls.ws,
            created_by=cls.owner_u,
        )
        cls.mission = Mission.objects.create(
            name='CB Mission', organization_goal=cls.goal, workspace=cls.ws,
            created_by=cls.owner_u,
        )
        cls.strategy = Strategy.objects.create(
            name='CB Strategy', mission=cls.mission, workspace=cls.ws,
            status='active', created_by=cls.owner_u,
        )
        cls.board = Board.objects.create(
            name='CB Board', organization=cls.org, workspace=cls.ws,
            strategy=cls.strategy, created_by=cls.owner_u,
        )
        Column.objects.create(name='To Do', board=cls.board, position=0)

        cls.member_u = User.objects.create_user('cb_member', password='x')
        cls.viewer_u = User.objects.create_user('cb_viewer', password='x')
        BoardMembership.objects.create(board=cls.board, user=cls.member_u, role='member')
        BoardMembership.objects.create(board=cls.board, user=cls.viewer_u, role='viewer')
        for u in (cls.owner_u, cls.member_u, cls.viewer_u):
            _mk_profile(u, cls.org, cls.ws)

        # Stranger in a separate org/workspace
        cls.stranger_u = User.objects.create_user('cb_stranger', password='x')
        cls.other_org = Organization.objects.create(
            name='CB Other', is_demo=False, created_by=cls.stranger_u,
        )
        cls.other_ws = Workspace.objects.create(
            name='CB Other WS', organization=cls.other_org, is_demo=False,
            is_active=True, created_by=cls.stranger_u,
        )
        _mk_profile(cls.stranger_u, cls.other_org, cls.other_ws)

    # ── Per-board feature view (forecasting) ─────────────────────────────────
    def test_stranger_denied_forecast_dashboard(self):
        self.client.force_login(self.stranger_u)
        resp = self.client.get(reverse('forecast_dashboard', args=[self.board.id]))
        self.assertEqual(resp.status_code, 403)

    def test_viewer_denied_generate_forecast(self):
        # Viewer is read-only — the write endpoint must reject before any work.
        self.client.force_login(self.viewer_u)
        resp = self.client.post(reverse('generate_forecast', args=[self.board.id]))
        self.assertEqual(resp.status_code, 403)

    # ── board_detail (spectra denial) ────────────────────────────────────────
    def test_stranger_denied_board_detail(self):
        self.client.force_login(self.stranger_u)
        resp = self.client.get(reverse('board_detail', args=[self.board.id]))
        self.assertEqual(resp.status_code, 403)

    # ── Strategic / portfolio API (previously IDOR) ──────────────────────────
    def test_stranger_denied_portfolio_analytics_api(self):
        self.client.force_login(self.stranger_u)
        resp = self.client.get(
            reverse('portfolio_analytics_api', args=['goal', self.goal.id])
        )
        self.assertEqual(resp.status_code, 403)

    def test_descendant_board_member_allowed_portfolio_analytics_api(self):
        # A board member under the goal has read (view_goal) access via the
        # descendant-board-member rule.
        self.client.force_login(self.member_u)
        resp = self.client.get(
            reverse('portfolio_analytics_api', args=['goal', self.goal.id])
        )
        self.assertEqual(resp.status_code, 200)

    def test_stranger_denied_generate_proxy_metrics_api(self):
        self.client.force_login(self.stranger_u)
        resp = self.client.post(
            reverse('generate_proxy_metrics_api', args=[self.goal.id])
        )
        self.assertEqual(resp.status_code, 403)


class PortfolioWorkspaceScopingTests(TestCase):
    """Record aggregation must never cross workspace boundaries."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('ps_user', password='x')
        cls.org = Organization.objects.create(
            name='PS Org', is_demo=False, created_by=cls.user,
        )
        cls.ws_a = Workspace.objects.create(
            name='WS A', organization=cls.org, is_demo=False,
            is_active=True, created_by=cls.user,
        )
        cls.ws_b = Workspace.objects.create(
            name='WS B', organization=cls.org, is_demo=False,
            is_active=True, created_by=cls.user,
        )
        # Goal lives in workspace A.
        cls.goal = OrganizationGoal.objects.create(
            name='Scoped Goal', organization=cls.org, workspace=cls.ws_a,
            created_by=cls.user,
        )
        cls.mission = Mission.objects.create(
            name='M', organization_goal=cls.goal, workspace=cls.ws_a,
            created_by=cls.user,
        )
        cls.strategy = Strategy.objects.create(
            name='S', mission=cls.mission, workspace=cls.ws_a, status='active',
            created_by=cls.user,
        )
        # Board A in workspace A (the legitimately linked board).
        cls.board_a = Board.objects.create(
            name='Board A', organization=cls.org, workspace=cls.ws_a,
            strategy=cls.strategy, created_by=cls.user,
        )
        # Board B is linked into the same strategy chain but sits in workspace B
        # (simulates a data inconsistency that must NOT bleed into aggregation).
        cls.board_b = Board.objects.create(
            name='Board B', organization=cls.org, workspace=cls.ws_b,
            strategy=cls.strategy, created_by=cls.user,
        )

    def test_get_boards_for_record_scopes_to_record_workspace(self):
        from kanban.utils.analytics_helpers import get_boards_for_record
        ids = set(get_boards_for_record(self.goal, 'goal').values_list('id', flat=True))
        self.assertIn(self.board_a.id, ids)
        self.assertNotIn(self.board_b.id, ids)


class SecondPassHardeningTests(TestCase):
    """Regressions for the launch-hardening pass: cross-tenant access-request
    approval and viewer-write enforcement on secondary write paths."""

    @classmethod
    def setUpTestData(cls):
        from kanban.access_request_models import AccessRequest

        # Org A — the victim board.
        cls.owner_u = User.objects.create_user('sp_owner', password='x')
        cls.org_a = Organization.objects.create(
            name='SP Org A', is_demo=False, created_by=cls.owner_u,
        )
        cls.ws_a = Workspace.objects.create(
            name='SP WS A', organization=cls.org_a, is_demo=False,
            is_active=True, created_by=cls.owner_u,
        )
        cls.board = Board.objects.create(
            name='SP Board', organization=cls.org_a, workspace=cls.ws_a,
            created_by=cls.owner_u,
        )
        Column.objects.create(name='To Do', board=cls.board, position=0)
        cls.viewer_u = User.objects.create_user('sp_viewer', password='x')
        BoardMembership.objects.create(board=cls.board, user=cls.viewer_u, role='viewer')
        for u in (cls.owner_u, cls.viewer_u):
            _mk_profile(u, cls.org_a, cls.ws_a)

        # Org B — an OrgAdmin of a *different* tenant (the attacker).
        cls.attacker = User.objects.create_user('sp_attacker', password='x')
        cls.org_b = Organization.objects.create(
            name='SP Org B', is_demo=False, created_by=cls.attacker,
        )
        cls.ws_b = Workspace.objects.create(
            name='SP WS B', organization=cls.org_b, is_demo=False,
            is_active=True, created_by=cls.attacker,
        )
        _mk_profile(cls.attacker, cls.org_b, cls.ws_b)
        org_admin_group, _ = Group.objects.get_or_create(name='OrgAdmin')
        cls.attacker.groups.add(org_admin_group)  # admin of org B only

        # A pending request to join the org-A board.
        cls.requester = User.objects.create_user('sp_requester', password='x')
        cls.req = AccessRequest.objects.create(
            requester=cls.requester, board=cls.board, owner=cls.owner_u,
            status='pending', requested_role='member',
        )

    def test_cross_tenant_admin_cannot_approve_access_request(self):
        # An OrgAdmin of a different tenant must not approve a request on this board.
        self.client.force_login(self.attacker)
        resp = self.client.post(
            reverse('api_approve_access_request', args=[self.req.id]),
            data='{}', content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, 'pending')
        self.assertFalse(
            BoardMembership.objects.filter(board=self.board, user=self.requester).exists()
        )

    def test_board_owner_can_approve_access_request(self):
        self.client.force_login(self.owner_u)
        resp = self.client.post(
            reverse('api_approve_access_request', args=[self.req.id]),
            data='{"role": "member"}', content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(
            BoardMembership.objects.filter(board=self.board, user=self.requester).exists()
        )

    def test_viewer_cannot_create_requirement(self):
        from requirements.models import Requirement
        self.client.force_login(self.viewer_u)
        resp = self.client.post(
            reverse('requirements:requirement_create', args=[self.board.id]),
            data={'title': 'Sneaky', 'description': 'x'},
        )
        self.assertIn(resp.status_code, (302, 403))
        self.assertEqual(Requirement.objects.filter(board=self.board).count(), 0)
