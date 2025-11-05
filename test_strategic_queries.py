"""
Test strategic query detection and RAG integration
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from ai_assistant.utils.chatbot_service import TaskFlowChatbotService

def test_strategic_queries():
    """Test strategic query detection and response"""
    
    print("=" * 80)
    print("STRATEGIC QUERY & RAG INTEGRATION TEST")
    print("=" * 80)
    
    # Get test user
    user = User.objects.filter(is_staff=False).first()
    if not user:
        user = User.objects.first()
    
    print(f"\nTesting with user: {user.username}\n")
    
    chatbot = TaskFlowChatbotService(user=user, board=None)
    
    # Test strategic queries
    strategic_test_queries = [
        "How to tackle high-risk issues in my project?",
        "What are best practices for risk mitigation?",
        "How should I handle task dependencies?",
        "Tips for improving team productivity",
        "How can I better manage project risks?",
        "What strategies should I use to reduce delays?",
        "Advice on handling critical tasks",
        "How to optimize resource allocation?",
    ]
    
    print("STRATEGIC QUERY DETECTION:")
    print("-" * 80)
    
    for query in strategic_test_queries:
        is_strategic = chatbot._is_strategic_query(query)
        is_search = chatbot._is_search_query(query)
        is_mitigation = chatbot._is_mitigation_query(query)
        is_risk = chatbot._is_risk_query(query)
        
        print(f"\nQuery: '{query}'")
        print(f"  ✓ Strategic: {'YES' if is_strategic else 'NO'}")
        print(f"  ✓ Search: {'YES' if is_search else 'NO'}")
        print(f"  ✓ Mitigation: {'YES' if is_mitigation else 'NO'}")
        print(f"  ✓ Risk: {'YES' if is_risk else 'NO'}")
        print(f"  → Will trigger RAG: {'YES' if (is_strategic or is_search) else 'NO'}")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    strategic_detected = sum(1 for q in strategic_test_queries if chatbot._is_strategic_query(q))
    rag_triggered = sum(1 for q in strategic_test_queries if (chatbot._is_strategic_query(q) or chatbot._is_search_query(q)))
    
    print(f"\n✓ Strategic Queries Detected: {strategic_detected}/{len(strategic_test_queries)}")
    print(f"✓ RAG Would Be Triggered: {rag_triggered}/{len(strategic_test_queries)}")
    print(f"\n{'✓' if strategic_detected == len(strategic_test_queries) else '✗'} All strategic queries properly detected")
    print(f"{'✓' if rag_triggered >= len(strategic_test_queries) * 0.8 else '✗'} RAG triggering working as expected")

if __name__ == "__main__":
    test_strategic_queries()
