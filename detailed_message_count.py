#!/usr/bin/env python
"""
Detailed analysis of message counting discrepancy
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import timedelta
from ai_assistant.models import AIAssistantAnalytics, AIAssistantSession, AIAssistantMessage

print("=" * 70)
print("DETAILED MESSAGE COUNT ANALYSIS")
print("=" * 70)

# Get testuser1
testuser = User.objects.get(username='testuser1')
print(f"\nAnalyzing user: {testuser.username} (ID: {testuser.id})")

# Check actual sessions and their messages
sessions = AIAssistantSession.objects.filter(user=testuser)
print(f"\n--- Sessions for testuser1 ---")
print(f"Total sessions: {sessions.count()}")

total_messages_in_sessions = 0
for session in sessions.order_by('-updated_at'):
    actual_message_count = AIAssistantMessage.objects.filter(session=session).count()
    print(f"\n  Session: {session.title}")
    print(f"    ID: {session.id}")
    print(f"    Created: {session.created_at}")
    print(f"    Updated: {session.updated_at}")
    print(f"    message_count field: {session.message_count}")
    print(f"    Actual messages in DB: {actual_message_count}")
    print(f"    Is demo: {session.is_demo}")
    total_messages_in_sessions += actual_message_count

print(f"\n  TOTAL ACTUAL MESSAGES ACROSS ALL SESSIONS: {total_messages_in_sessions}")

# Now check analytics
print(f"\n--- Analytics for testuser1 ---")
end_date = timezone.now().date()
start_date = end_date - timedelta(days=30)

analytics_records = AIAssistantAnalytics.objects.filter(
    user=testuser,
    date__gte=start_date,
    date__lte=end_date
)

print(f"Analytics records (last 30 days): {analytics_records.count()}")
total_analytics_messages = 0
for analytics in analytics_records.order_by('-date'):
    print(f"\n  Date: {analytics.date}")
    print(f"    messages_sent: {analytics.messages_sent}")
    print(f"    gemini_requests: {analytics.gemini_requests}")
    print(f"    Board: {analytics.board}")
    total_analytics_messages += analytics.messages_sent

print(f"\n  TOTAL from analytics.messages_sent: {total_analytics_messages}")

# Check if there are any demo sessions
demo_sessions = AIAssistantSession.objects.filter(is_demo=True)
print(f"\n--- Demo Sessions ---")
print(f"Total demo sessions: {demo_sessions.count()}")

for session in demo_sessions[:5]:
    actual_message_count = AIAssistantMessage.objects.filter(session=session).count()
    print(f"\n  Session: {session.title}")
    print(f"    User: {session.user.username}")
    print(f"    message_count field: {session.message_count}")
    print(f"    Actual messages: {actual_message_count}")

# Check analytics for demo users
demo_user_ids = demo_sessions.values_list('user_id', flat=True).distinct()
demo_analytics = AIAssistantAnalytics.objects.filter(
    user_id__in=demo_user_ids,
    date__gte=start_date,
    date__lte=end_date
)
demo_analytics_total = demo_analytics.aggregate(Sum('messages_sent'))['messages_sent__sum'] or 0
print(f"\n  Total messages in demo user analytics: {demo_analytics_total}")

print("\n" + "=" * 70)
print("SUMMARY:")
print(f"  testuser1 actual messages in sessions: {total_messages_in_sessions}")
print(f"  testuser1 analytics messages_sent: {total_analytics_messages}")
print(f"  Demo users analytics messages_sent: {demo_analytics_total}")
print(f"  Combined (old logic): {total_analytics_messages + demo_analytics_total}")
print("=" * 70)
