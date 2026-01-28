#!/usr/bin/env python
"""
Check all organizations and user memberships
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Organization, UserProfile

User = get_user_model()

print("\n" + "="*80)
print("ORGANIZATIONS IN DATABASE")
print("="*80)

orgs = Organization.objects.all()
if orgs.exists():
    for org in orgs:
        print(f"\n📁 {org.name}")
        print(f"   Domain: {org.domain}")
        print(f"   Is Demo: {org.is_demo}")
        print(f"   Created by: {org.created_by.username if org.created_by else 'N/A'}")
        
        # Count members
        member_count = UserProfile.objects.filter(organization=org).count()
        print(f"   Members: {member_count}")
else:
    print("❌ No organizations found")

print("\n" + "="*80)
print("ALL USERS AND THEIR ORGANIZATIONS")
print("="*80)

users = User.objects.all().order_by('username')
users_with_org = 0
users_without_org = 0

for user in users:
    try:
        profile = user.profile
        if profile.organization:
            org_name = profile.organization.name
            users_with_org += 1
        else:
            org_name = "❌ No organization"
            users_without_org += 1
    except UserProfile.DoesNotExist:
        org_name = "❌ No profile"
        users_without_org += 1
    
    print(f"  {user.username:25s} → {org_name}")

print("\n" + "="*80)
print(f"Total users: {users.count()}")
print(f"  With organization: {users_with_org}")
print(f"  Without organization: {users_without_org}")
print("="*80 + "\n")
