"""
Data migration: populate new RBAC structures after schema migration 0099.

1. Create Django Group 'OrgAdmin' and add superusers to it.
2. Set Board.owner = Board.created_by for every board.
3. Copy Board.members M2M → BoardMembership (role='member').
   Board creator gets role='owner'.
4. Set UserProfile.is_demo_account for demo personas.
5. Create Django Group 'Member' (default group for all users).
"""

from django.db import migrations


def populate_rbac_data(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    Board = apps.get_model('kanban', 'Board')
    BoardMembership = apps.get_model('kanban', 'BoardMembership')
    UserProfile = apps.get_model('accounts', 'UserProfile')

    # ── 1. Create Groups ──
    org_admin_group, _ = Group.objects.get_or_create(name='OrgAdmin')
    member_group, _ = Group.objects.get_or_create(name='Member')

    # Add all superusers to OrgAdmin
    for su in User.objects.filter(is_superuser=True):
        su.groups.add(org_admin_group)

    # Add all users to Member group
    for u in User.objects.all():
        u.groups.add(member_group)

    # ── 2. Set Board.owner = created_by ──
    for board in Board.objects.select_related('created_by').all():
        if board.created_by and not board.owner_id:
            board.owner = board.created_by
            board.save(update_fields=['owner'])

    # ── 3. Copy M2M → BoardMembership ──
    for board in Board.objects.prefetch_related('members').all():
        for user in board.members.all():
            role = 'owner' if user == board.created_by else 'member'
            BoardMembership.objects.get_or_create(
                board=board,
                user=user,
                defaults={
                    'role': role,
                    'added_by': board.created_by,
                },
            )

    # ── 3b. Fix any legacy FK values left over from schema migration ──
    # When SQLite altered role from FK→CharField, old integer FK values
    # were preserved as strings (e.g. '1', '3', '5'). Fix them.
    valid_roles = {'owner', 'member', 'viewer'}
    for bm in BoardMembership.objects.all():
        if bm.role not in valid_roles:
            bm.role = 'member'
            bm.save(update_fields=['role'])

    # ── 4. Flag demo accounts ──
    demo_usernames = ['alex_chen_demo', 'sam_rivera_demo', 'jordan_taylor_demo']
    UserProfile.objects.filter(
        user__username__in=demo_usernames,
    ).update(is_demo_account=True)


def reverse_populate(apps, schema_editor):
    """Reverse is a no-op — we don't want to delete membership data."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('kanban', '0099_demosandbox_strategicmembership_and_more'),
        ('accounts', '0009_userprofile_is_demo_account'),
        ('auth', '__latest__'),
    ]

    operations = [
        migrations.RunPython(populate_rbac_data, reverse_populate),
    ]
