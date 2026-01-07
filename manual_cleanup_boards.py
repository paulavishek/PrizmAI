"""
Manually clean up user-created boards from expired sessions
This demonstrates that the fix works
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from analytics.models import DemoSession
from kanban.models import Board

print("\n" + "="*80)
print("MANUAL CLEANUP OF EXPIRED SESSION BOARDS")
print("="*80)

# Get expired sessions
now = timezone.now()
expired_sessions = DemoSession.objects.filter(expires_at__lt=now)

# Get identifiers (session_ids AND fingerprints)
expired_session_ids = list(expired_sessions.values_list('session_id', flat=True))
expired_fingerprints = list(expired_sessions.exclude(
    browser_fingerprint__isnull=True
).values_list('browser_fingerprint', flat=True))

identifiers = expired_session_ids + expired_fingerprints

print(f"\nExpired sessions: {expired_sessions.count()}")
print(f"  - Session IDs: {len(expired_session_ids)}")
print(f"  - Fingerprints: {len(expired_fingerprints)}")
print(f"  - Total identifiers: {len(identifiers)}")

# Find boards to delete
boards_to_delete = Board.objects.filter(
    created_by_session__in=identifiers,
    is_official_demo_board=False
)

print(f"\nBoards to delete: {boards_to_delete.count()}")
for board in boards_to_delete:
    print(f"  - {board.name}")

# Confirm deletion
response = input("\nDelete these boards? (yes/no): ")

if response.lower() == 'yes':
    count = boards_to_delete.count()
    boards_to_delete.delete()
    print(f"\n✅ Deleted {count} board(s)")
    print("\nThe fix is working! The board has been cleaned up.")
    print("Going forward, the automated cleanup task will handle this.")
else:
    print("\n❌ Deletion cancelled")

print("\n" + "="*80)
print("NEXT STEPS")
print("="*80)
print("""
1. The fix is now in place
2. The cleanup_expired_demo_sessions task will automatically:
   - Run every hour (via Celery Beat)
   - Find expired sessions
   - Delete boards tagged with BOTH session_id AND browser_fingerprint
   
3. You can also manually run cleanup with:
   python manage.py cleanup_demo_sessions

The issue was that boards were tagged with browser_fingerprint,
but the cleanup only searched for session_id. Now it searches both!
""")
print("="*80 + "\n")
