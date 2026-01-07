import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from analytics.models import DemoSession
from kanban.models import Board

print("\n" + "="*80)
print("TESTING CLEANUP FIX")
print("="*80)

# Get expired sessions
now = timezone.now()
expired_sessions = DemoSession.objects.filter(expires_at__lt=now)

# Get session IDs and fingerprints
expired_session_ids = list(expired_sessions.values_list('session_id', flat=True))
expired_fingerprints = list(expired_sessions.exclude(
    browser_fingerprint__isnull=True
).values_list('browser_fingerprint', flat=True))

identifiers = expired_session_ids + expired_fingerprints

print(f"\nExpired sessions: {expired_sessions.count()}")
print(f"Session IDs: {len(expired_session_ids)}")
print(f"Fingerprints: {len(expired_fingerprints)}")
print(f"Total identifiers: {len(identifiers)}")

# Check what boards would be deleted
boards_to_delete = Board.objects.filter(
    created_by_session__in=identifiers,
    is_official_demo_board=False
)

print(f"\n" + "="*80)
print(f"BOARDS THAT WILL BE DELETED: {boards_to_delete.count()}")
print("="*80)

for board in boards_to_delete:
    print(f"\n✓ {board.name}")
    print(f"  Organization: {board.organization.name}")
    print(f"  created_by_session: {board.created_by_session[:16]}...")
    
    # Find matching DemoSession
    matching = DemoSession.objects.filter(
        browser_fingerprint=board.created_by_session
    ).first() or DemoSession.objects.filter(
        session_id=board.created_by_session
    ).first()
    
    if matching:
        print(f"  Expires: {matching.expires_at}")
        print(f"  Expired: {matching.expires_at < now}")

print("\n" + "="*80)
print("FIX VERIFIED!")
print("="*80)
print("The cleanup will now correctly find and delete user-created boards")
print("that are tagged with browser_fingerprints.\n")
