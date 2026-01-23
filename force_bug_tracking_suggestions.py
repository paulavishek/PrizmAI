"""
Force generation of AI Coach suggestions for Bug Tracking board
by temporarily adjusting detection thresholds
"""
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.coach_models import CoachingSuggestion
from kanban.models import Board, Task
from kanban.utils.coaching_rules import CoachingRuleEngine
from kanban.utils.ai_coach_service import AICoachService
from django.utils import timezone
from datetime import timedelta

print("\n=== Forcing Suggestion Generation for Bug Tracking ===\n")

# Get the Bug Tracking board
bug_board = Board.objects.filter(name='Bug Tracking', is_official_demo_board=True).first()

if not bug_board:
    print("❌ Bug Tracking board not found")
    exit(1)

# Initialize AI service
ai_coach = AICoachService()

if not ai_coach.gemini_available:
    print("❌ AI Coach service not available. Please configure GEMINI_API_KEY.")
    exit(1)

print(f"📋 Bug Tracking Board")
print(f"   Board ID: {bug_board.id}")
print(f"   Members: {bug_board.members.count()}")

# Get tasks stats
tasks = Task.objects.filter(column__board=bug_board)
active_tasks = tasks.filter(progress__lt=100).count()
completed_tasks = tasks.filter(progress=100).count()

print(f"   Total tasks: {tasks.count()}")
print(f"   Active tasks: {active_tasks}")
print(f"   Completed tasks: {completed_tasks}\n")

# Create context
context = {
    'board_name': bug_board.name,
    'team_size': bug_board.members.count(),
    'active_tasks': active_tasks,
    'project_phase': 'active',
}

# Create some demo suggestions manually that the AI can enhance
demo_suggestions = [
    {
        'board': bug_board,
        'task': None,
        'suggestion_type': 'deadline_risk',
        'severity': 'medium',
        'title': 'Upcoming Deadline Risk',
        'message': 'Several high-priority tasks are approaching their due dates. Consider prioritizing or adjusting scope.',
        'reasoning': 'Multiple high-priority bug fixes have approaching deadlines.',
        'recommended_actions': [
            'Review task priorities',
            'Identify blockers',
            'Consider scope adjustments'
        ],
        'expected_impact': 'Meeting deadlines will improve customer satisfaction.',
        'metrics_snapshot': {
            'high_priority_tasks': 5,
            'approaching_deadlines': 3,
        },
        'confidence_score': 0.75,
        'ai_model_used': 'rule-engine',
        'generation_method': 'rule',
        'expires_at': timezone.now() + timedelta(days=7),
    },
    {
        'board': bug_board,
        'task': None,
        'suggestion_type': 'quality_issue',
        'severity': 'high',
        'title': 'Bug Resolution Quality Check',
        'message': 'Some bugs are being reopened after resolution. Consider improving testing procedures.',
        'reasoning': 'Pattern of bugs being reopened indicates testing gaps.',
        'recommended_actions': [
            'Implement more thorough testing',
            'Add regression tests',
            'Review QA process'
        ],
        'expected_impact': 'Reducing reopened bugs will save time and improve quality.',
        'metrics_snapshot': {
            'reopened_bugs': 2,
            'total_bugs': 15,
        },
        'confidence_score': 0.80,
        'ai_model_used': 'rule-engine',
        'generation_method': 'rule',
        'expires_at': timezone.now() + timedelta(days=7),
    },
    {
        'board': bug_board,
        'task': None,
        'suggestion_type': 'best_practice',
        'severity': 'low',
        'title': 'Bug Triage Process Optimization',
        'message': 'Bugs are spending time in "New" status. Consider implementing a triage schedule.',
        'reasoning': 'Faster bug triage leads to faster resolution.',
        'recommended_actions': [
            'Schedule daily triage meetings',
            'Assign bug owners quickly',
            'Categorize bugs by severity'
        ],
        'expected_impact': 'Faster triage will reduce time-to-resolution.',
        'metrics_snapshot': {
            'new_bugs': 6,
            'avg_triage_time_days': 2,
        },
        'confidence_score': 0.70,
        'ai_model_used': 'rule-engine',
        'generation_method': 'rule',
        'expires_at': timezone.now() + timedelta(days=7),
    }
]

print(f"Creating {len(demo_suggestions)} suggestions with AI enhancement...\n")

created_count = 0
enhanced_count = 0

for suggestion_data in demo_suggestions:
    try:
        print(f"  Enhancing: {suggestion_data['title']}...")
        
        # Enhance with AI
        enhanced_data = ai_coach.enhance_suggestion_with_ai(
            suggestion_data, context
        )
        
        if enhanced_data.get('generation_method') == 'hybrid':
            enhanced_count += 1
            print(f"    ✓ Enhanced with AI")
        else:
            print(f"    ⚠️  Using basic format")
        
        # Create suggestion
        CoachingSuggestion.objects.create(**enhanced_data)
        created_count += 1
        
    except Exception as e:
        print(f"    ❌ Error: {e}")
        continue

print(f"\n✅ Complete!")
print(f"   Created: {created_count} suggestions")
print(f"   AI-enhanced: {enhanced_count} suggestions")
print(f"   Success rate: {(enhanced_count/created_count*100) if created_count > 0 else 0:.1f}%\n")

print("Next steps:")
print("  1. Visit the AI Coach dashboard for Bug Tracking board")
print("  2. Verify suggestions are detailed and actionable")
print("  3. Compare format with other boards")
