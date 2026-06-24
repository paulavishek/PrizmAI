"""
Cross-tenant isolation regression tests (pre-launch hardening).

Each test builds TWO fully independent tenants — separate Organization,
Workspace, user + profile, and board — and asserts that a user in tenant B
cannot see or act on tenant A's data. These lock in the fixes for the
organization-vs-workspace isolation gaps:

  * Spectra RBAC bypass — a self-org admin getting owner on every board.
  * join_board fail-open — self-joining any org-less board.
  * board-list / prediction leaks scoped by the nullable Board.organization.

Root cause of all of them: guards keyed on Board.organization, which is a
legacy nullable field (None on most boards). The fixes scope by Workspace /
board membership and fail CLOSED when the key is null.
"""

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse


def _make_tenant(slug):
    """Create an isolated tenant: org, workspace, user+profile, board, column.

    The user is the creator of their own Organization, which makes
    ``is_user_org_admin(user)`` True — exactly the condition that triggered the
    Spectra cross-tenant bypass, so tenant B is a realistic attacker here.
    """
    from accounts.models import Organization, UserProfile
    from kanban.models import Workspace, Board, Column

    user = User.objects.create_user(
        username=f'{slug}_user', password='pw', email=f'{slug}@example.com',
    )
    org = Organization.objects.create(name=f'{slug} Org', created_by=user)
    ws = Workspace.objects.create(
        name=f"{slug}'s Workspace", organization=org,
        created_by=user, is_demo=False,
    )
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.organization = org
    profile.active_workspace = ws
    profile.is_viewing_demo = False
    profile.save()

    board = Board.objects.create(
        name=f'{slug} Board', created_by=user, owner=user,
        organization=org, workspace=ws,
    )
    col = Column.objects.create(board=board, name='Backlog', position=0)
    return {
        'user': user, 'org': org, 'ws': ws,
        'board': board, 'col': col, 'profile': profile,
    }


def _completed_task(col, title, complexity=5, duration=3.0):
    """Create a completed task with a usable actual_duration_days.

    Uses .update() to set the derived fields directly, bypassing Task.save()
    so the prediction query (progress=100, actual_duration_days>0) sees them.
    """
    from kanban.models import Task
    t = Task.objects.create(column=col, title=title, complexity_score=complexity,
                            created_by=col.board.created_by)
    Task.objects.filter(id=t.id).update(progress=100, actual_duration_days=duration)
    return Task.objects.get(id=t.id)


class SpectraRBACIsolationTest(TestCase):
    """The headline bypass: a user who is admin of their OWN org must not get
    any role on another tenant's board through Spectra."""

    def test_self_org_admin_has_no_role_on_foreign_board(self):
        from ai_assistant.utils.rbac_utils import (
            get_user_board_role, can_spectra_read_board, can_spectra_write_board,
        )
        from kanban.permissions import is_user_org_admin

        a = _make_tenant('alpha')
        b = _make_tenant('bravo')

        # Precondition: B really is an org-admin (org creator) — the trigger.
        self.assertTrue(is_user_org_admin(b['user']))

        # B must get NO role / no access on A's board.
        self.assertIsNone(get_user_board_role(b['user'], a['board']))
        self.assertFalse(can_spectra_read_board(b['user'], a['board']))
        self.assertFalse(can_spectra_write_board(b['user'], a['board']))

        # Sanity: A (owner) still gets owner on their own board.
        self.assertEqual(get_user_board_role(a['user'], a['board']), 'owner')
        self.assertTrue(can_spectra_read_board(a['user'], a['board']))

    def test_org_admin_needs_membership_on_colleague_board(self):
        """Workspace is the tenant boundary now: org-admin status alone grants
        NO role on a colleague's board — access requires explicit membership.
        An explicit BoardMembership still works."""
        from ai_assistant.utils.rbac_utils import get_user_board_role
        from kanban.models import Board, Column, BoardMembership

        a = _make_tenant('charlie')
        # A colleague creates a board inside A's own org/workspace.
        colleague = User.objects.create_user(username='colleague', password='pw')
        board2 = Board.objects.create(
            name='Colleague Board', created_by=colleague, owner=colleague,
            organization=a['org'], workspace=a['ws'],
        )
        Column.objects.create(board=board2, name='Backlog', position=0)

        # A is org admin but NOT a member → no role (Organization is not a
        # basis for board access).
        self.assertIsNone(get_user_board_role(a['user'], board2))

        # Explicit membership grants the corresponding role.
        BoardMembership.objects.create(board=board2, user=a['user'], role='member')
        self.assertEqual(get_user_board_role(a['user'], board2), 'member')


