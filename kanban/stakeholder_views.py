# kanban/stakeholder_views.py
"""
Views for stakeholder engagement tracking and management
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Q, Avg
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import timedelta
import csv
import json

from .models import Board, Task
from .stakeholder_models import (
    ProjectStakeholder, StakeholderTaskInvolvement,
    StakeholderEngagementRecord, EngagementMetrics, StakeholderTag
)
from .stakeholder_forms import (
    ProjectStakeholderForm, StakeholderTaskInvolvementForm,
    StakeholderEngagementRecordForm, StakeholderTagForm,
    BulkStakeholderImportForm
)
from .stakeholder_utils import recalculate_stakeholder_metrics


def check_board_access(user, board_id):
    """Helper function to check if user has access to board"""
    board = get_object_or_404(Board, id=board_id)
    if board.created_by != user and user not in board.members.all():
        return None
    return board


@login_required
def stakeholder_list(request, board_id):
    """List all stakeholders for a board"""
    board = check_board_access(request.user, board_id)
    if not board:
        messages.error(request, 'Access denied to this board')
        return redirect('dashboard')
    
    stakeholders = ProjectStakeholder.objects.filter(board=board).prefetch_related(
        'task_involvements', 'engagement_records'
    )
    
    # Filtering
    influence_filter = request.GET.get('influence')
    interest_filter = request.GET.get('interest')
    engagement_filter = request.GET.get('engagement')
    
    if influence_filter:
        stakeholders = stakeholders.filter(influence_level=influence_filter)
    if interest_filter:
        stakeholders = stakeholders.filter(interest_level=interest_filter)
    if engagement_filter:
        stakeholders = stakeholders.filter(current_engagement=engagement_filter)
    
    # Calculate quadrant counts
    manage_closely_count = 0
    keep_satisfied_count = 0
    keep_informed_count = 0
    monitor_count = 0
    
    for stakeholder in stakeholders:
        quadrant = stakeholder.get_quadrant()
        if quadrant == 'Manage Closely':
            manage_closely_count += 1
        elif quadrant == 'Keep Satisfied':
            keep_satisfied_count += 1
        elif quadrant == 'Keep Informed':
            keep_informed_count += 1
        else:
            monitor_count += 1
    
    context = {
        'board': board,
        'stakeholders': stakeholders,
        'influence_choices': ProjectStakeholder.INFLUENCE_CHOICES,
        'interest_choices': ProjectStakeholder.INTEREST_CHOICES,
        'engagement_choices': ProjectStakeholder.ENGAGEMENT_STRATEGY_CHOICES,
        'manage_closely_count': manage_closely_count,
        'keep_satisfied_count': keep_satisfied_count,
        'keep_informed_count': keep_informed_count,
        'monitor_count': monitor_count,
    }
    return render(request, 'kanban/stakeholder_list.html', context)


@login_required
def stakeholder_create(request, board_id):
    """Create a new stakeholder for a board"""
    board = check_board_access(request.user, board_id)
    if not board:
        messages.error(request, 'Access denied to this board')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = ProjectStakeholderForm(request.POST)
        if form.is_valid():
            stakeholder = form.save(commit=False)
            stakeholder.board = board
            stakeholder.created_by = request.user
            stakeholder.save()
            messages.success(request, f'Stakeholder {stakeholder.name} created successfully!')
            return redirect('stakeholder:stakeholder_detail', board_id=board_id, pk=stakeholder.pk)
    else:
        form = ProjectStakeholderForm()
    
    context = {
        'board': board,
        'form': form,
        'action': 'Create',
    }
    return render(request, 'kanban/stakeholder_form.html', context)


@login_required
def stakeholder_detail(request, board_id, pk):
    """Display detailed stakeholder information and engagement history"""
    board = check_board_access(request.user, board_id)
    if not board:
        messages.error(request, 'Access denied to this board')
        return redirect('dashboard')
    
    stakeholder = get_object_or_404(ProjectStakeholder, pk=pk, board=board)
    
    # Get engagement records
    engagement_records = stakeholder.engagement_records.all()[:10]
    
    # Get task involvements
    task_involvements = stakeholder.task_involvements.all()
    
    # Get metrics if available
    metrics = getattr(stakeholder, 'metrics', None)
    
    # Calculate stats
    total_engagements = stakeholder.engagement_records.count()
    avg_satisfaction = stakeholder.engagement_records.filter(
        satisfaction_rating__isnull=False
    ).aggregate(Avg('satisfaction_rating'))['satisfaction_rating__avg']
    
    context = {
        'board': board,
        'stakeholder': stakeholder,
        'engagement_records': engagement_records,
        'task_involvements': task_involvements,
        'metrics': metrics,
        'total_engagements': total_engagements,
        'avg_satisfaction': round(avg_satisfaction, 2) if avg_satisfaction else 0,
        'quadrant': stakeholder.get_quadrant(),
        'engagement_gap': stakeholder.get_engagement_gap(),
    }
    return render(request, 'kanban/stakeholder_detail.html', context)


@login_required
def stakeholder_update(request, board_id, pk):
    """Update stakeholder information"""
    board = check_board_access(request.user, board_id)
    if not board:
        messages.error(request, 'Access denied to this board')
        return redirect('dashboard')
    
    stakeholder = get_object_or_404(ProjectStakeholder, pk=pk, board=board)
    
    if request.method == 'POST':
        form = ProjectStakeholderForm(request.POST, instance=stakeholder)
        if form.is_valid():
            form.save()
            messages.success(request, 'Stakeholder updated successfully!')
            return redirect('stakeholder:stakeholder_detail', board_id=board_id, pk=stakeholder.pk)
    else:
        form = ProjectStakeholderForm(instance=stakeholder)
    
    context = {
        'board': board,
        'stakeholder': stakeholder,
        'form': form,
        'action': 'Update',
    }
    return render(request, 'kanban/stakeholder_form.html', context)


@login_required
def stakeholder_delete(request, board_id, pk):
    """Delete a stakeholder"""
    board = check_board_access(request.user, board_id)
    if not board:
        messages.error(request, 'Access denied to this board')
        return redirect('dashboard')
    
    stakeholder = get_object_or_404(ProjectStakeholder, pk=pk, board=board)
    
    if request.method == 'POST':
        name = stakeholder.name
        stakeholder.delete()
        messages.success(request, f'Stakeholder {name} deleted successfully!')
        return redirect('stakeholder:stakeholder_list', board_id=board_id)
    
    context = {
        'board': board,
        'stakeholder': stakeholder,
    }
    return render(request, 'kanban/stakeholder_confirm_delete.html', context)


@login_required
def engagement_record_create(request, board_id, stakeholder_id):
    """Record a stakeholder engagement event"""
    board = check_board_access(request.user, board_id)
    if not board:
        messages.error(request, 'Access denied to this board')
        return redirect('dashboard')
    
    stakeholder = get_object_or_404(ProjectStakeholder, pk=stakeholder_id, board=board)
    
    if request.method == 'POST':
        form = StakeholderEngagementRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.stakeholder = stakeholder
            record.created_by = request.user
            record.save()
            
            # Update stakeholder's last engagement
            stakeholder.task_involvements.all().update(last_engagement=timezone.now())
            
            # Recalculate engagement metrics
            recalculate_stakeholder_metrics(stakeholder)
            
            messages.success(request, 'Engagement recorded successfully!')
            return redirect('stakeholder:stakeholder_detail', board_id=board_id, pk=stakeholder_id)
    else:
        # Set default date to today
        form = StakeholderEngagementRecordForm(initial={'date': timezone.now().date()})
    
    context = {
        'board': board,
        'stakeholder': stakeholder,
        'form': form,
    }
    return render(request, 'kanban/engagement_record_form.html', context)


@login_required
def engagement_record_update(request, board_id, stakeholder_id, record_id):
    """Edit an existing engagement record"""
    board = check_board_access(request.user, board_id)
    if not board:
        messages.error(request, 'Access denied to this board')
        return redirect('dashboard')
    
    stakeholder = get_object_or_404(ProjectStakeholder, pk=stakeholder_id, board=board)
    record = get_object_or_404(StakeholderEngagementRecord, pk=record_id, stakeholder=stakeholder)
    
    if request.method == 'POST':
        form = StakeholderEngagementRecordForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            
            # Recalculate engagement metrics
            recalculate_stakeholder_metrics(stakeholder)
            
            messages.success(request, 'Engagement record updated successfully!')
            return redirect('stakeholder:stakeholder_detail', board_id=board_id, pk=stakeholder_id)
    else:
        form = StakeholderEngagementRecordForm(instance=record)
    
    context = {
        'board': board,
        'stakeholder': stakeholder,
        'record': record,
        'form': form,
        'is_update': True,
    }
    return render(request, 'kanban/engagement_record_form.html', context)


@login_required
def engagement_record_delete(request, board_id, stakeholder_id, record_id):
    """Delete an engagement record"""
    board = check_board_access(request.user, board_id)
    if not board:
        messages.error(request, 'Access denied to this board')
        return redirect('dashboard')
    
    stakeholder = get_object_or_404(ProjectStakeholder, pk=stakeholder_id, board=board)
    record = get_object_or_404(StakeholderEngagementRecord, pk=record_id, stakeholder=stakeholder)
    
    if request.method == 'POST':
        record.delete()
        
        # Recalculate engagement metrics
        recalculate_stakeholder_metrics(stakeholder)
        
        messages.success(request, 'Engagement record deleted successfully!')
        return redirect('stakeholder:stakeholder_detail', board_id=board_id, pk=stakeholder_id)
    
    context = {
        'board': board,
        'stakeholder': stakeholder,
        'record': record,
    }
    return render(request, 'kanban/engagement_record_confirm_delete.html', context)


@login_required
def task_stakeholder_involvement(request, board_id, task_id):
    """Manage stakeholder involvement in a specific task"""
    board = check_board_access(request.user, board_id)
    if not board:
        messages.error(request, 'Access denied to this board')
        return redirect('dashboard')
    
    task = get_object_or_404(Task, pk=task_id, column__board=board)
    
    # Get current involvements
    involvements = task.stakeholder_involvements.select_related('stakeholder').all()
    
    # Get IDs of stakeholders already involved
    involved_stakeholder_ids = [inv.stakeholder.id for inv in involvements]
    
    # Get all stakeholders for this board that are not yet involved
    available_stakeholders = ProjectStakeholder.objects.filter(
        board=board
    ).exclude(id__in=involved_stakeholder_ids).order_by('name')
    
    context = {
        'board': board,
        'task': task,
        'stakeholders': available_stakeholders,
        'involvements': involvements,
    }
    return render(request, 'kanban/task_stakeholder_involvement.html', context)


@login_required
@require_http_methods(["POST"])
def add_task_stakeholder(request, board_id, task_id):
    """Add a stakeholder to a task"""
    board = check_board_access(request.user, board_id)
    if not board:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    task = get_object_or_404(Task, pk=task_id, column__board=board)
    stakeholder_id = request.POST.get('stakeholder_id')
    involvement_type = request.POST.get('involvement_type', 'stakeholder')
    
    stakeholder = get_object_or_404(ProjectStakeholder, pk=stakeholder_id, board=board)
    
    involvement, created = StakeholderTaskInvolvement.objects.get_or_create(
        stakeholder=stakeholder,
        task=task,
        defaults={'involvement_type': involvement_type}
    )
    
    if created:
        messages.success(request, f'{stakeholder.name} added to task')
    else:
        messages.info(request, f'{stakeholder.name} is already involved in this task')
    
    return redirect('stakeholder:task_stakeholder_involvement', board_id=board_id, task_id=task_id)


@login_required
def engagement_metrics_dashboard(request, board_id):
    """Display engagement metrics for a board"""
    board = check_board_access(request.user, board_id)
    if not board:
        messages.error(request, 'Access denied to this board')
        return redirect('dashboard')
    
    stakeholders = ProjectStakeholder.objects.filter(board=board)
    
    # Calculate metrics for all stakeholders
    stakeholder_metrics = []
    for stakeholder in stakeholders:
        total_engagements = stakeholder.engagement_records.count()
        avg_satisfaction = stakeholder.engagement_records.filter(
            satisfaction_rating__isnull=False
        ).aggregate(Avg('satisfaction_rating'))['satisfaction_rating__avg']
        
        last_engagement = stakeholder.engagement_records.first()
        days_since = 0
        if last_engagement:
            days_since = (timezone.now().date() - last_engagement.date).days
        
        task_count = stakeholder.task_involvements.count()
        
        stakeholder_metrics.append({
            'stakeholder': stakeholder,
            'total_engagements': total_engagements,
            'avg_satisfaction': round(avg_satisfaction, 2) if avg_satisfaction else 0,
            'days_since_engagement': days_since,
            'tasks_involved': task_count,
            'engagement_gap': stakeholder.get_engagement_gap(),
            'quadrant': stakeholder.get_quadrant(),
        })
    
    # Engagement summary
    total_stakeholders = stakeholders.count()
    total_engagements = sum(s['total_engagements'] for s in stakeholder_metrics)
    avg_satisfaction_all = sum(s['avg_satisfaction'] for s in stakeholder_metrics) / len(stakeholder_metrics) if stakeholder_metrics else 0
    
    # Quadrant distribution
    quadrant_dist = {}
    for sm in stakeholder_metrics:
        q = sm['quadrant']
        quadrant_dist[q] = quadrant_dist.get(q, 0) + 1
    
    context = {
        'board': board,
        'stakeholder_metrics': stakeholder_metrics,
        'total_stakeholders': total_stakeholders,
        'total_engagements': total_engagements,
        'avg_satisfaction_all': round(avg_satisfaction_all, 2),
        'quadrant_distribution': quadrant_dist,
    }
    return render(request, 'kanban/engagement_metrics_dashboard.html', context)


@login_required
def engagement_analytics(request, board_id):
    """Display detailed engagement analytics"""
    board = check_board_access(request.user, board_id)
    if not board:
        messages.error(request, 'Access denied to this board')
        return redirect('dashboard')
    
    # Period selection (default to last 30 days)
    days = int(request.GET.get('days', 30))
    start_date = timezone.now().date() - timedelta(days=days)
    
    # Engagement trends
    records = StakeholderEngagementRecord.objects.filter(
        stakeholder__board=board,
        date__gte=start_date
    ).order_by('date')
    
    # Communication channel breakdown
    channel_stats = {}
    for record in records:
        channel = record.get_communication_channel_display()
        channel_stats[channel] = channel_stats.get(channel, 0) + 1
    
    # Satisfaction trends
    records_with_rating = records.filter(satisfaction_rating__isnull=False)
    avg_satisfaction_trend = records_with_rating.aggregate(Avg('satisfaction_rating'))['satisfaction_rating__avg']
    
    context = {
        'board': board,
        'days': days,
        'total_records': records.count(),
        'channel_stats': channel_stats,
        'avg_satisfaction': round(avg_satisfaction_trend, 2) if avg_satisfaction_trend else 0,
    }
    return render(request, 'kanban/engagement_analytics.html', context)


@login_required
def stakeholder_api_data(request, board_id):
    """API endpoint to fetch stakeholder data for charts"""
    board = check_board_access(request.user, board_id)
    if not board:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    stakeholders = ProjectStakeholder.objects.filter(board=board)
    
    data = {
        'stakeholders': [],
        'quadrant_dist': {},
        'engagement_dist': {},
    }
    
    for stakeholder in stakeholders:
        data['stakeholders'].append({
            'id': stakeholder.id,
            'name': stakeholder.name,
            'role': stakeholder.role,
            'influence': stakeholder.get_influence_value(),
            'interest': stakeholder.get_interest_value(),
            'current_engagement': stakeholder.get_engagement_level_value(),
            'desired_engagement': stakeholder.get_desired_engagement_level_value(),
            'quadrant': stakeholder.get_quadrant(),
            'engagement_gap': stakeholder.get_engagement_gap(),
        })
        
        # Quadrant distribution
        q = stakeholder.get_quadrant()
        data['quadrant_dist'][q] = data['quadrant_dist'].get(q, 0) + 1
        
        # Engagement distribution
        eng = stakeholder.current_engagement
        data['engagement_dist'][eng] = data['engagement_dist'].get(eng, 0) + 1
    
    return JsonResponse(data)


@login_required
def edit_task_stakeholder(request, board_id, task_id, involvement_id):
    """Edit stakeholder involvement in a task"""
    board = check_board_access(request.user, board_id)
    if not board:
        messages.error(request, 'Access denied to this board')
        return redirect('dashboard')
    
    task = get_object_or_404(Task, pk=task_id, column__board=board)
    involvement = get_object_or_404(StakeholderTaskInvolvement, pk=involvement_id, task=task)
    
    if request.method == 'POST':
        form = StakeholderTaskInvolvementForm(request.POST, instance=involvement)
        if form.is_valid():
            involvement = form.save(commit=False)
            # Update last engagement timestamp
            involvement.last_engagement = timezone.now()
            involvement.engagement_count += 1
            involvement.save()
            messages.success(request, f'Updated involvement for {involvement.stakeholder.name}')
            return redirect('stakeholder:task_stakeholder_involvement', board_id=board_id, task_id=task_id)
    else:
        form = StakeholderTaskInvolvementForm(instance=involvement)
    
    context = {
        'board': board,
        'task': task,
        'involvement': involvement,
        'form': form,
    }
    return render(request, 'kanban/edit_task_stakeholder.html', context)


@login_required
@require_http_methods(["POST"])
def remove_task_stakeholder(request, board_id, task_id, involvement_id):
    """Remove a stakeholder from a task"""
    board = check_board_access(request.user, board_id)
    if not board:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    task = get_object_or_404(Task, pk=task_id, column__board=board)
    involvement = get_object_or_404(StakeholderTaskInvolvement, pk=involvement_id, task=task)
    
    stakeholder_name = involvement.stakeholder.name
    involvement.delete()
    
    messages.success(request, f'Removed {stakeholder_name} from this task')
    return redirect('stakeholder:task_stakeholder_involvement', board_id=board_id, task_id=task_id)
