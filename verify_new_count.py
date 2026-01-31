#!/usr/bin/env python
"""
Verify the new counting approach
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from django.db.models import Q, Sum
from django.utils import timezone
from datetime import timedelta
from ai_assistant.models import AIAssistantSession

print("=" * 70)
print("VERIFYING NEW MESSAGE COUNT APPROACH")
print("=" * 70)

testuser = User.objects.get(username='testuser1')

# Get sessions - include demo sessions and user's own sessions (last 30 days)
sessions_qs = AIAssistantSession.objects.filter(
    Q(user=testuser) | Q(is_demo=True),
    updated_at__gte=timezone.now() - timedelta(days=30)
)

print(f"\n--- Sessions (Demo + testuser1, last 30 days) ---")
print(f"Total sessions: {sessions_qs.count()}")

# Count demo vs user sessions
demo_sessions = sessions_qs.filter(is_demo=True)
user_sessions = sessions_qs.filter(user=testuser, is_demo=False)

print(f"  Demo sessions: {demo_sessions.count()}")
print(f"  testuser1 sessions: {user_sessions.count()}")

# Get message counts
demo_message_count = demo_sessions.aggregate(Sum('message_count'))['message_count__sum'] or 0
user_message_count = user_sessions.aggregate(Sum('message_count'))['message_count__sum'] or 0
total_message_count = sessions_qs.aggregate(Sum('message_count'))['message_count__sum'] or 0

print(f"\n--- Message Counts ---")
print(f"  Demo sessions total messages: {demo_message_count}")
print(f"  testuser1 sessions total messages: {user_message_count}")
print(f"  COMBINED TOTAL: {total_message_count}")

print("\n--- Demo Session Details ---")
for session in demo_sessions.order_by('-updated_at')[:10]:
    print(f"  {session.title}: {session.message_count} messages (User: {session.user.username})")

print("\n--- testuser1 Session Details ---")
for session in user_sessions:
    print(f"  {session.title}: {session.message_count} messages")

print("\n" + "=" * 70)
print(f"Expected analytics display: {total_message_count} total messages")
print("=" * 70)
