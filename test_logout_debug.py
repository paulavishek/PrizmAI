"""
Debug script to check logout view behavior and session tracking
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.conf import settings
from analytics.models import UserSession
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

print("=" * 60)
print("Logout Debug - Checking Active Sessions")
print("=" * 60)

# Check for active sessions
active_sessions = UserSession.objects.filter(session_end__isnull=True).order_by('-session_start')

print(f"\n✓ Found {active_sessions.count()} active sessions\n")

for session in active_sessions[:5]:  # Show last 5
    print(f"Session ID: {session.id}")
    print(f"  User: {session.user or 'Anonymous'}")
    print(f"  Session Key: {session.session_key}")
    print(f"  Started: {session.session_start}")
    print(f"  Duration: {session.duration_minutes} minutes")
    print(f"  Engagement: {session.engagement_level}")
    print(f"  Boards Viewed: {session.boards_viewed}")
    print(f"  Pages Visited: {session.pages_visited}")
    print(f"  AI Features: {session.ai_features_used}")
    
    # Check if would show feedback form
    min_engagement = getattr(settings, 'ANALYTICS_MIN_ENGAGEMENT_FOR_FEEDBACK', 2)
    show_form = session.duration_minutes >= min_engagement
    print(f"  Would show feedback form: {'✓ YES' if show_form else '❌ NO'}")
    print(f"    (Duration {session.duration_minutes} >= {min_engagement} minutes)")
    print()

# Check recently ended sessions
print("\n" + "=" * 60)
print("Recently Ended Sessions (Last 5)")
print("=" * 60 + "\n")

ended_sessions = UserSession.objects.filter(
    session_end__isnull=False
).order_by('-session_end')[:5]

for session in ended_sessions:
    print(f"Session ID: {session.id}")
    print(f"  User: {session.user or 'Anonymous'}")
    print(f"  Ended: {session.session_end}")
    print(f"  Duration: {session.duration_minutes} minutes")
    print(f"  End Reason: {session.end_reason}")
    print()

print("=" * 60)
print("Settings Check")
print("=" * 60)
print(f"\nANALYTICS_MIN_ENGAGEMENT_FOR_FEEDBACK: {settings.ANALYTICS_MIN_ENGAGEMENT_FOR_FEEDBACK}")
print(f"HUBSPOT_PORTAL_ID: {settings.HUBSPOT_PORTAL_ID}")
print(f"HUBSPOT_FORM_ID: {settings.HUBSPOT_FORM_ID}")
print(f"HUBSPOT_REGION: {settings.HUBSPOT_REGION}")
