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
        cls.demo_creator = User.objects.create_user('demo_creator', password='x')
        cls.demo_org = Organization.objects.create(
            name='Demo Org', is_demo=True, created_by=cls.demo_creator,
        )
        cls.demo_ws = Workspace.objects.create(
            name='Demo Workspace', organization=cls.demo_org,
            is_demo=True, is_active=True, created_by=cls.demo_creator,
        )
        cls.demo_goal = OrganizationGoal.objects.create(
            name='Demo Goal', organization=cls.demo_org,
            workspace=cls.demo_ws, is_demo=True, is_seed_demo_data=True,
            created_by=cls.demo_creator,
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
        cls.profile, _ = UserProfile.objects.get_or_create(user=cls.user)
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

    def test_demo_mode_includes_user_created_demo_board(self):
        """A board the user creates *inside the demo workspace* (not a sandbox
        copy) must appear in demo mode alongside the demo/sandbox boards — but a
        board in their real workspace must still be excluded."""
        demo_made = Board.objects.create(
            name='Demo Test Board', workspace=self.demo_ws,
            owner=self.user, created_by=self.user,
        )
        BoardMembership.objects.create(
            board=demo_made, user=self.user, role='owner',
        )

        self.profile.is_viewing_demo = True
        self.profile.active_workspace = self.demo_ws
        self.profile.save(update_fields=['is_viewing_demo', 'active_workspace'])

        names = set(get_user_boards(self.user).values_list('name', flat=True))
        assert 'Demo Test Board' in names   # user-created demo board now visible
        assert 'Sandbox Board' in names     # sandbox copy still visible
        assert 'Real Board' not in names    # real-workspace board stays isolated

    def test_real_mode_excludes_demo_created_board(self):
        """The same demo-workspace board must NOT leak into the user's real
        workspace view."""
        Board.objects.create(
            name='Demo Test Board', workspace=self.demo_ws,
            owner=self.user, created_by=self.user,
        )
        self.profile.is_viewing_demo = False
        self.profile.active_workspace = self.real_ws
        self.profile.save(update_fields=['is_viewing_demo', 'active_workspace'])

        names = set(get_user_boards(self.user).values_list('name', flat=True))
        assert 'Demo Test Board' not in names
        assert 'Real Board' in names

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


class WorkspacePresetIsolationTestCase(TestCase):
    """Workspace feature-level presets must not leak between sibling
    workspaces that share a single Organization.

    Regression for the bug where WorkspacePreset was keyed on Organization,
    so two users in different workspaces of the same org saw (and overwrote)
    each other's feature level.
    """

    @classmethod
    def setUpTestData(cls):
        cls.creator = User.objects.create_user('preset_creator', password='x')
        # One org, two independent workspaces (the leak scenario).
        cls.org = Organization.objects.create(
            name='Shared Org', is_demo=False, created_by=cls.creator,
        )
        cls.ws_a = Workspace.objects.create(
            name='Workspace A', organization=cls.org, created_by=cls.creator,
        )
        cls.ws_b = Workspace.objects.create(
            name='Workspace B', organization=cls.org, created_by=cls.creator,
        )

    def _preset(self, ws):
        from kanban.preset_models import WorkspacePreset
        return WorkspacePreset.objects.get(workspace=ws).global_preset

    def test_signal_creates_one_preset_per_workspace(self):
        """Each workspace gets its own auto-created preset row."""
        from kanban.preset_models import WorkspacePreset
        self.assertTrue(WorkspacePreset.objects.filter(workspace=self.ws_a).exists())
        self.assertTrue(WorkspacePreset.objects.filter(workspace=self.ws_b).exists())
        self.assertEqual(
            WorkspacePreset.objects.filter(workspace__organization=self.org).count(),
            2,
        )

    def test_changing_one_workspace_does_not_affect_sibling(self):
        """Setting Workspace A to lean leaves Workspace B untouched."""
        from kanban.preset_models import WorkspacePreset
        wp_a = WorkspacePreset.objects.get(workspace=self.ws_a)
        wp_a.global_preset = 'lean'
        wp_a.save()
        wp_b = WorkspacePreset.objects.get(workspace=self.ws_b)
        wp_b.global_preset = 'enterprise'
        wp_b.save()

        self.assertEqual(self._preset(self.ws_a), 'lean')
        self.assertEqual(self._preset(self.ws_b), 'enterprise')

    def test_board_effective_preset_follows_its_workspace(self):
        """A board resolves its global ceiling from its own workspace."""
        from kanban.preset_models import WorkspacePreset, BoardPreset
        WorkspacePreset.objects.filter(workspace=self.ws_a).update(global_preset='lean')
        WorkspacePreset.objects.filter(workspace=self.ws_b).update(global_preset='enterprise')

        board_a = Board.objects.create(
            name='Board A', organization=self.org, workspace=self.ws_a,
            created_by=self.creator,
        )
        board_b = Board.objects.create(
            name='Board B', organization=self.org, workspace=self.ws_b,
            created_by=self.creator,
        )
        bp_a = BoardPreset.objects.get(board=board_a)
        bp_b = BoardPreset.objects.get(board=board_b)

        self.assertEqual(bp_a.effective_preset(), 'lean')
        self.assertEqual(bp_b.effective_preset(), 'enterprise')
