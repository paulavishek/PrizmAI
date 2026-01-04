"""
Budget & ROI Tracking Views
Handles budget dashboard, analytics, and AI recommendations
"""
import logging
import time
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Sum, Avg, Count, Q
from django.db import models
import json

from kanban.models import Board, Task
from kanban.budget_models import (
    ProjectBudget, TaskCost, TimeEntry, ProjectROI, 
    BudgetRecommendation, CostPattern
)
from kanban.budget_utils import BudgetAnalyzer, ROICalculator
from kanban.budget_ai import BudgetAIOptimizer
from kanban.budget_forms import (
    ProjectBudgetForm, TaskCostForm, TimeEntryForm, 
    ProjectROIForm, BudgetRecommendationActionForm
)
from api.ai_usage_utils import track_ai_request, check_ai_quota
from kanban.utils.demo_limits import (
    check_ai_generation_limit, 
    increment_ai_generation_count, 
    record_limitation_hit
)

logger = logging.getLogger(__name__)


def budget_dashboard(request, board_id):
    """
    Main budget dashboard showing overview, metrics, and AI insights
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check if this is a demo board
    demo_org_names = ['Demo - Acme Corporation']
    is_demo_board = board.organization.name in demo_org_names
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')
    
    # For non-demo boards, require authentication
    if not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        # Check access - all boards require membership
        if not (board.created_by == request.user or request.user in board.members.all()):
            return HttpResponseForbidden("You don't have permission to access this board.")
    
    # For demo boards in team mode, check role-based permissions
    elif demo_mode_type == 'team':
        from kanban.utils.demo_permissions import DemoPermissions
        if not DemoPermissions.can_perform_action(request, 'can_use_ai_features'):
            return HttpResponseForbidden("You don't have permission to view budget in your current demo role.")
    # Solo demo mode: full access, no restrictions
    
    # Get or create budget
    try:
        budget = ProjectBudget.objects.get(board=board)
        has_budget = True
    except ProjectBudget.DoesNotExist:
        budget = None
        has_budget = False
    
    # Calculate metrics if budget exists
    metrics = None
    roi_metrics = None
    burn_rate = None
    recommendations = []
    
    if has_budget:
        metrics = BudgetAnalyzer.calculate_project_metrics(board)
        roi_metrics = BudgetAnalyzer.calculate_roi_metrics(board)
        burn_rate = BudgetAnalyzer.calculate_burn_rate(board)
        
        # Get pending recommendations
        recommendations = BudgetRecommendation.objects.filter(
            board=board,
            status='pending'
        ).order_by('-priority', '-created_at')[:5]
    
    # Get recent time entries
    recent_entries = TimeEntry.objects.filter(
        task__column__board=board
    ).select_related('user', 'task').order_by('-created_at')[:10]
    
    context = {
        'board': board,
        'budget': budget,
        'has_budget': has_budget,
        'metrics': metrics,
        'roi_metrics': roi_metrics,
        'burn_rate': burn_rate,
        'recommendations': recommendations,
        'recent_entries': recent_entries,
        'is_demo_mode': is_demo_mode,
        'is_demo_board': is_demo_board,
    }
    
    return render(request, 'kanban/budget_dashboard.html', context)


def budget_create_or_edit(request, board_id):
    """
    Create or edit project budget
    Note: Budget creation is disabled in TEAM demo mode only.
    SOLO demo mode has full access.
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check if this is a demo board
    demo_org_names = ['Demo - Acme Corporation']
    is_demo_board = board.organization.name in demo_org_names
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')
    
    # In TEAM demo mode only, redirect to budget dashboard (view only)
    # Solo demo mode has full access
    if is_demo_board and is_demo_mode and demo_mode_type == 'team':
        messages.info(request, 'Budget creation/editing is disabled in team demo mode. You can view the existing demo budget.')
        return redirect('budget_dashboard', board_id=board.id)
    
    # For non-demo boards, require authentication
    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())
    
    if not _can_access_board(request.user, board):
        return HttpResponseForbidden("You don't have permission to access this board.")
    
    try:
        budget = ProjectBudget.objects.get(board=board)
        is_new = False
    except ProjectBudget.DoesNotExist:
        budget = None
        is_new = True
    
    if request.method == 'POST':
        form = ProjectBudgetForm(request.POST, instance=budget)
        if form.is_valid():
            budget = form.save(commit=False)
            budget.board = board
            if is_new:
                budget.created_by = request.user
            budget.save()
            messages.success(request, 'Budget saved successfully!')
            return redirect('budget_dashboard', board_id=board.id)
    else:
        form = ProjectBudgetForm(instance=budget)
    
    context = {
        'board': board,
        'form': form,
        'is_new': is_new,
    }
    
    return render(request, 'kanban/budget_form.html', context)


