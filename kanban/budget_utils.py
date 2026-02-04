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


class BudgetRedistributor:
    """
    Utility class for applying budget recommendations and redistributing funds.
    Handles different recommendation types and creates audit logs.
    """
    
    def __init__(self, recommendation, user):
        """
        Initialize the redistributor with a recommendation and user.
        
        Args:
            recommendation: BudgetRecommendation instance
            user: User implementing the recommendation
        """
        self.recommendation = recommendation
        self.board = recommendation.board
        self.user = user
        self.changes_made = []
        
    def preview_changes(self) -> Dict:
        """
        Preview what changes will be made without applying them.
        
        Returns:
            Dictionary with preview of all changes
        """
        rec_type = self.recommendation.recommendation_type
        
        handlers = {
            'reallocation': self._preview_reallocation,
            'scope_cut': self._preview_scope_reduction,
            'resource_optimization': self._preview_resource_optimization,
            'risk_mitigation': self._preview_risk_mitigation,
            'efficiency_improvement': self._preview_efficiency_improvement,
            'timeline_change': self._preview_timeline_change,
        }
        
        handler = handlers.get(rec_type, self._preview_generic)
        return handler()
    
    def apply_changes(self) -> Dict:
        """
        Apply the recommendation changes and create audit logs.
        
        Returns:
            Dictionary with summary of applied changes
        """
        from kanban.budget_models import BudgetImplementationLog
        
        rec_type = self.recommendation.recommendation_type
        
        handlers = {
            'reallocation': self._apply_reallocation,
            'scope_cut': self._apply_scope_reduction,
            'resource_optimization': self._apply_resource_optimization,
            'risk_mitigation': self._apply_risk_mitigation,
            'efficiency_improvement': self._apply_efficiency_improvement,
            'timeline_change': self._apply_timeline_change,
        }
        
        handler = handlers.get(rec_type, self._apply_generic)
        result = handler()
        
        # Update recommendation status
        self.recommendation.status = 'implemented'
        self.recommendation.implemented_at = timezone.now()
        self.recommendation.reviewed_by = self.user
        self.recommendation.reviewed_at = timezone.now()
        self.recommendation.implementation_summary = self._generate_summary()
        self.recommendation.save()
        
        return result
    
    def _get_overrun_tasks(self) -> List:
        """Get tasks that are over budget"""
        from kanban.budget_models import TaskCost
        
        task_costs = TaskCost.objects.filter(
            task__column__board=self.board
        ).select_related('task')
        
        overrun_tasks = []
        for tc in task_costs:
            actual = tc.get_total_actual_cost()
            if actual > tc.estimated_cost and tc.estimated_cost > 0:
                variance = actual - tc.estimated_cost
                variance_percent = (variance / tc.estimated_cost) * 100
                overrun_tasks.append({
                    'task_cost': tc,
                    'task': tc.task,
                    'estimated': tc.estimated_cost,
                    'actual': actual,
                    'variance': variance,
                    'variance_percent': float(variance_percent),
                })
        
        return sorted(overrun_tasks, key=lambda x: x['variance'], reverse=True)
    
    def _get_underbudget_tasks(self) -> List:
        """Get tasks that are significantly under budget"""
        from kanban.budget_models import TaskCost
        
        task_costs = TaskCost.objects.filter(
            task__column__board=self.board
        ).select_related('task')
        
        underbudget_tasks = []
        for tc in task_costs:
            actual = tc.get_total_actual_cost()
            if tc.estimated_cost > actual and tc.estimated_cost > 0:
                savings = tc.estimated_cost - actual
                savings_percent = (savings / tc.estimated_cost) * 100
                # Only include if more than 20% under budget
                if savings_percent >= 20:
                    underbudget_tasks.append({
                        'task_cost': tc,
                        'task': tc.task,
                        'estimated': tc.estimated_cost,
                        'actual': actual,
                        'savings': savings,
                        'savings_percent': float(savings_percent),
                    })
        
        return sorted(underbudget_tasks, key=lambda x: x['savings'], reverse=True)
    
    def _preview_reallocation(self) -> Dict:
        """Preview budget reallocation changes"""
        overrun_tasks = self._get_overrun_tasks()
        underbudget_tasks = self._get_underbudget_tasks()
        
        changes = []
        total_reallocation = Decimal('0.00')
        
        # Calculate how much can be reallocated from underbudget tasks
        available_funds = sum(t['savings'] for t in underbudget_tasks)
        needed_funds = sum(t['variance'] for t in overrun_tasks)
        
        # Distribute from underbudget to overrun tasks
        for under_task in underbudget_tasks[:5]:  # Limit to top 5
            realloc_amount = min(under_task['savings'] * Decimal('0.5'), under_task['savings'])  # Take up to 50% of savings
            if realloc_amount > 100:  # Only if meaningful amount
                changes.append({
                    'type': 'reduce_estimate',
                    'task_id': under_task['task'].id,
                    'task_title': under_task['task'].title,
                    'field': 'estimated_cost',
                    'old_value': float(under_task['estimated']),
                    'new_value': float(under_task['estimated'] - realloc_amount),
                    'change_amount': float(-realloc_amount),
                    'reason': f"Task is {under_task['savings_percent']:.1f}% under budget, reallocating excess funds",
                })
                total_reallocation += realloc_amount
        
        # Increase estimates for overrun tasks
        remaining = total_reallocation
        for over_task in overrun_tasks[:3]:  # Limit to top 3 overruns
            if remaining <= 0:
                break
            add_amount = min(over_task['variance'], remaining)
            changes.append({
                'type': 'increase_estimate',
                'task_id': over_task['task'].id,
                'task_title': over_task['task'].title,
                'field': 'estimated_cost',
                'old_value': float(over_task['estimated']),
                'new_value': float(over_task['estimated'] + add_amount),
                'change_amount': float(add_amount),
                'reason': f"Task is {over_task['variance_percent']:.1f}% over budget, adding funds to cover overrun",
            })
            remaining -= add_amount
        
        return {
            'recommendation_type': 'Budget Reallocation',
            'summary': f"Reallocate {self.board.budget.currency} {total_reallocation:,.2f} from under-budget tasks to over-budget tasks",
            'changes': changes,
            'total_tasks_affected': len(changes),
            'estimated_savings': float(self.recommendation.estimated_savings or 0),
            'funds_available': float(available_funds),
            'funds_needed': float(needed_funds),
        }
    
    def _preview_scope_reduction(self) -> Dict:
        """Preview scope reduction changes"""
        overrun_tasks = self._get_overrun_tasks()
        
        changes = []
        total_reduction = Decimal('0.00')
        
        for task_data in overrun_tasks[:5]:  # Top 5 overrun tasks
            # Suggest reducing estimate to actual (accepting the overrun as new baseline)
            reduction = task_data['variance'] * Decimal('0.25')  # Suggest 25% scope cut
            if reduction > 50:
                new_estimate = task_data['estimated'] - reduction
                changes.append({
                    'type': 'scope_reduction',
                    'task_id': task_data['task'].id,
                    'task_title': task_data['task'].title,
                    'field': 'estimated_cost',
                    'old_value': float(task_data['estimated']),
                    'new_value': float(new_estimate),
                    'change_amount': float(-reduction),
                    'reason': f"Reduce scope to bring task within budget. Consider removing non-essential features.",
                })
                total_reduction += reduction
        
        return {
            'recommendation_type': 'Scope Reduction',
            'summary': f"Reduce scope on {len(changes)} tasks to save {self.board.budget.currency} {total_reduction:,.2f}",
            'changes': changes,
            'total_tasks_affected': len(changes),
            'estimated_savings': float(self.recommendation.estimated_savings or 0),
        }
    
    def _preview_resource_optimization(self) -> Dict:
        """Preview resource optimization changes"""
        from kanban.budget_models import TaskCost
        
        # Find tasks with high hourly rates
        task_costs = TaskCost.objects.filter(
            task__column__board=self.board,
            hourly_rate__isnull=False,
            hourly_rate__gt=0
        ).select_related('task').order_by('-hourly_rate')
        
        changes = []
        total_savings = Decimal('0.00')
        
        avg_rate = task_costs.aggregate(avg=Avg('hourly_rate'))['avg'] or Decimal('0.00')
        
        for tc in task_costs[:5]:
            if tc.hourly_rate > avg_rate * Decimal('1.2'):  # 20% above average
                new_rate = avg_rate * Decimal('1.1')  # Reduce to 10% above average
                hours = tc.estimated_hours or Decimal('0.00')
                savings = (tc.hourly_rate - new_rate) * hours
                
                if savings > 50:
                    changes.append({
                        'type': 'rate_optimization',
                        'task_id': tc.task.id,
                        'task_title': tc.task.title,
                        'field': 'hourly_rate',
                        'old_value': float(tc.hourly_rate),
                        'new_value': float(new_rate),
                        'change_amount': float(-savings),
                        'reason': f"Hourly rate is {((tc.hourly_rate / avg_rate) - 1) * 100:.0f}% above average. Consider using different resources.",
                    })
                    total_savings += savings
        
        return {
            'recommendation_type': 'Resource Optimization',
            'summary': f"Optimize resource rates on {len(changes)} tasks to save {self.board.budget.currency} {total_savings:,.2f}",
            'changes': changes,
            'total_tasks_affected': len(changes),
            'estimated_savings': float(self.recommendation.estimated_savings or 0),
            'average_hourly_rate': float(avg_rate),
        }
    
    def _preview_risk_mitigation(self) -> Dict:
        """Preview risk mitigation changes - add buffer to high-risk tasks"""
        overrun_tasks = self._get_overrun_tasks()
        
        changes = []
        total_buffer = Decimal('0.00')
        
        # Add 15% buffer to tasks with history of overruns
        for task_data in overrun_tasks[:5]:
            buffer_amount = task_data['actual'] * Decimal('0.15')
            new_estimate = task_data['actual'] + buffer_amount
            
            changes.append({
                'type': 'add_risk_buffer',
                'task_id': task_data['task'].id,
                'task_title': task_data['task'].title,
                'field': 'estimated_cost',
                'old_value': float(task_data['estimated']),
                'new_value': float(new_estimate),
                'change_amount': float(new_estimate - task_data['estimated']),
                'reason': f"Add 15% risk buffer based on historical overrun pattern.",
            })
            total_buffer += buffer_amount
        
        return {
            'recommendation_type': 'Risk Mitigation',
            'summary': f"Add risk buffers to {len(changes)} high-risk tasks",
            'changes': changes,
            'total_tasks_affected': len(changes),
            'estimated_savings': float(self.recommendation.estimated_savings or 0),
            'total_buffer_added': float(total_buffer),
        }
    
    def _preview_efficiency_improvement(self) -> Dict:
        """Preview efficiency improvement suggestions"""
        from kanban.budget_models import TaskCost
        
        # Find tasks where actual hours greatly exceed estimated
        task_costs = TaskCost.objects.filter(
            task__column__board=self.board,
            estimated_hours__gt=0
        ).select_related('task')
        
        changes = []
        
        for tc in task_costs:
            from kanban.budget_models import TimeEntry
            actual_hours = TimeEntry.objects.filter(
                task=tc.task
            ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
            
            if actual_hours > tc.estimated_hours * Decimal('1.25'):  # 25% over estimated hours
                efficiency_target = tc.estimated_hours * Decimal('1.1')  # Target 10% over
                hours_to_save = actual_hours - efficiency_target
                
                if hours_to_save > 2:  # Only if significant
                    hourly_rate = tc.hourly_rate or Decimal('50.00')
                    cost_savings = hours_to_save * hourly_rate
                    
                    changes.append({
                        'type': 'efficiency_target',
                        'task_id': tc.task.id,
                        'task_title': tc.task.title,
                        'field': 'estimated_hours',
                        'old_value': float(tc.estimated_hours),
                        'new_value': float(efficiency_target),
                        'change_amount': float(efficiency_target - tc.estimated_hours),
                        'actual_hours': float(actual_hours),
                        'potential_savings': float(cost_savings),
                        'reason': f"Task is running {((actual_hours / tc.estimated_hours) - 1) * 100:.0f}% over estimated hours. Review processes for efficiency.",
                    })
        
        return {
            'recommendation_type': 'Efficiency Improvement',
            'summary': f"Identified {len(changes)} tasks with efficiency improvement potential",
            'changes': changes[:10],  # Limit to top 10
            'total_tasks_affected': len(changes),
            'estimated_savings': float(self.recommendation.estimated_savings or 0),
        }
    
    def _preview_timeline_change(self) -> Dict:
        """Preview timeline adjustment suggestions"""
        return {
            'recommendation_type': 'Timeline Adjustment',
            'summary': "Timeline adjustments require manual review of project schedule",
            'changes': [],
            'total_tasks_affected': 0,
            'estimated_savings': float(self.recommendation.estimated_savings or 0),
            'note': "This recommendation suggests reviewing and adjusting project timelines. Please review task due dates and milestones manually.",
        }
    
    def _preview_generic(self) -> Dict:
        """Generic preview for unknown recommendation types"""
        return {
            'recommendation_type': self.recommendation.get_recommendation_type_display(),
            'summary': self.recommendation.description,
            'changes': [],
            'total_tasks_affected': 0,
            'estimated_savings': float(self.recommendation.estimated_savings or 0),
            'note': "This recommendation requires manual implementation.",
        }
    
    def _apply_reallocation(self) -> Dict:
        """Apply budget reallocation changes"""
        from kanban.budget_models import BudgetImplementationLog
        
        preview = self._preview_reallocation()
        
        for change in preview['changes']:
            self._apply_single_change(change, 'budget_reallocation')
        
        return {
            'success': True,
            'changes_applied': len(preview['changes']),
            'summary': preview['summary'],
        }
    
    def _apply_scope_reduction(self) -> Dict:
        """Apply scope reduction changes"""
        from kanban.budget_models import BudgetImplementationLog
        
        preview = self._preview_scope_reduction()
        
        for change in preview['changes']:
            self._apply_single_change(change, 'scope_reduction')
        
        return {
            'success': True,
            'changes_applied': len(preview['changes']),
            'summary': preview['summary'],
        }
    
    def _apply_resource_optimization(self) -> Dict:
        """Apply resource optimization changes"""
        preview = self._preview_resource_optimization()
        
        for change in preview['changes']:
            self._apply_single_change(change, 'hourly_rate_change')
        
        return {
            'success': True,
            'changes_applied': len(preview['changes']),
            'summary': preview['summary'],
        }
    
    def _apply_risk_mitigation(self) -> Dict:
        """Apply risk mitigation (add buffers)"""
        preview = self._preview_risk_mitigation()
        
        for change in preview['changes']:
            self._apply_single_change(change, 'task_estimate_update')
        
        return {
            'success': True,
            'changes_applied': len(preview['changes']),
            'summary': preview['summary'],
        }
    
    def _apply_efficiency_improvement(self) -> Dict:
        """Apply efficiency improvement targets"""
        preview = self._preview_efficiency_improvement()
        
        for change in preview['changes']:
            self._apply_single_change(change, 'task_estimate_update')
        
        return {
            'success': True,
            'changes_applied': len(preview['changes']),
            'summary': preview['summary'],
        }
    
    def _apply_timeline_change(self) -> Dict:
        """Timeline changes require manual implementation"""
        return {
            'success': True,
            'changes_applied': 0,
            'summary': "Timeline adjustment marked as implemented. Please manually review and adjust task due dates.",
            'manual_action_required': True,
        }
    
    def _apply_generic(self) -> Dict:
        """Generic implementation for unknown types"""
        return {
            'success': True,
            'changes_applied': 0,
            'summary': "Recommendation marked as implemented.",
            'manual_action_required': True,
        }
    
    def _apply_single_change(self, change: Dict, change_type: str):
        """Apply a single change and create audit log"""
        from kanban.budget_models import BudgetImplementationLog, TaskCost
        from kanban.models import Task
        
        try:
            task = Task.objects.get(id=change['task_id'])
            task_cost, created = TaskCost.objects.get_or_create(task=task)
            
            field = change['field']
            old_value = Decimal(str(change['old_value']))
            new_value = Decimal(str(change['new_value']))
            
            # Apply the change
            if hasattr(task_cost, field):
                setattr(task_cost, field, new_value)
                task_cost.save()
            
            # Create audit log
            log = BudgetImplementationLog.objects.create(
                recommendation=self.recommendation,
                change_type=change_type,
                affected_task=task,
                field_changed=field,
                old_value=old_value,
                new_value=new_value,
                change_details={
                    'reason': change.get('reason', ''),
                    'change_amount': change.get('change_amount', 0),
                },
                implemented_by=self.user,
            )
            
            self.changes_made.append({
                'log_id': log.id,
                'task': task.title,
                'field': field,
                'old': float(old_value),
                'new': float(new_value),
            })
            
        except Exception as e:
            logger.error(f"Error applying change for task {change.get('task_id')}: {e}")
    
    def _generate_summary(self) -> str:
        """Generate a human-readable summary of changes made"""
        if not self.changes_made:
            return "Recommendation implemented (no automatic changes applied)."
        
        summary_parts = [f"Applied {len(self.changes_made)} changes:"]
        for change in self.changes_made[:5]:  # Show first 5
            summary_parts.append(
                f"• {change['task']}: {change['field']} changed from {change['old']:.2f} to {change['new']:.2f}"
            )
        
        if len(self.changes_made) > 5:
            summary_parts.append(f"... and {len(self.changes_made) - 5} more changes.")
        
        return "\n".join(summary_parts)


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
        
        # Task breakdown - use progress instead of column name
        completed_tasks = tasks.filter(progress=100).count()
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
        
        # Task metrics - use progress instead of column name
        tasks = Task.objects.filter(column__board=board)
        completed_tasks = tasks.filter(progress=100).count()
        total_tasks = tasks.count()
        
        # Calculate ROI - use snapshot data consistently for historical tracking
        roi_percentage = None
        expected_value = Decimal('0.00')
        realized_value = Decimal('0.00')
        
        if latest_roi:
            expected_value = latest_roi.expected_value or Decimal('0.00')
            realized_value = latest_roi.realized_value or Decimal('0.00')
            # Use snapshot's total_cost instead of mixing with current costs
            roi_percentage = float(latest_roi.roi_percentage) if latest_roi.roi_percentage else 0
            # Use snapshot's cost for display consistency
            total_cost = latest_roi.total_cost
        
        # Calculate completion rate
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # Calculate cost efficiency (budget vs actual cost)
        cost_efficiency = 0
        if budget.allocated_budget > 0:
            cost_efficiency = (float(total_cost) / float(budget.allocated_budget)) * 100
        
        # Calculate value delivery (realized vs expected)
        value_delivery = 0
        if expected_value > 0:
            value_delivery = (float(realized_value) / float(expected_value)) * 100
        
        return {
            'budget': budget,
            'total_investment': float(total_cost),
            'expected_value': float(expected_value),
            'realized_value': float(realized_value),
            'roi_percent': round(roi_percentage, 2) if roi_percentage else 0,
            'roi_percentage': round(roi_percentage, 2) if roi_percentage else None,
            'tasks_completed': completed_tasks,
            'completed_tasks': completed_tasks,
            'total_tasks': total_tasks,
            'completion_rate': round(completion_rate, 1),
            'cost_efficiency': round(cost_efficiency, 2),
            'value_delivery': round(value_delivery, 2),
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
        if daily_burn_rate > 0 and remaining_budget > 0:
            days_remaining = int(remaining_budget / daily_burn_rate)
        # If remaining budget is negative or zero, days_remaining stays 0
        
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
        
        # Task metrics - use progress instead of column name
        tasks = Task.objects.filter(column__board=board)
        completed_tasks = tasks.filter(progress=100).count()
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
