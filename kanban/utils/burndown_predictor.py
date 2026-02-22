"""
Burndown/Burnup Prediction Service with Confidence Intervals
Statistical forecasting using historical velocity data and variance analysis
"""

from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import statistics
import math
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F


class BurndownPredictor:
    """
    Statistical burndown/burnup predictor with confidence intervals
    Uses historical velocity and variance to project completion dates
    """
    
    # Configuration constants
    DEFAULT_CONFIDENCE_LEVEL = 90  # 90% confidence interval
    MIN_VELOCITY_SAMPLES = 3  # Minimum samples for reliable prediction
    VELOCITY_WINDOW_WEEKS = 8  # Look back 8 weeks for velocity calculation
    Z_SCORES = {
        90: 1.645,  # 90% confidence
        95: 1.96,   # 95% confidence
        99: 2.576,  # 99% confidence
    }
    
    def __init__(self):
        pass
    
    def generate_burndown_prediction(
        self,
        board,
        target_date: Optional[date] = None,
        confidence_level: int = 90
    ) -> Dict:
        """
        Generate complete burndown prediction with confidence intervals
        
        Args:
            board: Board object
            target_date: Optional target completion date for comparison
            confidence_level: Confidence level (90, 95, or 99)
        
        Returns:
            Dict with prediction data and metrics
        """
        from kanban.burndown_models import (
            TeamVelocitySnapshot,
            BurndownPrediction,
            BurndownAlert
        )
        from kanban.models import Task
        
        # Step 1: Calculate current velocity snapshots if needed
        self._ensure_velocity_snapshots(board)
        
        # Step 2: Get velocity history
        velocity_history = self._get_velocity_history(board)
        
        if len(velocity_history) < self.MIN_VELOCITY_SAMPLES:
            return self._create_insufficient_data_prediction(board, target_date)
        
        # Step 3: Calculate velocity statistics
        velocity_stats = self._calculate_velocity_statistics(velocity_history)
        
        # Step 4: Get scope metrics
        scope_metrics = self._calculate_scope_metrics(board)
        
        # Step 5: Project completion date with confidence intervals
        completion_projection = self._project_completion_date(
            scope_metrics,
            velocity_stats,
            confidence_level
        )
        
        # Step 6: Assess risk and delay probability
        risk_assessment = self._assess_completion_risk(
            completion_projection,
            velocity_stats,
            target_date
        )
        
        # Step 7: Generate burndown curve data
        curve_data = self._generate_burndown_curve_data(
            scope_metrics,
            velocity_stats,
            completion_projection
        )
        
        # Step 8: Generate actionable suggestions
        suggestions = self._generate_actionable_suggestions(
            risk_assessment,
            velocity_stats,
            scope_metrics,
            target_date
        )
        
        # Step 9: Save prediction to database
        prediction = BurndownPrediction.objects.create(
            board=board,
            prediction_type='burndown',
            total_tasks=scope_metrics['total_tasks'],
            completed_tasks=scope_metrics['completed_tasks'],
            remaining_tasks=scope_metrics['remaining_tasks'],
            total_story_points=scope_metrics['total_story_points'],
            completed_story_points=scope_metrics['completed_story_points'],
            remaining_story_points=scope_metrics['remaining_story_points'],
            current_velocity=velocity_stats['current_velocity'],
            average_velocity=velocity_stats['average_velocity'],
            velocity_std_dev=velocity_stats['std_dev'],
            velocity_trend=velocity_stats['trend'],
            predicted_completion_date=completion_projection['predicted_date'],
            completion_date_lower_bound=completion_projection['lower_bound'],
            completion_date_upper_bound=completion_projection['upper_bound'],
            days_until_completion_estimate=completion_projection['days_until'],
            days_margin_of_error=completion_projection['margin_of_error'],
            confidence_percentage=confidence_level,
            prediction_confidence_score=velocity_stats['confidence_score'],
            delay_probability=risk_assessment['delay_probability'],
            risk_level=risk_assessment['risk_level'],
            target_completion_date=target_date,
            will_meet_target=risk_assessment['will_meet_target'],
            days_ahead_behind_target=risk_assessment['days_ahead_behind'],
            burndown_curve_data=curve_data,
            confidence_bands_data=curve_data['confidence_bands'],
            velocity_history_data=velocity_stats['history_data'],
            actionable_suggestions=suggestions,
            model_parameters={
                'confidence_level': confidence_level,
                'velocity_window_weeks': self.VELOCITY_WINDOW_WEEKS,
                'min_samples': self.MIN_VELOCITY_SAMPLES,
                'z_score': self.Z_SCORES.get(confidence_level, 1.645),
            }
        )
        
        # Link velocity snapshots
        for snapshot_id in velocity_stats.get('snapshot_ids', []):
            try:
                snapshot = TeamVelocitySnapshot.objects.get(id=snapshot_id)
                prediction.based_on_velocity_snapshots.add(snapshot)
            except:
                pass
        
        # Step 10: Create alerts if needed
        alerts = self._create_alerts(prediction, risk_assessment, velocity_stats)
        
        return {
            'prediction': prediction,
            'alerts': alerts,
            'velocity_stats': velocity_stats,
            'scope_metrics': scope_metrics,
            'risk_assessment': risk_assessment,
            'curve_data': curve_data,
        }
    
    def _ensure_velocity_snapshots(self, board):
        """Ensure velocity snapshots exist for recent periods"""
        from kanban.burndown_models import TeamVelocitySnapshot
        from kanban.models import Task
        from datetime import datetime
        
        today = timezone.now().date()
        
        # Always update/create snapshot for current period (last 7 days)
        # This ensures velocity reflects recently completed tasks
        current_period_end = today
        current_period_start = today - timedelta(days=6)  # 7-day period
        
        # Convert to timezone-aware datetime for proper comparison with DateTimeField
        period_start_dt = timezone.make_aware(datetime.combine(current_period_start, datetime.min.time()))
        period_end_dt = timezone.make_aware(datetime.combine(current_period_end, datetime.max.time()))
        
        # Calculate velocity for current period
        completed_tasks = Task.objects.filter(
            column__board=board,
            completed_at__gte=period_start_dt,
            completed_at__lte=period_end_dt
        )
        
        tasks_count = completed_tasks.count()
        story_points = sum(
            t.complexity_score or 5 for t in completed_tasks
        )
        
        # Get active team members
        team_members = list(board.members.all())
        active_count = len(team_members)
        
        # Update or create snapshot for current period
        TeamVelocitySnapshot.objects.update_or_create(
            board=board,
            period_start=current_period_start,
            period_end=current_period_end,
            defaults={
                'period_type': 'weekly',
                'tasks_completed': tasks_count,
                'story_points_completed': Decimal(str(story_points)),
                'hours_completed': Decimal(str(tasks_count * 8)),  # Estimate
                'active_team_members': active_count,
                'team_member_list': [m.id for m in team_members],
                'quality_score': Decimal('95.0'),  # Default high quality
            }
        )
        
        # Create velocity snapshots for previous weeks (if not exist)
        for week_offset in range(1, 8):  # Start from 1 to skip current week
            period_end = today - timedelta(days=week_offset * 7)
            period_start = period_end - timedelta(days=6)  # 7-day periods
            
            # Check if snapshot already exists
            if TeamVelocitySnapshot.objects.filter(
                board=board,
                period_start=period_start,
                period_end=period_end
            ).exists():
                continue
            
            # Convert to timezone-aware datetime for proper comparison
            hist_start_dt = timezone.make_aware(datetime.combine(period_start, datetime.min.time()))
            hist_end_dt = timezone.make_aware(datetime.combine(period_end, datetime.max.time()))
            
            # Calculate velocity for this period
            completed_tasks = Task.objects.filter(
                column__board=board,
                completed_at__gte=hist_start_dt,
                completed_at__lte=hist_end_dt
            )
            
            tasks_count = completed_tasks.count()
            story_points = sum(
                t.complexity_score or 5 for t in completed_tasks
            )
            
            # Create snapshot
            TeamVelocitySnapshot.objects.create(
                board=board,
                period_start=period_start,
                period_end=period_end,
                period_type='weekly',
                tasks_completed=tasks_count,
                story_points_completed=Decimal(str(story_points)),
                hours_completed=Decimal(str(tasks_count * 8)),  # Estimate
                active_team_members=active_count,
                team_member_list=[m.id for m in team_members],
                quality_score=Decimal('95.0'),  # Default high quality
            )
    
    def _get_velocity_history(self, board) -> List[Dict]:
        """Get historical velocity data"""
        from kanban.burndown_models import TeamVelocitySnapshot
        
        cutoff_date = timezone.now().date() - timedelta(weeks=self.VELOCITY_WINDOW_WEEKS)
        
        snapshots = TeamVelocitySnapshot.objects.filter(
            board=board,
            period_end__gte=cutoff_date
        ).order_by('-period_end')
        
        history = []
        for snapshot in snapshots:
            history.append({
                'id': snapshot.id,
                'period_start': snapshot.period_start.isoformat(),
                'period_end': snapshot.period_end.isoformat(),
                'tasks_completed': snapshot.tasks_completed,
                'story_points': float(snapshot.story_points_completed),
                'team_size': snapshot.active_team_members,
                'quality_score': float(snapshot.quality_score),
            })
        
        return history
    
    def _calculate_velocity_statistics(self, velocity_history: List[Dict]) -> Dict:
        """Calculate velocity statistics including mean, std dev, and trend"""
        
        velocities = [v['tasks_completed'] for v in velocity_history]
        story_points = [v['story_points'] for v in velocity_history]
        
        # Basic statistics
        avg_velocity = statistics.mean(velocities) if velocities else 0
        current_velocity = velocities[0] if velocities else 0
        
        # Standard deviation (measure of variance/noise)
        std_dev = statistics.stdev(velocities) if len(velocities) >= 2 else 0
        
        # Coefficient of variation (noise relative to signal)
        cv = (std_dev / avg_velocity * 100) if avg_velocity > 0 else 0
        
        # Trend analysis (simple linear regression slope)
        trend = self._calculate_velocity_trend(velocity_history)
        
        # Confidence score based on data quality
        confidence_score = self._calculate_confidence_score(
            len(velocity_history),
            cv,
            velocity_history
        )
        
        return {
            'current_velocity': Decimal(str(current_velocity)),
            'average_velocity': Decimal(str(avg_velocity)),
            'std_dev': Decimal(str(std_dev)),
            'coefficient_of_variation': cv,
            'trend': trend,
            'confidence_score': Decimal(str(confidence_score)),
            'sample_count': len(velocity_history),
            'history_data': velocity_history,
            'snapshot_ids': [v['id'] for v in velocity_history],
        }
    
    def _calculate_velocity_trend(self, velocity_history: List[Dict]) -> str:
        """Calculate velocity trend using simple regression"""
        
        if len(velocity_history) < 3:
            return 'insufficient_data'
        
        # Simple trend: compare recent average to older average
        recent = [v['tasks_completed'] for v in velocity_history[:3]]
        older = [v['tasks_completed'] for v in velocity_history[-3:]]
        
        recent_avg = statistics.mean(recent)
        older_avg = statistics.mean(older)
        
        change_percent = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        
        if change_percent > 10:
            return 'increasing'
        elif change_percent < -10:
            return 'decreasing'
        else:
            return 'stable'
    
    def _calculate_confidence_score(
        self,
        sample_count: int,
        coefficient_of_variation: float,
        velocity_history: List[Dict]
    ) -> float:
        """Calculate overall confidence in prediction"""
        
        # Factor 1: Sample size (more samples = higher confidence)
        sample_score = min(1.0, sample_count / 10)  # Max at 10 samples
        
        # Factor 2: Low variance = higher confidence
        variance_score = max(0.3, 1.0 - (coefficient_of_variation / 100))
        
        # Factor 3: Recent consistency
        if len(velocity_history) >= 3:
            recent_velocities = [v['tasks_completed'] for v in velocity_history[:3]]
            recent_cv = (statistics.stdev(recent_velocities) / statistics.mean(recent_velocities) * 100) if statistics.mean(recent_velocities) > 0 else 100
            consistency_score = max(0.3, 1.0 - (recent_cv / 100))
        else:
            consistency_score = 0.5
        
        # Weighted combination
        confidence = (
            sample_score * 0.3 +
            variance_score * 0.4 +
            consistency_score * 0.3
        )
        
        return round(confidence, 2)
    
    def _calculate_scope_metrics(self, board) -> Dict:
        """Calculate current scope and completion metrics"""
        from kanban.models import Task
        
        # Exclude milestones — only count real tasks
        all_tasks = Task.objects.filter(column__board=board, item_type='task')
        
        total_tasks = all_tasks.count()
        completed_tasks = all_tasks.filter(progress=100).count()
        remaining_tasks = total_tasks - completed_tasks
        
        # Story points (using complexity_score)
        total_story_points = sum(t.complexity_score or 5 for t in all_tasks)
        completed_story_points = sum(
            t.complexity_score or 5 for t in all_tasks.filter(progress=100)
        )
        remaining_story_points = total_story_points - completed_story_points
        
        return {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'remaining_tasks': remaining_tasks,
            'completion_percentage': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
            'total_story_points': Decimal(str(total_story_points)),
            'completed_story_points': Decimal(str(completed_story_points)),
            'remaining_story_points': Decimal(str(remaining_story_points)),
        }
    
    def _project_completion_date(
        self,
        scope_metrics: Dict,
        velocity_stats: Dict,
        confidence_level: int
    ) -> Dict:
        """Project completion date with confidence intervals"""
        
        today = timezone.now().date()
        remaining_tasks = scope_metrics['remaining_tasks']
        avg_velocity = float(velocity_stats['average_velocity'])
        std_dev = float(velocity_stats['std_dev'])
        
        if avg_velocity <= 0:
            # No velocity, can't predict
            return {
                'predicted_date': today + timedelta(days=999),
                'lower_bound': today + timedelta(days=999),
                'upper_bound': today + timedelta(days=999),
                'days_until': 999,
                'margin_of_error': 999,
            }
        
        # Calculate weeks needed (based on average velocity)
        weeks_needed = remaining_tasks / avg_velocity
        days_until = weeks_needed * 7
        
        # Calculate confidence interval using standard error
        # Standard error = std_dev / sqrt(n_periods)
        n_periods = max(remaining_tasks / avg_velocity, 1)
        standard_error = std_dev / math.sqrt(n_periods) if n_periods > 0 else std_dev
        
        # Get Z-score for confidence level
        z_score = self.Z_SCORES.get(confidence_level, 1.645)
        
        # Calculate margin of error in tasks
        margin_tasks = z_score * standard_error * math.sqrt(n_periods)
        
        # Convert to days
        margin_days = (margin_tasks / avg_velocity) * 7 if avg_velocity > 0 else 30
        
        # Calculate bounds
        predicted_date = today + timedelta(days=days_until)
        lower_bound = today + timedelta(days=max(1, days_until - margin_days))
        upper_bound = today + timedelta(days=days_until + margin_days)
        
        return {
            'predicted_date': predicted_date,
            'lower_bound': lower_bound,
            'upper_bound': upper_bound,
            'days_until': int(days_until),
            'margin_of_error': int(margin_days),
            'weeks_needed': weeks_needed,
        }
    
    def _assess_completion_risk(
        self,
        completion_projection: Dict,
        velocity_stats: Dict,
        target_date: Optional[date]
    ) -> Dict:
        """Assess risk of missing target date"""
        
        predicted_date = completion_projection['predicted_date']
        margin_of_error = completion_projection['margin_of_error']
        
        if not target_date:
            # No target set, assess general risk based on variance
            cv = velocity_stats['coefficient_of_variation']
            
            if cv < 20:
                risk_level = 'low'
                delay_probability = 10
            elif cv < 40:
                risk_level = 'medium'
                delay_probability = 25
            else:
                risk_level = 'high'
                delay_probability = 40
            
            return {
                'risk_level': risk_level,
                'delay_probability': Decimal(str(delay_probability)),
                'will_meet_target': True,  # Default to True when no target set
                'days_ahead_behind': 0,
                'assessment': f"High variance detected ({cv:.1f}% CV)",
            }
        
        # Calculate days ahead/behind target
        days_diff = (target_date - predicted_date).days
        
        # Calculate probability of meeting target
        # Using normal distribution approximation
        if margin_of_error > 0:
            z = days_diff / margin_of_error
            # Approximate probability using cumulative distribution
            if z > 2:
                prob_meet = 97
            elif z > 1:
                prob_meet = 84
            elif z > 0:
                prob_meet = 65
            elif z > -1:
                prob_meet = 35
            elif z > -2:
                prob_meet = 16
            else:
                prob_meet = 3
        else:
            prob_meet = 50 if days_diff >= 0 else 10
        
        delay_probability = 100 - prob_meet
        will_meet_target = days_diff >= 0
        
        # Determine risk level
        if delay_probability >= 50:
            risk_level = 'critical'
        elif delay_probability >= 30:
            risk_level = 'high'
        elif delay_probability >= 15:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        return {
            'risk_level': risk_level,
            'delay_probability': Decimal(str(delay_probability)),
            'will_meet_target': bool(will_meet_target),
            'days_ahead_behind': days_diff,
            'probability_meet_target': prob_meet,
            'assessment': f"{'On track' if will_meet_target else 'Behind schedule'} by {abs(days_diff)} days",
        }
    
    def _generate_burndown_curve_data(
        self,
        scope_metrics: Dict,
        velocity_stats: Dict,
        completion_projection: Dict
    ) -> Dict:
        """Generate burndown curve data for visualization"""
        
        today = timezone.now().date()
        predicted_date = completion_projection['predicted_date']
        
        total_tasks = scope_metrics['total_tasks']
        remaining_tasks = scope_metrics['remaining_tasks']
        completed_tasks = scope_metrics['completed_tasks']
        avg_velocity = float(velocity_stats['average_velocity'])
        std_dev = float(velocity_stats['std_dev'])
        
        # Historical data points - use actual velocity history
        historical_points = []
        velocity_history = velocity_stats.get('history_data', [])
        
        if velocity_history:
            # Sort by period_end (oldest first) for forward cumulative calculation
            sorted_history = sorted(velocity_history, key=lambda x: x['period_end'])
            
            # Calculate initial state: start with total tasks and work down
            # We'll use the oldest snapshot as starting point
            oldest_date = sorted_history[0]['period_start']
            
            # Add starting point (before any velocity history)
            historical_points.append({
                'date': oldest_date,
                'remaining': total_tasks,
                'completed': 0,
            })
            
            # Build historical points by subtracting each period's completions
            cumulative_completed = 0
            for snapshot in sorted_history:
                cumulative_completed += snapshot['tasks_completed']
                remaining = total_tasks - cumulative_completed
                
                historical_points.append({
                    'date': snapshot['period_end'],
                    'remaining': max(0, remaining),
                    'completed': cumulative_completed,
                })
        
        # Always add current point to anchor to actual state
        historical_points.append({
            'date': today.isoformat(),
            'remaining': remaining_tasks,
            'completed': completed_tasks,
        })
        
        # Projected data points (future)
        projected_points = []
        current_remaining = remaining_tasks
        current_date = today
        
        while current_remaining > 0 and current_date <= predicted_date + timedelta(days=30):
            current_date += timedelta(weeks=1)
            current_remaining = max(0, current_remaining - avg_velocity)
            
            projected_points.append({
                'date': current_date.isoformat(),
                'remaining': int(current_remaining),
                'completed': int(total_tasks - current_remaining),
            })
        
        # Confidence bands (±1 std dev)
        confidence_bands = {
            'upper_band': [],
            'lower_band': [],
        }
        
        for point in projected_points:
            point_date = datetime.fromisoformat(point['date']).date()
            weeks_out = (point_date - today).days / 7
            
            # Upper band (slower velocity)
            upper_remaining = remaining_tasks - (avg_velocity - std_dev) * weeks_out
            confidence_bands['upper_band'].append({
                'date': point['date'],
                'remaining': max(0, int(upper_remaining)),
            })
            
            # Lower band (faster velocity)
            lower_remaining = remaining_tasks - (avg_velocity + std_dev) * weeks_out
            confidence_bands['lower_band'].append({
                'date': point['date'],
                'remaining': max(0, int(lower_remaining)),
            })
        
        return {
            'historical': historical_points,
            'projected': projected_points,
            'confidence_bands': confidence_bands,
            'ideal_line': self._calculate_ideal_line(total_tasks, today, predicted_date),
        }
    
    def _calculate_ideal_line(self, total_tasks: int, start_date: date, end_date: date) -> List[Dict]:
        """Calculate ideal burndown line"""
        
        days_total = (end_date - start_date).days
        if days_total <= 0:
            return []
        
        daily_burn = total_tasks / days_total
        
        ideal_points = []
        for day in range(0, days_total + 1, 7):  # Weekly points
            current_date = start_date + timedelta(days=day)
            remaining = max(0, total_tasks - (daily_burn * day))
            
            ideal_points.append({
                'date': current_date.isoformat(),
                'remaining': int(remaining),
            })
        
        return ideal_points
    
    def _generate_actionable_suggestions(
        self,
        risk_assessment: Dict,
        velocity_stats: Dict,
        scope_metrics: Dict,
        target_date: Optional[date]
    ) -> List[Dict]:
        """Generate AI-powered actionable suggestions"""
        
        suggestions = []
        priority_counter = 1
        
        risk_level = risk_assessment['risk_level']
        delay_probability = float(risk_assessment['delay_probability'])
        cv = velocity_stats['coefficient_of_variation']
        trend = velocity_stats['trend']
        
        # High delay probability suggestions
        if delay_probability >= 30:
            suggestions.append({
                'priority': priority_counter,
                'type': 'reduce_scope',
                'title': 'Consider Scope Reduction',
                'description': f"Current trajectory shows {delay_probability:.0f}% risk of delay. "
                              f"Review {scope_metrics['remaining_tasks']} remaining tasks and identify "
                              f"items that could be deferred or descoped.",
                'impact': 'high',
                'effort': 'medium',
            })
            priority_counter += 1
        
        # High variance suggestions
        if cv > 40:
            suggestions.append({
                'priority': priority_counter,
                'type': 'stabilize_velocity',
                'title': 'Stabilize Team Velocity',
                'description': f"Velocity variance is high ({cv:.1f}% CV). Focus on consistent daily progress, "
                              f"remove blockers promptly, and reduce work-in-progress.",
                'impact': 'high',
                'effort': 'low',
            })
            priority_counter += 1
        
        # Declining velocity suggestions
        if trend == 'decreasing':
            suggestions.append({
                'priority': priority_counter,
                'type': 'address_slowdown',
                'title': 'Address Velocity Decline',
                'description': "Team velocity is trending downward. Investigate potential causes: "
                              "technical debt, team morale, unclear requirements, or external blockers.",
                'impact': 'critical',
                'effort': 'high',
            })
            priority_counter += 1
        
        # Add team capacity suggestion if high risk
        if risk_level in ['high', 'critical']:
            suggestions.append({
                'priority': priority_counter,
                'type': 'increase_capacity',
                'title': 'Consider Adding Team Capacity',
                'description': "Current capacity may not be sufficient to meet timeline. Options: "
                              "1) Add team members, 2) Reduce other commitments, 3) Hire contractors.",
                'impact': 'high',
                'effort': 'high',
            })
            priority_counter += 1
        
        # Process improvement suggestion
        if cv > 30 or trend == 'decreasing':
            suggestions.append({
                'priority': priority_counter,
                'type': 'process_improvement',
                'title': 'Improve Team Processes',
                'description': "Focus on process improvements: better estimation, clearer acceptance criteria, "
                              "more frequent reviews, and automated testing to increase throughput.",
                'impact': 'medium',
                'effort': 'medium',
            })
            priority_counter += 1
        
        # Daily monitoring suggestion
        if delay_probability >= 20:
            suggestions.append({
                'priority': priority_counter,
                'type': 'increase_monitoring',
                'title': 'Increase Progress Monitoring',
                'description': "Track progress daily and address blockers immediately. Consider daily standups "
                              "focused on completion metrics and removing impediments.",
                'impact': 'medium',
                'effort': 'low',
            })
            priority_counter += 1
        
        return suggestions
    
    def _create_insufficient_data_prediction(self, board, target_date: Optional[date]) -> Dict:
        """Create a limited prediction when insufficient data exists"""
        from kanban.burndown_models import BurndownPrediction
        from kanban.models import Task
        
        today = timezone.now().date()
        
        # Basic scope metrics
        all_tasks = Task.objects.filter(column__board=board)
        total = all_tasks.count()
        completed = all_tasks.filter(progress=100).count()
        remaining = total - completed
        
        # Very rough estimate: 5 tasks per week
        estimated_weeks = remaining / 5 if remaining > 0 else 1
        predicted_date = today + timedelta(weeks=estimated_weeks)
        
        prediction = BurndownPrediction.objects.create(
            board=board,
            prediction_type='burndown',
            total_tasks=total,
            completed_tasks=completed,
            remaining_tasks=remaining,
            current_velocity=Decimal('5.0'),
            average_velocity=Decimal('5.0'),
            velocity_std_dev=Decimal('2.0'),
            velocity_trend='insufficient_data',
            predicted_completion_date=predicted_date,
            completion_date_lower_bound=predicted_date - timedelta(days=14),
            completion_date_upper_bound=predicted_date + timedelta(days=14),
            days_until_completion_estimate=int(estimated_weeks * 7),
            days_margin_of_error=14,
            confidence_percentage=90,
            prediction_confidence_score=Decimal('0.30'),
            delay_probability=Decimal('50.0'),
            risk_level='medium',
            target_completion_date=target_date,
            actionable_suggestions=[{
                'priority': 1,
                'type': 'gather_data',
                'title': 'Gather More Historical Data',
                'description': 'Complete more tasks to build velocity history for accurate predictions.',
                'impact': 'high',
                'effort': 'low',
            }],
        )
        
        return {
            'prediction': prediction,
            'alerts': [],
            'velocity_stats': {'insufficient_data': True},
            'scope_metrics': {'total_tasks': total, 'completed_tasks': completed},
            'risk_assessment': {'insufficient_data': True},
        }
    
    def _create_alerts(
        self,
        prediction,
        risk_assessment: Dict,
        velocity_stats: Dict
    ) -> List:
        """Create burndown alerts based on prediction
        
        Only creates alerts if no active alert of the same type exists for this board.
        This prevents duplicate alerts from being created on each prediction generation.
        """
        from kanban.burndown_models import BurndownAlert
        
        alerts = []
        board = prediction.board
        
        # Helper function to check if active alert of type already exists
        def active_alert_exists(alert_type):
            return BurndownAlert.objects.filter(
                board=board,
                alert_type=alert_type,
                status='active'
            ).exists()
        
        # Delay probability alert
        delay_prob = float(risk_assessment['delay_probability'])
        if delay_prob >= 50:
            if not active_alert_exists('target_risk'):
                alert = BurndownAlert.objects.create(
                    prediction=prediction,
                    board=prediction.board,
                    alert_type='target_risk',
                    severity='critical',
                    status='active',
                    title=f"Critical: {delay_prob:.0f}% Risk of Missing Target",
                    message=f"Current trajectory shows {delay_prob:.0f}% probability of missing target date. "
                           f"Immediate action required to get back on track.",
                    metric_value=Decimal(str(delay_prob)),
                    threshold_value=Decimal('50.0'),
                    suggested_actions=[s for s in prediction.actionable_suggestions if s.get('impact') == 'critical' or s.get('priority') <= 2],
                )
                alerts.append(alert)
        elif delay_prob >= 30:
            if not active_alert_exists('target_risk'):
                alert = BurndownAlert.objects.create(
                    prediction=prediction,
                    board=prediction.board,
                    alert_type='target_risk',
                    severity='warning',
                    status='active',
                    title=f"Warning: {delay_prob:.0f}% Risk of Delay",
                    message=f"Elevated risk of missing target. Review priorities and consider corrective actions.",
                    metric_value=Decimal(str(delay_prob)),
                    threshold_value=Decimal('30.0'),
                    suggested_actions=[s for s in prediction.actionable_suggestions if s.get('priority') <= 3],
                )
                alerts.append(alert)
        else:
            # Risk is now low - resolve any existing target_risk alerts
            BurndownAlert.objects.filter(
                board=board,
                alert_type='target_risk',
                status='active'
            ).update(status='resolved')
        
        # Velocity variance alert
        cv = velocity_stats['coefficient_of_variation']
        if cv > 50:
            if not active_alert_exists('variance_high'):
                alert = BurndownAlert.objects.create(
                    prediction=prediction,
                    board=prediction.board,
                    alert_type='variance_high',
                    severity='warning',
                    status='active',
                    title=f"High Velocity Variance Detected",
                    message=f"Team velocity is inconsistent ({cv:.1f}% CV). This makes predictions less reliable. "
                           f"Focus on stabilizing workflow and removing blockers.",
                    metric_value=Decimal(str(cv)),
                    threshold_value=Decimal('50.0'),
                    suggested_actions=[s for s in prediction.actionable_suggestions if s.get('type') == 'stabilize_velocity'],
                )
                alerts.append(alert)
        else:
            # Variance is now acceptable - resolve any existing variance_high alerts
            BurndownAlert.objects.filter(
                board=board,
                alert_type='variance_high',
                status='active'
            ).update(status='resolved')
        
        # Velocity decline alert
        if velocity_stats['trend'] == 'decreasing':
            if not active_alert_exists('velocity_drop'):
                alert = BurndownAlert.objects.create(
                    prediction=prediction,
                    board=prediction.board,
                    alert_type='velocity_drop',
                    severity='critical',
                    status='active',
                    title="Team Velocity Declining",
                    message="Team velocity has been declining over recent periods. "
                           "Investigate root causes and take corrective action.",
                    suggested_actions=[s for s in prediction.actionable_suggestions if s.get('type') == 'address_slowdown'],
                )
                alerts.append(alert)
        else:
            # Velocity is no longer declining - resolve any existing velocity_drop alerts
            BurndownAlert.objects.filter(
                board=board,
                alert_type='velocity_drop',
                status='active'
            ).update(status='resolved')
        
        return alerts
