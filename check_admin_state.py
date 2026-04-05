"""Diagnostic: check org, workspace, and admin state for testuser1."""
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'kanban_board.settings'
django.setup()

from accounts.models import Organization, UserProfile
from kanban.models import Workspace

print("=== Organizations ===")
for org in Organization.objects.all():
    ws_list = Workspace.objects.filter(organization=org, is_demo=False)
    print(f"Org #{org.pk}: name={org.name!r}, created_by={org.created_by}")
    for ws in ws_list:
        print(f"  Workspace #{ws.pk}: name={ws.name!r}")

print("\n=== testuser1 profile ===")
for p in UserProfile.objects.filter(user__username='testuser1'):
    print(f"user={p.user}, is_admin={p.is_admin}, org_id={p.organization_id}")
    in_group = p.user.groups.filter(name='OrgAdmin').exists()
    print(f"OrgAdmin group: {in_group}")
    if p.organization:
        print(f"org.name={p.organization.name!r}, org.created_by={p.organization.created_by}")

print("\n=== is_user_org_admin check ===")
from kanban.permissions import is_user_org_admin
from django.contrib.auth import get_user_model
User = get_user_model()
u = User.objects.get(username='testuser1')
print(f"is_user_org_admin(testuser1) = {is_user_org_admin(u)}")
