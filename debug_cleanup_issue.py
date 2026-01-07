"""
Debug script to check why user-created boards aren't being cleaned up after session expiry
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from django.contrib.sessions.models import Session
from analytics.models import DemoSession
from kanban.models import Board, Organization
from datetime import timedelta

print("\n" + "="*80)
print("DEBUG: Demo Board Cleanup Issue")
print("="*80)

# 1. Check demo organization
print("\n1. DEMO ORGANIZATION")
print("-" * 40)
demo_orgs = Organization.objects.filter(name__icontains='demo')
for org in demo_orgs:
    print(f"   Organization: {org.name} (ID: {org.id}, is_demo={getattr(org, 'is_demo', 'N/A')})")
    boards = Board.objects.filter(organization=org)
    print(f"   Total boards: {boards.count()}")
    for board in boards:
        print(f"      - {board.name} | is_official={board.is_official_demo_board} | created_by_session={board.created_by_session}")

# 2. Check all DemoSessions
print("\n2. DEMO SESSIONS")
print("-" * 40)
all_demo_sessions = DemoSession.objects.all().order_by('-created_at')
now = timezone.now()

print(f"   Total DemoSessions: {all_demo_sessions.count()}")
for ds in all_demo_sessions:
    expired = "EXPIRED" if ds.expires_at < now else "ACTIVE"
    print(f"\n   Session ID: {ds.session_id}")
    print(f"   Browser Fingerprint: {ds.browser_fingerprint[:16] if ds.browser_fingerprint else 'None'}...")
    print(f"   First Demo Start: {ds.first_demo_start}")
    print(f"   Created: {ds.created_at}")
    print(f"   Expires: {ds.expires_at} ({expired})")
    print(f"   Demo Mode: {ds.demo_mode}")

# 3. Check active Django sessions
print("\n3. ACTIVE DJANGO SESSIONS")
print("-" * 40)
active_sessions = Session.objects.filter(expire_date__gte=now)
print(f"   Total active sessions: {active_sessions.count()}")

for session in active_sessions:
    data = session.get_decoded()
    is_demo = data.get('is_demo_mode', False)
    
    if is_demo:
        print(f"\n   Session Key: {session.session_key}")
        print(f"   Expires: {session.expire_date}")
        print(f"   is_demo_mode: {data.get('is_demo_mode')}")
        print(f"   demo_mode: {data.get('demo_mode')}")
        print(f"   browser_fingerprint: {data.get('browser_fingerprint', 'None')[:16] if data.get('browser_fingerprint') else 'None'}...")
        print(f"   demo_started_at: {data.get('demo_started_at', 'None')}")
        print(f"   demo_expires_at: {data.get('demo_expires_at', 'None')}")

# 4. Check boards created by sessions
print("\n4. BOARDS CREATED BY SESSIONS")
print("-" * 40)
user_created_boards = Board.objects.filter(created_by_session__isnull=False)
print(f"   Total user-created boards: {user_created_boards.count()}")

for board in user_created_boards:
    print(f"\n   Board: {board.name} (ID: {board.id})")
    print(f"   Organization: {board.organization.name}")
    print(f"   created_by_session: {board.created_by_session}")
    print(f"   is_official_demo_board: {board.is_official_demo_board}")
    print(f"   Created: {board.created_at if hasattr(board, 'created_at') else 'N/A'}")
    
    # Check if corresponding DemoSession exists
    matching_session = DemoSession.objects.filter(
        session_id=board.created_by_session
    ).first()
    
    if matching_session:
        expired = "EXPIRED" if matching_session.expires_at < now else "ACTIVE"
        print(f"   ✅ Matching DemoSession found:")
        print(f"      - Session expires: {matching_session.expires_at} ({expired})")
        print(f"      - First demo start: {matching_session.first_demo_start}")
    else:
        # Check if it's a browser fingerprint instead
        matching_fingerprint_session = DemoSession.objects.filter(
            browser_fingerprint=board.created_by_session
        ).first()
        
        if matching_fingerprint_session:
            expired = "EXPIRED" if matching_fingerprint_session.expires_at < now else "ACTIVE"
            print(f"   ⚠️ Board linked to browser_fingerprint, not session_id:")
            print(f"      - Session ID: {matching_fingerprint_session.session_id}")
            print(f"      - Session expires: {matching_fingerprint_session.expires_at} ({expired})")
            print(f"      - First demo start: {matching_fingerprint_session.first_demo_start}")
        else:
            print(f"   ❌ NO matching DemoSession found!")
            print(f"      - Board will NOT be cleaned up by cleanup task")

# 5. Analysis
print("\n" + "="*80)
print("ANALYSIS")
print("="*80)

# Check if there are expired sessions with boards
expired_sessions = DemoSession.objects.filter(expires_at__lt=now)
print(f"\n✓ Expired DemoSessions: {expired_sessions.count()}")

if expired_sessions.exists():
    print("\nExpired session IDs:")
    for ds in expired_sessions:
        print(f"   - {ds.session_id}")
        print(f"     Browser fingerprint: {ds.browser_fingerprint}")
    
    # Check if any boards match these sessions
    expired_session_ids = list(expired_sessions.values_list('session_id', flat=True))
    boards_to_cleanup_by_session = Board.objects.filter(
        created_by_session__in=expired_session_ids,
        is_official_demo_board=False
    )
    
    print(f"\n✓ Boards that SHOULD be cleaned up (by session_id): {boards_to_cleanup_by_session.count()}")
    for board in boards_to_cleanup_by_session:
        print(f"   - {board.name}")
    
    # Check by browser fingerprint
    expired_fingerprints = list(expired_sessions.values_list('browser_fingerprint', flat=True))
    expired_fingerprints = [f for f in expired_fingerprints if f]  # Remove None values
    
    boards_to_cleanup_by_fingerprint = Board.objects.filter(
        created_by_session__in=expired_fingerprints,
        is_official_demo_board=False
    )
    
    print(f"\n⚠️  Boards linked to browser_fingerprint (NOT being cleaned): {boards_to_cleanup_by_fingerprint.count()}")
    for board in boards_to_cleanup_by_fingerprint:
        print(f"   - {board.name} (created_by_session={board.created_by_session})")

print("\n" + "="*80)
print("ISSUE IDENTIFIED:")
print("="*80)
print("""
The problem is likely that:
1. Boards are being tagged with 'browser_fingerprint' instead of 'session_id'
2. The cleanup task searches for boards by 'session_id'
3. Mismatch between what's stored and what's searched causes boards to persist

Check kanban/views.py around line 260-266 where boards are created in demo mode.
The board.created_by_session should be set to request.session.session_key, 
NOT to browser_fingerprint!
""")
print("="*80 + "\n")
