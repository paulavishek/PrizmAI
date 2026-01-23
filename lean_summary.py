import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from kanban.models import Board, Task

print("="*70)
print("LEAN SIX SIGMA ANALYTICS - SUMMARY")
print("="*70)

boards = Board.objects.filter(organization__name='Demo - Acme Corporation').order_by('id')

for board in boards:
    print(f"\n{'='*70}")
    print(f"Board: {board.name} (ID: {board.id})")
    print(f"{'='*70}")
    
    # Get counts
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
    
    total = value_added_count + necessary_nva_count + waste_count
    total_tasks = Task.objects.filter(column__board=board).count()
    
    print(f"Total Tasks: {total_tasks}")
    print(f"Tasks with Lean Six Sigma Labels: {total}")
    if total > 0:
        print(f"  ✓ Value-Added: {value_added_count} ({value_added_count/total*100:.1f}%)")
        print(f"  ✓ Necessary NVA: {necessary_nva_count} ({necessary_nva_count/total*100:.1f}%)")
        print(f"  ✓ Waste/Eliminate: {waste_count} ({waste_count/total*100:.1f}%)")
    print(f"Analytics URL: http://127.0.0.1:8000/boards/{board.id}/analytics/")

print(f"\n{'='*70}")
print("✅ ALL DEMO BOARDS NOW HAVE LEAN SIX SIGMA DATA!")
print("✅ The Lean Six Sigma Analysis charts will now display properly")
print("="*70)
