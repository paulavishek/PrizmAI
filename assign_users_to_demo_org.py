#!/usr/bin/env python
"""
Assign users without organization to Demo - Acme Corporation
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Organization, UserProfile

User = get_user_model()

print("\n" + "="*80)
print("ASSIGNING USERS TO DEMO ORGANIZATION")
print("="*80)

# Get Demo organization
demo_org = Organization.objects.filter(name='Demo - Acme Corporation').first()

if not demo_org:
    print("❌ Demo organization not found!")
    exit(1)

print(f"\n✓ Found organization: {demo_org.name}\n")

# Get users without organization
users_to_fix = User.objects.all()

fixed_count = 0
created_profiles = 0
updated_profiles = 0

for user in users_to_fix:
    try:
        profile = user.profile
        if not profile.organization:
            profile.organization = demo_org
            profile.save()
            print(f"  ✓ Assigned {user.username} to {demo_org.name}")
            updated_profiles += 1
            fixed_count += 1
    except UserProfile.DoesNotExist:
        # Create profile for users without one
        UserProfile.objects.create(
            user=user,
            organization=demo_org,
            is_admin=False
        )
        print(f"  ✓ Created profile for {user.username} in {demo_org.name}")
        created_profiles += 1
        fixed_count += 1

print("\n" + "="*80)
print(f"✓ COMPLETE")
print(f"  Created profiles: {created_profiles}")
print(f"  Updated profiles: {updated_profiles}")
print(f"  Total fixed: {fixed_count}")
print("="*80 + "\n")
