#!/usr/bin/env python
"""
Check analytics data to debug the 286 messages issue
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
from ai_assistant.models import AIAssistantAnalytics, AIAssistantSession

print("=" * 70)
print("ANALYTICS DEBUG - Checking 'Analytics of Spectra' data")
print("=" * 70)

# Get date range (last 30 days)
end_date = timezone.now().date()
start_date = end_date - timedelta(days=30)

print(f"\nDate range: {start_date} to {end_date}")

# Check demo sessions and users
demo_sessions = AIAssistantSession.objects.filter(is_demo=True)
demo_user_ids = list(demo_sessions.values_list('user_id', flat=True).distinct())

print(f"\n--- Demo Sessions ---")
print(f"Total demo sessions: {demo_sessions.count()}")
print(f"Demo user IDs: {demo_user_ids}")

# Get demo users info
if demo_user_ids:
    demo_users = User.objects.filter(id__in=demo_user_ids)
    print(f"\nDemo users:")
    for user in demo_users:
        print(f"  - {user.username} (ID: {user.id})")

# Check analytics for demo users
print(f"\n--- Analytics Records (last 30 days) ---")
demo_analytics = AIAssistantAnalytics.objects.filter(
    user_id__in=demo_user_ids,
    date__gte=start_date,
    date__lte=end_date
)

print(f"Total analytics records for demo users: {demo_analytics.count()}")

# Show breakdown by user
for user_id in demo_user_ids:
    user = User.objects.get(id=user_id)
    user_analytics = demo_analytics.filter(user_id=user_id)
    total_msgs = user_analytics.aggregate(Sum('messages_sent'))['messages_sent__sum'] or 0
    print(f"\n  User: {user.username} (ID: {user_id})")
    print(f"    Analytics records: {user_analytics.count()}")
    print(f"    Total messages: {total_msgs}")
    
    # Show per-day breakdown
    for analytics in user_analytics.order_by('-date')[:10]:
        print(f"      {analytics.date}: {analytics.messages_sent} messages, {analytics.gemini_requests} requests")

# Check if there's a current logged-in user (testuser1)
print(f"\n--- Real User Analytics ---")
try:
    testuser = User.objects.get(username='testuser1')
    user_analytics = AIAssistantAnalytics.objects.filter(
        user=testuser,
        date__gte=start_date,
        date__lte=end_date
    )
    total_msgs = user_analytics.aggregate(Sum('messages_sent'))['messages_sent__sum'] or 0
    print(f"User: testuser1 (ID: {testuser.id})")
    print(f"  Analytics records: {user_analytics.count()}")
    print(f"  Total messages: {total_msgs}")
except User.DoesNotExist:
    print("testuser1 not found")

# Now replicate the query from the view
print(f"\n--- View Query Simulation ---")
# Try to get a user to simulate
test_user = User.objects.first()
if test_user:
    print(f"Simulating for user: {test_user.username}")
    
    analytics_qs = AIAssistantAnalytics.objects.filter(
        Q(user=test_user) | Q(user_id__in=demo_user_ids),
        date__gte=start_date,
        date__lte=end_date
    )
    
    total_messages = analytics_qs.aggregate(Sum('messages_sent'))['messages_sent__sum'] or 0
    kb_queries = analytics_qs.aggregate(Sum('knowledge_base_queries'))['knowledge_base_queries__sum'] or 0
    gemini_requests = analytics_qs.aggregate(Sum('gemini_requests'))['gemini_requests__sum'] or 0
    
    print(f"  Total analytics records: {analytics_qs.count()}")
    print(f"  Total messages: {total_messages}")
    print(f"  KB queries: {kb_queries}")
    print(f"  Gemini requests: {gemini_requests}")

print("\n" + "=" * 70)
