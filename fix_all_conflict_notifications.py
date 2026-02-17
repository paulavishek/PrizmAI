"""
Ensure all active conflicts have notifications for their affected users
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.conflict_models import ConflictDetection, ConflictNotification

print("=" * 60)
print("CHECKING ALL CONFLICT NOTIFICATIONS")
print("=" * 60)

# Get all active conflicts
active_conflicts = ConflictDetection.objects.filter(
    status='active'
).prefetch_related('affected_users', 'notifications')

print(f"\nFound {active_conflicts.count()} active conflicts\n")

missing_notifications = []

for conflict in active_conflicts:
    print(f"Checking conflict {conflict.id}: {conflict.title}")
    
    affected_users = conflict.affected_users.all()
    print(f"  - Affected users: {affected_users.count()}")
    
    for user in affected_users:
        # Check if notification exists
        has_notification = ConflictNotification.objects.filter(
            conflict=conflict,
            user=user
        ).exists()
        
        if not has_notification:
            print(f"    ❌ Missing notification for {user.username}")
            missing_notifications.append((conflict, user))
        else:
            notif = ConflictNotification.objects.get(conflict=conflict, user=user)
            print(f"    ✅ {user.username} - Acknowledged: {notif.acknowledged}")

print(f"\n{'='*60}")
print("SUMMARY:")
print("=" * 60)
print(f"Total active conflicts: {active_conflicts.count()}")
print(f"Missing notifications: {len(missing_notifications)}")

if missing_notifications:
    print(f"\n⚠️  Creating {len(missing_notifications)} missing notifications...\n")
    
    for conflict, user in missing_notifications:
        notification = ConflictNotification.objects.create(
            conflict=conflict,
            user=user,
            notification_type='in_app',
            acknowledged=False
        )
        print(f"   ✅ Created notification for {user.username} - {conflict.title}")
    
    print(f"\n✅ All notifications created!")
else:
    print("\n✅ All active conflicts have notifications for all affected users")

print("\n" + "=" * 60)
