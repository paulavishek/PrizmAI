"""
Budget & ROI Tracking Views
Handles budget dashboard, analytics, and AI recommendations
"""
import logging
import time
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Sum, Avg, Count, Q
from django.db import models
from datetime import timedelta
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
    
    if request.method == 'POST':
        form = TimeEntryForm(request.POST, user=request.user)
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
        form = TimeEntryForm(initial={'work_date': timezone.now().date()}, user=request.user)
    
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
    metrics['days_remaining'] = burn_rate_data.get('days_remaining', 0)
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
    
    # Check if budget exists
    try:
        budget = ProjectBudget.objects.get(board=board)
        has_budget = True
    except ProjectBudget.DoesNotExist:
        budget = None
        has_budget = False
    
    # Get ROI metrics
    roi_metrics = BudgetAnalyzer.calculate_roi_metrics(board)
    
    # Get historical ROI snapshots (chronological order - oldest first)
    roi_snapshots = ProjectROI.objects.filter(board=board).order_by('snapshot_date')[:10]
    
    context = {
        'board': board,
        'budget': budget,
        'has_budget': has_budget,
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
    Accept, reject, or mark recommendation as implemented.
    When implementing, actually applies budget changes.
    """
    from kanban.budget_utils import BudgetRedistributor
    
    recommendation = get_object_or_404(BudgetRecommendation, id=recommendation_id)
    board = recommendation.board
    
    try:
        # Get action from POST data (form submission)
        action = request.POST.get('action')  # 'accept', 'reject', 'implement'
        
        if action == 'accept':
            recommendation.status = 'accepted'
            recommendation.reviewed_by = request.user
            recommendation.reviewed_at = timezone.now()
            recommendation.save()
            messages.success(request, f'Recommendation "{recommendation.title}" has been accepted. You can now preview and implement the changes.')
            
        elif action == 'reject':
            recommendation.status = 'rejected'
            recommendation.reviewed_by = request.user
            recommendation.reviewed_at = timezone.now()
            recommendation.save()
            messages.info(request, f'Recommendation "{recommendation.title}" has been rejected.')
            
        elif action == 'implement':
            # Actually apply the budget changes using the redistributor
            redistributor = BudgetRedistributor(recommendation, request.user)
            result = redistributor.apply_changes()
            
            if result.get('success'):
                changes_count = result.get('changes_applied', 0)
                summary = result.get('summary', '')
                
                if changes_count > 0:
                    messages.success(
                        request, 
                        f'✅ Recommendation "{recommendation.title}" implemented successfully! '
                        f'{changes_count} budget changes applied. {summary}'
                    )
                else:
                    if result.get('manual_action_required'):
                        messages.info(
                            request,
                            f'Recommendation "{recommendation.title}" marked as implemented. '
                            f'This recommendation requires manual action: {summary}'
                        )
                    else:
                        messages.success(
                            request,
                            f'Recommendation "{recommendation.title}" has been marked as implemented.'
                        )
            else:
                messages.warning(
                    request,
                    f'Recommendation marked as implemented, but some changes may not have been applied.'
                )
        else:
            messages.error(request, 'Invalid action.')
            return redirect('recommendations_list', board_id=board.id)
        
        return redirect('recommendations_list', board_id=board.id)
        
    except Exception as e:
        logger.error(f"Error updating recommendation: {e}")
        messages.error(request, f'Error updating recommendation: {str(e)}')
        return redirect('recommendations_list', board_id=board.id)


@login_required
@require_http_methods(["GET"])
def recommendation_preview(request, recommendation_id):
    """
    Preview what changes will be made when implementing a recommendation.
    Returns JSON for modal display.
    """
    from kanban.budget_utils import BudgetRedistributor
    
    recommendation = get_object_or_404(BudgetRecommendation, id=recommendation_id)
    board = recommendation.board
    
    try:
        redistributor = BudgetRedistributor(recommendation, request.user)
        preview = redistributor.preview_changes()
        
        # Add recommendation info to preview
        preview['recommendation'] = {
            'id': recommendation.id,
            'title': recommendation.title,
            'type': recommendation.get_recommendation_type_display(),
            'description': recommendation.description,
            'priority': recommendation.priority,
            'confidence': recommendation.confidence_score,
            'estimated_savings': float(recommendation.estimated_savings) if recommendation.estimated_savings else 0,
        }
        preview['currency'] = board.budget.currency if hasattr(board, 'budget') else 'USD'
        
        return JsonResponse(preview)
        
    except Exception as e:
        logger.error(f"Error generating preview: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def recommendation_implementation_details(request, recommendation_id):
    """
    Get implementation details and audit log for an implemented recommendation.
    """
    from kanban.budget_models import BudgetImplementationLog
    
    recommendation = get_object_or_404(BudgetRecommendation, id=recommendation_id)
    board = recommendation.board
    
    logs = BudgetImplementationLog.objects.filter(
        recommendation=recommendation
    ).select_related('affected_task', 'implemented_by')
    
    implementation_data = {
        'recommendation_id': recommendation.id,
        'recommendation_title': recommendation.title,
        'implemented_at': recommendation.implemented_at.isoformat() if recommendation.implemented_at else None,
        'implemented_by': recommendation.reviewed_by.get_full_name() if recommendation.reviewed_by else None,
        'summary': recommendation.implementation_summary,
        'changes': [
            {
                'id': log.id,
                'change_type': log.get_change_type_display(),
                'task': log.affected_task.title if log.affected_task else 'N/A',
                'field': log.field_changed,
                'old_value': float(log.old_value) if log.old_value else None,
                'new_value': float(log.new_value) if log.new_value else None,
                'change_amount': float(log.get_change_amount()),
                'reason': log.change_details.get('reason', '') if log.change_details else '',
                'is_rolled_back': log.is_rolled_back,
            }
            for log in logs
        ],
        'total_changes': logs.count(),
        'currency': board.budget.currency if hasattr(board, 'budget') else 'USD',
    }
    
    return JsonResponse(implementation_data)


@login_required
@require_http_methods(["POST"])
def ai_predict_overrun(request, board_id):
    """
    Get AI prediction for cost overruns
    """
    start_time = time.time()
    board = get_object_or_404(Board, id=board_id)
    
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
    
    # Check AI quota
    has_quota, quota, remaining = check_ai_quota(request.user)
    if not has_quota:
        return JsonResponse({
            'error': 'AI usage quota exceeded. Please upgrade or wait for quota reset.',
            'quota_exceeded': True
        }, status=429)
    
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


# ============================================================================
# TIME TRACKING VIEWS
# ============================================================================

@login_required
def my_timesheet(request, board_id=None):
    """
    User's personal timesheet view with weekly grid for time entry.
    MVP Mode: Shows demo data when user has no time entries of their own.
    """
    from datetime import datetime, timedelta
    from django.db.models import Sum
    from accounts.models import Organization
    
    # Get week parameter or default to current week
    week_offset = int(request.GET.get('week', 0))
    today = timezone.now().date()
    # Start of week (Monday)
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    end_of_week = start_of_week + timedelta(days=6)
    
    # MVP Mode: Check if user has any time entries, if not show demo data
    user_has_entries = TimeEntry.objects.filter(user=request.user).exists()
    showing_demo_data = False
    display_user = request.user
    
    if not user_has_entries:
        # Try to get a demo user with time entries
        demo_usernames = ['alex_chen_demo', 'sam_rivera_demo', 'jordan_taylor_demo']
        for demo_username in demo_usernames:
            demo_user = User.objects.filter(username=demo_username).first()
            if demo_user and TimeEntry.objects.filter(user=demo_user).exists():
                display_user = demo_user
                showing_demo_data = True
                break
    
    # Get user's tasks (or demo user's tasks in MVP mode)
    if board_id:
        board = get_object_or_404(Board, id=board_id)
        tasks = Task.objects.filter(
            column__board=board,
            assigned_to=display_user
        ).select_related('column', 'column__board')
        boards = [board]
    else:
        # All boards user has access to (include demo boards in MVP mode)
        if showing_demo_data:
            demo_org = Organization.objects.filter(is_demo=True).first()
            if demo_org:
                boards = Board.objects.filter(
                    models.Q(created_by=request.user) | 
                    models.Q(members=request.user) |
                    models.Q(organization=demo_org)
                ).distinct()
            else:
                boards = Board.objects.filter(
                    models.Q(created_by=request.user) | models.Q(members=request.user)
                ).distinct()
        else:
            boards = Board.objects.filter(
                models.Q(created_by=request.user) | models.Q(members=request.user)
            ).distinct()
        tasks = Task.objects.filter(
            column__board__in=boards,
            assigned_to=display_user
        ).select_related('column', 'column__board')
    
    # Get time entries for the week (for display_user)
    entries = TimeEntry.objects.filter(
        user=display_user,
        work_date__gte=start_of_week,
        work_date__lte=end_of_week
    ).select_related('task', 'task__column', 'task__column__board')
    
    # Organize entries by task and date (support multiple entries per task/date)
    entries_by_task_date = {}
    for entry in entries:
        key = (entry.task.id, entry.work_date)
        if key not in entries_by_task_date:
            entries_by_task_date[key] = []
        entries_by_task_date[key].append(entry)
    
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
            entry_list = entries_by_task_date.get((task.id, day['date']), [])
            # Sum hours from all entries for this task/date
            hours = sum((e.hours_spent for e in entry_list), Decimal('0.00'))
            # Get the most recent entry for display (description, etc.)
            primary_entry = entry_list[-1] if entry_list else None
            row['entries'].append({
                'date': day['date'],
                'entry': primary_entry,
                'all_entries': entry_list,  # Keep all entries for tooltip
                'hours': round(hours, 2),
                'entry_count': len(entry_list),  # Track number of entries
            })
            row['total_hours'] += hours
        row['total_hours'] = round(row['total_hours'], 2)
        task_rows.append(row)
    
    # Calculate daily totals
    daily_totals = []
    for day in week_days:
        total = entries.filter(work_date=day['date']).aggregate(
            total=Sum('hours_spent')
        )['total'] or Decimal('0.00')
        daily_totals.append(round(total, 2))
    
    week_total = round(sum(daily_totals, Decimal('0.00')), 2)
    
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
        # MVP Mode: demo data indicator
        'showing_demo_data': showing_demo_data,
        'demo_user': display_user if showing_demo_data else None,
    }
    
    return render(request, 'kanban/my_timesheet.html', context)


@login_required
def time_tracking_dashboard(request, board_id=None):
    """
    Time tracking dashboard with stats, recent entries, and quick actions.
    MVP Mode: Shows demo data when user has no time entries of their own.
    """
    from datetime import timedelta
    from django.db.models import Sum, Count, Avg
    from accounts.models import Organization
    
    # MVP Mode: Check if user has any time entries, if not show demo data
    user_has_entries = TimeEntry.objects.filter(user=request.user).exists()
    showing_demo_data = False
    display_user = request.user
    
    if not user_has_entries:
        # Try to get a demo user with time entries
        demo_usernames = ['alex_chen_demo', 'sam_rivera_demo', 'jordan_taylor_demo']
        for demo_username in demo_usernames:
            demo_user = User.objects.filter(username=demo_username).first()
            if demo_user and TimeEntry.objects.filter(user=demo_user).exists():
                display_user = demo_user
                showing_demo_data = True
                break
    
    # Filter by board if specified
    if board_id:
        board = get_object_or_404(Board, id=board_id)
        boards = [board]
    else:
        # MVP Mode: Include demo boards when showing demo data
        if showing_demo_data:
            demo_org = Organization.objects.filter(is_demo=True).first()
            if demo_org:
                boards = Board.objects.filter(
                    models.Q(created_by=request.user) | 
                    models.Q(members=request.user) |
                    models.Q(organization=demo_org)
                ).distinct()
            else:
                boards = Board.objects.filter(
                    models.Q(created_by=request.user) | models.Q(members=request.user)
                ).distinct()
        else:
            boards = Board.objects.filter(
                models.Q(created_by=request.user) | models.Q(members=request.user)
            ).distinct()
        board = None
    
    # Get time entries for display_user (either request.user or demo user)
    entries = TimeEntry.objects.filter(user=display_user)
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
    today_hours = round(today_hours, 2)
    
    week_hours = entries.filter(
        work_date__gte=week_start,
        work_date__lte=today
    ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
    week_hours = round(week_hours, 2)
    
    month_hours = entries.filter(
        work_date__gte=month_start,
        work_date__lte=today
    ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
    month_hours = round(month_hours, 2)
    
    total_hours = entries.aggregate(
        total=Sum('hours_spent')
    )['total'] or Decimal('0.00')
    total_hours = round(total_hours, 2)
    
    # Recent entries
    recent_entries = entries.select_related(
        'task', 'task__column', 'task__column__board'
    ).order_by('-work_date', '-created_at')[:10]
    
    # Tasks with time logged (use display_user for MVP mode)
    tasks_with_time = Task.objects.filter(
        time_entries__user=display_user
    )
    if board_id:
        tasks_with_time = tasks_with_time.filter(column__board=board)
    
    tasks_with_time = tasks_with_time.annotate(
        total_hours=Sum('time_entries__hours_spent')
    ).order_by('-total_hours')[:10]
    
    # Round total_hours for display
    tasks_with_time_list = list(tasks_with_time)
    for task in tasks_with_time_list:
        if task.total_hours:
            task.total_hours = round(task.total_hours, 2)
    
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
            'hours': float(round(daily_hours, 2)),
        })
    
    # My tasks needing time entry (assigned and not done)
    my_tasks = Task.objects.filter(
        assigned_to=request.user,
        progress__lt=100
    )
    if board_id:
        my_tasks = my_tasks.filter(column__board=board)
    
    my_tasks = my_tasks.select_related('column', 'column__board')[:20]
    
    # AI-powered features
    from kanban.time_tracking_ai import TimeTrackingAIService
    ai_service = TimeTrackingAIService(request.user, board)
    
    # Get anomaly alerts (warnings about unusual time patterns)
    time_alerts = ai_service.detect_anomalies(days_back=14)
    
    # Get smart task suggestions
    smart_suggestions = ai_service.suggest_tasks(limit=5)
    suggested_task_ids = [s['task'].id for s in smart_suggestions]
    
    # Get missing time reminder (if applicable)
    missing_time_alert = ai_service.get_missing_time_alerts()
    
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
        'tasks_with_time': tasks_with_time_list,
        'chart_data': chart_data_json,
        'my_tasks': my_tasks,
        'time_alerts': time_alerts,
        'smart_suggestions': smart_suggestions,
        'suggested_task_ids': suggested_task_ids,
        'missing_time_alert': missing_time_alert,
        'today_date': today.isoformat(),
        'week_start_date': week_start.isoformat(),
        'month_start_date': month_start.isoformat(),
        # MVP Mode: demo data indicator
        'showing_demo_data': showing_demo_data,
        'demo_user': display_user if showing_demo_data else None,
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
            'total_hours': round(user_data['total_hours'], 2),
            'entries_count': user_data['entries_count'],
        }
        for day in week_days:
            date_str = day['date'].isoformat()
            hours = user_data['daily_hours'].get(date_str, Decimal('0.00'))
            row['daily_hours'].append(round(hours, 2))
        user_rows.append(row)
    
    # Calculate daily totals
    daily_totals = []
    for day in week_days:
        total = entries.filter(work_date=day['date']).aggregate(
            total=Sum('hours_spent')
        )['total'] or Decimal('0.00')
        daily_totals.append(round(total, 2))
    
    week_total = round(sum(daily_totals, Decimal('0.00')), 2)
    
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
    
    try:
        hours = Decimal(request.POST.get('hours', '0'))
        description = request.POST.get('description', '').strip()
        work_date_str = request.POST.get('work_date', timezone.now().date().isoformat())
        work_date = timezone.datetime.fromisoformat(work_date_str).date()
        
        if hours <= 0:
            return JsonResponse({'success': False, 'error': 'Hours must be greater than 0'}, status=400)
        
        if hours > 16:
            return JsonResponse({'success': False, 'error': 'Hours cannot exceed 16 per entry'}, status=400)
        
        # Round to nearest 0.25 increment
        hours = Decimal(str(round(float(hours) * 4) / 4))
        
        # Check daily total won't exceed 24 hours
        existing_hours = TimeEntry.objects.filter(
            user=request.user,
            work_date=work_date
        ).aggregate(total=Sum('hours_spent'))['total'] or Decimal('0.00')
        
        if existing_hours + hours > 24:
            return JsonResponse({
                'success': False, 
                'error': f'Daily total would exceed 24 hours. You already have {existing_hours}h logged for this date.'
            }, status=400)
        
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


@login_required
def time_entries_by_date(request):
    """
    Get time entries for a specific date (AJAX endpoint for chart drill-down)
    """
    date_str = request.GET.get('date')
    board_id = request.GET.get('board_id')
    
    if not date_str:
        return JsonResponse({'success': False, 'error': 'Date required'}, status=400)
    
    try:
        from datetime import datetime
        work_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Invalid date format'}, status=400)
    
    # MVP Mode: use demo user when the logged-in user has no entries of their own
    display_user = request.user
    user_has_entries = TimeEntry.objects.filter(user=request.user).exists()
    if not user_has_entries:
        demo_usernames = ['alex_chen_demo', 'sam_rivera_demo', 'jordan_taylor_demo']
        for demo_username in demo_usernames:
            demo_user = User.objects.filter(username=demo_username).first()
            if demo_user and TimeEntry.objects.filter(user=demo_user).exists():
                display_user = demo_user
                break
    
    # Get entries for this date
    entries_qs = TimeEntry.objects.filter(
        user=display_user,
        work_date=work_date
    ).select_related('task', 'task__column', 'task__column__board')
    
    if board_id:
        entries_qs = entries_qs.filter(task__column__board_id=board_id)
    
    entries_qs = entries_qs.order_by('-hours_spent')
    
    entries_data = []
    total_hours = Decimal('0.00')
    
    for entry in entries_qs:
        entries_data.append({
            'id': entry.id,
            'task_id': entry.task.id,
            'task_title': entry.task.title,
            'board_name': entry.task.column.board.name,
            'hours': float(entry.hours_spent),
            'description': entry.description or '',
        })
        total_hours += entry.hours_spent
    
    return JsonResponse({
        'success': True,
        'date': date_str,
        'date_display': work_date.strftime('%A, %B %d, %Y'),
        'entries': entries_data,
        'total_hours': float(total_hours),
        'entry_count': len(entries_data),
    })


@login_required
def time_entries_by_period(request):
    """
    Get time entries for a specific period (AJAX endpoint for metric card drill-down)
    """
    from datetime import timedelta
    
    period = request.GET.get('period')  # today, week, month, all
    board_id = request.GET.get('board_id')
    
    if period not in ['today', 'week', 'month', 'all']:
        return JsonResponse({'success': False, 'error': 'Invalid period'}, status=400)
    
    today = timezone.now().date()
    
    # Determine date range
    if period == 'today':
        start_date = today
        end_date = today
        period_display = f"Today ({today.strftime('%B %d, %Y')})"
    elif period == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = today
        period_display = f"This Week ({start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')})"
    elif period == 'month':
        start_date = today.replace(day=1)
        end_date = today
        period_display = f"This Month ({today.strftime('%B %Y')})"
    else:  # all
        start_date = None
        end_date = None
        period_display = "All Time"
    
    # MVP Mode: use demo user when the logged-in user has no entries of their own
    display_user = request.user
    user_has_entries = TimeEntry.objects.filter(user=request.user).exists()
    if not user_has_entries:
        demo_usernames = ['alex_chen_demo', 'sam_rivera_demo', 'jordan_taylor_demo']
        for demo_username in demo_usernames:
            demo_user = User.objects.filter(username=demo_username).first()
            if demo_user and TimeEntry.objects.filter(user=demo_user).exists():
                display_user = demo_user
                break

    # Get entries
    entries_qs = TimeEntry.objects.filter(user=display_user)
    
    if start_date:
        entries_qs = entries_qs.filter(work_date__gte=start_date)
    if end_date:
        entries_qs = entries_qs.filter(work_date__lte=end_date)
    if board_id:
        entries_qs = entries_qs.filter(task__column__board_id=board_id)
    
    entries_qs = entries_qs.select_related(
        'task', 'task__column', 'task__column__board'
    ).order_by('-work_date', '-hours_spent')
    
    # Group by task for summary
    task_summary = {}
    total_hours = Decimal('0.00')
    
    for entry in entries_qs:
        task_id = entry.task.id
        if task_id not in task_summary:
            task_summary[task_id] = {
                'task_id': task_id,
                'task_title': entry.task.title,
                'board_name': entry.task.column.board.name,
                'hours': Decimal('0.00'),
                'entry_count': 0,
                'entries': [],
            }
        task_summary[task_id]['hours'] += entry.hours_spent
        task_summary[task_id]['entry_count'] += 1
        task_summary[task_id]['entries'].append({
            'date': entry.work_date.strftime('%b %d'),
            'hours': float(entry.hours_spent),
            'description': entry.description or '',
        })
        total_hours += entry.hours_spent
    
    # Convert to list and sort by hours
    tasks_data = sorted(
        [
            {
                **task,
                'hours': float(task['hours']),
            }
            for task in task_summary.values()
        ],
        key=lambda x: x['hours'],
        reverse=True
    )
    
    return JsonResponse({
        'success': True,
        'period': period,
        'period_display': period_display,
        'tasks': tasks_data,
        'total_hours': float(total_hours),
        'task_count': len(tasks_data),
    })


@login_required
def search_tasks_for_time_entry(request):
    """
    Search tasks by name for time entry (AJAX endpoint for task search)
    """
    query = request.GET.get('q', '').strip()
    board_id = request.GET.get('board_id')
    
    if not query or len(query) < 2:
        return JsonResponse({'success': True, 'tasks': []})
    
    # Get boards user has access to
    boards = Board.objects.filter(
        models.Q(created_by=request.user) | models.Q(members=request.user)
    ).distinct()
    
    if board_id:
        boards = boards.filter(id=board_id)
    
    # Search tasks by title
    tasks_qs = Task.objects.filter(
        column__board__in=boards,
        progress__lt=100,
        title__icontains=query
    ).exclude(
        assigned_to=request.user  # Don't show assigned tasks here
    ).select_related('column', 'column__board').order_by('title')[:20]
    
    tasks_data = [
        {
            'id': task.id,
            'title': task.title,
            'board_name': task.column.board.name,
            'column_name': task.column.name,
        }
        for task in tasks_qs
    ]
    
    return JsonResponse({
        'success': True,
        'tasks': tasks_data,
        'count': len(tasks_data),
    })


# ============================================================================
# AI-POWERED TIME ENTRY VALIDATION & SPLIT SUGGESTIONS
# ============================================================================

@login_required
@require_http_methods(["POST"])
def validate_time_entry_api(request):
    """
    AI-powered validation of a proposed time entry.
    Returns suggestions if the hours would result in an excessive day.
    
    POST body:
        task_id: int - Task ID
        hours: float - Hours to log
        work_date: str - Date in YYYY-MM-DD format
    
    Returns:
        JSON with validation result and optional split suggestions
    """
    from kanban.time_tracking_ai import TimeTrackingAIService
    from datetime import datetime
    
    try:
        data = json.loads(request.body)
        task_id = data.get('task_id')
        hours = Decimal(str(data.get('hours', 0)))
        work_date_str = data.get('work_date')
        
        if not all([task_id, hours, work_date_str]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields: task_id, hours, work_date'
            }, status=400)
        
        # Parse date
        try:
            work_date = datetime.strptime(work_date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid date format. Use YYYY-MM-DD'
            }, status=400)
        
        # Get task
        task = get_object_or_404(Task, id=task_id)
        
        # Validate hours
        if hours <= 0:
            return JsonResponse({
                'success': False,
                'error': 'Hours must be greater than 0'
            }, status=400)
        
        if hours > 16:
            return JsonResponse({
                'success': False,
                'error': 'Maximum 16 hours per single entry'
            }, status=400)
        
        # Run AI validation
        ai_service = TimeTrackingAIService(request.user)
        validation_result = ai_service.validate_time_entry(task, hours, work_date)
        
        return JsonResponse({
            'success': True,
            **validation_result
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON body'
        }, status=400)
    except Exception as e:
        logger.error(f"Error validating time entry: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def create_split_time_entries(request):
    """
    Create multiple time entries at once from AI split suggestions.
    
    POST body:
        entries: list - Array of entry objects with:
            - task_id: int
            - hours: float
            - date: str (YYYY-MM-DD)
            - description: str (optional)
    
    Returns:
        JSON with created entries
    """
    from kanban.budget_models import TimeEntry
    from datetime import datetime
    
    try:
        data = json.loads(request.body)
        entries_data = data.get('entries', [])
        
        if not entries_data:
            return JsonResponse({
                'success': False,
                'error': 'No entries provided'
            }, status=400)
        
        if len(entries_data) > 10:
            return JsonResponse({
                'success': False,
                'error': 'Maximum 10 entries per request'
            }, status=400)
        
        created_entries = []
        errors = []
        
        for i, entry_data in enumerate(entries_data):
            try:
                task_id = entry_data.get('task_id')
                hours = Decimal(str(entry_data.get('hours', 0)))
                date_str = entry_data.get('date')
                description = entry_data.get('description', '')
                
                # Validate required fields
                if not all([task_id, hours, date_str]):
                    errors.append(f"Entry {i+1}: Missing required fields")
                    continue
                
                # Parse date
                try:
                    work_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    errors.append(f"Entry {i+1}: Invalid date format")
                    continue
                
                # Get task
                try:
                    task = Task.objects.get(id=task_id)
                except Task.DoesNotExist:
                    errors.append(f"Entry {i+1}: Task not found")
                    continue
                
                # Validate hours
                if hours <= 0 or hours > 16:
                    errors.append(f"Entry {i+1}: Hours must be between 0 and 16")
                    continue
                
                # Create the entry
                entry = TimeEntry.objects.create(
                    task=task,
                    user=request.user,
                    hours_spent=hours,
                    work_date=work_date,
                    description=description[:500] if description else ''
                )
                
                created_entries.append({
                    'id': entry.id,
                    'task_id': task.id,
                    'task_title': task.title,
                    'hours': float(entry.hours_spent),
                    'date': entry.work_date.isoformat(),
                    'description': entry.description
                })
                
            except Exception as e:
                errors.append(f"Entry {i+1}: {str(e)}")
        
        return JsonResponse({
            'success': len(created_entries) > 0,
            'created_count': len(created_entries),
            'entries': created_entries,
            'errors': errors if errors else None,
            'message': (
                f"Successfully created {len(created_entries)} time entries"
                if created_entries else "No entries were created"
            )
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON body'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating split time entries: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
