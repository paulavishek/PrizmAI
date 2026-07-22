# Generated data migration to assign orphaned boards to real workspaces

from django.db import migrations


def fix_orphaned_boards(apps, schema_editor):
    """
    Find boards that have workspace=NULL (not sandbox copies, not demo boards)
    and create/assign them to a real workspace.

    Groups orphaned boards by (organization, created_by) and creates one
    workspace per group named after the user.
    """
    Board = apps.get_model('kanban', 'Board')
    Workspace = apps.get_model('kanban', 'Workspace')
    UserProfile = apps.get_model('accounts', 'UserProfile')
    User = apps.get_model('auth', 'User')

    orphaned = Board.objects.filter(
        workspace__isnull=True,
        is_sandbox_copy=False,
        is_official_demo_board=False,
        organization__isnull=False,
    ).select_related('organization', 'created_by')

    # Group by (org_id, created_by_id)
    groups = {}
    for board in orphaned:
        key = (board.organization_id, board.created_by_id)
        groups.setdefault(key, []).append(board)

    for (org_id, user_id), boards in groups.items():
        # Check if a real workspace already exists for this user in this org
        existing_ws = Workspace.objects.filter(
            organization_id=org_id,
            created_by_id=user_id,
            is_demo=False,
            is_active=True,
        ).first()

        if existing_ws:
            ws = existing_ws
        else:
            # Create a real workspace named after the user
            try:
                user = User.objects.get(pk=user_id)
                ws_name = f"{user.first_name or user.username}'s Workspace"
            except User.DoesNotExist:
                ws_name = "My Workspace"

            ws = Workspace.objects.create(
                name=ws_name,
                organization_id=org_id,
                created_by_id=user_id,
                is_demo=False,
                is_active=True,
            )

        # Assign boards to this workspace
        for board in boards:
            board.workspace = ws
            board.save(update_fields=['workspace'])

    # Update profiles: if a user is viewing demo but now has a real workspace,
    # keep them on demo (login redirect will fix it). But for users whose
    # active_workspace is the demo WS and who own a real workspace, we leave
    # them alone — the login redirect logic will handle routing.


def reverse_fix(apps, schema_editor):
    pass  # Non-reversible data fix


class Migration(migrations.Migration):

    dependencies = [
        ('kanban', '0116_populate_workspaces'),
    ]

    operations = [
        migrations.RunPython(fix_orphaned_boards, reverse_fix),
    ]
