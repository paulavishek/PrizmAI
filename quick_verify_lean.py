"""
Quick verification that Lean Six Sigma data is ready for all demo boards
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Task

print("\n" + "="*70)
print("QUICK VERIFICATION - LEAN SIX SIGMA DATA")
print("="*70 + "\n")

demo_boards = Board.objects.filter(organization__name='Demo - Acme Corporation')
all_good = True

for board in demo_boards:
    # Count lean-labeled tasks
    lean_tasks = Task.objects.filter(
        column__board=board,
        labels__category='lean'
    ).distinct().count()
    
    total_tasks = Task.objects.filter(column__board=board).count()
    
    status = "✅" if lean_tasks == total_tasks else "❌"
    all_good = all_good and (lean_tasks == total_tasks)
    
    print(f"{status} {board.name}: {lean_tasks}/{total_tasks} tasks have Lean labels")

print("\n" + "="*70)
if all_good:
    print("✅ SUCCESS! All demo boards have complete Lean Six Sigma data.")
    print("   The analytics charts will now display properly.")
else:
    print("⚠️  WARNING: Some boards are missing Lean Six Sigma labels.")
print("="*70 + "\n")
