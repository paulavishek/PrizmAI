#!/usr/bin/env python
"""
Thoroughly verify all analytics numbers
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from django.db.models import Q, Sum, Avg
from django.utils import timezone
from datetime import timedelta
from ai_assistant.models import AIAssistantSession, AIAssistantAnalytics

print("=" * 70)
print("COMPREHENSIVE ANALYTICS VERIFICATION")
print("=" * 70)

testuser = User.objects.get(username='testuser1')

# Date range
end_date = timezone.now().date()
start_date = end_date - timedelta(days=30)
print(f"\nDate range: {start_date} to {end_date}")

# Get sessions - include demo sessions and user's own sessions
sessions_qs = AIAssistantSession.objects.filter(
    Q(user=testuser) | Q(is_demo=True),
    updated_at__gte=timezone.now() - timedelta(days=30)
)

# Get analytics from both demo users and current user
demo_user_ids = AIAssistantSession.objects.filter(is_demo=True).values_list('user_id', flat=True).distinct()
analytics_qs = AIAssistantAnalytics.objects.filter(
    Q(user=testuser) | Q(user_id__in=demo_user_ids),
    date__gte=start_date,
    date__lte=end_date
)

print("\n--- 1. TOTAL MESSAGES ---")
total_messages = sessions_qs.aggregate(Sum('message_count'))['message_count__sum'] or 0
print(f"Total messages (from sessions): {total_messages}")
print("✓ Expected: 48")

print("\n--- 2. RAG USAGE RATE ---")
kb_queries = analytics_qs.aggregate(Sum('knowledge_base_queries'))['knowledge_base_queries__sum'] or 0
gemini_requests = analytics_qs.aggregate(Sum('gemini_requests'))['gemini_requests__sum'] or 0
rag_usage_rate = round((kb_queries / gemini_requests * 100), 1) if gemini_requests > 0 else 0
print(f"Knowledge Base Queries: {kb_queries}")
print(f"Gemini Requests: {gemini_requests}")
print(f"RAG Usage Rate: {rag_usage_rate}%")

print("\n--- 3. KNOWLEDGE BASE QUERIES ---")
print(f"Total KB Queries: {kb_queries}")
print("✓ Expected: 130")

print("\n--- 4. CONTEXT-AWARE RESPONSES ---")
web_searches = analytics_qs.aggregate(Sum('web_searches_performed'))['web_searches_performed__sum'] or 0
context_aware_requests = kb_queries + web_searches
context_aware_rate = round((context_aware_requests / gemini_requests * 100), 1) if gemini_requests > 0 else 0
print(f"KB Queries: {kb_queries}")
print(f"Web Searches: {web_searches}")
print(f"Context-Aware Requests: {context_aware_requests}")
print(f"Gemini Requests: {gemini_requests}")
print(f"Context-Aware Rate: {context_aware_rate}%")
print("✓ Expected: 66.4%")

print("\n--- 5. MULTI-TURN CONVERSATIONS ---")
multi_turn = sessions_qs.filter(message_count__gte=3).count()
print(f"Sessions with 3+ messages: {multi_turn}")
print("\nBreakdown:")
for session in sessions_qs.order_by('-message_count'):
    marker = "✓" if session.message_count >= 3 else "✗"
    demo_marker = "[DEMO]" if session.is_demo else "[USER]"
    print(f"  {marker} {demo_marker} {session.title}: {session.message_count} messages")
print("✓ Expected: 7")

print("\n--- 6. AVG RESPONSE TIME ---")
avg_response_time = analytics_qs.aggregate(Avg('avg_response_time_ms'))['avg_response_time_ms__avg'] or 0
avg_response_time_sec = round(avg_response_time / 1000, 2) if avg_response_time else 0
print(f"Avg response time: {avg_response_time_sec}s")
print("✓ Expected: 1.52s")

print("\n--- 7. CHART DATA ANALYSIS ---")
print("\nAnalytics records with dates:")
print(f"Total analytics records: {analytics_qs.count()}")
print("\nSample records (first 10):")
for record in analytics_qs.order_by('date')[:10]:
    print(f"  Date: {record.date} | User: {record.user.username} | "
          f"Messages: {record.messages_sent} | Tokens: {record.total_tokens_used} | "
          f"Board: {record.board}")

print("\n--- 8. SESSION DATES vs ANALYTICS DATES ---")
print("\nSessions (created/updated dates):")
for session in sessions_qs.order_by('-updated_at')[:10]:
    demo = "[DEMO]" if session.is_demo else "[USER]"
    print(f"  {demo} {session.title}")
    print(f"      Created: {session.created_at.date()}")
    print(f"      Updated: {session.updated_at.date()}")
    print(f"      Messages: {session.message_count}")

print("\n" + "=" * 70)
print("SUMMARY:")
print(f"  Total Messages: {total_messages} (from session.message_count)")
print(f"  RAG Usage Rate: {rag_usage_rate}%")
print(f"  KB Queries: {kb_queries}")
print(f"  Context-Aware Rate: {context_aware_rate}%")
print(f"  Multi-turn Conversations: {multi_turn}")
print(f"  Avg Response Time: {avg_response_time_sec}s")
print("\nChart dates come from AIAssistantAnalytics.date field")
print("These are accumulated daily totals, not individual session dates")
print("=" * 70)
