import os
import django
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Task, TaskLabel

# Get all demo boards
boards = Board.objects.filter(organization__name='Demo - Acme Corporation')

for board in boards:
    print(f"\n\nProcessing Board: {board.name} (ID: {board.id})")
    
    # Get the three main lean labels for this board
    value_added = TaskLabel.objects.filter(
        board=board, 
        name='Value-Added', 
        category='lean'
    ).first()
    
    necessary_nva = TaskLabel.objects.filter(
        board=board, 
        name='Necessary NVA', 
        category='lean'
    ).first()
    
    waste = TaskLabel.objects.filter(
        board=board, 
        name='Waste/Eliminate', 
        category='lean'
    ).first()
    
    if not all([value_added, necessary_nva, waste]):
        print(f"  WARNING: Not all lean labels found for {board.name}")
        continue
    
    # Get all tasks for this board
    tasks = Task.objects.filter(column__board=board)
    
    # Get tasks that don't have any of the three main lean labels
    tasks_without_lean = []
    for task in tasks:
        task_labels = task.labels.filter(
            name__in=['Value-Added', 'Necessary NVA', 'Waste/Eliminate']
        )
        if not task_labels.exists():
            tasks_without_lean.append(task)
    
    print(f"  Tasks without lean labels: {len(tasks_without_lean)}")
    
    # Assign lean labels to tasks without them
    # Distribution: 50% Value-Added, 30% Necessary NVA, 20% Waste
    for task in tasks_without_lean:
        rand = random.random()
        if rand < 0.5:
            task.labels.add(value_added)
            label_name = "Value-Added"
        elif rand < 0.8:
            task.labels.add(necessary_nva)
            label_name = "Necessary NVA"
        else:
            task.labels.add(waste)
            label_name = "Waste/Eliminate"
        
        print(f"    Added '{label_name}' to task: {task.title[:50]}")
    
    # Verify the result
    value_count = Task.objects.filter(
        column__board=board, 
        labels__name='Value-Added', 
        labels__category='lean'
    ).count()
    
    nva_count = Task.objects.filter(
        column__board=board, 
        labels__name='Necessary NVA', 
        labels__category='lean'
    ).count()
    
    waste_count = Task.objects.filter(
        column__board=board, 
        labels__name='Waste/Eliminate', 
        labels__category='lean'
    ).count()
    
    print(f"  Final counts - Value-Added: {value_count}, Necessary NVA: {nva_count}, Waste: {waste_count}")
    print(f"  Total categorized: {value_count + nva_count + waste_count}")

print("\n\n✅ Lean Six Sigma labels populated successfully!")