@login_required
def task_cost_edit(request, task_id):
    """
    Edit task cost details
    """
    task = get_object_or_404(Task, id=task_id)
    board = task.column.board
    
    if not _can_access_board(request.user, board):
        return HttpResponseForbidden("You don't have permission to access this task.")
    
    try:
        task_cost = TaskCost.objects.get(task=task)
    except TaskCost.DoesNotExist:
        task_cost = None
    
    if request.method == 'POST':
        form = TaskCostForm(request.POST, instance=task_cost)
        if form.is_valid():
            cost = form.save(commit=False)
            cost.task = task
            cost.save()
            messages.success(request, f'Cost updated for task: {task.title}')
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Cost updated successfully'
                })
            return redirect('budget_dashboard', board_id=board.id)
    else:
        form = TaskCostForm(instance=task_cost)
    
    context = {
        'task': task,
        'form': form,
        'board': board,
    }
    
    return render(request, 'kanban/task_cost_form.html', context)


@login_required
def time_entry_create(request, task_id):
    """
    Create time entry for a task
    """
    task = get_object_or_404(Task, id=task_id)
    board = task.column.board
    
    if not _can_access_board(request.user, board):
        return HttpResponseForbidden("You don't have permission to access this task.")
    
    if request.method == 'POST':
        form = TimeEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.task = task
            entry.user = request.user
            entry.save()
            messages.success(request, f'Time logged: {entry.hours_spent} hours')
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Time logged successfully',
                    'entry_id': entry.id
                })
            return redirect('budget_dashboard', board_id=board.id)
    else:
        form = TimeEntryForm(initial={'work_date': timezone.now().date()})
    
    context = {
        'task': task,
        'form': form,
        'board': board,
    }
    
    return render(request, 'kanban/time_entry_form.html', context)


