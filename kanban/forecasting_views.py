"""
Views for Resource Demand Forecasting and Workload Distribution
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
import json
from decimal import Decimal

from kanban.models import (
    Board, ResourceDemandForecast, TeamCapacityAlert, 
    WorkloadDistributionRecommendation, Task
)
from kanban.utils.forecasting_service import DemandForecastingService, WorkloadAnalyzer
from kanban.utils.demo_permissions import DemoPermissions


def check_demo_access_for_forecasting(request, board, require_write=False):
    """
    Check if demo user has access to forecasting features for a specific board.
    
    Args:
        request: Django request object
        board: Board instance to check access for
        require_write: If True, check for write permissions
        
    Returns:
        tuple: (has_access: bool, error_response: HttpResponse or None, is_demo_mode: bool)
    """
    # Check if this is a demo board
    demo_org_names = ['Demo - Acme Corporation']
    is_demo_board = board.organization.name in demo_org_names
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')
    
    # For non-demo boards or non-demo mode, require authentication
    if not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return False, redirect_to_login(request.get_full_path()), False
        
        # Access restriction removed - all authenticated users can access
        return True, None, False
    
    # SOLO MODE: Full admin access, no restrictions
    if demo_mode_type == 'solo':
        return True, None, True
    
    # TEAM MODE: Check role-based permissions
    action = 'can_view_analytics' if not require_write else 'can_edit_tasks'
    if not DemoPermissions.can_perform_action(request, action):
        error_msg = "You don't have permission to access this feature in your current demo role."
        return False, HttpResponseForbidden(error_msg), True
    
    return True, None, True


def forecast_dashboard(request, board_id):
    """
    Main forecast dashboard showing team capacity, workload, and alerts
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check demo access
    has_access, error_response, is_demo_mode = check_demo_access_for_forecasting(request, board)
    if not has_access:
        return error_response
    
    demo_mode_type = request.session.get('demo_mode', 'solo')
    is_demo_board = board.organization.name in ['Demo - Acme Corporation']
    
    # Generate fresh forecasts if needed
    service = DemandForecastingService()
    forecast_data = service.generate_team_forecast(board, days_ahead=21)
    
    # Get recommendations
    recommendations = service.generate_workload_distribution_recommendations(board, period_days=21)
    
    # Get summary stats
    summary = service.get_forecast_summary(board, days=21)
    
    # Get active alerts
    alerts = TeamCapacityAlert.objects.filter(
        board=board,
        status__in=['active', 'acknowledged']
    ).order_by('-alert_level', '-created_at')
    
    context = {
        'board': board,
        'forecasts': forecast_data['forecasts'],
        'alerts': alerts,
        'critical_alerts': alerts.filter(alert_level='critical'),
        'warning_alerts': alerts.filter(alert_level='warning'),
        'recommendations': recommendations[:5],  # Top 5 recommendations
        'summary': summary,
        'period_start': forecast_data['period_start'],
        'period_end': forecast_data['period_end'],
        'is_demo_mode': is_demo_mode,
        'is_demo_board': is_demo_board,
        'demo_mode_type': demo_mode_type,
    }
    
    return render(request, 'kanban/forecast_dashboard.html', context)


def generate_forecast(request, board_id):
    """
    Generate forecasts for the board
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check demo access
    has_access, error_response, is_demo_mode = check_demo_access_for_forecasting(request, board, require_write=True)
    if not has_access:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    service = DemandForecastingService()
    
    try:
        forecast_data = service.generate_team_forecast(board, days_ahead=21)
        
        return JsonResponse({
            'success': True,
            'message': f"Generated forecasts for {len(forecast_data['forecasts'])} team members",
            'team_utilization': f"{forecast_data.get('team_utilization', 0):.0f}%",
            'alerts_created': len(forecast_data['alerts']),
            'forecasts': [
                {
                    'user': f.resource_user.get_full_name() if f.resource_user else f.resource_role,
                    'workload': float(f.predicted_workload_hours),
                    'capacity': float(f.available_capacity_hours),
                    'utilization': f"{f.utilization_percentage:.0f}%",
                    'overloaded': f.is_overloaded,
                } for f in forecast_data['forecasts']
            ]
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


def workload_recommendations(request, board_id):
    """
    Display workload distribution recommendations
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check demo access
    has_access, error_response, is_demo_mode = check_demo_access_for_forecasting(request, board)
    if not has_access:
        return error_response
    
    demo_mode_type = request.session.get('demo_mode', 'solo')
    is_demo_board = board.organization.name in ['Demo - Acme Corporation']
    
    service = DemandForecastingService()
    recommendations = service.generate_workload_distribution_recommendations(board, period_days=21)
    
    # Get summary
    summary = service.get_forecast_summary(board, days=21)
    
    context = {
        'board': board,
        'recommendations': recommendations,
        'summary': summary,
        'is_demo_mode': is_demo_mode,
        'is_demo_board': is_demo_board,
        'demo_mode_type': demo_mode_type,
    }
    
    return render(request, 'kanban/workload_recommendations.html', context)


