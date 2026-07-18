"""Custom-field demo isolation tests.

CustomFieldDefinition is workspace-scoped, but the demo sandbox is a single
shared workspace — so without per-user copies every demo user would see, rename,
and delete every other demo user's custom fields (and the (workspace, name)
uniqueness would even stop two users making the same field). The fix mirrors the
Wiki/Discovery model: demo custom fields are cloned per user
(``sandbox_owner=user``) and reads are scoped to the current user's own clones
(mgmt UI) or the board owner's clones (task resolution).

These tests pin that guarantee: templates stay hidden, each demo user gets their
own clones (definitions + options + seeded task values), one user's edits never
bleed to another, and two demo users can hold the same-named field.
"""
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User

from accounts.models import Organization, UserProfile
from kanban.models import Board, BoardMembership, Column, Task, Workspace
from kanban.custom_field_models import (
    CustomFieldDefinition, CustomFieldOption, TaskCustomFieldValue,
)
from kanban.custom_field_scoping import (
    custom_field_scope_q_for_board, custom_field_scope_q_for_user,
)
from kanban.sandbox_views import _clone_custom_fields_for_user


@pytest.fixture
def demo_setup(db):
    author = User.objects.create_user('priya.persona.cf', password='x')
    org = Organization.objects.create(name='Demo Org CF', is_demo=True, created_by=author)
    ws = Workspace.objects.create(
        name='Demo WS CF', organization=org, is_demo=True, is_active=True, created_by=author,
    )
    # Template board the sandbox copies clone from, with one seeded task.
    template = Board.objects.create(
        name='Template', organization=org, workspace=ws,
        is_official_demo_board=True, is_seed_demo_data=True,
        created_by=author, owner=author,
    )
    tcol = Column.objects.create(board=template, name='To Do', position=0)
    ttask = Task.objects.create(
        column=tcol, title='Build Login', item_type='task', created_by=author,
    )

    # Template field definitions (sandbox_owner=None) — the seeder's output.
    sprint = CustomFieldDefinition.objects.create(
        workspace=ws, name='Sprint', field_type='list', applies_to_tasks=True,
        position=1, sandbox_owner=None,
    )
    opt = CustomFieldOption.objects.create(field=sprint, value='Sprint 1', position=1)
    points = CustomFieldDefinition.objects.create(
        workspace=ws, name='Story Points', field_type='integer',
        applies_to_tasks=True, position=2, sandbox_owner=None,
    )
    # A seeded value on the template task.
    from decimal import Decimal
    tv = TaskCustomFieldValue.objects.create(task=ttask, field=points, value_number=Decimal(5))
    tv_list = TaskCustomFieldValue.objects.create(task=ttask, field=sprint)
    tv_list.selected_options.set([opt])

    return SimpleNamespace(
        org=org, ws=ws, author=author, template=template, ttask=ttask,
        sprint=sprint, points=points, opt=opt,
    )


def _demo_user_with_sandbox(username, ds):
    """Create a demo user + a sandbox copy of the template board with a
    same-titled task, so the clone can re-point seeded values by title."""
    user = User.objects.create_user(username, password='x')
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.active_workspace = ds.ws
    profile.is_viewing_demo = True
    profile.save()
    sb = Board.objects.create(
        name='Template', organization=None, workspace=ds.ws,
        is_sandbox_copy=True, owner=user, created_by=user, cloned_from=ds.template,
    )
    BoardMembership.objects.create(board=sb, user=user, role='owner')
    col = Column.objects.create(board=sb, name='To Do', position=0)
    Task.objects.create(
        column=col, title='Build Login', item_type='task', created_by=user,
    )
    return user, sb


@pytest.mark.django_db
def test_clone_creates_private_defs_options_and_values(demo_setup):
    alice, sb = _demo_user_with_sandbox('cf_alice', demo_setup)
    _clone_custom_fields_for_user(alice)

    defs = CustomFieldDefinition.objects.filter(sandbox_owner=alice)
    assert set(defs.values_list('name', flat=True)) == {'Sprint', 'Story Points'}
    # Options cloned and re-pointed at the clone.
    assert CustomFieldOption.objects.filter(field__sandbox_owner=alice).count() == 1
    # Seeded task values re-created on the sandbox task, pointed at the clones.
    vals = TaskCustomFieldValue.objects.filter(field__sandbox_owner=alice)
    assert vals.count() == 2
    assert all(v.task.column.board_id == sb.id for v in vals)


@pytest.mark.django_db
def test_templates_hidden_from_board_and_user_scope(demo_setup):
    alice, sb = _demo_user_with_sandbox('cf_alice', demo_setup)
    _clone_custom_fields_for_user(alice)

    # Board-scoped read (task resolution) returns ONLY the owner's clones.
    board_defs = CustomFieldDefinition.objects.filter(custom_field_scope_q_for_board(sb))
    assert set(board_defs.values_list('sandbox_owner_id', flat=True)) == {alice.id}
    assert demo_setup.sprint not in list(board_defs)

    # User-scoped read (mgmt UI, demo mode) also returns only the user's clones.
    user_defs = CustomFieldDefinition.objects.filter(custom_field_scope_q_for_user(alice))
    assert set(user_defs.values_list('sandbox_owner_id', flat=True)) == {alice.id}


@pytest.mark.django_db
def test_edits_do_not_bleed_between_demo_users(demo_setup):
    alice, _ = _demo_user_with_sandbox('cf_alice', demo_setup)
    bob, _ = _demo_user_with_sandbox('cf_bob', demo_setup)
    _clone_custom_fields_for_user(alice)
    _clone_custom_fields_for_user(bob)

    # Alice renames her Sprint field.
    alice_sprint = CustomFieldDefinition.objects.get(sandbox_owner=alice, name='Sprint')
    alice_sprint.name = 'Iteration'
    alice_sprint.save(update_fields=['name'])

    # Bob's field is untouched, and the template is untouched.
    assert CustomFieldDefinition.objects.filter(sandbox_owner=bob, name='Sprint').exists()
    demo_setup.sprint.refresh_from_db()
    assert demo_setup.sprint.name == 'Sprint'


@pytest.mark.django_db
def test_two_demo_users_can_hold_same_named_field(demo_setup):
    """The re-keyed unique constraint (workspace, sandbox_owner, name) lets each
    demo user own a same-named field without a uniqueness clash."""
    alice, _ = _demo_user_with_sandbox('cf_alice', demo_setup)
    bob, _ = _demo_user_with_sandbox('cf_bob', demo_setup)
    _clone_custom_fields_for_user(alice)
    _clone_custom_fields_for_user(bob)  # must not raise IntegrityError

    assert CustomFieldDefinition.objects.filter(name='Sprint', is_active=True).count() == 3  # tpl + alice + bob


@pytest.mark.django_db
def test_clone_is_idempotent(demo_setup):
    alice, _ = _demo_user_with_sandbox('cf_alice', demo_setup)
    _clone_custom_fields_for_user(alice)
    _clone_custom_fields_for_user(alice)  # second (re-)provision / reset

    assert CustomFieldDefinition.objects.filter(sandbox_owner=alice).count() == 2
    assert TaskCustomFieldValue.objects.filter(field__sandbox_owner=alice).count() == 2
