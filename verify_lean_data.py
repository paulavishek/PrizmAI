import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Task, TaskLabel

# Get all demo boards
boards = Board.objects.filter(organization__name='Demo - Acme Corporation')

for board in boards:
    print(f"\n{'='*60}")
    print(f"Board: {board.name} (ID: {board.id})")
    print(f"{'='*60}")
    
    # Get counts exactly as the view does
    value_added_count = Task.objects.filter(
        column__board=board, 
        labels__name='Value-Added', 
        labels__category='lean'
    ).count()
    
    necessary_nva_count = Task.objects.filter(
        column__board=board, 
        labels__name='Necessary NVA', 
        labels__category='lean'
    ).count()
    
    waste_count = Task.objects.filter(
        column__board=board, 
        labels__name='Waste/Eliminate', 
        labels__category='lean'
    ).count()
    
    # Calculate value-added percentage
    total_categorized = value_added_count + necessary_nva_count + waste_count
    value_added_percentage = 0
    if total_categorized > 0:
        value_added_percentage = (value_added_count / total_categorized) * 100
    
    print(f"Value-Added: {value_added_count}")
    print(f"Necessary NVA: {necessary_nva_count}")
    print(f"Waste/Eliminate: {waste_count}")
    print(f"Total Categorized: {total_categorized}")
    print(f"Value-Added Percentage: {value_added_percentage:.1f}%")
    
    # This is the data structure passed to the template
    tasks_by_lean_category = [
        {'name': 'Value-Added', 'count': value_added_count, 'color': '#28a745'},
        {'name': 'Necessary NVA', 'count': necessary_nva_count, 'color': '#ffc107'},
        {'name': 'Waste/Eliminate', 'count': waste_count, 'color': '#dc3545'}
    ]
    
    print(f"\nChart data:")
    for item in tasks_by_lean_category:
        print(f"  {item['name']}: {item['count']} (color: {item['color']})")

print("\n\n✅ Lean Six Sigma data ready for analytics dashboard!")
