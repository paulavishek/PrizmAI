import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from analytics.models import DemoSession
from kanban.models import Board

print("\n" + "="*80)
print("CHECKING FOR MULTIPLE SESSIONS WITH SAME FINGERPRINT")
print("="*80)

# The board's fingerprint
board = Board.objects.get(name="Website Redesign Project")
fingerprint = board.created_by_session

print(f"\nBoard: {board.name}")
print(f"Browser Fingerprint: {fingerprint[:16]}...")

# Find ALL sessions with this fingerprint
all_sessions = DemoSession.objects.filter(
    browser_fingerprint=fingerprint
).order_by('created_at')

print(f"\nTotal DemoSessions with this fingerprint: {all_sessions.count()}")

now = timezone.now()
for i, ds in enumerate(all_sessions, 1):
    expired = "EXPIRED" if ds.expires_at < now else "ACTIVE"
    print(f"\n{i}. Session: {ds.session_id}")
    print(f"   Created: {ds.created_at}")
    print(f"   Expires: {ds.expires_at}")
    print(f"   Status: {expired}")
    print(f"   First Demo Start: {ds.first_demo_start}")

print("\n" + "="*80)
print("ROOT CAUSE")
print("="*80)
print("""
If there are multiple DemoSessions with the same fingerprint:
- The board was created in an earlier session
- That earlier session has expired
- But a NEW session was created with the same fingerprint
- The board still exists because it's tagged with the fingerprint
- The cleanup should delete it when the OLD session expires

The fix we implemented will ensure cleanup works properly by:
1. Including both session_id AND browser_fingerprint in cleanup
2. The board will be deleted when ANY session with that fingerprint expires
""")
print("="*80 + "\n")
