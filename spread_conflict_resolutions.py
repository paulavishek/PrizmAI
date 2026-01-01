import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from kanban.conflict_models import ConflictDetection
from kanban.models import Board, Organization
import random

# Get demo boards
demo_orgs = Organization.objects.filter(name__in=['Demo - Acme Corporation'])
demo_boards = Board.objects.filter(organization__in=demo_orgs)

# Get all resolved conflicts
resolved_conflicts = ConflictDetection.objects.filter(
    board__in=demo_boards,
    status='resolved',
    resolved_at__isnull=False
).order_by('resolved_at')

print(f'Found {resolved_conflicts.count()} resolved conflicts')

# Spread resolutions across December 2025
for conflict in resolved_conflicts:
    # Get the start date (min of detected_at and resolved_at)
    start_date = min(conflict.detected_at, conflict.resolved_at)
    
    # Set resolution 1-7 days after start date
    days_to_resolve = random.randint(1, 7)
    new_resolved_at = start_date + timedelta(days=days_to_resolve, hours=random.randint(1, 23))
    
    # Update the resolved_at to be the max (later) date
    conflict.detected_at = start_date
    conflict.resolved_at = new_resolved_at
    conflict.save()
    
    print(f'Conflict {conflict.id}: detected={start_date.date()}, resolved={new_resolved_at.date()}')

print(f'\nSuccessfully updated {resolved_conflicts.count()} conflicts!')
