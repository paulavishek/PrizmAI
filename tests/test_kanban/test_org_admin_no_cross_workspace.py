"""Regression: Org Admin must NOT reach a colleague's separate-workspace data.

This locks in the fix for the org-admin cross-workspace leak (pre-launch
hardening). The dangerous configuration is TWO real users sharing ONE
Organization but owning SEPARATE workspaces — exactly what invite acceptance
produces: accepting a workspace/org invite reassigns the invitee's
``profile.organization`` to the inviter's org (``kanban/workspace_member_views``
/ ``accounts/views`` accept flows), while the invitee keeps their own workspace
and boards (org-stamped with the now-shared org).

Before the fix, the django-rules ``is_org_admin`` predicate was OR'd into every
board/strategic rule and matched on ``profile.organization_id == obj.organization_id``
— so the inviting org admin gained view/edit/delete on the invitee's boards and
strategic records. The fix removes ``is_org_admin`` from those rules
(``kanban/permissions.py``); Workspace membership is the sole boundary. Only
Django superusers retain cross-tenant reach.

These tests assert the org admin is denied on the colleague's board AND on their
strategic records, while both users keep full access to their own data.
"""
from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import Organization, UserProfile
from kanban.models import (
    Board, BoardMembership, Column, Workspace,
    OrganizationGoal, Mission, Strategy,
)
from kanban.permissions import is_user_org_admin


class OrgAdminNoCrossWorkspaceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # ── One shared Organization, created by the admin (User A) ──
        cls.admin = User.objects.create_user('org_admin_a', password='x')
        cls.shared_org = Organization.objects.create(
            name='Shared Org', is_demo=False, created_by=cls.admin,
        )

        # ── User A's own workspace + full strategic chain + board ──
        cls.ws_a = Workspace.objects.create(
            name="A's WS", organization=cls.shared_org, is_demo=False,
            is_active=True, created_by=cls.admin,
        )
        cls.board_a = Board.objects.create(
            name="A Board", organization=cls.shared_org, workspace=cls.ws_a,
            created_by=cls.admin, owner=cls.admin,
        )
        Column.objects.create(name='To Do', board=cls.board_a, position=0)

        # ── User B: a colleague in the SAME org (as if they accepted an invite,
        #    which reassigned their profile.organization to the shared org), but
        #    with their OWN separate workspace, board, and strategic records. ──
        cls.colleague = User.objects.create_user('colleague_b', password='x')
        cls.ws_b = Workspace.objects.create(
            name="B's WS", organization=cls.shared_org, is_demo=False,
            is_active=True, created_by=cls.colleague,
        )
        cls.goal_b = OrganizationGoal.objects.create(
            name="B Goal", organization=cls.shared_org, workspace=cls.ws_b,
            created_by=cls.colleague, owner=cls.colleague,
        )
        cls.mission_b = Mission.objects.create(
            name="B Mission", organization_goal=cls.goal_b, workspace=cls.ws_b,
            created_by=cls.colleague, owner=cls.colleague,
        )
        cls.strategy_b = Strategy.objects.create(
            name="B Strategy", mission=cls.mission_b, workspace=cls.ws_b,
            status='active', created_by=cls.colleague, owner=cls.colleague,
        )
        cls.board_b = Board.objects.create(
            name="B Board", organization=cls.shared_org, workspace=cls.ws_b,
            strategy=cls.strategy_b, created_by=cls.colleague, owner=cls.colleague,
        )
        Column.objects.create(name='To Do', board=cls.board_b, position=0)

        # Profiles: both point at the SAME shared org (the leak precondition).
        for u, ws in ((cls.admin, cls.ws_a), (cls.colleague, cls.ws_b)):
            p, _ = UserProfile.objects.get_or_create(user=u)
            p.organization = cls.shared_org
            p.active_workspace = ws
            p.is_viewing_demo = False
            p.save()

    def test_precondition_admin_is_org_admin(self):
        # If this ever regresses to False, the deny-assertions below would pass
        # trivially. Prove A really is an org admin of the shared org.
        self.assertTrue(is_user_org_admin(self.admin))

    def test_org_admin_denied_on_colleague_board(self):
        # The core leak: A must NOT reach B's board in B's own workspace.
        self.assertFalse(self.admin.has_perm('prizmai.view_board', self.board_b))
        self.assertFalse(self.admin.has_perm('prizmai.edit_board', self.board_b))
        self.assertFalse(self.admin.has_perm('prizmai.delete_board', self.board_b))
        self.assertFalse(self.admin.has_perm('prizmai.invite_board_member', self.board_b))

    def test_org_admin_denied_on_colleague_strategic_records(self):
        # Same leak class on the strategic hierarchy.
        self.assertFalse(self.admin.has_perm('prizmai.view_goal', self.goal_b))
        self.assertFalse(self.admin.has_perm('prizmai.edit_goal', self.goal_b))
        self.assertFalse(self.admin.has_perm('prizmai.view_mission', self.mission_b))
        self.assertFalse(self.admin.has_perm('prizmai.edit_mission', self.mission_b))
        self.assertFalse(self.admin.has_perm('prizmai.view_strategy', self.strategy_b))
        self.assertFalse(self.admin.has_perm('prizmai.edit_strategy', self.strategy_b))

    def test_owners_keep_access_to_their_own_data(self):
        # B still fully controls B's own board + strategy.
        self.assertTrue(self.colleague.has_perm('prizmai.view_board', self.board_b))
        self.assertTrue(self.colleague.has_perm('prizmai.edit_board', self.board_b))
        self.assertTrue(self.colleague.has_perm('prizmai.delete_board', self.board_b))
        self.assertTrue(self.colleague.has_perm('prizmai.edit_goal', self.goal_b))
        # A still fully controls A's own board.
        self.assertTrue(self.admin.has_perm('prizmai.view_board', self.board_a))
        self.assertTrue(self.admin.has_perm('prizmai.edit_board', self.board_a))
        self.assertTrue(self.admin.has_perm('prizmai.delete_board', self.board_a))

    def test_superuser_retains_cross_tenant_reach(self):
        # Superuser is the ONLY role with legitimate cross-tenant access.
        su = User.objects.create_superuser('root', 'root@example.com', 'x')
        self.assertTrue(su.has_perm('prizmai.view_board', self.board_b))
        self.assertTrue(su.has_perm('prizmai.edit_board', self.board_b))
