import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from analytics.models import DemoSession
from kanban.models import Board
from datetime import timedelta

print("\n" + "="*80)
print("CHECKING THE ACTUAL ISSUE")
print("="*80)

# The board we're investigating
board = Board.objects.get(name="Website Redesign Project")
print(f"\nBoard: {board.name}")
print(f"created_by_session: {board.created_by_session}")

# Find the DemoSession
demo_session = DemoSession.objects.filter(
    browser_fingerprint=board.created_by_session
).first()

if demo_session:
    now = timezone.now()
    print(f"\nMatching DemoSession found:")
    print(f"  Session ID: {demo_session.session_id}")
    print(f"  Created: {demo_session.created_at}")
    print(f"  First Demo Start: {demo_session.first_demo_start}")
    print(f"  Expires: {demo_session.expires_at}")
    print(f"  Current Time: {now}")
    print(f"  Is Expired: {demo_session.expires_at < now}")
    
    time_until_expiry = demo_session.expires_at - now
    print(f"  Time until expiry: {time_until_expiry}")
    
    # Check if this is from a previous session
    age = now - demo_session.created_at
    print(f"  Session age: {age}")
    
    if demo_session.first_demo_start:
        time_since_first_start = now - demo_session.first_demo_start
        print(f"  Time since FIRST demo start: {time_since_first_start}")
        
        # Calculate when it should have expired
        expected_expiry = demo_session.first_demo_start + timedelta(hours=48)
        print(f"  Expected expiry (first_start + 48h): {expected_expiry}")
        print(f"  Should be expired: {now > expected_expiry}")

print("\n" + "="*80)
print("EXPLANATION")
print("="*80)
print("""
The issue you're experiencing is related to the 48-hour demo session tracking:

1. When you first started the demo, a browser fingerprint was created
2. The board "Website Redesign Project" was tagged with this fingerprint
3. When your session expired and you logged in again, the system:
   - Found your existing DemoSession by fingerprint
   - Reused the FIRST demo start time (not current time)
   - Set expiry to first_start + 48 hours

This means:
- If your TOTAL time across all sessions exceeds 48 hours, cleanup will work
- The board will be deleted once the 48-hour window from your FIRST session start expires
- This is by design to prevent users from resetting the timer by logging out/in

However, if you're seeing a board from a previous session that should have
been cleaned up, it means either:
a) The cleanup task hasn't run yet
b) The session wasn't properly expired in the database
c) There's a mismatch in the cleanup logic (which we just fixed)
""")
print("="*80 + "\n")
