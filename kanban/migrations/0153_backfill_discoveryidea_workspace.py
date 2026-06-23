from django.db import migrations


def backfill_workspace(apps, schema_editor):
    """Backfill DiscoveryIdea.workspace from each idea's creator/owner.

    * Demo-org ideas → the shared demo workspace (per-user isolation is still
      provided by ``sandbox_owner``).
    * Real ideas → the submitter's (or sandbox owner's) owned real workspace,
      falling back to any active workspace under the idea's organization.
    """
    DiscoveryIdea = apps.get_model('kanban', 'DiscoveryIdea')
    Workspace = apps.get_model('kanban', 'Workspace')

    demo_ws = Workspace.objects.filter(is_demo=True).first()

    def _ws_for(user, org):
        if org is not None and getattr(org, 'is_demo', False):
            return demo_ws
        ws = None
        if user is not None:
            ws = (
                Workspace.objects
                .filter(created_by=user, is_demo=False, is_active=True)
                .order_by('-created_at')
                .first()
            )
        if ws is None and org is not None:
            ws = (
                Workspace.objects
                .filter(organization=org, is_demo=False, is_active=True)
                .order_by('-created_at')
                .first()
            )
        return ws

    for idea in DiscoveryIdea.objects.filter(workspace__isnull=True):
        user = idea.sandbox_owner or idea.submitted_by
        ws = _ws_for(user, idea.organization)
        if ws is not None:
            idea.workspace = ws
            idea.save(update_fields=['workspace'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('kanban', '0152_discoveryidea_workspace'),
    ]

    operations = [
        migrations.RunPython(backfill_workspace, noop),
    ]
