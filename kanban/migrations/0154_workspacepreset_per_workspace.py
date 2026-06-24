"""
Re-key WorkspacePreset from Organization → Workspace.

A single Organization can contain several independent Workspaces (one per
user/team).  Keying the preset on Organization caused the feature level to
leak between unrelated workspaces that shared an org.  This migration moves
the preset onto the Workspace (the real tenant boundary) and fans out each
org-level preset to every workspace inside that org.
"""
from django.db import migrations, models
import django.db.models.deletion


def fan_out_to_workspaces(apps, schema_editor):
    WorkspacePreset = apps.get_model('kanban', 'WorkspacePreset')
    Workspace = apps.get_model('kanban', 'Workspace')

    # Snapshot the existing org-keyed presets before we rebuild the table.
    org_preset = {}
    for wp in WorkspacePreset.objects.all():
        if wp.organization_id is not None:
            org_preset[wp.organization_id] = wp.global_preset

    # Clear the org-keyed rows and recreate one row per workspace, inheriting
    # the preset its organization had (default 'professional' for any org that
    # never had an explicit preset row).
    WorkspacePreset.objects.all().delete()
    rows = [
        WorkspacePreset(
            workspace=ws,
            global_preset=org_preset.get(ws.organization_id, 'professional'),
        )
        for ws in Workspace.objects.all()
    ]
    WorkspacePreset.objects.bulk_create(rows)


def noop(apps, schema_editor):
    # Reverse is best-effort: per-workspace presets cannot be losslessly
    # collapsed back to one-per-org, so we leave the rows as-is.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('kanban', '0153_backfill_discoveryidea_workspace'),
    ]

    operations = [
        # 1. Loosen the old org link so we can null/remove it during transition.
        migrations.AlterField(
            model_name='workspacepreset',
            name='organization',
            field=models.OneToOneField(
                null=True, blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='workspace_preset_legacy',
                to='accounts.organization',
            ),
        ),
        # 2. Add the new workspace link (nullable for the data step).
        migrations.AddField(
            model_name='workspacepreset',
            name='workspace',
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='workspace_preset',
                to='kanban.workspace',
            ),
        ),
        # 3. Fan out org presets to every workspace.
        migrations.RunPython(fan_out_to_workspaces, noop),
        # 4. Drop the legacy org link.
        migrations.RemoveField(
            model_name='workspacepreset',
            name='organization',
        ),
        # 5. Workspace is now required.
        migrations.AlterField(
            model_name='workspacepreset',
            name='workspace',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='workspace_preset',
                to='kanban.workspace',
            ),
        ),
    ]
