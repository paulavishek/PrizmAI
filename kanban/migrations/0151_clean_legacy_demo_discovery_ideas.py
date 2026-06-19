"""Data migration: clean up legacy user-created Discovery ideas in the demo org.

Before per-user sandbox isolation (migration 0150), demo users submitted ideas
straight into the shared demo organization (is_demo=False, no sandbox_owner).
Under the new model the demo org should contain only:

  - template ideas      (is_demo=True,  sandbox_owner IS NULL)
  - per-user clones      (sandbox_owner = the demo user)

Any leftover idea in the demo org that is is_demo=False with no sandbox_owner is
pre-isolation cruft: it is invisible to its creator (queries now scope by
sandbox_owner) and is never cleaned by reset. Delete those so the demo org is
clean. Real-org ideas are untouched (they live in non-demo organizations).
"""
from django.db import migrations


def clean_legacy_demo_ideas(apps, schema_editor):
    DiscoveryIdea = apps.get_model('kanban', 'DiscoveryIdea')
    Organization = apps.get_model('accounts', 'Organization')
    demo_org_ids = list(
        Organization.objects.filter(is_demo=True).values_list('id', flat=True)
    )
    if not demo_org_ids:
        return
    DiscoveryIdea.objects.filter(
        organization_id__in=demo_org_ids,
        is_demo=False,
        sandbox_owner__isnull=True,
    ).delete()


def noop(apps, schema_editor):
    # Irreversible cleanup — nothing to restore.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('kanban', '0150_discoveryidea_sandbox_owner'),
    ]

    operations = [
        migrations.RunPython(clean_legacy_demo_ideas, noop),
    ]
