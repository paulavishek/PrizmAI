"""RBAC-in-demo bypass guard.

Invariant: RBAC applies only in a user's real workspace and is fully bypassed in
the demo workspace — a demo user must never hit a 403 / "no access" on a demo
board. Several gates carried no demo term of their own and would 403 a demo user
on a demo board they don't own (e.g. the shared official template board, which a
brand-new demo user sees before provisioning). These tests pin the fixes to the
two verified gates and prove real-workspace RBAC still denies.
"""
import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory

from accounts.models import Organization, UserProfile
from kanban.models import Board, Workspace


@pytest.fixture
def demo_and_real(db):
    persona = User.objects.create_user('persona.rbac', password='x')
    demo_org = Organization.objects.create(name='Demo Org RBAC', is_demo=True, created_by=persona)
    demo_ws = Workspace.objects.create(
        name='Demo WS RBAC', organization=demo_org, is_demo=True, is_active=True,
        created_by=persona,
    )
    # Official template board owned by the persona (NOT the demo user under test).
    template = Board.objects.create(
        name='Template', organization=demo_org, workspace=demo_ws,
        is_official_demo_board=True, is_seed_demo_data=True,
        created_by=persona, owner=persona,
    )

    # A real (non-demo) user + their own real board, plus a real board they do
    # NOT own — RBAC must still deny the latter.
    owner = User.objects.create_user('real.owner', password='x')
    real_org = Organization.objects.create(name='Real Org', created_by=owner)
    real_ws = Workspace.objects.create(
        name='Real WS', organization=real_org, is_active=True, created_by=owner,
    )
    others_board = Board.objects.create(
        name='Someone Elses', organization=real_org, workspace=real_ws,
        created_by=owner, owner=owner,
    )

    # The user under test: a real user who can toggle into demo mode.
    user = User.objects.create_user('demo.explorer', password='x')
    UserProfile.objects.get_or_create(user=user)
    return type('D', (), {
        'demo_ws': demo_ws, 'template': template, 'user': user,
        'others_board': others_board,
    })()


def _req(user, demo):
    rf = RequestFactory()
    req = rf.get('/x/')
    req.user = user
    prof = user.profile
    prof.is_viewing_demo = demo
    prof.save(update_fields=['is_viewing_demo'])
    return req


@pytest.mark.django_db
def test_budget_gate_bypassed_for_demo_user_on_unowned_demo_board(demo_and_real):
    from kanban.budget_views import _require_budget_access
    d = demo_and_real
    # Demo user on the shared official template board (which they don't own).
    assert _require_budget_access(_req(d.user, demo=True), d.template) is None


@pytest.mark.django_db
def test_budget_gate_still_denies_real_user_on_unowned_real_board(demo_and_real):
    from kanban.budget_views import _require_budget_access
    d = demo_and_real
    denied = _require_budget_access(_req(d.user, demo=False), d.others_board)
    assert denied is not None  # 403 preserved in real workspaces


@pytest.mark.django_db
def test_requirements_gate_bypassed_for_demo_user_on_unowned_demo_board(demo_and_real):
    from requirements.views import _get_board_and_check_access
    d = demo_and_real
    board, _membership = _get_board_and_check_access(_req(d.user, demo=True), d.template.id)
    assert board is not None  # access granted, not the (None, None) denial


@pytest.mark.django_db
def test_requirements_gate_still_denies_real_user_on_unowned_real_board(demo_and_real):
    from requirements.views import _get_board_and_check_access
    d = demo_and_real
    board, _membership = _get_board_and_check_access(_req(d.user, demo=False), d.others_board.id)
    assert board is None  # denied in real workspaces
