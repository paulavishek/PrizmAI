"""
Scope Tracking Views
Handles scope dashboard, baseline management, snapshots, and alert management
Part of the Triple Constraint (Scope, Time, Cost) analysis feature
"""
import logging
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone
from django.db.models import Sum, Avg, Count, Q

from kanban.models import Board, Task, ScopeChangeSnapshot, ScopeCreepAlert
from kanban.utils.scope_analysis import (
    get_scope_trend_data, 
    calculate_scope_velocity,
    analyze_scope_changes_with_ai,
    create_scope_alert_if_needed
)

logger = logging.getLogger(__name__)


@login_required
def scope_dashboard(request, board_id):
    """
    Main Scope Dashboard - comprehensive scope tracking and management
    Shows baseline status, current scope, trends, alerts, and allows management
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Get current scope status
    scope_status = board.get_current_scope_status()
    has_baseline = scope_status is not None
    
    # Get all alerts
    all_alerts = ScopeCreepAlert.objects.filter(board=board).order_by('-detected_at')
    active_alerts = all_alerts.filter(status__in=['active', 'acknowledged'])
    resolved_alerts = all_alerts.filter(status='resolved')
    
    # Get snapshots
    snapshots_queryset = ScopeChangeSnapshot.objects.filter(board=board).order_by('-snapshot_date')
    baseline_snapshot = snapshots_queryset.filter(is_baseline=True).first()
    latest_snapshot = snapshots_queryset.first()
    snapshots = snapshots_queryset[:20]  # Limit to 20 for display
    
    # Get trend data (last 30 days)
    trend_data = get_scope_trend_data(board, days=30) if has_baseline else []
    
    # Calculate velocity
    velocity = calculate_scope_velocity(board, weeks=4) if has_baseline else None
    
    # Count alerts by severity
    critical_count = all_alerts.filter(severity='critical').count()
    warning_count = all_alerts.filter(severity='warning').count()
    info_count = all_alerts.filter(severity='info').count()
    
    # Calculate current task metrics
    tasks = Task.objects.filter(column__board=board)
    current_metrics = {
        'total_tasks': tasks.count(),
        'total_complexity': tasks.aggregate(Sum('complexity_score'))['complexity_score__sum'] or 0,
        'avg_complexity': tasks.aggregate(Avg('complexity_score'))['complexity_score__avg'] or 0,
        'high_priority': tasks.filter(priority='high').count(),
        'urgent_priority': tasks.filter(priority='urgent').count(),
        'todo_tasks': tasks.filter(
            Q(column__name__icontains='to do') | Q(column__name__icontains='backlog')
        ).count(),
        'in_progress_tasks': tasks.filter(
            Q(column__name__icontains='in progress') | Q(column__name__icontains='doing')
        ).count(),
        'completed_tasks': tasks.filter(
            Q(column__name__icontains='done') | Q(column__name__icontains='complete')
        ).count(),
    }
    
    # Prepare trend data for chart
    chart_data = {
        'labels': [item['date'] for item in trend_data],
        'tasks': [item['total_tasks'] for item in trend_data],
        'complexity': [item['complexity'] for item in trend_data],
        'scope_change': [item.get('scope_change_pct', 0) for item in trend_data],
    }
    
    context = {
        'board': board,
        'has_baseline': has_baseline,
        'scope_status': scope_status,
        'current_metrics': current_metrics,
        'all_alerts': all_alerts[:10],
        'active_alerts': active_alerts,
        'resolved_alerts': resolved_alerts[:5],
        'snapshots': snapshots,
        'baseline_snapshot': baseline_snapshot,
        'latest_snapshot': latest_snapshot,
        'trend_data': trend_data,
        'chart_data': chart_data,
        'velocity': velocity,
        'critical_count': critical_count,
        'warning_count': warning_count,
        'info_count': info_count,
    }
    
    return render(request, 'kanban/scope_dashboard.html', context)


@login_required
@require_POST
def set_scope_baseline(request, board_id):
    """
    Set or reset the scope baseline for a board
    This captures the current state as the baseline for scope tracking
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check if there's already a baseline
    existing_baseline = ScopeChangeSnapshot.objects.filter(
        board=board, is_baseline=True
    ).first()
    
    action = request.POST.get('action', 'set')
    notes = request.POST.get('notes', '')
    
    if action == 'reset' and existing_baseline:
        # Remove baseline flag from existing baseline
        existing_baseline.is_baseline = False
        existing_baseline.save()
        
        # Clear board baseline fields
        board.baseline_task_count = None
        board.baseline_complexity_total = None
        board.baseline_set_date = None
        board.baseline_set_by = None
        board.save()
        
        messages.success(request, 'Scope baseline has been reset. You can set a new baseline when ready.')
    else:
        # Prepare notes
        if existing_baseline and not notes:
            notes = f"Baseline reset from {existing_baseline.snapshot_date.strftime('%Y-%m-%d')}"
        
        # Remove baseline flag from existing baseline if any
        if existing_baseline:
            existing_baseline.is_baseline = False
            existing_baseline.save()
        
        # Create new baseline snapshot
        snapshot = board.create_scope_snapshot(
            user=request.user,
            snapshot_type='milestone',
            is_baseline=True,
            notes=notes or 'Initial baseline established'
        )
        
        messages.success(
            request, 
            f'Scope baseline set successfully! Tracking {snapshot.total_tasks} tasks '
            f'({snapshot.total_complexity_points} complexity points).'
        )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': 'Baseline updated successfully',
            'baseline_tasks': board.baseline_task_count,
            'baseline_complexity': board.baseline_complexity_total,
        })
    
    return redirect('scope_dashboard', board_id=board.id)


