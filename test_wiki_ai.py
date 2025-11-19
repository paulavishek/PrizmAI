"""
Quick test script to verify wiki AI assistant is working with the updated model
"""
import os
import sys
import django

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from wiki.ai_utils import generate_ai_content, analyze_meeting_notes_from_wiki

def test_generate_ai_content():
    """Test basic AI content generation"""
    print("=" * 60)
    print("Testing AI Content Generation with gemini-2.0-flash-exp")
    print("=" * 60)
    
    prompt = "Write a brief 2-sentence summary of what a daily standup meeting is."
    result = generate_ai_content(prompt)
    
    if result:
        print("✅ SUCCESS: AI content generated")
        print(f"\nResponse:\n{result}\n")
        return True
    else:
        print("❌ FAILED: No response from AI")
        return False

def test_analyze_meeting_notes():
    """Test meeting notes analysis"""
    print("=" * 60)
    print("Testing Meeting Notes Analysis")
    print("=" * 60)
    
    test_content = """
    # Daily Standup - November 19, 2025
    
    ## Attendees
    - John (Developer)
    - Sarah (Project Manager)
    - Mike (Designer)
    
    ## Updates
    
    **John**: Completed the user authentication feature. Need to review the code with Sarah.
    Will start working on the dashboard next.
    
    **Sarah**: Reviewed sprint backlog. We need to prioritize the payment integration feature.
    Mike, can you send the final designs by Friday?
    
    **Mike**: Working on the mobile UI designs. Will have them ready by end of week.
    Need feedback on the color scheme from the team.
    
    ## Blockers
    - Payment gateway API documentation is unclear - John needs clarification
    - Need design approval from client before proceeding
    
    ## Action Items
    - John to schedule code review with Sarah
    - Sarah to contact payment vendor for API docs
    - Mike to share design mockups by Friday
    - Team meeting on Friday to review designs
    """
    
    wiki_context = {
        'title': 'Daily Standup - Nov 19',
        'created_at': '2025-11-19T10:00:00',
        'created_by': 'admin',
        'tags': ['standup', 'daily']
    }
    
    result = analyze_meeting_notes_from_wiki(
        wiki_content=test_content,
        wiki_page_context=wiki_context,
        organization=None,
        available_boards=None
    )
    
    if result:
        print("✅ SUCCESS: Meeting notes analyzed")
        print(f"\nAction Items Found: {len(result.get('action_items', []))}")
        print(f"Decisions Found: {len(result.get('decisions', []))}")
        print(f"Blockers Found: {len(result.get('blockers', []))}")
        
        if result.get('action_items'):
            print("\nSample Action Items:")
            for i, item in enumerate(result['action_items'][:3], 1):
                print(f"  {i}. {item.get('title', 'No title')}")
        
        return True
    else:
        print("❌ FAILED: No analysis results")
        return False

if __name__ == '__main__':
    print("\n🔍 Testing Wiki AI Assistant with Updated Model\n")
    
    test1 = test_generate_ai_content()
    print()
    test2 = test_analyze_meeting_notes()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Basic AI Generation: {'✅ PASSED' if test1 else '❌ FAILED'}")
    print(f"Meeting Analysis: {'✅ PASSED' if test2 else '❌ FAILED'}")
    print()
    
    if test1 and test2:
        print("🎉 All tests passed! Wiki AI assistant is working correctly.")
    else:
        print("⚠️ Some tests failed. Please check the error messages above.")
