"""
Force generation of all possible AI Coach suggestions
"""
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board
from kanban.coach_models import CoachingSuggestion
from django.core.management import call_command

# Get the Software Development board
board = Board.objects.get(name='Software Development')
board_id = board.id

print(f"\n=== Current Suggestions for '{board.name}' ===\n")

suggestions = CoachingSuggestion.objects.filter(board=board).values(
    'title', 'generation_method', 'ai_model_used', 'reasoning'
)

for s in suggestions:
    print(f"Title: {s['title']}")
    print(f"  Method: {s['generation_method']}")
    print(f"  AI Model: {s['ai_model_used']}")
    reasoning_preview = s['reasoning'][:100] + '...' if s['reasoning'] and len(s['reasoning']) > 100 else s['reasoning'] or 'None'
    print(f"  Reasoning: {reasoning_preview}\n")

if suggestions:
    ai_enhanced = [s for s in suggestions if s['generation_method'] == 'hybrid']
    print(f"\nSummary:")
    print(f"  Total: {len(suggestions)}")
    print(f"  AI-Enhanced: {len(ai_enhanced)}")
    print(f"  Rule-only: {len(suggestions) - len(ai_enhanced)}")
else:
    print("No suggestions found!")

print(f"\n✓ Check the AI Coach page at: http://127.0.0.1:8000/board/{board_id}/coach/")
