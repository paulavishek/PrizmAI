"""
Check conflict notifications for Sam Rivera
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from kanban.conflict_models import ConflictDetection, ConflictNotification

print("=" * 60)
print("CHECKING CONFLICT NOTIFICATIONS")
print("=" * 60)

# Find Sam Rivera
try:
    sam = User.objects.get(username='sam_rivera_demo')
    print(f"\n✅ Found user: {sam.username} (ID: {sam.id})")
    print(f"   Name: {sam.get_full_name()}")
except User.DoesNotExist:
    print("\n❌ User 'sam_rivera_demo' not found!")
    exit(1)

# Check conflicts where Sam is affected
print(f"\n{'='*60}")
print("CONFLICTS WHERE SAM IS AFFECTED:")
print("=" * 60)

conflicts = ConflictDetection.objects.filter(
    affected_users=sam,
    status='active'
).prefetch_related('tasks', 'affected_users')

print(f"Found {conflicts.count()} active conflicts affecting Sam Rivera")

for conflict in conflicts:
    print(f"\n📋 Conflict ID: {conflict.id}")
    print(f"   Title: {conflict.title}")
    print(f"   Type: {conflict.conflict_type}")
    print(f"   Severity: {conflict.severity}")
    print(f"   Status: {conflict.status}")
    print(f"   Board: {conflict.board.name}")
    print(f"   Detected: {conflict.detected_at}")
    print(f"   Tasks: {[task.title for task in conflict.tasks.all()]}")
    print(f"   Affected Users: {[u.username for u in conflict.affected_users.all()]}")
    
    # Check if notification exists
    notification = ConflictNotification.objects.filter(
        conflict=conflict,
        user=sam
    ).first()
    
    if notification:
        print(f"   ✅ Notification EXISTS")
        print(f"      - Sent: {notification.sent_at}")
        print(f"      - Read: {notification.read_at}")
        print(f"      - Acknowledged: {notification.acknowledged}")
    else:
        print(f"   ❌ NO NOTIFICATION FOUND FOR THIS CONFLICT!")

# Check all notifications for Sam
print(f"\n{'='*60}")
print("ALL NOTIFICATIONS FOR SAM:")
print("=" * 60)

all_notifications = ConflictNotification.objects.filter(
    user=sam
).select_related('conflict').order_by('-sent_at')

print(f"Total notifications for Sam: {all_notifications.count()}")

for notif in all_notifications:
    print(f"\n📧 Notification ID: {notif.id}")
    print(f"   Conflict: {notif.conflict.title}")
    print(f"   Status: {notif.conflict.status}")
    print(f"   Acknowledged: {notif.acknowledged}")
    print(f"   Sent: {notif.sent_at}")

print(f"\n{'='*60}")
print("SUMMARY:")
print("=" * 60)
print(f"Active conflicts affecting Sam: {conflicts.count()}")
print(f"Total notifications for Sam: {all_notifications.count()}")
unack_notifications = all_notifications.filter(acknowledged=False)
print(f"Unacknowledged notifications: {unack_notifications.count()}")

# Find the missing notifications
conflicts_without_notifications = []
for conflict in conflicts:
    if not ConflictNotification.objects.filter(conflict=conflict, user=sam).exists():
        conflicts_without_notifications.append(conflict)

if conflicts_without_notifications:
    print(f"\n⚠️  ISSUE FOUND: {len(conflicts_without_notifications)} active conflict(s) WITHOUT notifications!")
    print("\n   Creating missing notifications...")
    
    for conflict in conflicts_without_notifications:
        notification = ConflictNotification.objects.create(
            conflict=conflict,
            user=sam,
            notification_type='in_app',
            acknowledged=False
        )
        print(f"   ✅ Created notification for: {conflict.title}")
    
    print(f"\n✅ Fixed! Created {len(conflicts_without_notifications)} missing notification(s)")
else:
    print("\n✅ All active conflicts have notifications")

print("\n" + "=" * 60)
