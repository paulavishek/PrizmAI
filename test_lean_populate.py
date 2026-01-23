"""
Test the updated populate_demo_data command to verify Lean Six Sigma labels are created
"""
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.core.management import call_command
from kanban.models import Board, Task, TaskLabel
from io import StringIO

print("\n" + "="*70)
print("TESTING LEAN SIX SIGMA LABEL POPULATION")
print("="*70 + "\n")

print("Running: python manage.py populate_demo_data --reset")
print("-" * 70)

# Capture command output
out = StringIO()
try:
    call_command('populate_demo_data', '--reset', stdout=out, stderr=out)
    print(out.getvalue())
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)

print("\n" + "="*70)
print("VERIFICATION - Checking Lean Six Sigma Labels")
print("="*70 + "\n")

# Get demo boards
boards = Board.objects.filter(
    organization__name='Demo - Acme Corporation',
    is_official_demo_board=True
)

all_good = True

for board in boards:
    print(f"\nBoard: {board.name}")
    print("-" * 70)
    
    # Check labels exist
    main_labels = TaskLabel.objects.filter(
        board=board,
        category='lean',
        name__in=['Value-Added', 'Necessary NVA', 'Waste/Eliminate']
    )
    
    print(f"Main Lean Labels Created: {main_labels.count()}/3")
    for label in main_labels:
        print(f"  ✓ {label.name} ({label.color})")
    
    # Check label assignments
    total_tasks = Task.objects.filter(column__board=board).count()
    
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
    
    total_categorized = value_added_count + necessary_nva_count + waste_count
    
    print(f"\nLabel Assignments:")
    print(f"  Total Tasks: {total_tasks}")
    print(f"  Value-Added: {value_added_count}")
    print(f"  Necessary NVA: {necessary_nva_count}")
    print(f"  Waste/Eliminate: {waste_count}")
    print(f"  Total Categorized: {total_categorized}")
    
    if total_categorized == total_tasks:
        print(f"  ✅ SUCCESS: All {total_tasks} tasks have Lean categories!")
    else:
        print(f"  ❌ FAILED: Only {total_categorized}/{total_tasks} tasks categorized")
        all_good = False

print("\n" + "="*70)
if all_good:
    print("✅ SUCCESS: Lean Six Sigma labels are properly populated!")
    print("   The analytics chart will now show data for all demo boards.")
    print("   This applies to:")
    print("   1. Manual populate_demo_data command")
    print("   2. Manual reset button")
    print("   3. 48-hour auto-reset")
else:
    print("❌ FAILED: Some boards are missing Lean Six Sigma labels")
print("="*70 + "\n")
