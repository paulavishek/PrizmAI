"""Dump per-board provider summaries (no LLM calls) to a UTF-8 file."""
import io
from django.contrib.auth import get_user_model
from kanban.models import Board
from ai_assistant.utils.context_providers import get_cached_summaries

U = get_user_model()
owners = {63: 'paul.biotech10@gmail.com', 51: 'avip3310@gmail.com', 82: 'avishekpaul1310@gmail.com'}
out = io.StringIO()
for bid, em in owners.items():
    u = U.objects.get(email=em)
    b = Board.objects.get(id=bid)
    s, _ = get_cached_summaries(u, b)
    out.write(f"\n========== BOARD {bid} {b.name} (owner {u.username}) ==========\n")
    out.write(s or "(no summaries)")
    out.write("\n")

with open('scripts/_board_summaries.txt', 'w', encoding='utf-8') as f:
    f.write(out.getvalue())
print("written scripts/_board_summaries.txt")
