"""Independent DB ground-truth for verifying Spectra's answers. Writes UTF-8."""
import io
from django.contrib.auth import get_user_model
from kanban.models import Board, Task
from django.utils import timezone

U = get_user_model()
out = io.StringIO()
b = Board.objects.get(id=63)
all_items = Task.objects.filter(column__board=b)
tasks = all_items.filter(item_type='task')
now = timezone.now()

out.write("# Ground Truth — Board 63 (Core AI Protocol Development)\n\n")
out.write(f"- Board name: {b.name}\n")
out.write(f"- Created: {getattr(b, 'created_at', 'n/a')}\n")
out.write(f"- Total items (task+milestone rows): {all_items.count()}\n")
out.write(f"- Total tasks (item_type=task): {tasks.count()}\n")
out.write(f"- Milestones (item_type=milestone): {all_items.exclude(item_type='task').count()}\n")

# columns in order
cols = b.columns.all().order_by('position') if hasattr(b, 'columns') else []
out.write(f"- Columns (ordered): {[c.name for c in cols]}\n")

# per-column counts
from collections import Counter
col_counts = Counter(t.column.name if t.column else '(none)' for t in tasks)
out.write(f"- Tasks per column: {dict(col_counts)}\n")

# priorities
pri = Counter((t.priority or '').lower() for t in tasks)
out.write(f"- Priority distribution: {dict(pri)}\n")
out.write(f"- HIGH priority task titles: {[t.title for t in tasks if (t.priority or '').lower()=='high']}\n")

# overdue (mirror dashboard: due_date < now and not done)
done_cols = {'done', 'closed', 'complete', 'completed'}
overdue = [t for t in tasks if t.due_date and t.due_date < now and (t.column.name.lower() if t.column else '') not in done_cols]
out.write(f"- Overdue tasks (due<now, not Done): {len(overdue)} -> {[t.title for t in overdue]}\n")

# done count
done = [t for t in tasks if (t.column.name.lower() if t.column else '') in done_cols]
out.write(f"- Done column tasks: {len(done)} -> {[t.title for t in done]}\n")

# assignments to testuser1
u1 = U.objects.get(email='paul.biotech10@gmail.com')
a1 = [t.title for t in tasks if t.assigned_to_id == u1.id]
out.write(f"- Tasks assigned to testuser1: {len(a1)} -> {a1}\n")

# members
try:
    mem = b.memberships.all() if hasattr(b, 'memberships') else b.boardmembership_set.all()
    out.write(f"- Memberships: {[(m.user.username, m.role) for m in mem]}\n")
except Exception as e:
    out.write(f"- Memberships: ERR {e}\n")

# labels
try:
    from collections import Counter as C2
    lab = C2()
    for t in tasks:
        for l in t.labels.all():
            lab[l.name] += 1
    out.write(f"- Label usage: {dict(lab)}\n")
except Exception as e:
    out.write(f"- Labels: ERR {e}\n")

with open('scripts/_ground_truth.txt', 'w', encoding='utf-8') as f:
    f.write(out.getvalue())
print("written scripts/_ground_truth.txt")
