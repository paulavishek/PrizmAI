"""
Views for AI-Powered Retrospective Generator
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods

from kanban.models import Board
from kanban.retrospective_models import (
    ProjectRetrospective, LessonLearned, ImprovementMetric,
    RetrospectiveActionItem, RetrospectiveTrend
)
from kanban.utils.retrospective_generator import RetrospectiveGenerator

logger = logging.getLogger(__name__)


@login_required
def retrospective_list(request, board_id):
    """List all retrospectives for a board"""
    board = get_object_or_404(Board, id=board_id)
    
    # Check permissions
    if not (request.user == board.created_by or request.user in board.members.all()):
        return HttpResponseForbidden("You don't have access to this board")
    
    retrospectives = ProjectRetrospective.objects.filter(board=board).select_related(
        'created_by', 'finalized_by'
    ).prefetch_related('lessons', 'action_items', 'metrics')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        retrospectives = retrospectives.filter(status=status_filter)
    
    # Filter by type
    type_filter = request.GET.get('type')
    if type_filter:
        retrospectives = retrospectives.filter(retrospective_type=type_filter)
    
    # Pagination
    paginator = Paginator(retrospectives, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Summary statistics
    stats = {
        'total_retrospectives': retrospectives.count(),
        'finalized_count': retrospectives.filter(status='finalized').count(),
        'total_lessons': LessonLearned.objects.filter(board=board).count(),
        'implemented_lessons': LessonLearned.objects.filter(
            board=board, status__in=['implemented', 'validated']
        ).count(),
        'total_actions': RetrospectiveActionItem.objects.filter(board=board).count(),
        'completed_actions': RetrospectiveActionItem.objects.filter(
            board=board, status='completed'
        ).count(),
    }
    
    context = {
        'board': board,
        'page_obj': page_obj,
        'retrospectives': page_obj,
        'stats': stats,
        'status_filter': status_filter,
        'type_filter': type_filter,
    }
    
    return render(request, 'kanban/retrospective_list.html', context)


@login_required
def retrospective_detail(request, board_id, retro_id):
    """View detailed retrospective"""
    board = get_object_or_404(Board, id=board_id)
    retrospective = get_object_or_404(
        ProjectRetrospective.objects.select_related('created_by', 'finalized_by'),
        id=retro_id,
        board=board
    )
    
    # Check permissions
    if not (request.user == board.created_by or request.user in board.members.all()):
        return HttpResponseForbidden("You don't have access to this board")
    
    # Get related data
    lessons = retrospective.lessons.all().order_by('-priority', '-created_at')
    action_items = retrospective.action_items.all().order_by('-priority', 'target_completion_date')
    metrics = retrospective.metrics.all().order_by('metric_type')
    
    # Calculate statistics
    stats = {
        'lessons_count': lessons.count(),
        'lessons_implemented': lessons.filter(status__in=['implemented', 'validated']).count(),
        'actions_count': action_items.count(),
        'actions_completed': action_items.filter(status='completed').count(),
        'actions_overdue': action_items.filter(
            target_completion_date__lt=timezone.now().date(),
            status__in=['pending', 'in_progress']
        ).count(),
    }
    
    context = {
        'board': board,
        'retrospective': retrospective,
        'lessons': lessons,
        'action_items': action_items,
        'metrics': metrics,
        'stats': stats,
    }
    
    return render(request, 'kanban/retrospective_detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def retrospective_create(request, board_id):
    """Create a new retrospective"""
    board = get_object_or_404(Board, id=board_id)
    
    # Check permissions
    if not (request.user == board.created_by or request.user in board.members.all()):
        return HttpResponseForbidden("You don't have access to this board")
    
    if request.method == 'GET':
        # Show form for date selection
        # Suggest default period (last 14 days for sprint, last 30 for project)
        suggested_end = timezone.now().date()
        suggested_start = suggested_end - timedelta(days=14)
        
        context = {
            'board': board,
            'suggested_start': suggested_start,
            'suggested_end': suggested_end,
        }
        return render(request, 'kanban/retrospective_create.html', context)
    
    else:  # POST
        try:
            # Get form data
            period_start = datetime.strptime(request.POST.get('period_start'), '%Y-%m-%d').date()
            period_end = datetime.strptime(request.POST.get('period_end'), '%Y-%m-%d').date()
            retrospective_type = request.POST.get('retrospective_type', 'sprint')
            
            # Validate dates
            if period_start >= period_end:
                messages.error(request, "Start date must be before end date")
                return redirect('retrospective_create', board_id=board_id)
            
            if period_end > timezone.now().date():
                messages.error(request, "End date cannot be in the future")
                return redirect('retrospective_create', board_id=board_id)
            
            # Generate retrospective
            generator = RetrospectiveGenerator(board, period_start, period_end)
            retrospective = generator.create_retrospective(
                created_by=request.user,
                retrospective_type=retrospective_type
            )
            
            messages.success(
                request,
                f"Retrospective generated successfully! AI analyzed {retrospective.metrics_snapshot.get('total_tasks', 0)} tasks."
            )
            return redirect('retrospective_detail', board_id=board_id, retro_id=retrospective.id)
            
        except Exception as e:
            logger.error(f"Error creating retrospective: {e}")
            messages.error(request, f"Error generating retrospective: {str(e)}")
            return redirect('retrospective_create', board_id=board_id)


@login_required
@require_http_methods(["POST"])
def retrospective_finalize(request, board_id, retro_id):
    """Finalize a retrospective"""
    board = get_object_or_404(Board, id=board_id)
    retrospective = get_object_or_404(ProjectRetrospective, id=retro_id, board=board)
    
    # Check permissions (only board owner or creator)
    if not (request.user == board.created_by or request.user == retrospective.created_by):
        return HttpResponseForbidden("You don't have permission to finalize this retrospective")
    
    # Add team notes if provided
    team_notes = request.POST.get('team_notes', '')
    if team_notes:
        retrospective.team_notes = team_notes
    
    retrospective.finalize(request.user)
    
    messages.success(request, "Retrospective finalized successfully!")
    return redirect('retrospective_detail', board_id=board_id, retro_id=retro_id)


@login_required
def retrospective_dashboard(request, board_id):
    """Dashboard showing improvement trends over time"""
    board = get_object_or_404(Board, id=board_id)
    
    # Check permissions
    if not (request.user == board.created_by or request.user in board.members.all()):
        return HttpResponseForbidden("You don't have access to this board")
    
    # Get recent retrospectives
    retrospectives = ProjectRetrospective.objects.filter(
        board=board,
        status__in=['reviewed', 'finalized']
    ).order_by('-period_end')[:10]
    
    # Aggregate statistics
    all_lessons = LessonLearned.objects.filter(board=board)
    all_actions = RetrospectiveActionItem.objects.filter(board=board)
    
    stats = {
        'total_retrospectives': ProjectRetrospective.objects.filter(board=board).count(),
        'total_lessons': all_lessons.count(),
        'lessons_implemented': all_lessons.filter(status__in=['implemented', 'validated']).count(),
        'implementation_rate': 0,
        'total_actions': all_actions.count(),
        'actions_completed': all_actions.filter(status='completed').count(),
        'completion_rate': 0,
        'recurring_issues': all_lessons.filter(is_recurring_issue=True).count(),
    }
    
    if stats['total_lessons'] > 0:
        stats['implementation_rate'] = (stats['lessons_implemented'] / stats['total_lessons'] * 100)
    
    if stats['total_actions'] > 0:
        stats['completion_rate'] = (stats['actions_completed'] / stats['total_actions'] * 100)
    
    # Get metrics over time
    metrics_data = ImprovementMetric.objects.filter(
        board=board
    ).values('metric_type', 'metric_name').annotate(
        avg_value=Avg('metric_value'),
        count=Count('id')
    ).order_by('metric_type')
    
    # Get top lessons by category
    lessons_by_category = all_lessons.values('category').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # Get pending high-priority actions
    urgent_actions = all_actions.filter(
        status__in=['pending', 'in_progress'],
        priority__in=['high', 'critical']
    ).order_by('-priority', 'target_completion_date')[:10]
    
    # Calculate trend
    trend = None
    if retrospectives.count() >= 2:
        trend = RetrospectiveTrend.objects.filter(
            board=board,
            period_type='quarterly'
        ).order_by('-analysis_date').first()
        
        if not trend or (timezone.now().date() - trend.analysis_date).days > 30:
            # Generate new trend analysis
            trend = _generate_trend_analysis(board)
    
    context = {
        'board': board,
        'retrospectives': retrospectives,
        'stats': stats,
        'metrics_data': metrics_data,
        'lessons_by_category': lessons_by_category,
        'urgent_actions': urgent_actions,
        'trend': trend,
    }
    
    return render(request, 'kanban/retrospective_dashboard.html', context)


@login_required
@require_http_methods(["POST"])
def lesson_update_status(request, board_id, lesson_id):
    """Update lesson learned status"""
    board = get_object_or_404(Board, id=board_id)
    lesson = get_object_or_404(LessonLearned, id=lesson_id, board=board)
    
    # Check permissions
    if not (request.user == board.created_by or request.user in board.members.all()):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    new_status = request.POST.get('status')
    if new_status not in dict(LessonLearned.STATUS_CHOICES):
        return JsonResponse({'error': 'Invalid status'}, status=400)
    
    lesson.status = new_status
    
    if new_status == 'implemented':
        lesson.implementation_date = timezone.now().date()
    elif new_status == 'validated':
        lesson.validation_date = timezone.now().date()
    
    lesson.save()
    
    return JsonResponse({
        'success': True,
        'status': new_status,
        'status_display': lesson.get_status_display()
    })


@login_required
@require_http_methods(["POST"])
def action_update_status(request, board_id, action_id):
    """Update action item status"""
    board = get_object_or_404(Board, id=board_id)
    action = get_object_or_404(RetrospectiveActionItem, id=action_id, board=board)
    
    # Check permissions
    if not (request.user == board.created_by or request.user in board.members.all()):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    new_status = request.POST.get('status')
    progress = request.POST.get('progress')
    
    if new_status and new_status in dict(RetrospectiveActionItem.STATUS_CHOICES):
        action.status = new_status
        
        if new_status == 'completed':
            action.actual_completion_date = timezone.now().date()
            action.progress_percentage = 100
    
    if progress:
        try:
            action.progress_percentage = int(progress)
        except ValueError:
            pass
    
    action.save()
    
    return JsonResponse({
        'success': True,
        'status': action.status,
        'status_display': action.get_status_display(),
        'progress': action.progress_percentage
    })


@login_required
def lessons_learned_list(request, board_id):
    """View all lessons learned across retrospectives"""
    board = get_object_or_404(Board, id=board_id)
    
    # Check permissions
    if not (request.user == board.created_by or request.user in board.members.all()):
        return HttpResponseForbidden("You don't have access to this board")
    
    lessons = LessonLearned.objects.filter(board=board).select_related(
        'retrospective', 'action_owner'
    )
    
    # Filters
    category_filter = request.GET.get('category')
    if category_filter:
        lessons = lessons.filter(category=category_filter)
    
    status_filter = request.GET.get('status')
    if status_filter:
        lessons = lessons.filter(status=status_filter)
    
    priority_filter = request.GET.get('priority')
    if priority_filter:
        lessons = lessons.filter(priority=priority_filter)
    
    # Pagination
    paginator = Paginator(lessons, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'board': board,
        'page_obj': page_obj,
        'lessons': page_obj,
        'category_filter': category_filter,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'categories': LessonLearned.CATEGORY_CHOICES,
        'statuses': LessonLearned.STATUS_CHOICES,
        'priorities': LessonLearned.PRIORITY_CHOICES,
    }
    
    return render(request, 'kanban/lessons_learned_list.html', context)


def _generate_trend_analysis(board):
    """Generate retrospective trend analysis"""
    from kanban.retrospective_models import (
        RetrospectiveTrend, ProjectRetrospective, 
        LessonLearned, RetrospectiveActionItem, ImprovementMetric
    )
    
    # Get retrospectives from last 90 days
    start_date = timezone.now().date() - timedelta(days=90)
    retrospectives = ProjectRetrospective.objects.filter(
        board=board,
        period_end__gte=start_date,
        status__in=['reviewed', 'finalized']
    )
    
    if not retrospectives.exists():
        return None
    
    # Aggregate data
    lessons = LessonLearned.objects.filter(
        retrospective__in=retrospectives
    )
    actions = RetrospectiveActionItem.objects.filter(
        retrospective__in=retrospectives
    )
    
    # Find recurring issues
    recurring = lessons.values('title').annotate(
        count=Count('id')
    ).filter(count__gte=2).order_by('-count')[:5]
    
    recurring_issues = [
        {'issue': item['title'], 'count': item['count']}
        for item in recurring
    ]
    
    # Top categories
    top_categories = lessons.values('category', 'category').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    top_categories_list = [
        {'category': item['category'], 'count': item['count']}
        for item in top_categories
    ]
    
    # Calculate velocity trend
    metrics = ImprovementMetric.objects.filter(
        board=board,
        metric_type='velocity',
        measured_at__gte=start_date
    ).order_by('measured_at')
    
    velocity_trend = 'stable'
    if metrics.count() >= 3:
        values = list(metrics.values_list('metric_value', flat=True))
        first_half_avg = sum(values[:len(values)//2]) / (len(values)//2)
        second_half_avg = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
        
        change = ((second_half_avg - first_half_avg) / first_half_avg * 100) if first_half_avg > 0 else 0
        if change > 10:
            velocity_trend = 'improving'
        elif change < -10:
            velocity_trend = 'declining'
    
    # Create trend
    trend = RetrospectiveTrend.objects.create(
        board=board,
        period_type='quarterly',
        retrospectives_analyzed=retrospectives.count(),
        total_lessons_learned=lessons.count(),
        lessons_implemented=lessons.filter(status__in=['implemented', 'validated']).count(),
        lessons_validated=lessons.filter(status='validated').count(),
        total_action_items=actions.count(),
        action_items_completed=actions.filter(status='completed').count(),
        recurring_issues=recurring_issues,
        top_improvement_categories=top_categories_list,
        velocity_trend=velocity_trend,
        quality_trend='stable',  # Could be enhanced with more data
    )
    
    return trend


@login_required
def retrospective_export(request, board_id, retro_id):
    """Export retrospective as JSON or PDF"""
    board = get_object_or_404(Board, id=board_id)
    retrospective = get_object_or_404(ProjectRetrospective, id=retro_id, board=board)
    
    # Check permissions
    if not (request.user == board.created_by or request.user in board.members.all()):
        return HttpResponseForbidden("You don't have access to this board")
    
    export_format = request.GET.get('format', 'json')
    
    if export_format == 'json':
        import json
        from django.http import HttpResponse
        
        data = {
            'title': retrospective.title,
            'period': {
                'start': str(retrospective.period_start),
                'end': str(retrospective.period_end),
            },
            'type': retrospective.retrospective_type,
            'status': retrospective.status,
            'what_went_well': retrospective.what_went_well,
            'what_needs_improvement': retrospective.what_needs_improvement,
            'lessons_learned': retrospective.lessons_learned,
            'key_achievements': retrospective.key_achievements,
            'challenges_faced': retrospective.challenges_faced,
            'improvement_recommendations': retrospective.improvement_recommendations,
            'metrics': retrospective.metrics_snapshot,
            'sentiment_score': float(retrospective.overall_sentiment_score) if retrospective.overall_sentiment_score else None,
            'team_morale': retrospective.team_morale_indicator,
            'performance_trend': retrospective.performance_trend,
        }
        
        response = HttpResponse(
            json.dumps(data, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="retrospective_{retro_id}.json"'
        return response
    
    else:
        messages.error(request, "Export format not supported yet")
        return redirect('retrospective_detail', board_id=board_id, retro_id=retro_id)
