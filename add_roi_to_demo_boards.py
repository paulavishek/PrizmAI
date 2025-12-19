"""
Add Budget & ROI data to all demo boards
This script adds budget tracking, ROI metrics, and AI recommendations to existing demo boards
"""
import os
import django
import random
from decimal import Decimal
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from kanban.models import Board, Task
from kanban.budget_models import (
    ProjectBudget, TaskCost, TimeEntry, ProjectROI,
    BudgetRecommendation, CostPattern
)

print("=" * 80)
print(" " * 20 + "ADDING ROI DATA TO DEMO BOARDS")
print("=" * 80)

# Get all three demo boards
demo_boards = {
    'Software Project': Board.objects.filter(name='Software Project').first(),
    'Marketing Campaign': Board.objects.filter(name='Marketing Campaign').first(),
    'Bug Tracking': Board.objects.filter(name='Bug Tracking').first(),
}

# Budget configuration for each board
budget_config = {
    'Software Project': {
        'budget': Decimal('50000.00'),
        'hours': Decimal('800.0'),
        'expected_roi_multiplier': Decimal('1.5'),
    },
    'Marketing Campaign': {
        'budget': Decimal('25000.00'),
        'hours': Decimal('400.0'),
        'expected_roi_multiplier': Decimal('2.0'),
    },
    'Bug Tracking': {
        'budget': Decimal('30000.00'),
        'hours': Decimal('600.0'),
        'expected_roi_multiplier': Decimal('1.3'),
    },
}

boards_processed = 0