def capacity_alerts(request, board_id):
    """
    Display all capacity alerts for the board
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check demo access
    has_access, error_response, is_demo_mode = check_demo_access_for_forecasting(request, board)
    if not has_access:
        return error_response
    
    demo_mode_type = request.session.get('demo_mode', 'solo')
    
    # Get all alerts
    alerts = TeamCapacityAlert.objects.filter(board=board).order_by('-created_at')
    
    # Separate by status
    active_alerts = alerts.filter(status='active')
    acknowledged_alerts = alerts.filter(status='acknowledged')
    resolved_alerts = alerts.filter(status='resolved')
    
    context = {
        'board': board,
        'alerts': alerts,
        'active_alerts': active_alerts,
        'acknowledged_alerts': acknowledged_alerts,
        'resolved_alerts': resolved_alerts,
        'critical_count': active_alerts.filter(alert_level='critical').count(),
        'warning_count': active_alerts.filter(alert_level='warning').count(),
        'is_demo_mode': is_demo_mode,
        'demo_mode_type': demo_mode_type,
    }
    
    return render(request, 'kanban/capacity_alerts.html', context)


def acknowledge_alert(request, board_id, alert_id):
    """
    Acknowledge a capacity alert
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    alert = get_object_or_404(TeamCapacityAlert, id=alert_id, board=board)
    
    # Check demo access
    has_access, error_response, is_demo_mode = check_demo_access_for_forecasting(request, board, require_write=True)
    if not has_access:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    if request.method == 'POST':
        alert.status = 'acknowledged'
        if request.user.is_authenticated:
            alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Alert acknowledged'})
        else:
            messages.success(request, 'Alert acknowledged')
            return redirect('capacity_alerts', board_id=board_id)
    
    return JsonResponse({'success': False, 'error': 'POST required'}, status=400)


def resolve_alert(request, board_id, alert_id):
    """
    Mark a capacity alert as resolved
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team - admin role only in team mode)
    """
    board = get_object_or_404(Board, id=board_id)
    alert = get_object_or_404(TeamCapacityAlert, id=alert_id, board=board)
    
    # Check demo access
    has_access, error_response, is_demo_mode = check_demo_access_for_forecasting(request, board, require_write=True)
    if not has_access:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    # Access restriction removed - all authenticated users can resolve alerts
    # For team mode, check admin role
    demo_mode_type = request.session.get('demo_mode', 'solo')
    if is_demo_mode and demo_mode_type == 'team':
        demo_role = request.session.get('demo_role', 'admin')
        if demo_role != 'admin':
            return JsonResponse({'success': False, 'error': 'Only admins can resolve alerts'}, status=403)
    
    if request.method == 'POST':
        alert.status = 'resolved'
        alert.resolved_at = timezone.now()
        alert.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Alert resolved'})
        else:
            messages.success(request, 'Alert resolved')
            return redirect('capacity_alerts', board_id=board_id)
    
    return JsonResponse({'success': False, 'error': 'POST required'}, status=400)


