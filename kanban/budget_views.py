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
from django.db.models import Sum, Avg, Count
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

logger = logging.getLogger(__name__)


@login_required
def budget_dashboard(request, board_id):
    """
    Main budget dashboard showing overview, metrics, and AI insights
    """
    board = get_object_or_404(Board, id=board_id)
    
    # Check permissions
    if not _can_access_board(request.user, board):
        return HttpResponseForbidden("You don't have permission to access this board.")
    
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
    }
    
    return render(request, 'kanban/budget_dashboard.html', context)


@login_required
def budget_create_or_edit(request, board_id):
    """
    Create or edit project budget
    """
    board = get_object_or_404(Board, id=board_id)
    
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


@login_required
def budget_analytics(request, board_id):
    """
    Detailed budget analytics and reports
    """
    board = get_object_or_404(Board, id=board_id)
    
    if not _can_access_board(request.user, board):
        return HttpResponseForbidden("You don't have permission to access this board.")
    
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
    }
    
    return render(request, 'kanban/budget_analytics.html', context)


@login_required
def roi_dashboard(request, board_id):
    """
    ROI tracking and analysis dashboard
    """
    board = get_object_or_404(Board, id=board_id)
    
    if not _can_access_board(request.user, board):
        return HttpResponseForbidden("You don't have permission to access this board.")
    
    # Get ROI metrics
    roi_metrics = BudgetAnalyzer.calculate_roi_metrics(board)
    
    # Get historical ROI snapshots
    roi_snapshots = ProjectROI.objects.filter(board=board).order_by('-snapshot_date')[:10]
    
    context = {
        'board': board,
        'roi_metrics': roi_metrics,
        'roi_snapshots': roi_snapshots,
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
    """
    # Direct membership or creator
    if board.created_by == user or user in board.members.all():
        return True
    
    # Demo boards: organization-level access
    demo_org_names = ['Dev Team', 'Marketing Team']
    if board.organization.name in demo_org_names:
        # Check if user has access to any board in this demo organization
        from kanban.models import Board as BoardModel
        return BoardModel.objects.filter(
            organization=board.organization,
            members=user
        ).exists()
    
    return False
