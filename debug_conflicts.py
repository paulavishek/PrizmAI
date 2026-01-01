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

conflicts = ConflictDetection.objects.filter(board__in=demo_boards, detected_at__isnull=False)
print(f'Total demo conflicts: {conflicts.count()}')
print(f'Active: {conflicts.filter(status="active").count()}')
print(f'Resolved: {conflicts.filter(status="resolved").count()}')

resolved = conflicts.filter(status='resolved', resolved_at__isnull=False).order_by('-resolved_at')[:10]
print(f'\nSample resolved conflicts:')

detected_by_date = {}
resolved_by_date = {}

for c in resolved:
    start_date = min(c.detected_at, c.resolved_at)
    end_date = max(c.detected_at, c.resolved_at)
    start_key = start_date.date().strftime('%Y-%m-%d')
    end_key = end_date.date().strftime('%Y-%m-%d')
    
    detected_by_date[start_key] = detected_by_date.get(start_key, 0) + 1
    resolved_by_date[end_key] = resolved_by_date.get(end_key, 0) + 1
    
    print(f'  ID {c.id}: start={start_key}, end={end_key}')

print(f'\nDetected by date: {detected_by_date}')
print(f'Resolved by date: {resolved_by_date}')
print(f'\nThirty days ago: {thirty_days_ago.date()}')
print(f'Today: {timezone.now().date()}')