@login_required
@require_POST
def create_scope_snapshot(request, board_id):
    """
    Create a manual scope snapshot for tracking
    Useful for milestone tracking or periodic reviews
    """
    board = get_object_or_404(Board, id=board_id)
    
    snapshot_type = request.POST.get('snapshot_type', 'manual')
    notes = request.POST.get('notes', '')
    run_ai_analysis = request.POST.get('ai_analysis', 'false') == 'true'
    
    # Create snapshot
    snapshot = board.create_scope_snapshot(
        user=request.user,
        snapshot_type=snapshot_type,
        is_baseline=False,
        notes=notes or f'Manual snapshot - {timezone.now().strftime("%Y-%m-%d %H:%M")}'
    )
    
    # Run AI analysis if requested and there's a baseline
    if run_ai_analysis and snapshot.baseline_snapshot:
        try:
            ai_analysis = analyze_scope_changes_with_ai(snapshot, snapshot.baseline_snapshot)
            snapshot.ai_analysis = ai_analysis
            snapshot.predicted_delay_days = ai_analysis.get('estimated_delay_days')
            snapshot.save()
            
            # Create alert if needed
            alert = create_scope_alert_if_needed(snapshot)
            if alert:
                messages.warning(
                    request,
                    f'Scope alert created: {alert.get_severity_display()} '
                    f'- Scope increased by {alert.scope_increase_percentage:.1f}%'
                )
        except Exception as e:
            logger.error(f"Error running AI analysis: {e}")
            messages.warning(request, 'Snapshot created but AI analysis failed.')
    
    messages.success(
        request,
        f'Scope snapshot created: {snapshot.total_tasks} tasks, '
        f'{snapshot.total_complexity_points} complexity points.'
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'snapshot_id': snapshot.id,
            'total_tasks': snapshot.total_tasks,
            'total_complexity': snapshot.total_complexity_points,
            'scope_change': snapshot.scope_change_percentage,
        })
    
    return redirect('scope_dashboard', board_id=board.id)


@login_required
def scope_snapshot_detail(request, board_id, snapshot_id):
    """
    View detailed information about a specific scope snapshot
    """
    board = get_object_or_404(Board, id=board_id)
    snapshot = get_object_or_404(ScopeChangeSnapshot, id=snapshot_id, board=board)
    
    # Get comparison with baseline
    comparison = None
    if snapshot.baseline_snapshot:
        comparison = {
            'baseline_tasks': snapshot.baseline_snapshot.total_tasks,
            'baseline_complexity': snapshot.baseline_snapshot.total_complexity_points,
            'tasks_change': snapshot.total_tasks - snapshot.baseline_snapshot.total_tasks,
            'complexity_change': snapshot.total_complexity_points - snapshot.baseline_snapshot.total_complexity_points,
            'scope_pct': snapshot.scope_change_percentage,
            'complexity_pct': snapshot.complexity_change_percentage,
        }
    
    context = {
        'board': board,
        'snapshot': snapshot,
        'comparison': comparison,
    }
    
    return render(request, 'kanban/scope_snapshot_detail.html', context)


@login_required
@require_POST
def acknowledge_scope_alert(request, board_id, alert_id):
    """
    Acknowledge a scope creep alert
    """
    board = get_object_or_404(Board, id=board_id)
    alert = get_object_or_404(ScopeCreepAlert, id=alert_id, board=board)
    
    alert.acknowledge(request.user)
    messages.success(request, 'Alert acknowledged.')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'status': 'acknowledged'})
    
    return redirect('scope_dashboard', board_id=board.id)


@login_required
@require_POST
def resolve_scope_alert(request, board_id, alert_id):
    """
    Resolve a scope creep alert with optional notes
    """
    board = get_object_or_404(Board, id=board_id)
    alert = get_object_or_404(ScopeCreepAlert, id=alert_id, board=board)
    
    notes = request.POST.get('notes', '')
    alert.resolve(request.user, notes=notes)
    messages.success(request, 'Alert resolved.')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'status': 'resolved'})
    
    return redirect('scope_dashboard', board_id=board.id)


