import os, django, json
os.environ['DJANGO_SETTINGS_MODULE'] = 'kanban_board.settings'
django.setup()

from kanban.models import Board, Task
from kanban.burndown_models import BurndownPrediction
from kanban.utils.whatif_engine import WhatIfEngine

board = Board.objects.get(id=44)
engine = WhatIfEngine(board)

# Check effective deadline
prediction = BurndownPrediction.objects.filter(board=board).order_by('-prediction_date').first()
effective_deadline = engine._get_effective_deadline(prediction)
print(f'Effective deadline: {effective_deadline}')

max_due = Task.objects.filter(
    column__board=board, item_type='task', due_date__isnull=False
).order_by('-due_date').values_list('due_date', flat=True).first()
print(f'Max task due date: {max_due}')

# Run simulation with screenshot params: +4 tasks, -1 team, -7 days
params = {'tasks_added': 4, 'team_size_delta': -1, 'deadline_shift_days': -7}
results = engine.simulate(params)

print('\n=== BASELINE ===')
print(json.dumps(results['baseline'], indent=2, default=str))
print('\n=== PROJECTED ===')
print(json.dumps(results['projected'], indent=2, default=str))
print('\n=== DELTAS ===')
print(json.dumps(results['deltas'], indent=2, default=str))
print('\n=== CONFLICTS ===')
print(json.dumps(results['new_conflicts'], indent=2, default=str))
print('\nFeasibility:', results['feasibility_score'])
print('\n=== WARNINGS ===')
print(json.dumps(results['warnings'], indent=2, default=str))