class CoreAccessGateIsolationTest(TestCase):
    def test_can_access_board_denies_foreign_tenant(self):
        from kanban.simple_access import can_access_board

        a = _make_tenant('delta')
        b = _make_tenant('echo')

        self.assertFalse(can_access_board(b['user'], a['board']))
        self.assertTrue(can_access_board(a['user'], a['board']))


class BoardListIsolationTest(TestCase):
    def test_get_user_boards_excludes_foreign_workspace(self):
        from kanban.utils.demo_protection import get_user_boards

        a = _make_tenant('foxtrot')
        b = _make_tenant('golf')

        b_ids = set(get_user_boards(b['user']).values_list('id', flat=True))
        self.assertIn(b['board'].id, b_ids)
        self.assertNotIn(a['board'].id, b_ids)


class PredictionIsolationTest(TestCase):
    """task_prediction must never pull completed tasks from another workspace."""

    def test_prediction_history_stays_within_workspace(self):
        from kanban.models import Task
        from kanban.utils.task_prediction import predict_task_completion_date

        a = _make_tenant('hotel')
        b = _make_tenant('india')

        # Tenant A: 3 completed complexity-5 tasks (must NOT leak into B).
        for i in range(3):
            _completed_task(a['col'], f'A done {i}', complexity=5)
        # Tenant B: 2 completed complexity-5 tasks (the only valid history).
        b_done_ids = {
            _completed_task(b['col'], f'B done {i}', complexity=5).id
            for i in range(2)
        }

        # An in-progress B task to predict.
        from django.utils import timezone
        target = Task.objects.create(
            column=b['col'], title='B target', complexity_score=5,
            progress=40, start_date=timezone.now().date(),
            created_by=b['user'],
        )

        pred = predict_task_completion_date(target)
        self.assertIsNotNone(pred)
        # Only B's 2 completed tasks count — never A's 3.
        self.assertEqual(pred['based_on_tasks'], 2)
        shown_ids = {s['id'] for s in pred.get('similar_tasks', [])}
        self.assertTrue(shown_ids.issubset(b_done_ids))


class JoinBoardIsolationTest(TestCase):
    def test_cannot_join_foreign_workspace_board(self):
        from kanban.models import BoardMembership

        a = _make_tenant('juliet')
        b = _make_tenant('kilo')

        client = Client()
        client.force_login(b['user'])
        resp = client.get(reverse('join_board', args=[a['board'].id]))

        # Denied → redirected away, and NO membership granted.
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(
            BoardMembership.objects.filter(board=a['board'], user=b['user']).exists()
        )

    def test_can_join_board_in_own_workspace(self):
        """Positive control: same-workspace self-join still works (we scoped to
        workspace, we didn't disable the feature)."""
        from kanban.models import Board, Column, BoardMembership

        b = _make_tenant('lima')
        colleague = User.objects.create_user(username='lima_mate', password='pw')
        shared = Board.objects.create(
            name='Shared', created_by=colleague, owner=colleague,
            organization=b['org'], workspace=b['ws'],
        )
        Column.objects.create(board=shared, name='Backlog', position=0)

        client = Client()
        client.force_login(b['user'])
        resp = client.get(reverse('join_board', args=[shared.id]))

        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            BoardMembership.objects.filter(board=shared, user=b['user']).exists()
        )


