"""
Views for Burndown/Burnup Prediction with Confidence Intervals
Statistical forecasting and project completion tracking
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta, datetime
import json

from kanban.models import Board, Task
from kanban.burndown_models import (
    TeamVelocitySnapshot,
    BurndownPrediction,
    BurndownAlert,
    SprintMilestone
)
from kanban.utils.burndown_predictor import BurndownPredictor


def check_board_access_for_demo(request, board):
    """
    Helper function to check board access supporting demo mode
    Returns (has_access: bool, error_response: HttpResponse or None)
    """
    demo_org_names = ['Demo - Acme Corporation']
    is_demo_board = board.organization.name in demo_org_names
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')
    
    # For non-demo boards, require authentication
    if not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return False, redirect_to_login(request.get_full_path())
        
        # Access restriction removed - all authenticated users can access
    
    # For demo boards in team mode, check role-based permissions
    elif demo_mode_type == 'team':
        from kanban.utils.demo_permissions import DemoPermissions
        if not DemoPermissions.can_perform_action(request, 'can_view_analytics'):
            return False, None
    # Solo demo mode: full access, no restrictions
    
    return True, None


def burndown_dashboard(request, board_id):
    """
    Main burndown dashboard with predictions and confidence intervals
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check if this is a demo board (for display purposes only)
    demo_org_names = ['Demo - Acme Corporation']
    is_demo_board = board.organization.name in demo_org_names
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')  # 'solo' or 'team'
    
    # For non-demo boards, require authentication
    if not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        # Access restriction removed - all authenticated users can access
    
    # For demo boards in team mode, check role-based permissions
    elif demo_mode_type == 'team':
        from kanban.utils.demo_permissions import DemoPermissions
        if not DemoPermissions.can_perform_action(request, 'can_view_analytics'):
            messages.error(request, "You don't have permission to view analytics in your current demo role.")
            return redirect('demo_dashboard')
    # Solo demo mode: full access, no restrictions
    
    # Get or generate latest prediction
    predictor = BurndownPredictor()
    
    # Check for recent prediction (within last 24 hours)
    recent_prediction = BurndownPrediction.objects.filter(
        board=board,
        prediction_date__gte=timezone.now() - timedelta(hours=24)
    ).first()
    
    if not recent_prediction:
        # Generate new prediction
        try:
            result = predictor.generate_burndown_prediction(board)
            prediction = result['prediction']
            alerts = result['alerts']
        except Exception as e:
            messages.warning(request, f"Could not generate prediction: {str(e)}")
            prediction = None
            alerts = []
    else:
        prediction = recent_prediction
        alerts = prediction.alerts.filter(status__in=['active', 'acknowledged'])
    
    # Get velocity history
    velocity_snapshots = TeamVelocitySnapshot.objects.filter(
        board=board
    ).order_by('-period_end')[:12]  # Last 12 periods
    
    # Get milestones
    milestones = SprintMilestone.objects.filter(board=board).order_by('target_date')
    
    # Get active alerts
    active_alerts = BurndownAlert.objects.filter(
        board=board,
        status__in=['active', 'acknowledged']
    ).order_by('-severity', '-created_at')
    
    context = {
        'board': board,
        'prediction': prediction,
        'velocity_snapshots': velocity_snapshots,
        'milestones': milestones,
        'alerts': active_alerts,
        'critical_alerts': active_alerts.filter(severity='critical'),
        'warning_alerts': active_alerts.filter(severity='warning'),
        'is_demo_mode': is_demo_mode,
        'is_demo_board': is_demo_board,
    }
    
    return render(request, 'kanban/burndown_dashboard.html', context)


def generate_burndown_prediction(request, board_id):
    """
    Generate a new burndown prediction
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check if this is a demo board
    demo_org_names = ['Demo - Acme Corporation']
    is_demo_board = board.organization.name in demo_org_names
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')
    
    # For non-demo boards, require authentication and check access
    if not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
        # Access restriction removed - all authenticated users can access

        pass  # Original: board membership check removed
    
    # For demo boards in team mode, check role-based permissions
    elif demo_mode_type == 'team':
        from kanban.utils.demo_permissions import DemoPermissions
        if not DemoPermissions.can_perform_action(request, 'can_view_analytics'):
            return JsonResponse({'success': False, 'error': 'Permission denied in current demo role'}, status=403)
    # Solo demo mode: full access, no restrictions
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=400)
    
    try:
        # Get target date if provided
        target_date_str = request.POST.get('target_date')
        target_date = None
        if target_date_str:
            try:
                target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            except:
                pass
        
        # Generate prediction
        predictor = BurndownPredictor()
        result = predictor.generate_burndown_prediction(board, target_date=target_date)
        
        prediction = result['prediction']
        alerts = result['alerts']
        
        return JsonResponse({
            'success': True,
            'message': 'Burndown prediction generated successfully',
            'prediction': {
                'id': prediction.id,
                'predicted_date': prediction.predicted_completion_date.isoformat() if prediction.predicted_completion_date else None,
                'lower_bound': prediction.completion_date_lower_bound.isoformat() if prediction.completion_date_lower_bound else None,
                'upper_bound': prediction.completion_date_upper_bound.isoformat() if prediction.completion_date_upper_bound else None,
                'days_until': prediction.days_until_completion_estimate,
                'margin_of_error': prediction.days_margin_of_error,
                'confidence': prediction.confidence_percentage,
                'delay_probability': float(prediction.delay_probability),
                'risk_level': prediction.risk_level,
                'completion_percentage': float(prediction.completion_percentage),
            },
            'alerts_created': len(alerts),
            'velocity': {
                'current': float(prediction.current_velocity),
                'average': float(prediction.average_velocity),
                'trend': prediction.velocity_trend,
            }
        })
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


def burndown_chart_data(request, board_id):
    """
    API endpoint for burndown chart data with confidence bands
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check access
    has_access, error_response = check_board_access_for_demo(request, board)
    if not has_access:
        if error_response:
            return error_response
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    # Get latest prediction
    prediction = BurndownPrediction.objects.filter(board=board).first()
    
    if not prediction:
        return JsonResponse({
            'success': False,
            'error': 'No prediction available. Generate a prediction first.'
        }, status=404)
    
    # Prepare chart data
    chart_data = {
        'historical': prediction.burndown_curve_data.get('historical', []),
        'projected': prediction.burndown_curve_data.get('projected', []),
        'confidence_bands': prediction.confidence_bands_data,
        'ideal_line': prediction.burndown_curve_data.get('ideal_line', []),
        'prediction_info': {
            'predicted_date': prediction.predicted_completion_date.isoformat(),
            'lower_bound': prediction.completion_date_lower_bound.isoformat(),
            'upper_bound': prediction.completion_date_upper_bound.isoformat(),
            'confidence_level': prediction.confidence_percentage,
            'risk_level': prediction.risk_level,
        },
        'scope': {
            'total_tasks': prediction.total_tasks,
            'completed_tasks': prediction.completed_tasks,
            'remaining_tasks': prediction.remaining_tasks,
        }
    }
    
    return JsonResponse(chart_data)


