"""
View detailed AI Coach suggestion example from Marketing and Bug Tracking boards
"""
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.coach_models import CoachingSuggestion
from kanban.models import Board

print("\n=== AI Coach Detailed Suggestions ===\n")

# Get boards
marketing_board = Board.objects.filter(name='Marketing Campaign', is_official_demo_board=True).first()
bug_board = Board.objects.filter(name='Bug Tracking', is_official_demo_board=True).first()

for board in [marketing_board, bug_board]:
    if not board:
        continue
    
    print("="*80)
    print(f"Board: {board.name}")
    print("="*80)
    
    suggestion = CoachingSuggestion.objects.filter(
        board=board,
        generation_method='hybrid'
    ).first()
    
    if not suggestion:
        print("No AI-enhanced suggestions found\n")
        continue
    
    print(f"\n📌 {suggestion.title}")
    print(f"   Severity: {suggestion.severity.upper()}")
    print(f"   Type: {suggestion.suggestion_type}")
    print(f"   Method: {suggestion.generation_method}")
    print(f"   AI Model: {suggestion.ai_model_used}")
    print(f"   Confidence: {suggestion.confidence_score}")
    
    print(f"\n💬 Message:")
    print(f"   {suggestion.message}")
    
    print(f"\n🎯 Why This Matters:")
    if suggestion.reasoning:
        # Wrap text at 70 chars
        reasoning_lines = suggestion.reasoning.split('\n')
        for line in reasoning_lines:
            words = line.split()
            current_line = "   "
            for word in words:
                if len(current_line) + len(word) + 1 > 77:
                    print(current_line)
                    current_line = "   " + word
                else:
                    current_line += " " + word if current_line != "   " else word
            if current_line.strip():
                print(current_line)
    else:
        print("   (No reasoning provided)")
    
    print(f"\n✅ Recommended Actions:")
    if suggestion.recommended_actions:
        for i, action in enumerate(suggestion.recommended_actions, 1):
            print(f"   {i}. {action}")
    else:
        print("   (No actions provided)")
    
    print(f"\n📊 Expected Impact:")
    if suggestion.expected_impact:
        impact_lines = suggestion.expected_impact.split('\n')
        for line in impact_lines:
            words = line.split()
            current_line = "   "
            for word in words:
                if len(current_line) + len(word) + 1 > 77:
                    print(current_line)
                    current_line = "   " + word
                else:
                    current_line += " " + word if current_line != "   " else word
            if current_line.strip():
                print(current_line)
    else:
        print("   (No impact provided)")
    
    print("\n")

print("="*80)
print("✅ All suggestions are now in detailed AI-enhanced format!")
print("="*80)