def recommendation_detail(request, board_id, rec_id):
    """
    View details of a workload recommendation and accept/reject it
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    recommendation = get_object_or_404(WorkloadDistributionRecommendation, id=rec_id, board=board)
    
    # Check demo access
    has_access, error_response, is_demo_mode = check_demo_access_for_forecasting(request, board)
    if not has_access:
        return error_response
    
    demo_mode_type = request.session.get('demo_mode', 'solo')
    
    if request.method == 'POST':
        # For POST requests, check write access
        if is_demo_mode and demo_mode_type == 'team':
            if not DemoPermissions.can_perform_action(request, 'can_edit_tasks'):
                return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        action = request.POST.get('action')
        
        if action == 'accept':
            recommendation.status = 'accepted'
            messages.success(request, f"Recommendation accepted: {recommendation.title}")
        elif action == 'reject':
            recommendation.status = 'rejected'
            messages.info(request, f"Recommendation rejected: {recommendation.title}")
        elif action == 'implement':
            # Try to implement the recommendation
            try:
                if recommendation.recommendation_type == 'reassign':
                    # Reassign tasks to suggested users
                    affected_users = list(recommendation.affected_users.all())
                    if len(affected_users) >= 2:
                        new_assignee = affected_users[1]
                        for task in recommendation.affected_tasks.all():
                            task.assigned_to = new_assignee
                            task.save()
                            messages.success(request, f"Reassigned '{task.title}' to {new_assignee.get_full_name()}")
                    
                    recommendation.status = 'implemented'
                    recommendation.implemented_at = timezone.now()
                    messages.success(request, "Recommendation implemented successfully")
                
                elif recommendation.recommendation_type == 'defer':
                    # Move tasks to future period (move to next column or mark differently)
                    for task in recommendation.affected_tasks.all():
                        # Find next column
                        current_col = task.column
                        next_col = current_col.board.columns.filter(
                            position__gt=current_col.position
                        ).first()
                        
                        if next_col:
                            task.column = next_col
                            task.save()
                            messages.success(request, f"Deferred '{task.title}' to later period")
                    
                    recommendation.status = 'implemented'
                    recommendation.implemented_at = timezone.now()
                    messages.success(request, "Recommendation implemented successfully")
            
            except Exception as e:
                messages.error(request, f"Error implementing recommendation: {str(e)}")
                recommendation.status = 'pending'
        
        recommendation.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True, 
                'message': f"Recommendation {recommendation.status}",
                'status': recommendation.status
            })
        else:
            return redirect('workload_recommendations', board_id=board_id)
    
    context = {
        'board': board,
        'recommendation': recommendation,
        'affected_tasks': recommendation.affected_tasks.all(),
        'affected_users': recommendation.affected_users.all(),
        'is_demo_mode': is_demo_mode,
        'demo_mode_type': demo_mode_type,
    }
    
    return render(request, 'kanban/recommendation_detail.html', context)


def team_capacity_chart(request, board_id):
    """
    API endpoint for team capacity visualization
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check demo access
    has_access, error_response, is_demo_mode = check_demo_access_for_forecasting(request, board)
    if not has_access:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    # Get latest forecasts
    forecasts = ResourceDemandForecast.objects.filter(board=board).order_by('-forecast_date')[:20]
    
    data = {
        'labels': [f.resource_user.get_full_name() if f.resource_user else f.resource_role for f in forecasts],
        'capacity': [float(f.available_capacity_hours) for f in forecasts],
        'workload': [float(f.predicted_workload_hours) for f in forecasts],
        'utilization': [f.utilization_percentage for f in forecasts],
        'overloaded': [f.is_overloaded for f in forecasts],
    }
    
    return JsonResponse(data)


def task_assignment_suggestion(request, board_id, task_id):
    """
    Get suggested assignee for a task based on capacity
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    task = get_object_or_404(Task, id=task_id, column__board=board)
    
    # Check demo access
    has_access, error_response, is_demo_mode = check_demo_access_for_forecasting(request, board)
    if not has_access:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    
    # Find optimal assignee
    optimal_assignee = WorkloadAnalyzer.find_optimal_assignee(task, board, exclude_user=task.assigned_to)
    
    if optimal_assignee:
        return JsonResponse({
            'success': True,
            'suggested_user_id': optimal_assignee.id,
            'suggested_user': optimal_assignee.get_full_name() or optimal_assignee.username,
            'reason': 'Team member has available capacity for this task'
        })
    else:
        return JsonResponse({
            'success': False,
            'message': 'No team members have available capacity'
        })
