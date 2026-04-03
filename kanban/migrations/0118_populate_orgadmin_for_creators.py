"""
Data migration: ensure every Organization.created_by user is in the OrgAdmin
Django Group.

This fixes the gap where onboarding created organizations with created_by set
but never added the user to the OrgAdmin group.  It also syncs any users whose
UserProfile.is_admin is True into the group for consistency.
"""
from django.db import migrations


def populate_orgadmin_for_creators(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Organization = apps.get_model('accounts', 'Organization')
    UserProfile = apps.get_model('accounts', 'UserProfile')

    org_admin_group, _ = Group.objects.get_or_create(name='OrgAdmin')

    # 1. Add every org creator to OrgAdmin
    for org in Organization.objects.select_related('created_by').all():
        if org.created_by_id:
            org.created_by.groups.add(org_admin_group)

    # 2. Add every user with profile.is_admin=True to OrgAdmin
    for profile in UserProfile.objects.filter(is_admin=True).select_related('user'):
        profile.user.groups.add(org_admin_group)


def reverse_populate(apps, schema_editor):
    """Reverse is a no-op — we don't want to remove admin access."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('kanban', '0117_fix_orphaned_board_workspaces'),
        ('accounts', '__latest__'),
        ('auth', '__latest__'),
    ]

    operations = [
        migrations.RunPython(populate_orgadmin_for_creators, reverse_populate),
    ]
