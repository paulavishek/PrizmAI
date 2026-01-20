from kanban.models import Board, Task

board = Board.objects.get(id=1)
print(f'Board: {board.name}')
print(f'Num phases: {board.num_phases}')

for i in range(1, board.num_phases + 1):
    phase_name = f'Phase {i}'
    tasks = Task.objects.filter(column__board=board, phase=phase_name)
    print(f'\n{phase_name}:')
    print(f'  Total tasks: {tasks.count()}')
    
    task_starts = list(tasks.filter(item_type='task', start_date__isnull=False).values_list('start_date', flat=True))
    task_ends = list(tasks.filter(due_date__isnull=False).values_list('due_date', flat=True))
    
    if task_starts:
        print(f'  Earliest start: {min(task_starts)}')
    else:
        print(f'  No start dates')
        
    if task_ends:
        print(f'  Latest end: {max(task_ends)}')
    else:
        print(f'  No end dates')