def velocity_chart_data(request, board_id):
    """
    API endpoint for velocity history chart
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check access
    has_access, error_response = check_board_access_for_demo(request, board)
    if not has_access:
        if error_response:
            return error_response
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    # Get velocity snapshots
    snapshots = TeamVelocitySnapshot.objects.filter(
        board=board
    ).order_by('period_end')[:20]  # Last 20 periods
    
    velocity_data = {
        'labels': [s.period_end.isoformat() for s in snapshots],
        'velocities': [s.tasks_completed for s in snapshots],
        'story_points': [float(s.story_points_completed) for s in snapshots],
        'team_sizes': [s.active_team_members for s in snapshots],
        'quality_scores': [float(s.quality_score) for s in snapshots],
    }
    
    # Calculate statistics
    velocities = velocity_data['velocities']
    if velocities:
        import statistics
        velocity_data['average'] = statistics.mean(velocities)
        velocity_data['std_dev'] = statistics.stdev(velocities) if len(velocities) >= 2 else 0
        velocity_data['min'] = min(velocities)
        velocity_data['max'] = max(velocities)
    
    return JsonResponse(velocity_data)


def acknowledge_burndown_alert(request, board_id, alert_id):
    """
    Acknowledge a burndown alert
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    alert = get_object_or_404(BurndownAlert, id=alert_id, board=board)
    
    # Check access
    has_access, error_response = check_board_access_for_demo(request, board)
    if not has_access:
        if error_response:
            return error_response
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    if request.method == 'POST':
        alert.status = 'acknowledged'
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Alert acknowledged'})
        else:
            messages.success(request, 'Alert acknowledged')
            return redirect('burndown_dashboard', board_id=board_id)
    
    return JsonResponse({'success': False, 'error': 'POST required'}, status=400)


def resolve_burndown_alert(request, board_id, alert_id):
    """
    Resolve a burndown alert
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    alert = get_object_or_404(BurndownAlert, id=alert_id, board=board)
    
    # Check access - demo mode has full access
    is_demo_board = board.organization.name in ['Demo - Acme Corporation']
    is_demo_mode = request.session.get('is_demo_mode', False)
    
    if not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Authentication required'}, status=401)
        # Access restriction removed - all authenticated users can access
    
    if request.method == 'POST':
        alert.status = 'resolved'
        alert.resolved_at = timezone.now()
        alert.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Alert resolved'})
        else:
            messages.success(request, 'Alert resolved')
            return redirect('burndown_dashboard', board_id=board_id)
    
    return JsonResponse({'success': False, 'error': 'POST required'}, status=400)


def prediction_history(request, board_id):
    """
    View historical predictions and accuracy
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check access
    has_access, error_response = check_board_access_for_demo(request, board)
    if not has_access:
        if error_response:
            return error_response
        messages.error(request, "You don't have access to this board.")
        return redirect('dashboard')
    
    predictions = BurndownPrediction.objects.filter(
        board=board
    ).order_by('-prediction_date')[:30]  # Last 30 predictions
    
    context = {
        'board': board,
        'predictions': predictions,
    }
    
    return render(request, 'kanban/prediction_history.html', context)


def actionable_suggestions_api(request, board_id):
    """
    Get actionable suggestions from latest prediction
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check access
    has_access, error_response = check_board_access_for_demo(request, board)
    if not has_access:
        if error_response:
            return error_response
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    # Get latest prediction
    prediction = BurndownPrediction.objects.filter(board=board).first()
    
    if not prediction:
        return JsonResponse({
            'success': False,
            'error': 'No prediction available'
        }, status=404)
    
    return JsonResponse({
        'success': True,
        'suggestions': prediction.actionable_suggestions,
        'risk_level': prediction.risk_level,
        'delay_probability': float(prediction.delay_probability),
        'prediction_date': prediction.prediction_date.isoformat(),
    })