def budget_analytics(request, board_id):
    """
    Detailed budget analytics and reports
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check if this is a demo board
    demo_org_names = ['Demo - Acme Corporation']
    is_demo_board = board.organization.name in demo_org_names
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')
    
    # For non-demo boards, require authentication
    if not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        # Check access - all boards require membership
        if not (board.created_by == request.user or request.user in board.members.all()):
            return HttpResponseForbidden("You don't have permission to access this board.")
    
    # For demo boards in team mode, check role-based permissions
    elif demo_mode_type == 'team':
        from kanban.utils.demo_permissions import DemoPermissions
        if not DemoPermissions.can_perform_action(request, 'can_use_ai_features'):
            return HttpResponseForbidden("You don't have permission to view budget analytics in your current demo role.")
    # Solo demo mode: full access, no restrictions
    
    try:
        budget = ProjectBudget.objects.get(board=board)
    except ProjectBudget.DoesNotExist:
        messages.warning(request, 'Please create a budget first.')
        return redirect('budget_create_or_edit', board_id=board.id)
    
    # Get comprehensive analytics
    metrics = BudgetAnalyzer.calculate_project_metrics(board)
    cost_breakdown = BudgetAnalyzer.get_task_cost_breakdown(board)
    overruns = BudgetAnalyzer.identify_cost_overruns(board)
    trend_data_result = BudgetAnalyzer.get_cost_trend_data(board, days=30)
    trend_data = trend_data_result.get('trend_data', [])
    
    # Calculate additional metrics for analytics page
    from kanban.budget_models import TimeEntry
    from decimal import Decimal
    
    # Get burn rate and days remaining
    burn_rate_data = BudgetAnalyzer.calculate_burn_rate(board, period_days=7)
    
    # Get total time logged
    total_time_logged = TimeEntry.objects.filter(
        task__column__board=board
    ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
    
    # Calculate cost per hour
    cost_per_hour = Decimal('0.00')
    if total_time_logged > 0:
        cost_per_hour = metrics['budget']['spent'] / float(total_time_logged)
    
    # Calculate projected final cost based on completion rate
    projected_final_cost = metrics['budget']['spent']
    if metrics['tasks']['completion_rate'] > 0:
        projected_final_cost = (metrics['budget']['spent'] / metrics['tasks']['completion_rate']) * 100
    
    # Calculate projected overrun
    projected_overrun = max(0, projected_final_cost - metrics['budget']['allocated'])
    
    # Add these to metrics
    metrics['burn_rate'] = burn_rate_data.get('daily_burn_rate', 0)
    metrics['days_remaining'] = burn_rate_data.get('days_until_depleted', 0)
    metrics['total_time_logged'] = float(total_time_logged)
    metrics['cost_per_hour'] = float(cost_per_hour)
    metrics['projected_final_cost'] = projected_final_cost
    metrics['projected_overrun'] = projected_overrun
    metrics['budget']['allocated_90_percent'] = metrics['budget']['allocated'] * 0.9
    
    context = {
        'board': board,
        'budget': budget,
        'metrics': metrics,
        'cost_breakdown': cost_breakdown,
        'overruns': overruns,
        'trend_data': trend_data,
        'is_demo_mode': is_demo_mode,
        'is_demo_board': is_demo_board,
    }
    
    return render(request, 'kanban/budget_analytics.html', context)


def roi_dashboard(request, board_id):
    """
    ROI tracking and analysis dashboard
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check if this is a demo board
    demo_org_names = ['Demo - Acme Corporation']
    is_demo_board = board.organization.name in demo_org_names
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')
    
    # For non-demo boards, require authentication
    if not (is_demo_board and is_demo_mode):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        # Check access - all boards require membership
        if not (board.created_by == request.user or request.user in board.members.all()):
            return HttpResponseForbidden("You don't have permission to access this board.")
    
    # For demo boards in team mode, check role-based permissions
    elif demo_mode_type == 'team':
        from kanban.utils.demo_permissions import DemoPermissions
        if not DemoPermissions.can_perform_action(request, 'can_use_ai_features'):
            return HttpResponseForbidden("You don't have permission to view ROI dashboard in your current demo role.")
    # Solo demo mode: full access, no restrictions
    
    # Check if budget exists
    try:
        budget = ProjectBudget.objects.get(board=board)
        has_budget = True
    except ProjectBudget.DoesNotExist:
        budget = None
        has_budget = False
    
    # Get ROI metrics
    roi_metrics = BudgetAnalyzer.calculate_roi_metrics(board)
    
    # Get historical ROI snapshots
    roi_snapshots = ProjectROI.objects.filter(board=board).order_by('-snapshot_date')[:10]
    
    context = {
        'board': board,
        'budget': budget,
        'has_budget': has_budget,
        'roi_metrics': roi_metrics,
        'roi_snapshots': roi_snapshots,
        'is_demo_mode': is_demo_mode,
        'is_demo_board': is_demo_board,
    }
    
    return render(request, 'kanban/roi_dashboard.html', context)


@login_required
def roi_snapshot_create(request, board_id):
    """
    Create new ROI snapshot
    """
    board = get_object_or_404(Board, id=board_id)
    
    if not _can_access_board(request.user, board):
        return HttpResponseForbidden("You don't have permission to access this board.")
    
    if request.method == 'POST':
        form = ProjectROIForm(request.POST)
        if form.is_valid():
            expected_value = form.cleaned_data.get('expected_value')
            realized_value = form.cleaned_data.get('realized_value')
            
            result = ROICalculator.create_roi_snapshot(
                board=board,
                user=request.user,
                expected_value=expected_value,
                realized_value=realized_value
            )
            
            messages.success(request, 'ROI snapshot created successfully!')
            return redirect('roi_dashboard', board_id=board.id)
    else:
        form = ProjectROIForm()
    
    context = {
        'board': board,
        'form': form,
    }
    
    return render(request, 'kanban/roi_snapshot_form.html', context)


