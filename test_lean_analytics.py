import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Task, TaskLabel

print("="*60)
print("TESTING LEAN SIX SIGMA DATA FOR ANALYTICS")
print("="*60)

# Get Software Development board (the one in the screenshot)
board = Board.objects.get(id=1, name='Software Development')
print(f"\nBoard: {board.name} (ID: {board.id})")

# Replicate exactly what the view does
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

# Replicate the exact data structure sent to template
tasks_by_lean_category = [
    {'name': 'Value-Added', 'count': value_added_count, 'color': '#28a745'},
    {'name': 'Necessary NVA', 'count': necessary_nva_count, 'color': '#ffc107'},
    {'name': 'Waste/Eliminate', 'count': waste_count, 'color': '#dc3545'}
]

print(f"\nCounts:")
print(f"  Value-Added: {value_added_count}")
print(f"  Necessary NVA: {necessary_nva_count}")
print(f"  Waste/Eliminate: {waste_count}")
print(f"  Total: {total_categorized}")
print(f"  Value-Added %: {value_added_percentage:.1f}%")

print(f"\nJSON data that will be in template:")
print(json.dumps(tasks_by_lean_category, indent=2))

print(f"\nArray length: {len(tasks_by_lean_category)}")
print(f"Sum of all counts: {sum(item['count'] for item in tasks_by_lean_category)}")

# Check if this would pass the JavaScript validation
if len(tasks_by_lean_category) == 0:
    print("\n❌ Would fail: Array is empty")
elif sum(item['count'] for item in tasks_by_lean_category) == 0:
    print("\n⚠️  Warning: All counts are zero, chart might appear empty")
else:
    print("\n✅ Data is valid and should render in chart")

# List some actual tasks with their lean labels
print(f"\nSample tasks with Lean labels:")
sample_tasks = Task.objects.filter(
    column__board=board,
    labels__category='lean'
).distinct()[:5]

for task in sample_tasks:
    lean_labels = task.labels.filter(category='lean')
    label_names = [l.name for l in lean_labels]
    print(f"  - {task.title[:40]}: {', '.join(label_names)}")
