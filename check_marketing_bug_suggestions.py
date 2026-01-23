"""
Check AI Coach suggestions for Marketing Campaign and Bug Tracking boards
"""
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.coach_models import CoachingSuggestion
from kanban.models import Board
from django.db.models import Count

print("\n=== AI Coach Suggestions Status ===\n")

# Check overall statistics
print("Overall Statistics:")
methods = CoachingSuggestion.objects.values('generation_method').annotate(count=Count('id'))
for m in methods:
    print(f"  {m['generation_method']:15} : {m['count']}")

print("\n" + "="*80 + "\n")

# Check each demo board
board_names = ['Software Development', 'Marketing Campaign', 'Bug Tracking']

for board_name in board_names:
    board = Board.objects.filter(name=board_name, is_official_demo_board=True).first()
    
    if not board:
        print(f"❌ {board_name} board not found\n")
        continue
    
    suggestions = CoachingSuggestion.objects.filter(board=board).order_by('-created_at')
    
    print(f"📋 {board_name} Board")
    print(f"   Total suggestions: {suggestions.count()}")
    
    if suggestions.exists():
        # Count by generation method
        rule_only = suggestions.filter(generation_method='rule').count()
        ai_hybrid = suggestions.filter(generation_method='hybrid').count()
        
        print(f"   - Rule-only (brief):  {rule_only}")
        print(f"   - AI-hybrid (detailed): {ai_hybrid}")
        
        # Show sample
        print(f"\n   Recent suggestions:")
        for s in suggestions[:3]:
            print(f"   • {s.title}")
            print(f"     Method: {s.generation_method}, AI Model: {s.ai_model_used or 'N/A'}")
            has_reasoning = 'Yes' if s.reasoning and len(s.reasoning) > 100 else 'No'
            print(f"     Has detailed reasoning: {has_reasoning}")
            if s.reasoning:
                preview = s.reasoning[:80] + '...' if len(s.reasoning) > 80 else s.reasoning
                print(f"     Reasoning preview: {preview}")
            print()
    else:
        print(f"   ⚠️  No suggestions found\n")
    
    print("="*80 + "\n")

print("\n✅ Analysis complete")
print("\nRecommendation:")
print("  If Marketing Campaign or Bug Tracking boards have 'rule-only' suggestions,")
print("  run: python regenerate_marketing_bug_suggestions.py")
