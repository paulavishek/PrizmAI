import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()
from kanban.models import Board, DemoSandbox, Task
from django.contrib.auth.models import User

# For testuser3 (uid=50), restore the 3 extra assigned tasks back to demo users
user = User.objects.get(pk=50)
sb = user.demo_sandbox
board = Board.objects.filter(owner=user, is_sandbox_copy=True).first()

# Find tasks assigned to user on this board that are NOT in the reassignment mapping
mapping = sb.reassigned_tasks or {}
mapped_ids = set(int(tid) for tid in mapping.keys())

extra_tasks = Task.objects.filter(
    column__board=board,
    assigned_to=user,
).exclude(id__in=mapped_ids)

for t in extra_tasks:
    # Check the template task to find original assignee
    template_board = Board.objects.get(id=1)
    template_task = Task.objects.filter(
        column__board=template_board,
        title=t.title,
    ).first()
    if template_task and template_task.assigned_to:
        print(f'Restoring task {t.id} "{t.title}" -> {template_task.assigned_to.username}')
        t.assigned_to = template_task.assigned_to
        t.save(update_fields=['assigned_to'])
    else:
        print(f'No match for task {t.id} "{t.title}"')

assigned_after = Task.objects.filter(column__board=board, assigned_to=user).count()
print(f'testuser3 assigned count after fix: {assigned_after}')
