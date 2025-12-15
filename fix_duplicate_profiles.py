"""
Fix duplicate UserPerformanceProfile records
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.resource_leveling_models import UserPerformanceProfile
from django.db.models import Count
from django.contrib.auth.models import User

print("=" * 80)
print("FIXING DUPLICATE USERPERFORMANCEPROFILE RECORDS")
print("=" * 80)

# Find duplicates
duplicates = UserPerformanceProfile.objects.values('user').annotate(
    count=Count('user')
).filter(count__gt=1)

print(f"\nFound {duplicates.count()} users with duplicate profiles")

if duplicates.count() == 0:
    print("No duplicates found!")
else:
    # For each user with duplicates, keep the most recent one
    for dup in duplicates:
        user_id = dup['user']
        user = User.objects.get(id=user_id)
        profiles = UserPerformanceProfile.objects.filter(user=user).order_by('-last_updated')
        
        print(f"\nUser: {user.username} has {profiles.count()} profiles")
        
        # Keep the first (most recent), delete the rest
        keep_profile = profiles.first()
        delete_profiles = profiles[1:]
        
        print(f"  Keeping profile ID {keep_profile.id} (last updated: {keep_profile.last_updated})")
        print(f"  Deleting {delete_profiles.count()} duplicate profiles")
        
        for profile in delete_profiles:
            print(f"    - Deleting profile ID {profile.id} (org: {profile.organization.name})")
            profile.delete()

print("\n" + "=" * 80)
print("CLEANUP COMPLETE")
print("=" * 80)
