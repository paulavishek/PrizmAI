from django.db import migrations


def backfill_workspace(apps, schema_editor):
    """Backfill workspace on WikiPage / MeetingNotes / WikiCategory.

    * Demo-org rows → the shared demo workspace.
    * Real rows → the creator's owned real workspace, falling back to any active
      workspace under the row's organization.
    * Categories (no creator) inherit from one of their pages, else org-derived.
    """
    WikiPage = apps.get_model('wiki', 'WikiPage')
    WikiCategory = apps.get_model('wiki', 'WikiCategory')
    MeetingNotes = apps.get_model('wiki', 'MeetingNotes')
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

    for page in WikiPage.objects.filter(workspace__isnull=True):
        ws = _ws_for(page.created_by, page.organization)
        if ws is not None:
            page.workspace = ws
            page.save(update_fields=['workspace'])

    for mn in MeetingNotes.objects.filter(workspace__isnull=True):
        ws = _ws_for(mn.created_by, mn.organization)
        if ws is not None:
            mn.workspace = ws
            mn.save(update_fields=['workspace'])

    for cat in WikiCategory.objects.filter(workspace__isnull=True):
        ws = None
        page = cat.pages.exclude(workspace__isnull=True).first()
        if page is not None:
            ws = page.workspace
        if ws is None:
            ws = _ws_for(None, cat.organization)
        if ws is not None:
            cat.workspace = ws
            cat.save(update_fields=['workspace'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('wiki', '0013_meetingnotes_workspace_wikicategory_workspace_and_more'),
        ('kanban', '0152_discoveryidea_workspace'),
    ]

    operations = [
        migrations.RunPython(backfill_workspace, noop),
    ]
