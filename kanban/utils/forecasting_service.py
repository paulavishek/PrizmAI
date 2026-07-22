"""
Resource Demand Forecasting Service for TaskFlow
Adapted from ResourcePro with simplified 2-3 week forecasting and workload distribution
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count, Q, F, Avg
import statistics


class DemandForecastingService:
    """
    Service for generating predictive demand forecasts and workload distribution
    Provides 2-3 week team capacity forecasting with AI-powered recommendations
    """
    
    FORECAST_PERIOD_DAYS = 21  # 3-week forecast period
    CAPACITY_WARNING_THRESHOLD = 0.80  # 80% utilization triggers warning
    CAPACITY_CRITICAL_THRESHOLD = 1.00  # 100% utilization triggers critical alert
    
    def __init__(self):
        pass
    
    def generate_team_forecast(self, board, days_ahead=21):
        """
        Generate demand forecast for entire team for next 21 days (3 weeks)
        
        Args:
            board: Board object
            days_ahead: Number of days to forecast (default 21)
        
        Returns:
            Dict with forecast data and alerts
        """
        from kanban.models import ResourceDemandForecast, Task, TeamCapacityAlert
        from accounts.models import Organization
        
        if days_ahead < 7 or days_ahead > 30:
            days_ahead = 21
        
        period_start = timezone.now().date()
        period_end = period_start + timedelta(days=days_ahead)
        
        # Get all board members
        User = get_user_model()
        team_members = User.objects.filter(board_memberships__board=board)
        forecasts = []
        alerts = []
        
        for member in team_members:
            # Calculate current and predicted workload
            current_workload = self._calculate_current_workload(member, board, period_start, period_end)
            available_capacity = self._calculate_available_capacity(member, period_start, period_end)
            predicted_workload = self._predict_future_workload(member, board, period_start, period_end)
            
            # Generate forecast
            confidence, explainability = self._calculate_confidence_score(member, board)
            
            forecast = ResourceDemandForecast.objects.create(
                board=board,
                resource_user=member,
                resource_role=self._get_user_role(member),
                period_start=period_start,
                period_end=period_end,
                predicted_workload_hours=predicted_workload,
                available_capacity_hours=available_capacity,
                confidence_score=confidence,
                forecast_explainability=explainability
            )
            forecasts.append(forecast)
            
            # Check for capacity issues
            if forecast.is_overloaded:
                utilization = forecast.utilization_percentage
                
                # Create alert
                if utilization >= 100:
                    alert_level = 'critical'
                    alert_message = f"{member.get_full_name() or member.username} is critically overloaded ({utilization:.0f}% capacity)"
                else:
                    alert_level = 'warning'
                    alert_message = f"{member.get_full_name() or member.username} is near capacity ({utilization:.0f}%)"
                
                alert = TeamCapacityAlert.objects.create(
                    board=board,
                    forecast=forecast,
                    alert_type='individual',
                    alert_level=alert_level,
                    status='active',
                    resource_user=member,
                    message=alert_message,
                    workload_percentage=int(utilization)
                )
                alerts.append(alert)
        
        # Calculate team-wide metrics
        total_capacity = sum(f.available_capacity_hours for f in forecasts)
        total_predicted = sum(f.predicted_workload_hours for f in forecasts)
        team_utilization = (total_predicted / total_capacity * 100) if total_capacity > 0 else 0
        
        # Check for team-wide overload
        if team_utilization >= 100:
            team_alert = TeamCapacityAlert.objects.create(
                board=board,
                alert_type='team',
                alert_level='critical',
                status='active',
                message=f"Team is critically overloaded ({team_utilization:.0f}% total capacity)",
                workload_percentage=int(team_utilization)
            )
            alerts.append(team_alert)
        elif team_utilization >= 80:
            team_alert = TeamCapacityAlert.objects.create(
                board=board,
                alert_type='team',
                alert_level='warning',
                status='active',
                message=f"Team is near capacity ({team_utilization:.0f}% total capacity)",
                workload_percentage=int(team_utilization)
            )
            alerts.append(team_alert)
        
        return {
            'forecasts': forecasts,
            'alerts': alerts,
            'team_utilization': team_utilization,
            'period_start': period_start,
            'period_end': period_end,
            'total_capacity': total_capacity,
            'total_predicted_workload': total_predicted
        }
    
    def generate_workload_distribution_recommendations(self, board, period_days=21):
        """
        Generate AI-powered recommendations for optimal workload distribution
        
        Args:
            board: Board object
            period_days: Days to analyze (default 21)
        
        Returns:
            List of WorkloadDistributionRecommendation objects
        """
        from kanban.models import (
            WorkloadDistributionRecommendation, Task, ResourceDemandForecast,
            TeamCapacityAlert
        )
        
        recommendations = []
        period_start = timezone.now().date()
        period_end = period_start + timedelta(days=period_days)
        
        # Get current forecasts
        forecasts = ResourceDemandForecast.objects.filter(
            board=board,
            period_start=period_start,
            period_end=period_end
        )
        
        # Find overloaded team members
        overloaded = [f for f in forecasts if f.is_overloaded]
        
        if not overloaded:
            return recommendations
        
        # Get unassigned and low-priority tasks
        active_tasks = Task.objects.filter(
            column__board=board,
            column__name__in=['To Do', 'In Progress']
        ).order_by('priority', 'due_date')
        
        # For each overloaded member, suggest reassignments or deferrals
        for forecast in overloaded:
            member = forecast.resource_user
            if not member:
                continue
            
            # Find tasks assigned to this member
            member_tasks = active_tasks.filter(assigned_to=member).order_by('priority')
            
            # Suggest deferring low-priority tasks
            low_priority_tasks = member_tasks.filter(priority__in=['low'])
            for task in low_priority_tasks[:3]:  # Suggest top 3
                rec = WorkloadDistributionRecommendation.objects.create(
                    board=board,
                    forecast=forecast,
                    recommendation_type='defer',
                    priority=7,
                    title=f"Defer: {task.title}",
                    description=f"Defer task '{task.title}' to later period to reduce current workload on {member.get_full_name()}. "
                               f"This task is marked as low priority and can be scheduled after high-priority items.",
                    expected_capacity_savings_hours=Decimal('2.0'),
                    confidence_score=Decimal('0.85'),
                    status='pending'
                )
                rec.affected_tasks.add(task)
                rec.affected_users.add(member)
                recommendations.append(rec)
            
            # Suggest task reassignment to underutilized members
            underutilized = [f for f in forecasts 
                           if not f.is_overloaded and f.available_capacity_hours > (f.predicted_workload_hours + 5)]
            
            if underutilized and member_tasks.exists():
                for underutil_forecast in underutilized[:2]:
                    underutil_member = underutil_forecast.resource_user
                    if not underutil_member:
                        continue
                    
                    # Find compatible tasks
                    reassignable = member_tasks.filter(priority__in=['medium', 'low'])[:2]
                    
                    if reassignable.exists():
                        rec = WorkloadDistributionRecommendation.objects.create(
                            board=board,
                            forecast=forecast,
                            recommendation_type='reassign',
                            priority=8,
                            title=f"Reassign to {underutil_member.get_full_name()}",
                            description=f"Reassign tasks from {member.get_full_name()} to {underutil_member.get_full_name()}. "
                                       f"{underutil_member.get_full_name()} has available capacity and can handle additional work.",
                            expected_capacity_savings_hours=Decimal('5.0'),
                            confidence_score=Decimal('0.75'),
                            status='pending'
                        )
                        for task in reassignable:
                            rec.affected_tasks.add(task)
                        rec.affected_users.add(member)
                        rec.affected_users.add(underutil_member)
                        recommendations.append(rec)
        
        return recommendations
    
    def _calculate_current_workload(self, user, board, start_date, end_date):
        """Calculate current workload for a user in given period"""
        from kanban.models import Task
        
        tasks = Task.objects.filter(
            assigned_to=user,
            column__board=board,
            column__name__in=['To Do', 'In Progress', 'In Review']
        )
        
        # Estimate 8 hours per task as base
        # Can be enhanced with actual time tracking
        base_hours = len(tasks) * 8
        
        # Add any high-priority overhead
        high_priority = tasks.filter(priority__in=['high', 'urgent']).count()
        additional_hours = high_priority * 4
        
        return Decimal(str(base_hours + additional_hours))
    
    def _calculate_available_capacity(self, user, start_date, end_date):
        """Calculate available capacity (working hours) for a user"""
        # Calculate working days (excluding weekends)
        days_count = (end_date - start_date).days
        weeks = days_count / 7
        working_days = weeks * 5  # 5 working days per week
        
        # Assume 8 hours per working day, adjustable
        hours_per_day = 8
        total_available = working_days * hours_per_day
        
        return Decimal(str(total_available))
    
    def _predict_future_workload(self, user, board, start_date, end_date):
        """Predict future workload based on current tasks and trends"""
        from kanban.models import Task
        
        # Get pending and in-progress tasks
        current_workload = self._calculate_current_workload(user, board, start_date, end_date)
        
        # Look at historical patterns
        all_tasks = Task.objects.filter(
            assigned_to=user,
            column__board=board
        ).order_by('-created_at')
        
        # Add buffer for new tasks (20% increase expected)
        trend_multiplier = 1.2
        predicted = current_workload * Decimal(str(trend_multiplier))
        
        return predicted
    
    def _calculate_confidence_score(self, user, board):
        """
        Calculate confidence score based on historical data quality.
        Returns a tuple of (confidence: Decimal, explainability: dict).
        """
        from kanban.models import Task
        
        factors = []
        
        # More tasks = higher confidence
        task_count = Task.objects.filter(
            assigned_to=user,
            column__board=board
        ).count()
        
        completed_count = Task.objects.filter(
            assigned_to=user,
            column__board=board,
            completed_at__isnull=False
        ).count()
        
        # Base confidence increases with task history
        if task_count < 5:
            confidence = Decimal('0.50')
            factors.append({'factor': 'Task history', 'status': 'limited', 'detail': f'{task_count} tasks (< 5)', 'impact': 'low_confidence'})
        elif task_count < 15:
            confidence = Decimal('0.65')
            factors.append({'factor': 'Task history', 'status': 'moderate', 'detail': f'{task_count} tasks', 'impact': 'medium_confidence'})
        else:
            confidence = Decimal('0.85')
            factors.append({'factor': 'Task history', 'status': 'strong', 'detail': f'{task_count} tasks (15+)', 'impact': 'high_confidence'})
        
        # Completion history bonus
        if completed_count > 0:
            completion_ratio = completed_count / max(task_count, 1)
            if completion_ratio >= 0.5:
                confidence += Decimal('0.05')
                factors.append({'factor': 'Completion track record', 'status': 'positive', 'detail': f'{completed_count}/{task_count} completed ({completion_ratio:.0%})', 'impact': '+5%'})
            else:
                factors.append({'factor': 'Completion track record', 'status': 'neutral', 'detail': f'{completed_count}/{task_count} completed', 'impact': 'none'})
        
        confidence = min(confidence, Decimal('0.95'))
        
        explainability = {
            'confidence_factors': factors,
            'calculation_method': 'Historical task count and completion ratio analysis',
            'assumptions': [
                'Past workload patterns will continue into the forecast period.',
                'Available capacity is based on standard working hours (8h/day, 5 days/week).',
                'Task complexity is evenly distributed across the forecast period.',
            ],
            'limitations': [
                'Does not account for planned time off or holidays.',
                'Does not factor in cross-board assignments.',
            ] if task_count < 15 else [
                'Does not account for planned time off or holidays.',
            ],
        }
        
        return confidence, explainability
    
    def _get_user_role(self, user):
        """Get user's role/title"""
        # Try to get from user profile if available
        try:
            from accounts.models import UserProfile
            profile = user.userprofile
            return profile.role or user.get_full_name() or user.username
        except:
            return user.get_full_name() or user.username
    
    def get_forecast_summary(self, board, days=21):
        """Get summary statistics for forecasts"""
        from kanban.models import ResourceDemandForecast, TeamCapacityAlert
        
        period_start = timezone.now().date()
        period_end = period_start + timedelta(days=days)
        
        forecasts = ResourceDemandForecast.objects.filter(
            board=board,
            period_start=period_start,
            period_end__lte=period_end
        )
        
        alerts = TeamCapacityAlert.objects.filter(
            board=board,
            status='active'
        )
        
        if not forecasts:
            return None
        
        total_capacity = sum(f.available_capacity_hours for f in forecasts)
        total_workload = sum(f.predicted_workload_hours for f in forecasts)
        avg_confidence = sum(f.confidence_score for f in forecasts) / len(forecasts)
        
        overloaded_count = len([f for f in forecasts if f.is_overloaded])
        
        return {
            'total_capacity': total_capacity,
            'total_workload': total_workload,
            'team_utilization_percent': (total_workload / total_capacity * 100) if total_capacity > 0 else 0,
            'average_confidence': avg_confidence,
            'overloaded_members': overloaded_count,
            'total_members': len(forecasts),
            'active_alerts': alerts.count(),
            'critical_alerts': alerts.filter(alert_level='critical').count(),
            'warning_alerts': alerts.filter(alert_level='warning').count(),
        }


