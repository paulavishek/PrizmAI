"""
Setup Enhanced Permission System
Run this after applying the migration to initialize roles and permissions
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from accounts.models import Organization
from kanban.permission_models import Role, BoardMembership
from kanban.models import Board

print("=" * 80)
print("ENHANCED PERMISSION SYSTEM - SETUP")
print("=" * 80)

# Step 1: Create default roles for organizations that don't have them
print("\n[1/4] Creating default roles for organizations...")
orgs_without_roles = []
for org in Organization.objects.all():
    role_count = Role.objects.filter(organization=org).count()
    if role_count == 0:
        orgs_without_roles.append(org)
        print(f"  ✓ Creating roles for: {org.name}")
        Role.create_default_roles(org)
    else:
        print(f"  - {org.name} already has {role_count} roles")

if orgs_without_roles:
    print(f"\n  Created default roles for {len(orgs_without_roles)} organization(s)")
else:
    print(f"  All organizations already have roles configured")

# Step 2: Create BoardMemberships for existing board members
print("\n[2/4] Creating BoardMembership records for existing members...")
created_count = 0
boards = Board.objects.all()

for board in boards:
    # Get default role (Editor) for this board's organization
    default_role = Role.objects.filter(
        organization=board.organization,
        is_default=True
    ).first()
    
    if not default_role:
        default_role = Role.objects.filter(
            organization=board.organization,
            name='Editor'
        ).first()
    
    if not default_role:
        print(f"  ⚠ No default role found for {board.organization.name}, skipping {board.name}")
        continue
    
    # For each member, create BoardMembership if it doesn't exist
    for member in board.members.all():
        membership, created = BoardMembership.objects.get_or_create(
            board=board,
            user=member,
            defaults={
                'role': default_role,
                'added_by': board.created_by
            }
        )
        if created:
            created_count += 1

print(f"  ✓ Created {created_count} BoardMembership records")

# Step 3: Verify setup
print("\n[3/4] Verifying setup...")
total_roles = Role.objects.count()
total_memberships = BoardMembership.objects.count()
total_orgs = Organization.objects.count()

print(f"  • Organizations: {total_orgs}")
print(f"  • Roles: {total_roles}")
print(f"  • Board Memberships: {total_memberships}")

# Show role breakdown
print(f"\n  Role Distribution:")
for org in Organization.objects.all():
    org_roles = Role.objects.filter(organization=org).count()
    print(f"    - {org.name}: {org_roles} roles")

# Step 4: Display next steps
print("\n[4/4] Setup Complete!")
print("\n" + "=" * 80)
print("NEXT STEPS:")
print("=" * 80)
print("\n1. Access Role Management:")
print("   URL: http://localhost:8000/permissions/roles/")
print("   Purpose: Create custom roles, view permissions")

print("\n2. Manage Board Members:")
print("   URL: http://localhost:8000/board/<board_id>/members/manage/")
print("   Purpose: Assign roles, add/remove members")

print("\n3. View Audit Logs:")
print("   URL: http://localhost:8000/permissions/audit/")
print("   Purpose: Track permission changes")

print("\n4. Set Column Permissions (Optional):")
print("   Use Django shell or admin to create ColumnPermission objects")
print("   Example: Restrict 'Done' column to admins only")

print("\n5. Read Documentation:")
print("   File: ENHANCED_PERMISSIONS_GUIDE.md")
print("   File: PERMISSION_ENHANCEMENT_SUMMARY.md")

print("\n" + "=" * 80)
print("✅ Enhanced Permission System is ready to use!")
print("=" * 80)
