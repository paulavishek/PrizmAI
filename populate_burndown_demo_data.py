"""
Populate burndown chart data for demo boards
This script creates historical task completion data to generate a proper burndown chart
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
import random

from kanban.models import Board, Task
from kanban.burndown_models import TeamVelocitySnapshot, BurndownPrediction
from kanban.utils.burndown_predictor import BurndownPredictor


def populate_task_completion_dates(board, weeks_back=6):
    """
    Populate completed_at dates for completed tasks to create historical data
    This spreads completed tasks across the past weeks to simulate realistic progress
    """
    print(f"\nProcessing board: {board.name}")
    
    # Get completed tasks
    completed_tasks = list(Task.objects.filter(column__board=board, progress=100))
    
    if not completed_tasks:
        print("  No completed tasks found. Marking some tasks as complete...")
        # Get some in-progress or todo tasks and mark them complete
        tasks_to_complete = list(Task.objects.filter(column__board=board, progress__lt=100)[:15])
        for task in tasks_to_complete:
            task.progress = 100
            completed_tasks.append(task)
    
    print(f"  Found {len(completed_tasks)} completed tasks")
    
    # Distribute completion dates across past weeks
    now = timezone.now()
    tasks_per_week = len(completed_tasks) // weeks_back if weeks_back > 0 else len(completed_tasks)
    
    task_index = 0
    for week in range(weeks_back, 0, -1):
        # Calculate date range for this week
        week_end = now - timedelta(weeks=week-1)
        week_start = week_end - timedelta(days=7)
        
        # Determine how many tasks to complete this week (with some variation)
        base_count = tasks_per_week
        variation = random.randint(-2, 3)
        tasks_this_week = max(1, base_count + variation)
        
        # Make sure we don't exceed available tasks
        tasks_this_week = min(tasks_this_week, len(completed_tasks) - task_index)
        
        print(f"  Week {weeks_back - week + 1} ({week_start.date()} to {week_end.date()}): {tasks_this_week} tasks")
        
        for i in range(tasks_this_week):
            if task_index >= len(completed_tasks):
                break
                
            task = completed_tasks[task_index]
            
            # Random completion time within the week
            days_offset = random.randint(0, 6)
            hours_offset = random.randint(0, 23)
            minutes_offset = random.randint(0, 59)
            
            completion_date = week_start + timedelta(
                days=days_offset,
                hours=hours_offset,
                minutes=minutes_offset
            )
            
            task.completed_at = completion_date
            task.progress = 100
            task.save()
            
            task_index += 1
    
    # Mark remaining tasks as completed recently (current week)
    current_week_start = now - timedelta(days=7)
    while task_index < len(completed_tasks):
        task = completed_tasks[task_index]
        days_offset = random.randint(0, 6)
        hours_offset = random.randint(0, 23)
        
        completion_date = current_week_start + timedelta(
            days=days_offset,
            hours=hours_offset
        )
        
        task.completed_at = completion_date
        task.progress = 100
        task.save()
        task_index += 1
    
    print(f"  ✓ Updated completion dates for {task_index} tasks")


def regenerate_velocity_snapshots(board):
    """Delete old snapshots and regenerate based on actual completed tasks"""
    print(f"\n  Regenerating velocity snapshots for {board.name}...")
    
    # Delete old snapshots
    old_count = TeamVelocitySnapshot.objects.filter(board=board).count()
    TeamVelocitySnapshot.objects.filter(board=board).delete()
    print(f"    Deleted {old_count} old snapshots")
    
    # Create predictor to generate new snapshots
    predictor = BurndownPredictor()
    predictor._ensure_velocity_snapshots(board)
    
    new_count = TeamVelocitySnapshot.objects.filter(board=board).count()
    print(f"    Created {new_count} new snapshots")
    
    # Display the snapshots
    snapshots = TeamVelocitySnapshot.objects.filter(board=board).order_by('period_end')
    for snap in snapshots:
        print(f"      {snap.period_start} to {snap.period_end}: {snap.tasks_completed} tasks, {snap.story_points_completed} points")


def regenerate_burndown_prediction(board):
    """Generate new burndown prediction with updated data"""
    print(f"\n  Generating burndown prediction for {board.name}...")
    
    predictor = BurndownPredictor()
    result = predictor.generate_burndown_prediction(board)
    
    prediction = result.get('prediction')
    if prediction:
        print(f"    ✓ Prediction generated successfully")
        print(f"      Total: {prediction.total_tasks}, Completed: {prediction.completed_tasks}, Remaining: {prediction.remaining_tasks}")
        print(f"      Predicted completion: {prediction.predicted_completion_date}")
        print(f"      Confidence: {float(prediction.prediction_confidence_score) * 100:.1f}%, Risk: {prediction.risk_level}")
        
        curve = prediction.burndown_curve_data
        print(f"      Chart data: {len(curve.get('historical', []))} historical, {len(curve.get('projected', []))} projected points")
    else:
        print(f"    ✗ Failed to generate prediction")


def main():
    """Main execution"""
    print("="*70)
    print("Populating Burndown Chart Demo Data")
    print("="*70)
    
    # Process all boards
    boards = Board.objects.all()
    
    for board in boards:
        print(f"\n{'='*70}")
        print(f"Board: {board.name} (ID: {board.id})")
        print('='*70)
        
        # Step 1: Populate historical completion dates
        populate_task_completion_dates(board, weeks_back=6)
        
        # Step 2: Regenerate velocity snapshots
        regenerate_velocity_snapshots(board)
        
        # Step 3: Generate burndown prediction
        regenerate_burndown_prediction(board)
    
    print(f"\n{'='*70}")
    print("✓ All boards processed successfully!")
    print("="*70)
    print("\nYou can now view the burndown charts for each board:")
    for board in boards:
        print(f"  - {board.name}: /board/{board.id}/burndown/")


if __name__ == '__main__':
    main()
