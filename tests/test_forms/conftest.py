"""Shared fixtures for the Forms app test suite."""
from types import SimpleNamespace

import pytest
from django.contrib.auth.models import User

from accounts.models import Organization, UserProfile
from kanban.models import Board, BoardMembership, Column, Workspace, WorkspaceMembership
from kanban.preset_models import WorkspacePreset


@pytest.fixture
def workspace_setup(db):
    """
    A real (non-demo) org + workspace on the Professional preset (so
    features.show_forms is True), with a 'member' user (can build/submit
    forms) and a 'viewer' user (read-only, per _is_viewer).
    """
    owner = User.objects.create_user('owner_user', password='x')
    org = Organization.objects.create(name='Acme', created_by=owner)
    ws = Workspace.objects.create(name='Acme WS', organization=org, created_by=owner)
    # A post_save signal on Workspace already auto-creates a WorkspacePreset
    # (kanban.signals.create_workspace_preset_for_workspace) — just make sure
    # it's on the Professional tier so features.show_forms is True.
    WorkspacePreset.objects.filter(workspace=ws).update(global_preset='professional')

    member = User.objects.create_user('member_user', password='x')
    member_profile, _ = UserProfile.objects.get_or_create(user=member)
    member_profile.organization = org
    member_profile.active_workspace = ws
    member_profile.save()
    WorkspaceMembership.objects.create(workspace=ws, user=member, role='member')

    viewer = User.objects.create_user('viewer_user', password='x')
    viewer_profile, _ = UserProfile.objects.get_or_create(user=viewer)
    viewer_profile.organization = org
    viewer_profile.active_workspace = ws
    viewer_profile.save()
    WorkspaceMembership.objects.create(workspace=ws, user=viewer, role='viewer')

    board = Board.objects.create(
        name='Delivery Board', organization=org, workspace=ws,
        created_by=owner, owner=member,
    )
    BoardMembership.objects.create(board=board, user=member, role='owner')
    backlog = Column.objects.create(board=board, name='Backlog', position=0)
    done = Column.objects.create(board=board, name='Done', position=1)

    return SimpleNamespace(
        org=org, ws=ws, owner=owner, member=member, viewer=viewer,
        board=board, backlog=backlog, done=done,
    )