class WorkloadAnalyzer:
    """Analyze and optimize workload distribution"""
    
    @staticmethod
    def calculate_task_workload_impact(task, assigned_user=None):
        """
        Calculate estimated workload impact of a task
        
        Returns:
            Dict with estimated hours and impact level
        """
        from kanban.models import Task
        
        # Base estimate: 4 hours per task
        base_hours = 4
        
        # Adjust by priority
        priority_multiplier = {
            'low': 1.0,
            'medium': 1.5,
            'high': 2.0,
            'urgent': 3.0,
        }
        
        multiplier = priority_multiplier.get(task.priority, 1.5)
        estimated_hours = base_hours * multiplier
        
        # Adjust by complexity (if available)
        if hasattr(task, 'complexity_score') and task.complexity_score:
            complexity_factor = (task.complexity_score / 50)  # Normalize to 0-2
            estimated_hours *= complexity_factor
        
        # Determine impact level
        if estimated_hours < 2:
            impact = 'low'
        elif estimated_hours < 4:
            impact = 'medium'
        elif estimated_hours < 8:
            impact = 'high'
        else:
            impact = 'critical'
        
        return {
            'estimated_hours': Decimal(str(estimated_hours)),
            'impact_level': impact,
            'multiplier': multiplier
        }
    
    @staticmethod
    def find_optimal_assignee(task, board, exclude_user=None):
        """
        Find optimal team member for task assignment based on capacity
        
        Returns:
            User object or None
        """
        from kanban.models import ResourceDemandForecast
        from django.utils import timezone
        from datetime import timedelta
        
        period_start = timezone.now().date()
        period_end = period_start + timedelta(days=21)
        
        # Get active forecasts
        forecasts = ResourceDemandForecast.objects.filter(
            board=board,
            period_start=period_start,
            period_end__lte=period_end,
            resource_user__isnull=False
        ).order_by('predicted_workload_hours')
        
        if exclude_user:
            forecasts = forecasts.exclude(resource_user=exclude_user)
        
        # Find first non-overloaded member
        for forecast in forecasts:
            if not forecast.is_overloaded:
                return forecast.resource_user
        
        # If all overloaded, return least overloaded
        if forecasts:
            return forecasts.first().resource_user
        
        return None
