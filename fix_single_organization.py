#!/usr/bin/env python
"""
Fix organization setup - ensure only ONE organization exists and all users belong to it
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Organization, UserProfile

User = get_user_model()

print("=" * 70)
print("FIXING SINGLE ORGANIZATION SETUP")
print("=" * 70)

# Step 1: Get or ensure Demo - Acme Corporation exists
demo_org = Organization.objects.filter(name='Demo - Acme Corporation').first()

if not demo_org:
    print("\n❌ Demo - Acme Corporation not found!")
    print("Please run: python manage.py create_demo_organization")
    exit(1)

print(f"\n✅ Found primary organization: {demo_org.name}")

# Step 2: Delete all other organizations
other_orgs = Organization.objects.exclude(id=demo_org.id)
if other_orgs.exists():
    print(f"\n🗑️  Deleting {other_orgs.count()} extra organization(s):")
    for org in other_orgs:
        print(f"   - {org.name} (created by {org.created_by})")
        org.delete()
    print("   ✅ Extra organizations deleted")
else:
    print("\n✅ No extra organizations found")

# Step 3: Assign ALL users to Demo - Acme Corporation
print(f"\n👥 Assigning all users to '{demo_org.name}':")

all_users = User.objects.all()
assigned_count = 0
created_count = 0

for user in all_users:
    try:
        profile = user.profile
        if profile.organization != demo_org:
            profile.organization = demo_org
            profile.save()
            print(f"   ✅ Updated {user.username} -> {demo_org.name}")
            assigned_count += 1
        else:
            print(f"   ✓ {user.username} already in {demo_org.name}")
    except UserProfile.DoesNotExist:
        # Create profile for user
        UserProfile.objects.create(
            user=user,
            organization=demo_org,
            is_admin=False
        )
        print(f"   ✅ Created profile for {user.username} -> {demo_org.name}")
        created_count += 1

print(f"\n📊 Summary:")
print(f"   - Profiles created: {created_count}")
print(f"   - Profiles updated: {assigned_count}")
print(f"   - Total users in {demo_org.name}: {all_users.count()}")

# Step 4: Verify
print(f"\n🔍 Verification:")
print(f"   Total organizations: {Organization.objects.count()}")
print(f"   Total users: {User.objects.count()}")
print(f"   Users in {demo_org.name}: {UserProfile.objects.filter(organization=demo_org).count()}")

print("\n" + "=" * 70)
print("✅ SINGLE ORGANIZATION SETUP COMPLETE")
print("=" * 70)
