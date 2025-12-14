import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.db import transaction
from kanban.models import Board, Task

# Get the duplicate boards
duplicate_ids = [16, 17]

print("Attempting to delete duplicate boards...")
for board_id in duplicate_ids:
    try:
        board = Board.objects.get(id=board_id)
        print(f"\nProcessing: {board.name} (ID: {board_id})")
        
        # Try to delete with transaction
        with transaction.atomic():
            board.delete()
            print(f"  ✓ Successfully deleted {board.name}")
    except Board.DoesNotExist:
        print(f"  Board ID {board_id} not found (may already be deleted)")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        print(f"  Attempting manual cleanup...")
        
        try:
            # Get the board again
            board = Board.objects.get(id=board_id)
            
            # Delete related objects manually
            print(f"    - Deleting columns and tasks...")
            for column in board.columns.all():
                column.delete()
            
            print(f"    - Deleting labels...")
            board.labels.all().delete()
            
            print(f"    - Deleting milestones...")
            board.milestones.all().delete()
            
            print(f"    - Deleting chat rooms...")
            board.chat_rooms.all().delete()
            
            print(f"    - Attempting to delete board again...")
            board.delete()
            print(f"  ✓ Successfully deleted {board.name} after manual cleanup")
            
        except Exception as e2:
            print(f"  ✗ Manual cleanup also failed: {e2}")

print("\n\nFinal board list:")
for board in Board.objects.all():
    org_name = board.organization.name if board.organization else "No Org"
    task_count = Task.objects.filter(column__board=board).count()
    print(f"{board.id}: {board.name} ({org_name}) - {task_count} tasks")
