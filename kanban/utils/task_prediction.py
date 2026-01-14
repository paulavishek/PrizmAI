"""
Task Completion Prediction Module
Predicts task completion dates based on historical data and team velocity
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, StdDev, Count, Q
from kanban.models import Task

logger = logging.getLogger(__name__)


def predict_task_completion_date(task):
    """
    Predict task completion date based on historical data and multiple factors.
    
    Args:
        task: Task object to predict completion for
    
    Returns:
        dict: {
            'predicted_date': datetime,
            'confidence': float (0.0-1.0),
            'confidence_interval_days': float,
            'based_on_tasks': int,
            'factors': dict with detailed factors used,
            'early_date': datetime (optimistic),
            'late_date': datetime (pessimistic)
        }
        or None if insufficient data
    """
    
    # Don't predict for completed tasks
    if task.progress == 100:
        return None
    
    # Need start_date for prediction
    if not task.start_date:
        return _fallback_prediction(task)
    
    # Calculate remaining work
    remaining_progress = (100 - task.progress) / 100.0
    
    if remaining_progress <= 0:
        remaining_progress = 0.01  # Nearly complete
    
    # Get historical data
    historical_stats = _get_historical_statistics(task)
    
    if not historical_stats:
        return _fallback_prediction(task)
    
    # Calculate base prediction from historical average
    base_days = historical_stats['avg_duration'] * remaining_progress
    
    # Apply adjustments
    adjusted_days = _apply_prediction_adjustments(
        base_days, 
        task, 
        historical_stats
    )
    
    # Calculate prediction date
    predicted_date = timezone.now() + timedelta(days=adjusted_days)
    
    # Calculate confidence based on data quality
    confidence = _calculate_confidence(historical_stats, task)
    
    # Calculate confidence interval (95% confidence)
    std_dev = historical_stats.get('std_dev', 0) or 0
    confidence_interval = std_dev * 1.96  # 95% confidence interval
    
    # Calculate early/late estimates
    early_date = timezone.now() + timedelta(
        days=max(0.5, adjusted_days - confidence_interval)
    )
    late_date = timezone.now() + timedelta(
        days=adjusted_days + confidence_interval
    )
    
    # Compile factors used in prediction
    factors = {
        'base_estimate_days': round(base_days, 1),
        'adjusted_estimate_days': round(adjusted_days, 1),
        'remaining_progress': round(remaining_progress * 100, 1),
        'complexity_score': task.complexity_score,
        'priority': task.priority,
        'team_member_velocity': round(historical_stats.get('velocity_factor', 1.0), 2),
        'historical_avg_days': round(historical_stats['avg_duration'], 1),
        'sample_size': historical_stats['sample_size'],
        'data_quality': historical_stats.get('data_quality', 'unknown'),
        'adjustments_applied': historical_stats.get('adjustments', {})
    }
    
    return {
        'predicted_date': predicted_date,
        'confidence': round(confidence, 2),
        'confidence_interval_days': round(confidence_interval, 1),
        'based_on_tasks': historical_stats['sample_size'],
        'similar_tasks': historical_stats.get('similar_tasks', []),
        'factors': factors,
        'early_date': early_date,
        'late_date': late_date,
        'prediction_method': 'historical_analysis'
    }


def _get_historical_statistics(task):
    """
    Get statistical data from historical completed tasks.
    
    Args:
        task: Task object to analyze
    
    Returns:
        dict with avg_duration, std_dev, sample_size, velocity_factor
        or None if insufficient data
    """
    
    # Build query for similar tasks
    query = Q(
        progress=100,
        actual_duration_days__isnull=False,
        actual_duration_days__gt=0
    )
    
    # Priority 1: Same assignee, similar complexity and priority
    same_assignee_tasks = None
    if task.assigned_to:
        same_assignee_tasks = Task.objects.filter(
            query,
            assigned_to=task.assigned_to,
            priority=task.priority,
            complexity_score__range=(
                max(1, task.complexity_score - 2),
                min(10, task.complexity_score + 2)
            )
        ).exclude(id=task.id)
        
        stats = same_assignee_tasks.aggregate(
            avg=Avg('actual_duration_days'),
            std=StdDev('actual_duration_days'),
            count=Count('id')
        )
        
        if stats['count'] >= 5:  # Good sample size
            # Get similar tasks and format completed_at for JSON serialization
            similar_tasks_list = []
            for task_data in same_assignee_tasks[:10].values('id', 'title', 'actual_duration_days', 'complexity_score', 'priority', 'completed_at'):
                task_dict = dict(task_data)
                if task_dict.get('completed_at'):
                    task_dict['completed_at'] = task_dict['completed_at'].isoformat()
                similar_tasks_list.append(task_dict)
            
            return {
                'avg_duration': stats['avg'],
                'std_dev': stats['std'],
                'sample_size': stats['count'],
                'data_quality': 'high',
                'velocity_factor': task.get_velocity_factor(),
                'similar_tasks': similar_tasks_list
            }
    
    # Priority 2: Same board, similar complexity and priority
    board_tasks = Task.objects.filter(
        query,
        column__board=task.column.board,
        priority=task.priority,
        complexity_score__range=(
            max(1, task.complexity_score - 2),
            min(10, task.complexity_score + 2)
        )
    ).exclude(id=task.id)
    
    stats = board_tasks.aggregate(
        avg=Avg('actual_duration_days'),
        std=StdDev('actual_duration_days'),
        count=Count('id')
    )
    
    if stats['count'] >= 3:
        # Get similar tasks and format completed_at for JSON serialization
        similar_tasks_list = []
        for task_data in board_tasks[:10].values('id', 'title', 'actual_duration_days', 'complexity_score', 'priority', 'completed_at'):
            task_dict = dict(task_data)
            if task_dict.get('completed_at'):
                task_dict['completed_at'] = task_dict['completed_at'].isoformat()
            similar_tasks_list.append(task_dict)
        
        return {
            'avg_duration': stats['avg'],
            'std_dev': stats['std'],
            'sample_size': stats['count'],
            'data_quality': 'medium',
            'velocity_factor': 1.0,
            'similar_tasks': similar_tasks_list
        }
    
    # Priority 3: Organization-wide with same complexity
    org_tasks = Task.objects.filter(
        query,
        column__board__organization=task.column.board.organization,
        complexity_score__range=(
            max(1, task.complexity_score - 2),
            min(10, task.complexity_score + 2)
        )
    ).exclude(id=task.id)
    
    stats = org_tasks.aggregate(
        avg=Avg('actual_duration_days'),
        std=StdDev('actual_duration_days'),
        count=Count('id')
    )
    
    if stats['count'] >= 2:
        # Get similar tasks and format completed_at for JSON serialization
        similar_tasks_list = []
        for task_data in org_tasks[:10].values('id', 'title', 'actual_duration_days', 'complexity_score', 'priority', 'completed_at'):
            task_dict = dict(task_data)
            if task_dict.get('completed_at'):
                task_dict['completed_at'] = task_dict['completed_at'].isoformat()
            similar_tasks_list.append(task_dict)
        
        return {
            'avg_duration': stats['avg'],
            'std_dev': stats['std'],
            'sample_size': stats['count'],
            'data_quality': 'low',
            'velocity_factor': 1.0,
            'similar_tasks': similar_tasks_list
        }
    
    return None


def _apply_prediction_adjustments(base_days, task, historical_stats):
    """
    Apply various adjustments to the base prediction.
    
    Args:
        base_days: Base prediction in days
        task: Task object
        historical_stats: Historical statistics dict
    
    Returns:
        float: Adjusted days
    """
    
    adjusted_days = base_days
    adjustments = {}
    
    # Priority adjustment
    priority_factors = {
        'urgent': 0.8,   # Urgent tasks completed 20% faster (more focus)
        'high': 0.9,     # High priority: 10% faster
        'medium': 1.0,   # Baseline
        'low': 1.2       # Low priority: 20% slower (less attention)
    }
    
    priority_factor = priority_factors.get(task.priority, 1.0)
    if priority_factor != 1.0:
        adjusted_days *= priority_factor
        adjustments['priority_adjustment'] = f"{priority_factor}x ({task.priority})"
    
    # Risk adjustment - high risk tasks tend to take longer
    if task.risk_score and task.risk_score > 6:
        risk_factor = 1.0 + ((task.risk_score - 6) * 0.05)  # +5% per point above 6
        adjusted_days *= risk_factor
        adjustments['risk_adjustment'] = f"{risk_factor:.2f}x (risk score: {task.risk_score})"
    
    # Dependency adjustment - tasks with dependencies take longer
    if task.dependencies.exists():
        dependency_count = task.dependencies.count()
        dependency_factor = 1.0 + (dependency_count * 0.1)  # +10% per dependency
        adjusted_days *= min(dependency_factor, 1.5)  # Cap at +50%
        adjustments['dependency_adjustment'] = f"{dependency_count} dependencies"
    
    # Collaboration adjustment - collaborative tasks take longer
    if task.collaboration_required:
        adjusted_days *= 1.15  # +15% for collaboration overhead
        adjustments['collaboration_adjustment'] = "+15% (collaboration required)"
    
    # Team velocity adjustment
    velocity_factor = historical_stats.get('velocity_factor', 1.0)
    if velocity_factor != 1.0:
        adjusted_days *= velocity_factor
        adjustments['velocity_adjustment'] = f"{velocity_factor:.2f}x (team member velocity)"
    
    # Store adjustments in historical stats for reference
    historical_stats['adjustments'] = adjustments
    
    return max(0.5, adjusted_days)  # Minimum 0.5 days


def _calculate_confidence(historical_stats, task):
    """
    Calculate confidence score based on data quality and task attributes.
    
    Args:
        historical_stats: Historical statistics dict
        task: Task object
    
    Returns:
        float: Confidence score (0.0-1.0)
    """
    
    confidence = 0.5  # Base confidence
    
    # Sample size factor (more data = higher confidence)
    sample_size = historical_stats['sample_size']
    if sample_size >= 20:
        confidence += 0.30
    elif sample_size >= 10:
        confidence += 0.25
    elif sample_size >= 5:
        confidence += 0.20
    elif sample_size >= 3:
        confidence += 0.10
    
    # Data quality factor
    data_quality = historical_stats.get('data_quality', 'low')
    if data_quality == 'high':
        confidence += 0.15  # Same assignee data
    elif data_quality == 'medium':
        confidence += 0.10  # Same board data
    else:
        confidence += 0.05  # Organization-wide data
    
    # Standard deviation factor (lower variance = higher confidence)
    std_dev = historical_stats.get('std_dev', 0)
    avg = historical_stats.get('avg_duration', 1)
    if std_dev and avg:
        coefficient_of_variation = std_dev / avg
        if coefficient_of_variation < 0.3:
            confidence += 0.05  # Low variance
        elif coefficient_of_variation > 0.7:
            confidence -= 0.05  # High variance
    
    # Task clarity factor
    if task.description and len(task.description) > 50:
        confidence += 0.05  # Well-defined task
    
    if task.start_date:
        confidence += 0.05  # Task has been started
    
    # Cap confidence between 0.0 and 1.0
    return max(0.0, min(1.0, confidence))


def _fallback_prediction(task):
    """
    Fallback prediction using rule-based estimation when insufficient historical data.
    
    Args:
        task: Task object
    
    Returns:
        dict: Prediction with fallback method indicator
    """
    
    # Base estimate: complexity * 1.5 days per point
    base_days = task.complexity_score * 1.5
    
    # Priority adjustment
    priority_factors = {
        'urgent': 0.8,
        'high': 0.9,
        'medium': 1.0,
        'low': 1.2
    }
    adjusted_days = base_days * priority_factors.get(task.priority, 1.0)
    
    # Remaining work adjustment
    remaining_progress = (100 - task.progress) / 100.0
    adjusted_days *= remaining_progress
    
    predicted_date = timezone.now() + timedelta(days=adjusted_days)
    
    # Lower confidence for fallback predictions
    confidence = 0.35
    confidence_interval = adjusted_days * 0.5  # ±50% uncertainty
    
    return {
        'predicted_date': predicted_date,
        'confidence': confidence,
        'confidence_interval_days': round(confidence_interval, 1),
        'based_on_tasks': 0,
        'factors': {
            'base_estimate_days': round(base_days, 1),
            'adjusted_estimate_days': round(adjusted_days, 1),
            'remaining_progress': round(remaining_progress * 100, 1),
            'complexity_score': task.complexity_score,
            'priority': task.priority,
            'note': 'Insufficient historical data - using rule-based estimation'
        },
        'early_date': timezone.now() + timedelta(days=max(0.5, adjusted_days * 0.5)),
        'late_date': timezone.now() + timedelta(days=adjusted_days * 1.5),
        'prediction_method': 'rule_based_fallback'
    }


def update_task_prediction(task):
    """
    Update prediction for a task and save to database.
    
    Args:
        task: Task object to update prediction for
    
    Returns:
        dict: Prediction result or None
    """
    
    if task.progress == 100:
        # Clear predictions for completed tasks
        task.predicted_completion_date = None
        task.prediction_confidence = None
        task.prediction_metadata = {}
        task.last_prediction_update = None
        task.save()
        return None
    
    prediction = predict_task_completion_date(task)
    
    if prediction:
        task.predicted_completion_date = prediction['predicted_date']
        task.prediction_confidence = prediction['confidence']
        task.prediction_metadata = {
            'confidence_interval_days': prediction['confidence_interval_days'],
            'based_on_tasks': prediction['based_on_tasks'],
            'similar_tasks': prediction.get('similar_tasks', []),
            'factors': prediction['factors'],
            'early_date': prediction['early_date'].isoformat(),
            'late_date': prediction['late_date'].isoformat(),
            'prediction_method': prediction['prediction_method']
        }
        task.last_prediction_update = timezone.now()
        task.save()
        
        logger.info(
            f"Updated prediction for task {task.id}: "
            f"{prediction['predicted_date'].date()} "
            f"(confidence: {prediction['confidence']:.2f})"
        )
    
    return prediction


def bulk_update_predictions(board=None, organization=None):
    """
    Update predictions for all active tasks in a board or organization.
    
    Args:
        board: Board object (optional)
        organization: Organization object (optional)
    
    Returns:
        dict: Statistics about updates
    """
    
    # Build query
    query = Q(progress__lt=100, start_date__isnull=False)
    
    if board:
        query &= Q(column__board=board)
    elif organization:
        query &= Q(column__board__organization=organization)
    
    tasks = Task.objects.filter(query)
    
    updated_count = 0
    failed_count = 0
    
    for task in tasks:
        try:
            prediction = update_task_prediction(task)
            if prediction:
                updated_count += 1
        except Exception as e:
            logger.error(f"Failed to update prediction for task {task.id}: {e}")
            failed_count += 1
    
    return {
        'total_tasks': tasks.count(),
        'updated': updated_count,
        'failed': failed_count
    }
