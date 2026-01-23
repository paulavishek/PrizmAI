"""
Populate historical ROI snapshots for demo boards to show meaningful trends
"""
import os
import django
from decimal import Decimal
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from kanban.models import Board
from kanban.budget_models import ProjectROI, ProjectBudget, TaskCost
from django.contrib.auth import get_user_model

User = get_user_model()

def populate_roi_snapshots():
    """Create historical ROI snapshots for each demo board"""
    
    # Get demo boards
    demo_org_names = ['Demo - Acme Corporation']
    boards = Board.objects.filter(organization__name__in=demo_org_names)
    
    if not boards.exists():
        print("❌ No demo boards found")
        return
    
    # Get admin user for created_by field
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        admin_user = User.objects.first()
    
    now = timezone.now()
    
    for board in boards:
        print(f"\n📊 Processing board: {board.name}")
        
        # Check if budget exists
        try:
            budget = ProjectBudget.objects.get(board=board)
        except ProjectBudget.DoesNotExist:
            print(f"   ⚠️  No budget found, skipping")
            continue
        
        # Calculate current costs
        task_costs = TaskCost.objects.filter(task__column__board=board)
        total_cost = sum([tc.get_total_actual_cost() for tc in task_costs]) if task_costs else Decimal('0.00')
        
        # Count tasks
        from kanban.models import Task
        total_tasks = Task.objects.filter(column__board=board).count()
        completed_tasks = Task.objects.filter(column__board=board, progress=100).count()
        
        # Delete existing snapshots to recreate
        deleted_count = ProjectROI.objects.filter(board=board).delete()[0]
        print(f"   🗑️  Deleted {deleted_count} old ROI snapshots")
        
        # Create 10 historical snapshots over the past 10 months
        snapshots_created = 0
        
        # Set initial values based on board type for realistic data
        if "Software Development" in board.name:
            base_expected = budget.allocated_budget * Decimal('2.0')  # 100% ROI expected
            base_realized_ratio = Decimal('0.4')  # Starting at 40% realization
        elif "Marketing" in board.name:
            base_expected = budget.allocated_budget * Decimal('1.8')  # 80% ROI expected
            base_realized_ratio = Decimal('0.35')  # Starting at 35% realization
        else:  # Bug Tracking
            base_expected = budget.allocated_budget * Decimal('1.5')  # 50% ROI expected
            base_realized_ratio = Decimal('0.45')  # Starting at 45% realization
        
        for i in range(10):
            snapshot_date = now - timedelta(days=30 * (9 - i))  # Go back 9 months, then forward
            
            # Calculate progressive improvement
            progress_factor = Decimal(str(i / 9))  # 0 to 1 over time
            
            # Realized value improves over time (from base to 80% of expected)
            realized_value = base_expected * (base_realized_ratio + (Decimal('0.4') * progress_factor))
            
            # Cost also increases progressively
            snapshot_cost = total_cost * (Decimal('0.3') + (Decimal('0.7') * progress_factor))
            
            # Calculate ROI percentage
            if snapshot_cost > 0:
                roi_percentage = float(((realized_value - snapshot_cost) / snapshot_cost) * 100)
            else:
                roi_percentage = 0
            
            # Create snapshot
            snapshot = ProjectROI.objects.create(
                board=board,
                snapshot_date=snapshot_date,
                expected_value=base_expected,
                realized_value=realized_value,
                roi_percentage=roi_percentage,
                total_cost=snapshot_cost,
                total_tasks=total_tasks,
                completed_tasks=int(completed_tasks * progress_factor),  # Progressive completion
                created_by=admin_user
            )
            snapshots_created += 1
        
        print(f"   ✅ Created {snapshots_created} ROI snapshots")
        
        # Show latest snapshot
        latest = ProjectROI.objects.filter(board=board).order_by('-snapshot_date').first()
        if latest:
            print(f"   📈 Latest ROI: {latest.roi_percentage:.2f}%")
            print(f"   💰 Realized Value: ${latest.realized_value:,.2f}")
            print(f"   💵 Total Cost: ${latest.total_cost:,.2f}")
    
    print("\n✅ ROI snapshot population complete!")

if __name__ == '__main__':
    populate_roi_snapshots()