@login_required
@require_http_methods(["POST"])
def ai_analyze_budget(request, board_id):
    """
    Trigger AI budget analysis
    """
    start_time = time.time()
    board = get_object_or_404(Board, id=board_id)
    
    if not _can_access_board(request.user, board):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        # Check demo mode AI generation limit first
        ai_limit_status = check_ai_generation_limit(request)
        if ai_limit_status['is_demo'] and not ai_limit_status['can_generate']:
            record_limitation_hit(request, 'ai_limit')
            return JsonResponse({
                'error': ai_limit_status['message'],
                'quota_exceeded': True,
                'demo_limit': True
            }, status=429)
        
        # Check AI quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)
        
        # Check if budget exists
        budget = ProjectBudget.objects.get(board=board)
        
        if not budget.ai_optimization_enabled:
            return JsonResponse({
                'error': 'AI optimization is disabled for this budget'
            }, status=400)
        
        # Run AI analysis
        optimizer = BudgetAIOptimizer(board)
        results = optimizer.analyze_budget_health()
        
        if 'error' in results:
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='budget_analysis',
                request_type='analyze',
                board_id=board.id,
                success=False,
                error_message=results['error'],
                response_time_ms=response_time_ms
            )
            return JsonResponse({'error': results['error']}, status=400)
        
        # Increment demo AI generation count on success
        increment_ai_generation_count(request)
        
        # Track successful request
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='budget_analysis',
            request_type='analyze',
            board_id=board.id,
            success=True,
            response_time_ms=response_time_ms
        )
        
        return JsonResponse({
            'success': True,
            'analysis': results
        })
        
    except ProjectBudget.DoesNotExist:
        return JsonResponse({'error': 'No budget configured'}, status=400)
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='budget_analysis',
            request_type='analyze',
            board_id=board.id,
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms
        )
        logger.error(f"Error in AI budget analysis: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def ai_generate_recommendations(request, board_id):
    """
    Generate AI-powered budget recommendations
    """
    start_time = time.time()
    board = get_object_or_404(Board, id=board_id)
    
    if not _can_access_board(request.user, board):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        # Check demo mode AI generation limit first
        ai_limit_status = check_ai_generation_limit(request)
        if ai_limit_status['is_demo'] and not ai_limit_status['can_generate']:
            record_limitation_hit(request, 'ai_limit')
            return JsonResponse({
                'error': ai_limit_status['message'],
                'quota_exceeded': True,
                'demo_limit': True
            }, status=429)
        
        # Check AI quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)
        
        budget = ProjectBudget.objects.get(board=board)
        
        if not budget.ai_optimization_enabled:
            return JsonResponse({
                'error': 'AI optimization is disabled'
            }, status=400)
        
        # Get optional context from request
        context = None
        if request.body:
            data = json.loads(request.body)
            context = data.get('context')
        
        # Generate recommendations
        optimizer = BudgetAIOptimizer(board)
        recommendations = optimizer.generate_recommendations(context=context)
        
        # Increment demo AI generation count on success
        increment_ai_generation_count(request)
        
        # Track successful request
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='budget_recommendations',
            request_type='generate',
            board_id=board.id,
            success=True,
            response_time_ms=response_time_ms
        )
        
        return JsonResponse({
            'success': True,
            'recommendations': recommendations,
            'count': len(recommendations)
        })
        
    except ProjectBudget.DoesNotExist:
        return JsonResponse({'error': 'No budget configured'}, status=400)
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='budget_recommendations',
            request_type='generate',
            board_id=board.id,
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms
        )
        logger.error(f"Error generating recommendations: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def recommendations_list(request, board_id):
    """
    View all budget recommendations
    """
    board = get_object_or_404(Board, id=board_id)
    
    if not _can_access_board(request.user, board):
        return HttpResponseForbidden("You don't have permission to access this board.")
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    recommendations = BudgetRecommendation.objects.filter(board=board)
    
    if status_filter != 'all':
        recommendations = recommendations.filter(status=status_filter)
    
    recommendations = recommendations.order_by('-priority', '-created_at')
    
    context = {
        'board': board,
        'recommendations': recommendations,
        'status_filter': status_filter,
    }
    
    return render(request, 'kanban/recommendations_list.html', context)


@login_required
@require_http_methods(["POST"])
def recommendation_action(request, recommendation_id):
    """
    Accept, reject, or mark recommendation as implemented
    """
    recommendation = get_object_or_404(BudgetRecommendation, id=recommendation_id)
    board = recommendation.board
    
    if not _can_access_board(request.user, board):
        messages.error(request, "You don't have permission to access this board.")
        return redirect('budget_dashboard', board_id=board.id)
    
    try:
        # Get action from POST data (form submission)
        action = request.POST.get('action')  # 'accept', 'reject', 'implement'
        
        if action == 'accept':
            recommendation.status = 'accepted'
            messages.success(request, f'Recommendation "{recommendation.title}" has been accepted.')
        elif action == 'reject':
            recommendation.status = 'rejected'
            messages.info(request, f'Recommendation "{recommendation.title}" has been rejected.')
        elif action == 'implement':
            recommendation.status = 'implemented'
            messages.success(request, f'Recommendation "{recommendation.title}" has been marked as implemented.')
        else:
            messages.error(request, 'Invalid action.')
            return redirect('recommendations_list', board_id=board.id)
        
        recommendation.reviewed_by = request.user
        recommendation.reviewed_at = timezone.now()
        recommendation.save()
        
        return redirect('recommendations_list', board_id=board.id)
        
    except Exception as e:
        logger.error(f"Error updating recommendation: {e}")
        messages.error(request, f'Error updating recommendation: {str(e)}')
        return redirect('recommendations_list', board_id=board.id)


@login_required
@require_http_methods(["POST"])
def ai_predict_overrun(request, board_id):
    """
    Get AI prediction for cost overruns
    """
    start_time = time.time()
    board = get_object_or_404(Board, id=board_id)
    
    if not _can_access_board(request.user, board):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        # Check demo mode AI generation limit first
        ai_limit_status = check_ai_generation_limit(request)
        if ai_limit_status['is_demo'] and not ai_limit_status['can_generate']:
            record_limitation_hit(request, 'ai_limit')
            return JsonResponse({
                'error': ai_limit_status['message'],
                'quota_exceeded': True,
                'demo_limit': True
            }, status=429)
        
        # Check AI quota
        has_quota, quota, remaining = check_ai_quota(request.user)
        if not has_quota:
            return JsonResponse({
                'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
                'quota_exceeded': True
            }, status=429)
        
        budget = ProjectBudget.objects.get(board=board)
        
        if not budget.ai_optimization_enabled:
            return JsonResponse({'error': 'AI optimization is disabled'}, status=400)
        
        optimizer = BudgetAIOptimizer(board)
        prediction = optimizer.predict_cost_overrun()
        
        if 'error' in prediction:
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='budget_prediction',
                request_type='predict_overrun',
                board_id=board.id,
                success=False,
                error_message=prediction['error'],
                response_time_ms=response_time_ms
            )
            return JsonResponse({'error': prediction['error']}, status=400)
        
        # Increment demo AI generation count on success
        increment_ai_generation_count(request)
        
        # Track successful request
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='budget_prediction',
            request_type='predict_overrun',
            board_id=board.id,
            success=True,
            response_time_ms=response_time_ms
        )
        
        return JsonResponse({
            'success': True,
            'prediction': prediction
        })
        
    except ProjectBudget.DoesNotExist:
        return JsonResponse({'error': 'No budget configured'}, status=400)
    except Exception as e:
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='budget_prediction',
            request_type='predict_overrun',
            board_id=board.id,
            success=False,
            error_message=str(e),
            response_time_ms=response_time_ms
        )
        logger.error(f"Error predicting overrun: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def ai_learn_patterns(request, board_id):
    """
    Trigger AI pattern learning
    """
    board = get_object_or_404(Board, id=board_id)
    
    if not _can_access_board(request.user, board):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        budget = ProjectBudget.objects.get(board=board)
        
        if not budget.ai_optimization_enabled:
            return JsonResponse({'error': 'AI optimization is disabled'}, status=400)
        
        optimizer = BudgetAIOptimizer(board)
        results = optimizer.learn_cost_patterns()
        
        if 'error' in results:
            return JsonResponse({'error': results['error']}, status=400)
        
        return JsonResponse({
            'success': True,
            'results': results
        })
        
    except ProjectBudget.DoesNotExist:
        return JsonResponse({'error': 'No budget configured'}, status=400)
    except Exception as e:
        logger.error(f"Error learning patterns: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def budget_api_metrics(request, board_id):
    """
    API endpoint for budget metrics (for AJAX updates)
    """
    board = get_object_or_404(Board, id=board_id)
    
    if not _can_access_board(request.user, board):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        metrics = BudgetAnalyzer.calculate_project_metrics(board)
        roi_metrics = BudgetAnalyzer.calculate_roi_metrics(board)
        burn_rate = BudgetAnalyzer.calculate_burn_rate(board)
        
        return JsonResponse({
            'success': True,
            'metrics': metrics,
            'roi_metrics': roi_metrics,
            'burn_rate': burn_rate,
            'timestamp': timezone.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def _can_access_board(user, board):
    """
    Check if user can access the board - requires board membership or demo org access
    Note: This function assumes the user is authenticated. For demo mode, check before calling this.
    """
    # If user is not authenticated, return False (demo mode should be checked before calling this)
    if not user.is_authenticated:
        return False
    
    # Direct membership or creator
    if board.created_by == user or user in board.members.all():
        return True
    
    # Demo boards: organization-level access
    demo_org_names = ['Demo - Acme Corporation']
    if board.organization.name in demo_org_names:
        # Check if user has access to any board in this demo organization
        from kanban.models import Board as BoardModel
        return BoardModel.objects.filter(
            organization=board.organization,
            members=user
        ).exists()
    
    return False


# ============================================================================
# TIME TRACKING VIEWS
# ============================================================================

@login_required
def my_timesheet(request, board_id=None):
    """
    User's personal timesheet view with weekly grid for time entry
    """
    from datetime import datetime, timedelta
    from django.db.models import Sum
    
    # Get week parameter or default to current week
    week_offset = int(request.GET.get('week', 0))
    today = timezone.now().date()
    # Start of week (Monday)
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    end_of_week = start_of_week + timedelta(days=6)
    
    # Get user's tasks
    if board_id:
        board = get_object_or_404(Board, id=board_id)
        if not _can_access_board(request.user, board):
            return HttpResponseForbidden("You don't have permission to access this board.")
        tasks = Task.objects.filter(
            column__board=board,
            assigned_to=request.user
        ).select_related('column', 'column__board')
        boards = [board]
    else:
        # All boards user has access to
        boards = Board.objects.filter(
            models.Q(created_by=request.user) | models.Q(members=request.user)
        ).distinct()
        tasks = Task.objects.filter(
            column__board__in=boards,
            assigned_to=request.user
        ).select_related('column', 'column__board')
    
    # Get time entries for the week
    entries = TimeEntry.objects.filter(
        user=request.user,
        work_date__gte=start_of_week,
        work_date__lte=end_of_week
    ).select_related('task', 'task__column', 'task__column__board')
    
    # Organize entries by task and date
    entries_by_task_date = {}
    for entry in entries:
        key = (entry.task.id, entry.work_date)
        entries_by_task_date[key] = entry
    
    # Build week days
    week_days = []
    for i in range(7):
        day = start_of_week + timedelta(days=i)
        week_days.append({
            'date': day,
            'is_today': day == today,
            'is_weekend': day.weekday() >= 5,
            'day_name': day.strftime('%a'),
        })
    
    # Build task rows with entries
    task_rows = []
    for task in tasks:
        row = {
            'task': task,
            'entries': [],
            'total_hours': Decimal('0.00'),
        }
        for day in week_days:
            entry = entries_by_task_date.get((task.id, day['date']))
            row['entries'].append({
                'date': day['date'],
                'entry': entry,
                'hours': entry.hours_spent if entry else Decimal('0.00'),
            })
            if entry:
                row['total_hours'] += entry.hours_spent
        task_rows.append(row)
    
    # Calculate daily totals
    daily_totals = []
    for day in week_days:
        total = entries.filter(work_date=day['date']).aggregate(
            total=Sum('hours_spent')
        )['total'] or Decimal('0.00')
        daily_totals.append(total)
    
    week_total = sum(daily_totals, Decimal('0.00'))
    
    # Previous/next week dates
    prev_week = week_offset - 1
    next_week = week_offset + 1
    
    context = {
        'board': board if board_id else None,
        'boards': boards,
        'tasks': tasks,
        'task_rows': task_rows,
        'week_days': week_days,
        'daily_totals': daily_totals,
        'week_total': week_total,
        'start_of_week': start_of_week,
        'end_of_week': end_of_week,
        'prev_week': prev_week,
        'next_week': next_week,
        'week_offset': week_offset,
    }
    
    return render(request, 'kanban/my_timesheet.html', context)


@login_required
def time_tracking_dashboard(request, board_id=None):
    """
    Time tracking dashboard with stats, recent entries, and quick actions
    """
    from datetime import timedelta
    from django.db.models import Sum, Count, Avg
    
    # Filter by board if specified
    if board_id:
        board = get_object_or_404(Board, id=board_id)
        if not _can_access_board(request.user, board):
            return HttpResponseForbidden("You don't have permission to access this board.")
        boards = [board]
    else:
        boards = Board.objects.filter(
            models.Q(created_by=request.user) | models.Q(members=request.user)
        ).distinct()
        board = None
    
    # Get time entries
    entries = TimeEntry.objects.filter(user=request.user)
    if board_id:
        entries = entries.filter(task__column__board=board)
    
    # Date ranges
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    
    # Calculate metrics
    today_hours = entries.filter(work_date=today).aggregate(
        total=Sum('hours_spent')
    )['total'] or Decimal('0.00')
    
    week_hours = entries.filter(
        work_date__gte=week_start,
        work_date__lte=today
    ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
    
    month_hours = entries.filter(
        work_date__gte=month_start,
        work_date__lte=today
    ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
    
    total_hours = entries.aggregate(
        total=Sum('hours_spent')
    )['total'] or Decimal('0.00')
    
    # Recent entries
    recent_entries = entries.select_related(
        'task', 'task__column', 'task__column__board'
    ).order_by('-work_date', '-created_at')[:10]
    
    # Tasks with time logged
    tasks_with_time = Task.objects.filter(
        time_entries__user=request.user
    )
    if board_id:
        tasks_with_time = tasks_with_time.filter(column__board=board)
    
    tasks_with_time = tasks_with_time.annotate(
        total_hours=Sum('time_entries__hours_spent')
    ).order_by('-total_hours')[:10]
    
    # Daily chart data (last 14 days)
    chart_data = []
    for i in range(13, -1, -1):
        date = today - timedelta(days=i)
        daily_hours = entries.filter(work_date=date).aggregate(
            total=Sum('hours_spent')
        )['total'] or Decimal('0.00')
        chart_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'day': date.strftime('%a'),
            'hours': float(daily_hours),
        })
    
    # My tasks needing time entry (assigned and not done)
    my_tasks = Task.objects.filter(
        assigned_to=request.user,
        progress__lt=100
    )
    if board_id:
        my_tasks = my_tasks.filter(column__board=board)
    
    my_tasks = my_tasks.select_related('column', 'column__board')[:20]
    
    # Serialize chart data for JavaScript
    import json
    chart_data_json = json.dumps(chart_data)
    
    context = {
        'board': board,
        'boards': boards,
        'today_hours': today_hours,
        'week_hours': week_hours,
        'month_hours': month_hours,
        'total_hours': total_hours,
        'recent_entries': recent_entries,
        'tasks_with_time': tasks_with_time,
        'chart_data': chart_data_json,
        'my_tasks': my_tasks,
    }
    
    return render(request, 'kanban/time_tracking_dashboard.html', context)


@login_required
def team_timesheet(request, board_id):
    """
    Team timesheet view for managers to see all team member time entries
    """
    from datetime import timedelta
    from django.db.models import Sum
    
    board = get_object_or_404(Board, id=board_id)
    
    if not _can_access_board(request.user, board):
        return HttpResponseForbidden("You don't have permission to access this board.")
    
    # Get week parameter
    week_offset = int(request.GET.get('week', 0))
    today = timezone.now().date()
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    end_of_week = start_of_week + timedelta(days=6)
    
    # Get all time entries for this board in the week
    entries = TimeEntry.objects.filter(
        task__column__board=board,
        work_date__gte=start_of_week,
        work_date__lte=end_of_week
    ).select_related('user', 'task')
    
    # Group by user
    users_data = {}
    for entry in entries:
        if entry.user.id not in users_data:
            users_data[entry.user.id] = {
                'user': entry.user,
                'total_hours': Decimal('0.00'),
                'entries_count': 0,
                'daily_hours': {},
            }
        users_data[entry.user.id]['total_hours'] += entry.hours_spent
        users_data[entry.user.id]['entries_count'] += 1
        
        date_str = entry.work_date.isoformat()
        if date_str not in users_data[entry.user.id]['daily_hours']:
            users_data[entry.user.id]['daily_hours'][date_str] = Decimal('0.00')
        users_data[entry.user.id]['daily_hours'][date_str] += entry.hours_spent
    
    # Build week days
    week_days = []
    for i in range(7):
        day = start_of_week + timedelta(days=i)
        week_days.append({
            'date': day,
            'is_today': day == today,
            'is_weekend': day.weekday() >= 5,
            'day_name': day.strftime('%a'),
        })
    
    # Build user rows
    user_rows = []
    for user_data in sorted(users_data.values(), key=lambda x: x['total_hours'], reverse=True):
        row = {
            'user': user_data['user'],
            'daily_hours': [],
            'total_hours': user_data['total_hours'],
            'entries_count': user_data['entries_count'],
        }
        for day in week_days:
            date_str = day['date'].isoformat()
            hours = user_data['daily_hours'].get(date_str, Decimal('0.00'))
            row['daily_hours'].append(hours)
        user_rows.append(row)
    
    # Calculate daily totals
    daily_totals = []
    for day in week_days:
        total = entries.filter(work_date=day['date']).aggregate(
            total=Sum('hours_spent')
        )['total'] or Decimal('0.00')
        daily_totals.append(total)
    
    week_total = sum(daily_totals, Decimal('0.00'))
    
    prev_week = week_offset - 1
    next_week = week_offset + 1
    
    context = {
        'board': board,
        'user_rows': user_rows,
        'week_days': week_days,
        'daily_totals': daily_totals,
        'week_total': week_total,
        'start_of_week': start_of_week,
        'end_of_week': end_of_week,
        'prev_week': prev_week,
        'next_week': next_week,
        'week_offset': week_offset,
    }
    
    return render(request, 'kanban/team_timesheet.html', context)


@login_required
@require_http_methods(["POST"])
def quick_time_entry(request, task_id):
    """
    Quick time entry API for inline logging
    """
    task = get_object_or_404(Task, id=task_id)
    board = task.column.board
    
    if not _can_access_board(request.user, board):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    try:
        hours = Decimal(request.POST.get('hours', '0'))
        description = request.POST.get('description', '').strip()
        work_date_str = request.POST.get('work_date', timezone.now().date().isoformat())
        work_date = timezone.datetime.fromisoformat(work_date_str).date()
        
        if hours <= 0:
            return JsonResponse({'success': False, 'error': 'Hours must be greater than 0'}, status=400)
        
        entry = TimeEntry.objects.create(
            task=task,
            user=request.user,
            hours_spent=hours,
            work_date=work_date,
            description=description
        )
        
        # Calculate total time logged on task
        total_time = TimeEntry.objects.filter(task=task).aggregate(
            total=Sum('hours_spent')
        )['total'] or Decimal('0.00')
        
        return JsonResponse({
            'success': True,
            'entry_id': entry.id,
            'hours': float(entry.hours_spent),
            'total_time': float(total_time),
            'message': f'{entry.hours_spent}h logged successfully'
        })
    except Exception as e:
        logger.error(f"Error creating time entry: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["DELETE"])
def delete_time_entry(request, entry_id):
    """
    Delete a time entry
    """
    entry = get_object_or_404(TimeEntry, id=entry_id)
    
    # Check permissions - user can only delete their own entries
    if entry.user != request.user:
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
    
    task_id = entry.task.id
    entry.delete()
    
    # Recalculate total
    total_time = TimeEntry.objects.filter(task_id=task_id).aggregate(
        total=Sum('hours_spent')
    )['total'] or Decimal('0.00')
    
    return JsonResponse({
        'success': True,
        'total_time': float(total_time),
        'message': 'Time entry deleted'
    })
