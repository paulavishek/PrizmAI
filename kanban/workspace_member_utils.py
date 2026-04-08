"""
Workspace-level member management utilities.

Handles syncing WorkspaceMembership ↔ BoardMembership so that adding
a user to a workspace automatically gives them the same role on every
board in that workspace (and future boards).
"""
import logging

from django.db import transaction

from kanban.models import (
    Board,
    BoardMembership,
    WorkspaceMembership,
)

logger = logging.getLogger(__name__)


def add_workspace_member(workspace, user, role, added_by=None):
    """
    Add a user to a workspace and propagate membership to all workspace boards.

    Returns the created (or existing) WorkspaceMembership.
    """
    with transaction.atomic():
        ws_membership, created = WorkspaceMembership.objects.get_or_create(
            workspace=workspace,
            user=user,
            defaults={'role': role, 'added_by': added_by},
        )
        if not created:
            # Already a workspace member — update role if different
            if ws_membership.role != role:
                ws_membership.role = role
                ws_membership.save(update_fields=['role'])

        # Propagate to all boards in this workspace
        boards = Board.objects.filter(
            workspace=workspace,
            is_official_demo_board=False,
            is_sandbox_copy=False,
        )
        for board in boards:
            BoardMembership.objects.get_or_create(
                board=board,
                user=user,
                defaults={'role': role, 'added_by': added_by},
            )

    logger.info(
        'Added %s to workspace #%s (%s) as %s — synced to %d boards',
        user.username, workspace.pk, workspace.name, role, boards.count(),
    )
    return ws_membership


def remove_workspace_member(workspace, user):
    """
    Remove a user from a workspace and all workspace boards.

    Protects board creators — they keep their membership on boards they created.
    Cannot remove the workspace creator.
    """
    if workspace.created_by_id == user.pk:
        raise ValueError("Cannot remove the workspace creator.")

    with transaction.atomic():
        WorkspaceMembership.objects.filter(
            workspace=workspace, user=user,
        ).delete()

        # Remove from all workspace boards, except boards the user created
        boards = Board.objects.filter(
            workspace=workspace,
            is_official_demo_board=False,
            is_sandbox_copy=False,
        ).exclude(created_by=user)

        removed_count = BoardMembership.objects.filter(
            board__in=boards, user=user,
        ).delete()[0]

    logger.info(
        'Removed %s from workspace #%s — deleted %d board memberships',
        user.username, workspace.pk, removed_count,
    )
    return removed_count


def update_workspace_member_role(workspace, user, new_role):
    """
    Update a user's workspace role and propagate to all workspace boards.

    Skips boards where the user is the board creator (creator stays owner).
    """
    with transaction.atomic():
        ws_membership = WorkspaceMembership.objects.get(
            workspace=workspace, user=user,
        )
        ws_membership.role = new_role
        ws_membership.save(update_fields=['role'])

        # Update all board memberships in this workspace
        boards = Board.objects.filter(
            workspace=workspace,
            is_official_demo_board=False,
            is_sandbox_copy=False,
        ).exclude(created_by=user)  # Don't downgrade board creators

        updated = BoardMembership.objects.filter(
            board__in=boards, user=user,
        ).update(role=new_role)

    logger.info(
        'Updated %s role to %s in workspace #%s — updated %d board memberships',
        user.username, new_role, workspace.pk, updated,
    )
    return updated


def auto_add_workspace_members_to_board(board):
    """
    Called after a board is created. Adds all workspace members to the board
    with their workspace-level role.

    Skips if the board has no workspace, or is a demo/sandbox board.
    """
    if not board.workspace_id:
        return 0
    if getattr(board, 'is_official_demo_board', False):
        return 0
    if getattr(board, 'is_sandbox_copy', False):
        return 0

    ws_memberships = WorkspaceMembership.objects.filter(
        workspace=board.workspace,
    ).select_related('user', 'added_by')

    created_count = 0
    for ws_mem in ws_memberships:
        _, created = BoardMembership.objects.get_or_create(
            board=board,
            user=ws_mem.user,
            defaults={'role': ws_mem.role, 'added_by': ws_mem.added_by},
        )
        if created:
            created_count += 1

    if created_count:
        logger.info(
            'Auto-added %d workspace members to board #%s (%s)',
            created_count, board.pk, board.name,
        )
    return created_count
