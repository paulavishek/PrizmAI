import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from analytics.models import DemoSession
from kanban.models import Board

# The board's created_by_session value
session_value = '71bb44cd5a4b7b3e98b177734aeab7cefad031d3128b6a19a27cd5d7d365889f'

print(f"\nChecking: {session_value}")
print("=" * 60)

# Check if it's a session_id
by_session = DemoSession.objects.filter(session_id=session_value).first()
print(f"\nMatch by session_id: {bool(by_session)}")

# Check if it's a browser fingerprint
by_fp = DemoSession.objects.filter(browser_fingerprint=session_value).first()
print(f"Match by fingerprint: {bool(by_fp)}")

# Check expired sessions
now = timezone.now()
expired = DemoSession.objects.filter(expires_at__lt=now)
print(f"\nTotal expired sessions: {expired.count()}")

if by_fp:
    print(f"\n⚠️ ISSUE FOUND: Board is linked to FINGERPRINT, not session_id!")
    print(f"   Actual session_id: {by_fp.session_id}")
    print(f"   Expires at: {by_fp.expires_at}")
    print(f"   Is expired: {by_fp.expires_at < now}")
    print(f"\nCleanup task searches for session_id, but board has fingerprint!")
    print(f"That's why the board isn't being deleted.\n")
elif by_session:
    print(f"\nBoard correctly linked to session_id")
else:
    print(f"\n⚠️ No matching DemoSession found at all!")
