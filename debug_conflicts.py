import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from kanban.conflict_models import ConflictDetection
from kanban.models import Board, Organization

thirty_days_ago = timezone.now() - timedelta(days=30)

# Check demo boards
demo_orgs = Organization.objects.filter(name__in=['Demo - Acme Corporation'])
demo_boards = Board.objects.filter(organization__in=demo_orgs)
print(f'Demo boards: {demo_boards.count()}')

conflicts = ConflictDetection.objects.filter(board__in=demo_boards, detected_at__isnull=False)
print(f'\nTotal demo conflicts: {conflicts.count()}')
print(f'Active: {conflicts.filter(status="active").count()}')
print(f'Resolved: {conflicts.filter(status="resolved").count()}')

resolved = conflicts.filter(status='resolved', resolved_at__isnull=False).order_by('-resolved_at')[:10]
print(f'\nSample resolved conflicts:')
backward_count = 0
for c in resolved:
    backward = c.resolved_at < c.detected_at
    if backward:
        backward_count += 1
    print(f'  ID {c.id}: detected={c.detected_at.date()}, resolved={c.resolved_at.date()}, backward={backward}')

print(f'\nTotal with backward dates: {backward_count}/{resolved.count()}')
