"""
Budget & ROI Utility Functions
Provides calculation, analysis, and reporting utilities for budget tracking
"""
from decimal import Decimal
from datetime import datetime, timedelta
from django.db.models import Sum, Avg, Count, Q, F
from django.utils import timezone
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class BudgetAnalyzer:
    """
    Utility class for budget analysis and calculations
    """
    
    @staticmethod
    def calculate_project_metrics(board) -> Dict:
        """
        Calculate comprehensive project budget metrics
        
        Args:
            board: Board instance
            
        Returns:
            Dictionary with all budget metrics
        """
        from kanban.budget_models import ProjectBudget, TaskCost, TimeEntry
        
        try:
            budget = ProjectBudget.objects.get(board=board)
        except ProjectBudget.DoesNotExist:
            return {
                'error': 'No budget configured for this project',
                'has_budget': False
            }
        
        # Get all tasks for the board
        from kanban.models import Task
        tasks = Task.objects.filter(column__board=board)
        
        # Calculate spent amounts
        spent_amount = budget.get_spent_amount()
        spent_hours = budget.get_spent_hours()
        remaining_budget = budget.get_remaining_budget()
        
        # Calculate utilization
        budget_utilization = budget.get_budget_utilization_percent()
        time_utilization = budget.get_time_utilization_percent()
        
        # Task cost analysis
        task_costs = TaskCost.objects.filter(task__column__board=board)
        total_estimated_cost = task_costs.aggregate(
            total=Sum('estimated_cost')
        )['total'] or Decimal('0.00')
        
        # Calculate actual costs including labor
        actual_costs = []
        for tc in task_costs:
            actual_costs.append(tc.get_total_actual_cost())
        total_actual_cost = sum(actual_costs) if actual_costs else Decimal('0.00')
        
        # Cost variance
        cost_variance = total_actual_cost - total_estimated_cost
        cost_variance_percent = 0
        if total_estimated_cost > 0:
            cost_variance_percent = float((cost_variance / total_estimated_cost) * 100)
        
        # Task breakdown
        completed_tasks = tasks.filter(
            Q(column__name__icontains='done') | Q(column__name__icontains='complete')
        ).count()
        total_tasks = tasks.count()
        
        # Cost per task
        cost_per_task = Decimal('0.00')
        if completed_tasks > 0:
            cost_per_task = total_actual_cost / completed_tasks
        
        # Budget status
        status = budget.get_status()
        
        return {
            'has_budget': True,
            'budget': {
                'allocated': float(budget.allocated_budget),
                'spent': float(spent_amount),
                'remaining': float(remaining_budget),
                'currency': budget.currency,
                'utilization_percent': round(budget_utilization, 2),
                'status': status,
            },
            'time': {
                'allocated_hours': float(budget.allocated_hours) if budget.allocated_hours else None,
                'spent_hours': float(spent_hours),
                'utilization_percent': round(time_utilization, 2) if budget.allocated_hours else None,
            },
            'costs': {
                'total_estimated': float(total_estimated_cost),
                'total_actual': float(total_actual_cost),
                'variance': float(cost_variance),
                'variance_percent': round(cost_variance_percent, 2),
            },
            'tasks': {
                'total': total_tasks,
                'completed': completed_tasks,
                'completion_rate': round((completed_tasks / total_tasks * 100), 2) if total_tasks > 0 else 0,
                'cost_per_completed_task': float(cost_per_task),
            },
            'alerts': BudgetAnalyzer._generate_alerts(budget, budget_utilization, time_utilization),
        }
    
    @staticmethod
    def _generate_alerts(budget, budget_utilization: float, time_utilization: float) -> List[Dict]:
        """Generate budget alerts based on thresholds"""
        alerts = []
        
        # Budget alerts
        if budget_utilization >= 100:
            alerts.append({
                'type': 'critical',
                'category': 'budget',
                'message': f'Project is over budget by {budget_utilization - 100:.1f}%',
            })
        elif budget_utilization >= budget.critical_threshold:
            alerts.append({
                'type': 'critical',
                'category': 'budget',
                'message': f'Project is at {budget_utilization:.1f}% of budget (critical threshold)',
            })
        elif budget_utilization >= budget.warning_threshold:
            alerts.append({
                'type': 'warning',
                'category': 'budget',
                'message': f'Project is at {budget_utilization:.1f}% of budget (warning threshold)',
            })
        
        # Time alerts
        if budget.allocated_hours and time_utilization >= 100:
            alerts.append({
                'type': 'critical',
                'category': 'time',
                'message': f'Time budget exceeded by {time_utilization - 100:.1f}%',
            })
        elif budget.allocated_hours and time_utilization >= budget.critical_threshold:
            alerts.append({
                'type': 'warning',
                'category': 'time',
                'message': f'Time usage at {time_utilization:.1f}% (approaching limit)',
            })
        
        return alerts
    
    @staticmethod
    def calculate_roi_metrics(board) -> Dict:
        """
        Calculate ROI metrics for a project
        
        Args:
            board: Board instance
            
        Returns:
            Dictionary with ROI metrics
        """
        from kanban.budget_models import ProjectBudget, ProjectROI, TaskCost
        from kanban.models import Task
        
        try:
            budget = ProjectBudget.objects.get(board=board)
        except ProjectBudget.DoesNotExist:
            return {'error': 'No budget configured'}
        
        # Get latest ROI analysis
        latest_roi = ProjectROI.objects.filter(board=board).first()
        
        # Calculate current costs
        task_costs = TaskCost.objects.filter(task__column__board=board)
        total_cost = sum([tc.get_total_actual_cost() for tc in task_costs]) if task_costs else Decimal('0.00')
        
        # Task metrics
        tasks = Task.objects.filter(column__board=board)
        completed_tasks = tasks.filter(
            Q(column__name__icontains='done') | Q(column__name__icontains='complete')
        ).count()
        total_tasks = tasks.count()
        
        # Calculate ROI
        roi_percentage = None
        if latest_roi:
            value = latest_roi.realized_value or latest_roi.expected_value or Decimal('0.00')
            if total_cost > 0 and value > 0:
                roi_percentage = float(((value - total_cost) / total_cost) * 100)
        
        return {
            'total_investment': float(total_cost),
            'expected_value': float(latest_roi.expected_value) if latest_roi and latest_roi.expected_value else None,
            'realized_value': float(latest_roi.realized_value) if latest_roi and latest_roi.realized_value else 0,
            'roi_percentage': round(roi_percentage, 2) if roi_percentage else None,
            'completed_tasks': completed_tasks,
            'total_tasks': total_tasks,
            'cost_per_task': float(total_cost / completed_tasks) if completed_tasks > 0 else 0,
            'last_analysis_date': latest_roi.snapshot_date.isoformat() if latest_roi else None,
        }
    
    @staticmethod
    def get_cost_trend_data(board, days: int = 30) -> Dict:
        """
        Get cost trend data for the specified period
        
        Args:
            board: Board instance
            days: Number of days to include
            
        Returns:
            Dictionary with trend data
        """
        from kanban.budget_models import TimeEntry, TaskCost
        from django.db.models.functions import TruncDate
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Daily time entries
        daily_hours = TimeEntry.objects.filter(
            task__column__board=board,
            work_date__gte=start_date.date()
        ).values('work_date').annotate(
            total_hours=Sum('hours_spent')
        ).order_by('work_date')
        
        # Calculate cumulative costs
        cumulative_data = []
        cumulative_cost = Decimal('0.00')
        
        for entry in daily_hours:
            # Estimate cost (this is simplified - actual calculation would need hourly rates)
            estimated_daily_cost = entry['total_hours'] * Decimal('50.00')  # Default rate
            cumulative_cost += estimated_daily_cost
            
            cumulative_data.append({
                'date': entry['work_date'],  # Keep as date object for template formatting
                'daily_hours': float(entry['total_hours']),
                'daily_cost_estimate': float(estimated_daily_cost),
                'cumulative_cost': float(cumulative_cost),
            })
        
        return {
            'start_date': start_date.date().isoformat(),
            'end_date': end_date.date().isoformat(),
            'trend_data': cumulative_data,
            'total_days': days,
        }
    
    @staticmethod
    def get_task_cost_breakdown(board) -> List[Dict]:
        """
        Get detailed cost breakdown by task
        
        Args:
            board: Board instance
            
        Returns:
            List of task cost breakdowns
        """
        from kanban.budget_models import TaskCost, TimeEntry, ProjectBudget
        
        task_costs = TaskCost.objects.filter(
            task__column__board=board
        ).select_related('task', 'task__assigned_to')
        
        # Get budget for percent calculation
        try:
            budget = ProjectBudget.objects.get(board=board)
            total_budget = float(budget.allocated_budget)
        except ProjectBudget.DoesNotExist:
            total_budget = 1.0  # Avoid division by zero
        
        breakdown = []
        for tc in task_costs:
            total_actual = tc.get_total_actual_cost()
            variance = tc.get_cost_variance()
            variance_percent = tc.get_cost_variance_percent()
            
            # Get time logged for this task
            time_logged = TimeEntry.objects.filter(
                task=tc.task
            ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
            
            # Calculate percent of total budget
            percent_of_budget = (float(total_actual) / total_budget * 100) if total_budget > 0 else 0
            
            breakdown.append({
                'task_id': tc.task.id,
                'task_title': tc.task.title,
                'assignee': tc.task.assigned_to.username if tc.task.assigned_to else None,
                'estimated_cost': float(tc.estimated_cost),
                'actual_cost': float(tc.actual_cost),
                'labor_cost': float(tc.get_labor_cost()),
                'resource_cost': float(tc.resource_cost),
                'total_actual_cost': float(total_actual),
                'time_logged': float(time_logged),
                'variance': float(variance),
                'variance_percent': round(variance_percent, 2),
                'percent_of_budget': round(percent_of_budget, 2),
                'is_over_budget': tc.is_over_budget(),
                'status': tc.task.column.name,
            })
        
        # Sort by variance (highest overrun first)
        breakdown.sort(key=lambda x: x['variance_percent'], reverse=True)
        return breakdown
    
    @staticmethod
    def calculate_burn_rate(board, period_days: int = 7) -> Dict:
        """
        Calculate budget burn rate
        
        Args:
            board: Board instance
            period_days: Number of days to calculate rate over
            
        Returns:
            Dictionary with burn rate metrics
        """
        from kanban.budget_models import ProjectBudget, TimeEntry
        
        try:
            budget = ProjectBudget.objects.get(board=board)
        except ProjectBudget.DoesNotExist:
            return {'error': 'No budget configured'}
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=period_days)
        
        # Calculate costs in the period
        period_entries = TimeEntry.objects.filter(
            task__column__board=board,
            work_date__gte=start_date.date(),
            work_date__lte=end_date.date()
        )
        
        period_hours = period_entries.aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
        # Simplified cost calculation - in real scenario, would use actual rates
        estimated_period_cost = period_hours * Decimal('50.00')
        
        # Calculate daily burn rate
        daily_burn_rate = estimated_period_cost / period_days if period_days > 0 else Decimal('0.00')
        
        # Calculate remaining budget and days
        remaining_budget = budget.get_remaining_budget()
        days_remaining = 0
        if daily_burn_rate > 0:
            days_remaining = int(remaining_budget / daily_burn_rate)
        
        # Calculate projected end date
        projected_end_date = None
        if days_remaining > 0:
            projected_end_date = (timezone.now() + timedelta(days=days_remaining)).date()
        
        return {
            'period_days': period_days,
            'period_cost': float(estimated_period_cost),
            'daily_burn_rate': float(daily_burn_rate),
            'remaining_budget': float(remaining_budget),
            'days_remaining': days_remaining,
            'projected_end_date': projected_end_date.isoformat() if projected_end_date else None,
            'is_sustainable': days_remaining > 30 if days_remaining > 0 else False,
        }
    
    @staticmethod
    def identify_cost_overruns(board) -> List[Dict]:
        """
        Identify tasks with cost overruns
        
        Args:
            board: Board instance
            
        Returns:
            List of tasks with overruns
        """
        from kanban.budget_models import TaskCost
        
        overruns = []
        task_costs = TaskCost.objects.filter(
            task__column__board=board
        ).select_related('task')
        
        for tc in task_costs:
            if tc.is_over_budget():
                variance = tc.get_cost_variance()
                variance_percent = tc.get_cost_variance_percent()
                
                overruns.append({
                    'task_id': tc.task.id,
                    'task_title': tc.task.title,
                    'estimated_cost': float(tc.estimated_cost),
                    'actual_cost': float(tc.get_total_actual_cost()),
                    'overrun_amount': float(variance),
                    'overrun_percent': round(variance_percent, 2),
                    'assignee': tc.task.assigned_to.username if tc.task.assigned_to else None,
                })
        
        # Sort by overrun percentage
        overruns.sort(key=lambda x: x['overrun_percent'], reverse=True)
        return overruns