class BoardAccessMiddlewareTest(TestCase):
    """The systemic backstop: BoardAccessEnforcementMiddleware must deny any
    board/task/column-scoped request whose user can't view that board, while
    leaving legitimate access (owner, member, demo) untouched."""

    def _ajax_request(self, user):
        from django.test import RequestFactory
        # AJAX so the denial is a JsonResponse (no template render in unit test).
        req = RequestFactory().get('/x/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        req.user = user
        return req

    def _mw(self):
        from kanban.middleware.board_access import BoardAccessEnforcementMiddleware
        return BoardAccessEnforcementMiddleware(lambda r: None)

    @staticmethod
    def _view(request, **kwargs):  # generic non-whitelisted view
        return None

    def test_foreign_board_denied(self):
        a = _make_tenant('mike')
        b = _make_tenant('november')
        resp = self._mw().process_view(
            self._ajax_request(b['user']), self._view, [], {'board_id': a['board'].id})
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status_code, 403)

    def test_owner_allowed(self):
        a = _make_tenant('oscar')
        resp = self._mw().process_view(
            self._ajax_request(a['user']), self._view, [], {'board_id': a['board'].id})
        self.assertIsNone(resp)

    def test_member_allowed(self):
        from kanban.models import BoardMembership
        a = _make_tenant('papa')
        b = _make_tenant('quebec')
        BoardMembership.objects.create(board=a['board'], user=b['user'], role='member')
        resp = self._mw().process_view(
            self._ajax_request(b['user']), self._view, [], {'board_id': a['board'].id})
        self.assertIsNone(resp)

    def test_foreign_task_and_column_denied(self):
        from kanban.models import Task
        a = _make_tenant('romeo')
        b = _make_tenant('sierra')
        task = Task.objects.create(column=a['col'], title='secret', created_by=a['user'])
        resp_t = self._mw().process_view(
            self._ajax_request(b['user']), self._view, [], {'task_id': task.id})
        resp_c = self._mw().process_view(
            self._ajax_request(b['user']), self._view, [], {'column_id': a['col'].id})
        self.assertEqual(getattr(resp_t, 'status_code', None), 403)
        self.assertEqual(getattr(resp_c, 'status_code', None), 403)

    def test_whitelisted_join_board_not_enforced(self):
        # A view named join_board manages its own access → middleware must skip it.
        def join_board(request, **kwargs):
            return None
        a = _make_tenant('tango')
        b = _make_tenant('uniform')
        resp = self._mw().process_view(
            self._ajax_request(b['user']), join_board, [], {'board_id': a['board'].id})
        self.assertIsNone(resp)

    def test_official_demo_board_allowed_for_any_user(self):
        from kanban.models import Board
        b = _make_tenant('victor')
        demo = Board.objects.create(
            name='Official Demo', created_by=b['user'], is_official_demo_board=True,
        )
        # A different user with no relationship still passes (demo is universal).
        outsider = User.objects.create_user(username='outsider', password='pw')
        from accounts.models import UserProfile
        UserProfile.objects.get_or_create(user=outsider)
        resp = self._mw().process_view(
            self._ajax_request(outsider), self._view, [], {'board_id': demo.id})
        self.assertIsNone(resp)

    def test_non_board_kwarg_is_inert(self):
        # A pk/id that isn't a real board → middleware stays out of the way.
        a = _make_tenant('whiskey')
        resp = self._mw().process_view(
            self._ajax_request(a['user']), self._view, [], {'board_id': 99999999})
        self.assertIsNone(resp)


class BoardDetailEndToEndIsolationTest(TestCase):
    """End-to-end through the full middleware stack: the primary board page must
    render for its owner and be denied (403) to a foreign tenant — proving the
    enforcement middleware doesn't break legitimate access."""

    def test_owner_can_open_board_detail(self):
        a = _make_tenant('xray')
        client = Client()
        client.force_login(a['user'])
        resp = client.get(reverse('board_detail', args=[a['board'].id]))
        self.assertEqual(resp.status_code, 200)

    def test_foreign_tenant_denied_board_detail(self):
        a = _make_tenant('yankee')
        b = _make_tenant('zulu')
        client = Client()
        client.force_login(b['user'])
        resp = client.get(reverse('board_detail', args=[a['board'].id]))
        self.assertEqual(resp.status_code, 403)


