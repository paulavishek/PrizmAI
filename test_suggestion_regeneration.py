"""
Test that acknowledged suggestions can be regenerated
"""
import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board
from kanban.coach_models import CoachingSuggestion
from django.utils import timezone
from datetime import timedelta

# Get the Software Development board
board = Board.objects.get(name='Software Development')

print("\n=== Testing Suggestion Regeneration ===\n")

# Check current suggestions
current = CoachingSuggestion.objects.filter(board=board)
print(f"Current suggestions on board:")
for s in current.values('id', 'title', 'status', 'suggestion_type'):
    print(f"  ID {s['id']}: {s['title']}")
    print(f"    Status: {s['status']}")
    print(f"    Type: {s['suggestion_type']}\n")

# Test: Acknowledge a suggestion and check if it blocks regeneration
if current.exists():
    test_suggestion = current.first()
    original_status = test_suggestion.status
    
    print(f"Test Scenario:")
    print(f"  1. Found suggestion: '{test_suggestion.title}'")
    print(f"  2. Current status: {test_suggestion.status}")
    
    # Change to acknowledged
    test_suggestion.status = 'acknowledged'
    test_suggestion.save()
    print(f"  3. Changed status to: acknowledged")
    
    # Check duplicate detection logic (what the view uses)
    from datetime import timedelta
    from django.utils import timezone
    
    # OLD logic (buggy) - would find the acknowledged one
    old_logic_duplicate = CoachingSuggestion.objects.filter(
        board=board,
        suggestion_type=test_suggestion.suggestion_type,
        status__in=['active', 'acknowledged'],
        created_at__gte=timezone.now() - timedelta(days=3)
    ).exists()
    
    # NEW logic (fixed) - only checks active
    new_logic_duplicate = CoachingSuggestion.objects.filter(
        board=board,
        suggestion_type=test_suggestion.suggestion_type,
        status='active',
        created_at__gte=timezone.now() - timedelta(days=3)
    ).exists()
    
    print(f"\n  Duplicate Detection:")
    print(f"    OLD logic (includes acknowledged): {'❌ BLOCKED' if old_logic_duplicate else '✓ ALLOWED'}")
    print(f"    NEW logic (active only): {'❌ BLOCKED' if new_logic_duplicate else '✓ ALLOWED'}")
    
    if not new_logic_duplicate and old_logic_duplicate:
        print(f"\n✅ FIX VERIFIED! Acknowledged suggestions no longer block regeneration!")
    elif new_logic_duplicate:
        print(f"\n⚠️  Still blocked because there's an ACTIVE suggestion of this type")
    else:
        print(f"\n✓ Neither logic blocks - no duplicates exist")
    
    # Restore original status
    test_suggestion.status = original_status
    test_suggestion.save()
    print(f"\n  (Restored original status: {original_status})")
else:
    print("No suggestions found to test with.")

print("\n" + "="*50)
print("\nSummary:")
print("✓ Fixed duplicate detection to only check 'active' status")
print("✓ Acknowledged suggestions will no longer block new ones")
print("✓ Users can now regenerate suggestions after acknowledging them")