class ROICalculator:
    """
    Specialized ROI calculation utilities
    """
    
    @staticmethod
    def create_roi_snapshot(board, user, expected_value=None, realized_value=None) -> Dict:
        """
        Create a new ROI snapshot for analysis
        
        Args:
            board: Board instance
            user: User creating the snapshot
            expected_value: Expected value (optional)
            realized_value: Realized value (optional)
            
        Returns:
            Dictionary with snapshot results
        """
        from kanban.budget_models import ProjectROI, TaskCost
        from kanban.models import Task
        
        # Calculate current costs
        task_costs = TaskCost.objects.filter(task__column__board=board)
        total_cost = sum([tc.get_total_actual_cost() for tc in task_costs])
        
        # Task metrics
        tasks = Task.objects.filter(column__board=board)
        completed_tasks = tasks.filter(
            Q(column__name__icontains='done') | Q(column__name__icontains='complete')
        ).count()
        total_tasks = tasks.count()
        
        # Calculate ROI
        roi_percentage = None
        if expected_value or realized_value:
            value = realized_value or expected_value or Decimal('0.00')
            if total_cost > 0:
                roi_percentage = ((value - total_cost) / total_cost) * 100
        
        # Create snapshot
        snapshot = ProjectROI.objects.create(
            board=board,
            expected_value=expected_value,
            realized_value=realized_value or Decimal('0.00'),
            total_cost=total_cost,
            roi_percentage=roi_percentage,
            completed_tasks=completed_tasks,
            total_tasks=total_tasks,
            created_by=user,
        )
        
        return {
            'snapshot_id': snapshot.id,
            'total_cost': float(total_cost),
            'roi_percentage': float(roi_percentage) if roi_percentage else None,
            'completed_tasks': completed_tasks,
            'snapshot_date': snapshot.snapshot_date.isoformat(),
        }
    
    @staticmethod
    def compare_roi_snapshots(board, snapshot1_id: int, snapshot2_id: int) -> Dict:
        """
        Compare two ROI snapshots to show progress
        
        Args:
            board: Board instance
            snapshot1_id: First snapshot ID (earlier)
            snapshot2_id: Second snapshot ID (later)
            
        Returns:
            Dictionary with comparison data
        """
        from kanban.budget_models import ProjectROI
        
        try:
            snapshot1 = ProjectROI.objects.get(id=snapshot1_id, board=board)
            snapshot2 = ProjectROI.objects.get(id=snapshot2_id, board=board)
        except ProjectROI.DoesNotExist:
            return {'error': 'Snapshot not found'}
        
        cost_change = snapshot2.total_cost - snapshot1.total_cost
        cost_change_percent = 0
        if snapshot1.total_cost > 0:
            cost_change_percent = (cost_change / snapshot1.total_cost) * 100
        
        tasks_completed_change = snapshot2.completed_tasks - snapshot1.completed_tasks
        
        roi_change = None
        if snapshot1.roi_percentage and snapshot2.roi_percentage:
            roi_change = snapshot2.roi_percentage - snapshot1.roi_percentage
        
        return {
            'period': {
                'start_date': snapshot1.snapshot_date.isoformat(),
                'end_date': snapshot2.snapshot_date.isoformat(),
                'days': (snapshot2.snapshot_date - snapshot1.snapshot_date).days,
            },
            'cost': {
                'start': float(snapshot1.total_cost),
                'end': float(snapshot2.total_cost),
                'change': float(cost_change),
                'change_percent': float(cost_change_percent),
            },
            'tasks': {
                'start_completed': snapshot1.completed_tasks,
                'end_completed': snapshot2.completed_tasks,
                'completed_in_period': tasks_completed_change,
            },
            'roi': {
                'start': float(snapshot1.roi_percentage) if snapshot1.roi_percentage else None,
                'end': float(snapshot2.roi_percentage) if snapshot2.roi_percentage else None,
                'change': float(roi_change) if roi_change else None,
            }
        }
