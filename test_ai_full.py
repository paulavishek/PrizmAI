"""
Comprehensive AI Enhancement Test
Run with: venv\Scripts\python.exe test_ai_full.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.utils.ai_coach_service import AICoachService

print("=" * 70)
print("AI Coach Enhancement - Comprehensive Test")
print("=" * 70)

# Initialize AI Coach
coach = AICoachService()
print(f"\n✓ AI Coach Service initialized")
print(f"  Gemini Available: {coach.gemini_available}")

if not coach.gemini_available:
    print("\n✗ ERROR: Gemini API is NOT configured!")
    print("\n  To enable AI enhancement:")
    print("  1. Add GEMINI_API_KEY to your settings")
    print("  2. Restart the server")
    sys.exit(1)

print(f"  Status: ✓ ENABLED")

# Test enhancement
print(f"\n{'=' * 70}")
print("Testing AI Enhancement...")
print("=" * 70)

test_suggestion = {
    'title': 'Team velocity declining (20% drop)',
    'message': 'Your team velocity has decreased by 20%. This is worth monitoring to prevent further decline.',
    'suggestion_type': 'velocity_drop',
    'severity': 'medium',
    'confidence_score': 0.75,
    'reasoning': 'Velocity dropped from 2.5 to 2.0.',
    'recommended_actions': [
        'Monitor velocity trend over the next sprint',
        'Ask team about challenges'
    ],
    'expected_impact': 'Early intervention can prevent issues.',
    'metrics_snapshot': {
        'current_velocity': 2.0,
        'avg_previous_velocity': 2.5,
        'drop_percentage': 20.0
    }
}

test_context = {
    'board_name': 'Software Development',
    'team_size': 5,
    'active_tasks': 20,
    'project_phase': 'active',
    'velocity': 2.0
}

try:
    print("\nCalling Gemini AI to enhance suggestion...")
    enhanced = coach.enhance_suggestion_with_ai(test_suggestion, test_context)
    
    print("\n✓ AI Enhancement SUCCESSFUL!")
    print("\n" + "=" * 70)
    print("Enhancement Results:")
    print("=" * 70)
    
    print(f"\n1. Generation Method: {enhanced.get('generation_method')}")
    print(f"   {'✓ HYBRID (AI-enhanced)' if enhanced.get('generation_method') == 'hybrid' else '✗ Rule-based only'}")
    
    print(f"\n2. AI Model Used: {enhanced.get('ai_model_used')}")
    
    print(f"\n3. Confidence Score: {enhanced.get('confidence_score')}")
    
    has_reasoning = bool(enhanced.get('reasoning'))
    print(f"\n4. Has Detailed Reasoning: {has_reasoning}")
    if has_reasoning:
        reasoning = enhanced.get('reasoning', '')
        print(f"   Length: {len(reasoning)} characters")
        print(f"   Preview: {reasoning[:150]}...")
    
    actions = enhanced.get('recommended_actions', [])
    print(f"\n5. Recommended Actions: {len(actions)} actions")
    if actions:
        print(f"   First action length: {len(actions[0])} characters")
        print(f"   Preview: {actions[0][:200]}...")
    
    has_impact = bool(enhanced.get('expected_impact'))
    print(f"\n6. Has Expected Impact: {has_impact}")
    if has_impact:
        impact = enhanced.get('expected_impact', '')
        print(f"   Length: {len(impact)} characters")
        print(f"   Preview: {impact[:150]}...")
    
    print("\n" + "=" * 70)
    print("DETAILED FORMAT VERIFICATION")
    print("=" * 70)
    
    checks = {
        'Generation method is hybrid': enhanced.get('generation_method') == 'hybrid',
        'Has detailed reasoning (>100 chars)': len(enhanced.get('reasoning', '')) > 100,
        'Has 3+ detailed actions': len(actions) >= 3,
        'Actions include rationale': any('Rationale:' in str(a) or 'rationale' in str(a).lower() for a in actions),
        'Has meaningful impact statement': len(enhanced.get('expected_impact', '')) > 50,
    }
    
    print()
    all_passed = True
    for check, passed in checks.items():
        status = "✓" if passed else "✗"
        print(f"{status} {check}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓✓✓ ALL CHECKS PASSED - DETAILED FORMAT WORKING! ✓✓✓")
    else:
        print("⚠ SOME CHECKS FAILED - Review configuration")
    print("=" * 70)
    
    print("\n\nFULL ENHANCED SUGGESTION:")
    print("=" * 70)
    print(f"\nTitle: {enhanced.get('title')}")
    print(f"\nMessage: {enhanced.get('message')}")
    print(f"\nWhy this matters:")
    print(enhanced.get('reasoning', 'N/A'))
    print(f"\nRecommended Actions:")
    for i, action in enumerate(actions, 1):
        print(f"{i}. {action}")
    print(f"\nExpected Impact:")
    print(enhanced.get('expected_impact', 'N/A'))
    print("=" * 70)
    
except Exception as e:
    print(f"\n✗ Enhancement FAILED!")
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n\n" + "=" * 70)
print("Test completed successfully!")
print("=" * 70)
print("\nNext Steps:")
print("1. Go to AI Coach dashboard in your browser")
print("2. Click 'Refresh Suggestions' button")
print("3. All new suggestions will have detailed format")
print("=" * 70)
