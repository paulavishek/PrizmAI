"""
Workspace Isolation Tests
=========================

Verify that demo and real workspace data never leak across boundaries.

These tests catch the class of bugs where:
  - Real boards/missions/goals appear in demo mode
  - Demo boards/missions/goals appear in real mode
  - toggle_demo_mode / switch_workspace corrupt profile state
  - _join_demo_org / _leave_demo_org lose the user's real org
"""

from django.test import TestCase
from django.contrib.auth.models import User, Group

from accounts.models import Organization, UserProfile
from kanban.models import (
    Board, BoardMembership, Column, Task, Mission, Strategy,
    OrganizationGoal, Workspace,
)
from kanban.utils.demo_protection import (
    get_user_boards,
    get_user_missions,
    get_user_goals,
    get_demo_workspace,
)
from kanban.sandbox_views import _join_demo_org, _leave_demo_org


class WorkspaceIsolationTestCase(TestCase):
    """End-to-end isolation between demo and real workspaces."""

    @classmethod
    def setUpTestData(cls):
        # ── Demo infrastructure ──
        cls.demo_org = Organization.objects.create(
            name='Demo Org', is_demo=True,
        )
        cls.demo_ws = Workspace.objects.create(
            name='Demo Workspace', organization=cls.demo_org,
            is_demo=True, is_active=True,
        )
        cls.demo_goal = OrganizationGoal.objects.create(
            name='Demo Goal', organization=cls.demo_org,
            workspace=cls.demo_ws, is_demo=True, is_seed_demo_data=True,
            created_by=User.objects.create_user('demo_creator', password='x'),
        )
        cls.demo_mission = Mission.objects.create(
            name='Demo Mission', organization_goal=cls.demo_goal,
            workspace=cls.demo_ws, is_demo=True, is_seed_demo_data=True,
            created_by=cls.demo_goal.created_by,
        )
        cls.demo_strategy = Strategy.objects.create(
            name='Demo Strategy', mission=cls.demo_mission,
            workspace=cls.demo_ws, status='active',
            created_by=cls.demo_goal.created_by,
        )
        cls.demo_board = Board.objects.create(
            name='Demo Board', organization=cls.demo_org,
            workspace=cls.demo_ws, is_official_demo_board=True,
            is_seed_demo_data=True, strategy=cls.demo_strategy,
            created_by=cls.demo_goal.created_by,
        )

        # ── Real user + workspace ──
        cls.user = User.objects.create_user('realuser', password='pass123')
        cls.real_org = Organization.objects.create(
            name='Real Org', is_demo=False, created_by=cls.user,
        )
        cls.real_ws = Workspace.objects.create(
            name='Real Workspace', organization=cls.real_org,
            is_demo=False, is_active=True, created_by=cls.user,
        )
        cls.real_goal = OrganizationGoal.objects.create(
            name='Real Goal', organization=cls.real_org,
            workspace=cls.real_ws, created_by=cls.user,
        )
        cls.real_mission = Mission.objects.create(
            name='Real Mission', organization_goal=cls.real_goal,
            workspace=cls.real_ws, created_by=cls.user,
        )
        cls.real_strategy = Strategy.objects.create(
            name='Real Strategy', mission=cls.real_mission,
            workspace=cls.real_ws, status='active',
            created_by=cls.user,
        )
        cls.real_board = Board.objects.create(
            name='Real Board', organization=cls.real_org,
            workspace=cls.real_ws, strategy=cls.real_strategy,
            created_by=cls.user,
        )
        BoardMembership.objects.create(
            board=cls.real_board, user=cls.user, role='owner',
        )

        # ── Sandbox copy (user's personal demo board) ──
        cls.sandbox_board = Board.objects.create(
            name='Sandbox Board', owner=cls.user,
            is_sandbox_copy=True, cloned_from=cls.demo_board,
            created_by=cls.user,
        )
        col = Column.objects.create(name='To Do', board=cls.sandbox_board, position=0)
        Task.objects.create(title='Sandbox Task', column=col, created_by=cls.user)

        # ── User profile ──
        cls.profile = UserProfile.objects.get(user=cls.user)
        cls.profile.organization = cls.real_org
        cls.profile.active_workspace = cls.real_ws
        cls.profile.is_viewing_demo = False
        cls.profile.onboarding_version = 2
        cls.profile.onboarding_status = 'completed'
        cls.profile.save()

    # ──────────────────────────────────────────────────────────────
    # Board isolation
    # ──────────────────────────────────────────────────────────────

    def test_real_mode_boards_exclude_demo(self):
        """In real mode, get_user_boards must NOT return demo or sandbox boards."""
        self.profile.is_viewing_demo = False
        self.profile.active_workspace = self.real_ws
        self.profile.save(update_fields=['is_viewing_demo', 'active_workspace'])

        boards = get_user_boards(self.user)
        board_names = set(boards.values_list('name', flat=True))

        assert 'Real Board' in board_names
        assert 'Demo Board' not in board_names
        assert 'Sandbox Board' not in board_names

    def test_demo_mode_boards_exclude_real(self):
        """In demo mode, get_user_boards must NOT return real workspace boards."""
        self.profile.is_viewing_demo = True
        self.profile.active_workspace = self.demo_ws
        self.profile.save(update_fields=['is_viewing_demo', 'active_workspace'])

        boards = get_user_boards(self.user)
        board_names = set(boards.values_list('name', flat=True))

        assert 'Sandbox Board' in board_names
        assert 'Real Board' not in board_names

    # ──────────────────────────────────────────────────────────────
    # Mission isolation
    # ──────────────────────────────────────────────────────────────

    def test_real_mode_missions_exclude_demo(self):
        """In real mode, get_user_missions must NOT return demo missions."""
        self.profile.is_viewing_demo = False
        self.profile.active_workspace = self.real_ws
        self.profile.save(update_fields=['is_viewing_demo', 'active_workspace'])

        missions = get_user_missions(self.user)
        names = set(missions.values_list('name', flat=True))

        assert 'Real Mission' in names
        assert 'Demo Mission' not in names

    def test_demo_mode_missions_exclude_real(self):
        """In demo mode, get_user_missions must NOT return real missions."""
        self.profile.is_viewing_demo = True
        self.profile.active_workspace = self.demo_ws
        self.profile.save(update_fields=['is_viewing_demo', 'active_workspace'])

        missions = get_user_missions(self.user)
        names = set(missions.values_list('name', flat=True))

        assert 'Demo Mission' in names
        assert 'Real Mission' not in names

    # ──────────────────────────────────────────────────────────────
    # Goal isolation
    # ──────────────────────────────────────────────────────────────

    def test_real_mode_goals_exclude_demo(self):
        self.profile.is_viewing_demo = False
        self.profile.active_workspace = self.real_ws
        self.profile.save(update_fields=['is_viewing_demo', 'active_workspace'])

        goals = get_user_goals(self.user)
        names = set(goals.values_list('name', flat=True))

        assert 'Real Goal' in names
        assert 'Demo Goal' not in names

    def test_demo_mode_goals_exclude_real(self):
        self.profile.is_viewing_demo = True
        self.profile.active_workspace = self.demo_ws
        self.profile.save(update_fields=['is_viewing_demo', 'active_workspace'])

        goals = get_user_goals(self.user)
        names = set(goals.values_list('name', flat=True))

        assert 'Demo Goal' in names
        assert 'Real Goal' not in names

    # ──────────────────────────────────────────────────────────────
    # Demo org join / leave cycle
    # ──────────────────────────────────────────────────────────────

    def test_join_leave_demo_preserves_real_org(self):
        """After join → leave cycle, user's real org must be restored."""
        self.profile.organization = self.real_org
        self.profile.save(update_fields=['organization'])

        # Join demo
        _join_demo_org(self.user)
        self.profile.refresh_from_db()
        assert self.profile.organization_id == self.demo_org.id

        # Leave demo
        _leave_demo_org(self.user)
        self.profile.refresh_from_db()
        assert self.profile.organization_id == self.real_org.id
        assert self.profile.organization.is_demo is False

    def test_leave_demo_never_sets_org_to_none(self):
        """_leave_demo_org must not leave org as None when user has a real workspace."""
        self.profile.organization = self.demo_org
        self.profile.save(update_fields=['organization'])

        _leave_demo_org(self.user)
        self.profile.refresh_from_db()

        assert self.profile.organization is not None
        assert self.profile.organization.is_demo is False

    # ──────────────────────────────────────────────────────────────
    # get_demo_workspace helper
    # ──────────────────────────────────────────────────────────────

    def test_get_demo_workspace_is_independent_of_profile(self):
        """get_demo_workspace() must always find the demo ws regardless of user state."""
        self.profile.organization = self.real_org
        self.profile.save(update_fields=['organization'])

        ws = get_demo_workspace()
        assert ws is not None
        assert ws.is_demo is True
        assert ws.id == self.demo_ws.id

    # ──────────────────────────────────────────────────────────────
    # Middleware heal
    # ──────────────────────────────────────────────────────────────

    def test_middleware_heals_demo_without_workspace(self):
        """If is_viewing_demo=True but active_workspace is None, middleware heals it."""
        from accounts.middleware import WorkspaceMiddleware

        self.profile.is_viewing_demo = True
        self.profile.active_workspace = None
        self.profile.save(update_fields=['is_viewing_demo', 'active_workspace'])

        WorkspaceMiddleware._heal_workspace_state(self.profile)
        self.profile.refresh_from_db()

        assert self.profile.active_workspace is not None
        assert self.profile.active_workspace.is_demo is True

    def test_middleware_heals_non_demo_with_demo_org(self):
        """If is_viewing_demo=False but org is demo, middleware restores real org."""
        from accounts.middleware import WorkspaceMiddleware

        self.profile.is_viewing_demo = False
        self.profile.organization = self.demo_org
        self.profile.active_workspace = None
        self.profile.save(update_fields=['is_viewing_demo', 'organization', 'active_workspace'])

        WorkspaceMiddleware._heal_workspace_state(self.profile)
        self.profile.refresh_from_db()

        assert self.profile.organization_id == self.real_org.id
        assert self.profile.active_workspace_id == self.real_ws.id