@login_required
@require_POST
def dismiss_scope_alert(request, board_id, alert_id):
    """
    Dismiss a scope creep alert (mark as not applicable)
    """
    board = get_object_or_404(Board, id=board_id)
    alert = get_object_or_404(ScopeCreepAlert, id=alert_id, board=board)
    
    alert.status = 'dismissed'
    alert.resolved_at = timezone.now()
    alert.resolved_by = request.user
    alert.resolution_notes = request.POST.get('notes', 'Dismissed by user')
    alert.save()
    
    messages.info(request, 'Alert dismissed.')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'status': 'dismissed'})
    
    return redirect('scope_dashboard', board_id=board.id)


@login_required
@require_POST
def run_scope_analysis(request, board_id):
    """
    Run AI analysis on current scope vs baseline
    Creates a new snapshot with AI-powered insights
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check if baseline exists
    if not board.baseline_task_count:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'No baseline set. Please set a baseline first.'
            }, status=400)
        messages.error(request, 'No baseline set. Please set a baseline first.')
        return redirect('scope_dashboard', board_id=board.id)
    
    # Create a new snapshot with AI analysis
    snapshot = board.create_scope_snapshot(
        user=request.user,
        snapshot_type='manual',
        is_baseline=False,
        notes='AI analysis snapshot'
    )
    
    # Get baseline snapshot
    baseline = ScopeChangeSnapshot.objects.filter(
        board=board, is_baseline=True
    ).order_by('-snapshot_date').first()
    
    if baseline:
        try:
            ai_analysis = analyze_scope_changes_with_ai(snapshot, baseline)
            snapshot.ai_analysis = ai_analysis
            snapshot.predicted_delay_days = ai_analysis.get('estimated_delay_days')
            snapshot.save()
            
            # Create alert if necessary
            alert = create_scope_alert_if_needed(snapshot)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'analysis': ai_analysis,
                    'alert_created': alert is not None,
                    'alert_severity': alert.severity if alert else None,
                })
            
            messages.success(request, 'AI analysis completed successfully.')
            if alert:
                messages.warning(
                    request, 
                    f'Scope alert created: {alert.get_severity_display()}'
                )
                
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'AI analysis failed. Please try again.'
                }, status=500)
            messages.error(request, 'AI analysis failed. Please try again.')
    
    return redirect('scope_dashboard', board_id=board.id)


@login_required
def scope_api_metrics(request, board_id):
    """
    API endpoint for scope metrics - used for dashboard widgets
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Get current status
    scope_status = board.get_current_scope_status()
    
    # Get active alerts count
    active_alerts_count = ScopeCreepAlert.objects.filter(
        board=board,
        status__in=['active', 'acknowledged']
    ).count()
    
    # Get latest snapshot
    latest_snapshot = ScopeChangeSnapshot.objects.filter(
        board=board
    ).order_by('-snapshot_date').first()
    
    data = {
        'has_baseline': scope_status is not None,
        'scope_status': scope_status,
        'active_alerts_count': active_alerts_count,
        'latest_snapshot': {
            'date': latest_snapshot.snapshot_date.isoformat() if latest_snapshot else None,
            'total_tasks': latest_snapshot.total_tasks if latest_snapshot else 0,
            'scope_change': latest_snapshot.scope_change_percentage if latest_snapshot else 0,
        } if latest_snapshot else None
    }
    
    return JsonResponse(data)


@login_required
def scope_comparison(request, board_id):
    """
    Compare two scope snapshots side by side
    """
    board = get_object_or_404(Board, id=board_id)
    
    snapshot1_id = request.GET.get('snapshot1')
    snapshot2_id = request.GET.get('snapshot2')
    
    snapshots = ScopeChangeSnapshot.objects.filter(board=board).order_by('-snapshot_date')
    
    snapshot1 = None
    snapshot2 = None
    comparison = None
    
    if snapshot1_id and snapshot2_id:
        snapshot1 = get_object_or_404(ScopeChangeSnapshot, id=snapshot1_id, board=board)
        snapshot2 = get_object_or_404(ScopeChangeSnapshot, id=snapshot2_id, board=board)
        
        comparison = {
            'tasks_diff': snapshot2.total_tasks - snapshot1.total_tasks,
            'complexity_diff': snapshot2.total_complexity_points - snapshot1.total_complexity_points,
            'high_priority_diff': snapshot2.high_priority_tasks - snapshot1.high_priority_tasks,
            'urgent_priority_diff': snapshot2.urgent_priority_tasks - snapshot1.urgent_priority_tasks,
            'todo_diff': snapshot2.todo_tasks - snapshot1.todo_tasks,
            'in_progress_diff': snapshot2.in_progress_tasks - snapshot1.in_progress_tasks,
            'completed_diff': snapshot2.completed_tasks - snapshot1.completed_tasks,
        }
        
        if snapshot1.total_tasks > 0:
            comparison['tasks_pct'] = round(
                (comparison['tasks_diff'] / snapshot1.total_tasks) * 100, 2
            )
        else:
            comparison['tasks_pct'] = 0
    
    context = {
        'board': board,
        'snapshots': snapshots,
        'snapshot1': snapshot1,
        'snapshot2': snapshot2,
        'comparison': comparison,
    }
    
    return render(request, 'kanban/scope_comparison.html', context)
