"""
Regenerate all AI Coach suggestions with AI enhancement
This will delete old brief suggestions and create new detailed ones
"""
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.coach_models import CoachingSuggestion
from kanban.models import Board

# Get the Software Development board
board = Board.objects.get(name='Software Development')

print(f"\n=== Regenerating AI Coach Suggestions for '{board.name}' ===\n")

# Count before
before_count = CoachingSuggestion.objects.filter(board=board).count()
before_ai_enhanced = CoachingSuggestion.objects.filter(board=board, generation_method='hybrid').count()

print(f"Before:")
print(f"  Total suggestions: {before_count}")
print(f"  AI-enhanced (hybrid): {before_ai_enhanced}")
print(f"  Basic (rule-only): {before_count - before_ai_enhanced}")

# Delete all existing suggestions for this board
deleted = CoachingSuggestion.objects.filter(board=board).delete()
print(f"\n✓ Deleted {deleted[0]} old suggestions")

# Trigger regeneration by calling the view endpoint
# Note: You'll need to click "Refresh Suggestions" button in the UI
# OR run the management command
print(f"\nNext steps:")
print(f"  1. Go to: http://127.0.0.1:8000/board/{board.id}/coach/")
print(f"  2. Click the 'Refresh Suggestions' button")
print(f"  3. All new suggestions will be AI-enhanced with detailed format!")
print(f"\nOR run this command:")
print(f"  python manage.py generate_coach_suggestions --board-id={board.id}")