for board_name, board in demo_boards.items():
    if not board:
        print(f"\n⚠️  {board_name} board not found - skipping")
        continue
    
    print(f"\n{'=' * 80}")
    print(f"Processing: {board_name}")
    print(f"{'=' * 80}")
    
    config = budget_config[board_name]
    
    # 1. Create or update Project Budget
    budget, created = ProjectBudget.objects.get_or_create(
        board=board,
        defaults={
            'allocated_budget': config['budget'],
            'currency': 'USD',
            'allocated_hours': config['hours'],
            'warning_threshold': 80,
            'critical_threshold': 95,
            'ai_optimization_enabled': True,
            'created_by': User.objects.first(),
        }
    )
    
    if created:
        print(f"✓ Created budget: ${budget.allocated_budget}")
    else:
        print(f"✓ Budget already exists: ${budget.allocated_budget}")
    
    # 2. Create Task Costs and Time Entries
    tasks = Task.objects.filter(column__board=board)[:15]
    users = list(User.objects.all()[:5])
    
    task_costs_created = 0
    time_entries_created = 0
    
    for i, task in enumerate(tasks):
        # Create TaskCost
        estimated_cost = Decimal(random.uniform(100, 2000))
        estimated_hours = Decimal(random.uniform(2, 40))
        
        # Make some tasks over budget
        is_over_budget = i % 4 == 0
        variance_factor = Decimal(random.uniform(1.1, 1.4)) if is_over_budget else Decimal(random.uniform(0.7, 1.0))
        
        actual_cost = estimated_cost * variance_factor
        hourly_rate = Decimal(random.choice(['50.00', '75.00', '100.00', '125.00']))
        resource_cost = Decimal(random.uniform(0, 500)) if i % 3 == 0 else Decimal('0.00')
        
        task_cost, tc_created = TaskCost.objects.get_or_create(
            task=task,
            defaults={
                'estimated_cost': estimated_cost,
                'estimated_hours': estimated_hours,
                'actual_cost': actual_cost,
                'hourly_rate': hourly_rate,
                'resource_cost': resource_cost,
            }
        )
        
        if tc_created:
            task_costs_created += 1
        
        # Create time entries
        num_entries = random.randint(2, 5)
        for j in range(num_entries):
            user = random.choice(users)
            hours_spent = Decimal(random.uniform(1, 8))
            work_date = timezone.now().date() - timedelta(days=random.randint(1, 30))
            
            descriptions = [
                'Implemented core functionality',
                'Fixed bugs and edge cases',
                'Code review and testing',
                'Updated documentation',
                'Refactored for performance',
                'Integration testing',
                'UI/UX improvements',
                'Database optimization',
                'Security enhancements',
                'API development',
            ]
            
            # Check if time entry already exists
            if not TimeEntry.objects.filter(task=task, user=user, work_date=work_date).exists():
                TimeEntry.objects.create(
                    task=task,
                    user=user,
                    hours_spent=hours_spent,
                    work_date=work_date,
                    description=random.choice(descriptions)
                )
                time_entries_created += 1
    
    print(f"✓ Created {task_costs_created} task costs")
    print(f"✓ Created {time_entries_created} time entries")
    
    # 3. Create ROI Snapshot
    # Use progress instead of column name for completed tasks
    completed_tasks = Task.objects.filter(
        column__board=board,
        progress=100
    ).count()
    
    total_tasks = Task.objects.filter(column__board=board).count()
    
    # Calculate total cost
    total_cost = sum([tc.get_total_actual_cost() for tc in TaskCost.objects.filter(task__column__board=board)])
    
    # Create ROI snapshot
    expected_value = budget.allocated_budget * config['expected_roi_multiplier']
    realized_value = expected_value * Decimal(random.uniform(0.8, 1.2))
    
    roi_percentage = None
    if total_cost > 0:
        roi_percentage = ((realized_value - total_cost) / total_cost) * 100
    
    # Delete old snapshots for this board to avoid duplicates
    old_snapshots = ProjectROI.objects.filter(board=board)
    if old_snapshots.exists():
        count = old_snapshots.count()
        old_snapshots.delete()
        print(f"✓ Removed {count} old ROI snapshots")
    
    roi_snapshot = ProjectROI.objects.create(
        board=board,
        expected_value=expected_value,
        realized_value=realized_value,
        total_cost=total_cost,
        roi_percentage=roi_percentage,
        completed_tasks=completed_tasks,
        total_tasks=total_tasks,
        snapshot_date=timezone.now(),
        created_by=User.objects.first(),
        ai_insights={
            'health': 'Good' if roi_percentage and roi_percentage > 20 else 'Fair',
            'risks': [
                'Resource allocation needs optimization',
                'Some tasks showing cost overruns',
                'Timeline pressure may increase costs'
            ],
            'opportunities': [
                f'Strong completion rate: {(completed_tasks/total_tasks*100):.1f}%' if total_tasks > 0 else 'Project starting up',
                'Good ROI projection' if roi_percentage and roi_percentage > 20 else 'ROI improvement possible',
                'Team productivity trending upward'
            ]
        },
        ai_risk_score=random.randint(25, 45)
    )
    
    if roi_percentage:
        print(f"✓ Created ROI snapshot: {roi_percentage:.1f}% ROI")
    else:
        print(f"✓ Created ROI snapshot")
    
    # 4. Create AI Recommendations
    recommendations_data = [
        {
            'type': 'resource_optimization',
            'title': 'Optimize Senior Developer Allocation',
            'description': 'Reallocate senior developer time to critical path tasks. Current allocation shows senior developers spending 30% of time on low-priority tasks.',
            'savings': Decimal('2500.00'),
            'confidence': 85,
            'priority': 'high',
            'reasoning': 'Analysis of time entries shows inefficient resource allocation. Senior developers are spending time on tasks that could be handled by junior team members.',
        },
        {
            'type': 'timeline_change',
            'title': 'Extend Sprint by 3 Days to Reduce Overtime',
            'description': 'Current burn rate suggests team is working overtime. Extending sprint by 3 days would reduce overtime costs and improve quality.',
            'savings': Decimal('1800.00'),
            'confidence': 72,
            'priority': 'medium',
            'reasoning': 'Time entry patterns show consistent late-night work. Extending timeline would reduce overtime costs while maintaining quality.',
        },
        {
            'type': 'scope_cut',
            'title': 'Defer Low-Priority Feature to Next Release',
            'description': 'Feature "Advanced Reporting" has high cost variance and low business impact. Consider moving to next release.',
            'savings': Decimal('3200.00'),
            'confidence': 78,
            'priority': 'medium',
            'reasoning': 'Cost-benefit analysis shows this feature consuming 15% of budget with minimal immediate value. Deferring would ensure on-budget completion.',
        },
        {
            'type': 'efficiency_improvement',
            'title': 'Implement Code Review Automation',
            'description': 'Code reviews are taking 20% longer than industry average. Implementing automated checks could save significant time.',
            'savings': Decimal('1500.00'),
            'confidence': 65,
            'priority': 'low',
            'reasoning': 'Time tracking shows code reviews averaging 3.2 hours per task vs industry standard of 2.5 hours. Automation could improve efficiency.',
        },
    ]
    
    # Delete old recommendations for this board
    old_recs = BudgetRecommendation.objects.filter(board=board)
    if old_recs.exists():
        count = old_recs.count()
        old_recs.delete()
        print(f"✓ Removed {count} old recommendations")
    
    for rec_data in recommendations_data:
        BudgetRecommendation.objects.create(
            board=board,
            recommendation_type=rec_data['type'],
            title=rec_data['title'],
            description=rec_data['description'],
            estimated_savings=rec_data.get('savings'),
            confidence_score=rec_data['confidence'],
            priority=rec_data['priority'],
            ai_reasoning=rec_data['reasoning'],
            status='pending',
            based_on_patterns={
                'time_entries_analyzed': time_entries_created,
                'tasks_analyzed': task_costs_created,
                'pattern_confidence': rec_data['confidence']
            }
        )
    
    print(f"✓ Created {len(recommendations_data)} AI recommendations")
    
    # 5. Create Cost Patterns
    patterns_data = [
        {
            'name': 'Backend Tasks Consistently Over Budget',
            'type': 'task_overrun',
            'confidence': Decimal('82.5'),
            'occurrences': 5,
            'data': {
                'task_category': 'backend',
                'average_overrun': '25%',
                'frequency': 'high',
                'root_cause': 'Underestimation of complexity'
            }
        },
        {
            'name': 'Friday Afternoon Productivity Dip',
            'type': 'time_pattern',
            'confidence': Decimal('71.0'),
            'occurrences': 8,
            'data': {
                'time_period': 'Friday 2pm-5pm',
                'productivity_drop': '35%',
                'recommendation': 'Schedule less complex tasks for Friday afternoons'
            }
        },
        {
            'name': 'UI/UX Tasks Exceeding Time Estimates',
            'type': 'task_overrun',
            'confidence': Decimal('76.3'),
            'occurrences': 6,
            'data': {
                'task_category': 'ui_ux',
                'time_overrun': '40%',
                'cost_impact': 'medium',
                'pattern': 'Design iteration cycles not accounted for in estimates'
            }
        }
    ]
    
    # Delete old patterns for this board
    old_patterns = CostPattern.objects.filter(board=board)
    if old_patterns.exists():
        count = old_patterns.count()
        old_patterns.delete()
        print(f"✓ Removed {count} old cost patterns")
    
    for pattern_data in patterns_data:
        CostPattern.objects.create(
            board=board,
            pattern_name=pattern_data['name'],
            pattern_type=pattern_data['type'],
            pattern_data=pattern_data['data'],
            confidence=pattern_data['confidence'],
            occurrence_count=pattern_data['occurrences'],
            last_occurred=timezone.now() - timedelta(days=random.randint(1, 7))
        )
    
    print(f"✓ Created {len(patterns_data)} cost patterns")
    
    boards_processed += 1

print("\n" + "=" * 80)
print(f"✅ Successfully added ROI data to {boards_processed} demo boards!")
print("=" * 80)
print("\nWhat was added:")
print("  • Project budgets with realistic allocations")
print("  • Task costs and time tracking entries")
print("  • ROI snapshots with projections")
print("  • AI-powered budget recommendations")
print("  • Cost pattern analysis data")
print("\nNext steps:")
print("  1. Navigate to any demo board")
print("  2. Click on the 'Budget' tab")
print("  3. Explore budget tracking, ROI metrics, and AI recommendations")
print("  4. Click 'ROI' button to see detailed ROI dashboard")
print("=" * 80)
