"""
Test script to verify AI enhancement is working
Run this with: python manage.py shell < test_ai_enhancement.py
             OR: python test_ai_enhancement.py (standalone)
"""

# Setup Django environment if running standalone
import os
import sys

if __name__ == '__main__':
    # Add the project directory to the path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Setup Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
    
    import django
    django.setup()

from kanban.utils.ai_coach_service import AICoachService

print("=" * 60)
print("AI Coach Enhancement Test")
print("=" * 60)

# Initialize AI Coach
coach = AICoachService()
print(f"\n1. Gemini Available: {coach.gemini_available}")

if coach.gemini_available:
    print("   ✓ Gemini API is configured")
    
    # Test enhancement
    print("\n2. Testing AI enhancement...")
    
    test_suggestion = {
        'title': 'Test Suggestion',
        'message': 'Your team has 5 overdue tasks.',
        'suggestion_type': 'deadline_risk',
        'severity': 'medium',
        'confidence_score': 0.75,
        'reasoning': '',
        'recommended_actions': [],
        'expected_impact': '',
        'metrics_snapshot': {'overdue_count': 5}
    }
    
    test_context = {
        'board_name': 'Test Board',
        'team_size': 5,
        'active_tasks': 20,
        'project_phase': 'active',
        'velocity': 10
    }
    
    try:
        enhanced = coach.enhance_suggestion_with_ai(test_suggestion, test_context)
        
        print(f"   ✓ Enhancement successful!")
        print(f"\n3. Enhanced Fields:")
        print(f"   - Generation Method: {enhanced.get('generation_method')}")
        print(f"   - Has Reasoning: {bool(enhanced.get('reasoning'))}")
        print(f"   - Has Actions: {len(enhanced.get('recommended_actions', []))} actions")
        print(f"   - Has Impact: {bool(enhanced.get('expected_impact'))}")
        
        if enhanced.get('reasoning'):
            print(f"\n4. Sample Reasoning (first 100 chars):")
            print(f"   {enhanced['reasoning'][:100]}...")
        
        if enhanced.get('recommended_actions'):
            print(f"\n5. Sample Action:")
            print(f"   {enhanced['recommended_actions'][0][:150]}...")
            
        print("\n" + "=" * 60)
        print("✓ AI Enhancement is working correctly!")
        print("=" * 60)
        
    except Exception as e:
        print(f"   ✗ Enhancement failed: {e}")
        import traceback
        traceback.print_exc()
else:
    print("   ✗ Gemini API is NOT configured")
    print("\n   To enable AI enhancement:")
    print("   1. Add GEMINI_API_KEY to your settings")
    print("   2. Restart the server")
    print("   3. Run this test again")

print("\n")
