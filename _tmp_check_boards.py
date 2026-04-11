"""Check testuser1's boards."""
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()
from kanban.models import Board
from django.contrib.auth import get_user_model
u = get_user_model().objects.get(username='testuser1')
boards = Board.objects.filter(memberships__user=u, is_archived=False)
print(f"Total boards with membership: {boards.count()}")
for b in boards:
    ws = b.workspace
    ws_demo = getattr(ws, 'is_demo', 'N/A') if ws else 'no_ws'
    print(f"  {b.name} | sandbox={b.is_sandbox_copy} | official={b.is_official_demo_board} | ws_demo={ws_demo} | session={b.created_by_session}")