def _make_pending_suggestion(tenant):
    """A pending ResourceLevelingSuggestion on ``tenant``'s board."""
    from datetime import timedelta
    from django.utils import timezone
    from kanban.models import Task
    from kanban.resource_leveling_models import ResourceLevelingSuggestion

    task = Task.objects.create(
        column=tenant['col'], title='RL task', created_by=tenant['user'],
        assigned_to=tenant['user'],
    )
    return ResourceLevelingSuggestion.objects.create(
        task=task,
        workspace=tenant['ws'],
        current_assignee=tenant['user'],
        suggested_assignee=tenant['user'],
        confidence_score=80.0,
        time_savings_hours=2.0,
        time_savings_percentage=20.0,
        skill_match_score=50.0,
        workload_impact='balances_load',
        reasoning='test',
        expires_at=timezone.now() + timedelta(hours=48),
    )


class ResourceLevelingSuggestionIsolationTest(TestCase):
    """accept/reject_suggestion are keyed on suggestion_id, which the board-access
    middleware does NOT cover — they must enforce board access themselves."""

    def test_foreign_tenant_cannot_accept_suggestion(self):
        a = _make_tenant('rl_alpha')
        b = _make_tenant('rl_bravo')
        sug = _make_pending_suggestion(a)

        client = Client()
        client.force_login(b['user'])
        resp = client.post(reverse('accept_suggestion', args=[sug.id]))

        self.assertEqual(resp.status_code, 403)
        sug.refresh_from_db()
        self.assertEqual(sug.status, 'pending')  # no state change

    def test_foreign_tenant_cannot_reject_suggestion(self):
        a = _make_tenant('rl_charlie')
        b = _make_tenant('rl_delta')
        sug = _make_pending_suggestion(a)

        client = Client()
        client.force_login(b['user'])
        resp = client.post(reverse('reject_suggestion', args=[sug.id]))

        self.assertEqual(resp.status_code, 403)
        sug.refresh_from_db()
        self.assertEqual(sug.status, 'pending')  # no state change

    def test_owner_can_act_on_own_suggestion(self):
        # Positive control: the board owner is not blocked by the new gate.
        a = _make_tenant('rl_echo')
        sug = _make_pending_suggestion(a)

        client = Client()
        client.force_login(a['user'])
        resp = client.post(reverse('reject_suggestion', args=[sug.id]))

        self.assertEqual(resp.status_code, 200)
        sug.refresh_from_db()
        self.assertEqual(sug.status, 'rejected')


class PerformanceProfileIsolationTest(TestCase):
    """get_user_performance_profile is keyed on user_id (not board-scoped) — a
    user may read only their own profile or that of someone on a shared board."""

    def test_foreign_user_profile_denied(self):
        a = _make_tenant('pp_alpha')
        b = _make_tenant('pp_bravo')
        client = Client()
        client.force_login(b['user'])
        resp = client.get(
            reverse('get_user_performance_profile', args=[a['user'].id])
        )
        self.assertEqual(resp.status_code, 403)

    def test_own_profile_allowed(self):
        b = _make_tenant('pp_charlie')
        client = Client()
        client.force_login(b['user'])
        resp = client.get(
            reverse('get_user_performance_profile', args=[b['user'].id])
        )
        self.assertEqual(resp.status_code, 200)


class MemoryFeedbackIsolationTest(TestCase):
    """memory_feedback is keyed on query_id — only the user who ran the query may
    submit feedback (otherwise another tenant could poison memory ranking)."""

    def test_foreign_tenant_cannot_submit_feedback(self):
        import json
        from knowledge_graph.models import OrganizationalMemoryQuery

        a = _make_tenant('mf_alpha')
        b = _make_tenant('mf_bravo')
        query = OrganizationalMemoryQuery.objects.create(
            asked_by=a['user'], query_text='what is the secret?',
        )

        client = Client()
        client.force_login(b['user'])
        resp = client.post(
            reverse('memory_feedback', args=[query.id]),
            data=json.dumps({'was_helpful': False}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)
        query.refresh_from_db()
        self.assertIsNone(query.was_helpful)  # no state change
