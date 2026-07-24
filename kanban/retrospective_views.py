"""
Views for AI-Powered Retrospective Generator
"""

import logging
import time
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

from kanban.models import Board, Task
from kanban.favorite_views import is_user_favorite as _is_fav
from kanban.retrospective_models import (
    ProjectRetrospective, LessonLearned, ImprovementMetric,
    RetrospectiveActionItem, RetrospectiveTrend
)
from kanban.utils.retrospective_generator import RetrospectiveGenerator
from kanban.simple_access import check_access_or_403, check_modify_or_403
from api.ai_usage_utils import track_ai_request, check_ai_quota

logger = logging.getLogger(__name__)


def _add_manual_lessons(retrospective, board, lessons_list):
    """Add manually entered lessons learned"""
    for lesson_text in lessons_list:
        try:
            LessonLearned.objects.create(
                retrospective=retrospective,
                board=board,
                title=lesson_text[:100],
                description=lesson_text,
                category='other',
                priority='medium',
                recommended_action='Review and implement this lesson in the next sprint.',
                ai_suggested=False,
                status='identified'
            )
        except Exception as e:
            logger.error(f"Error creating manual lesson: {e}")


def _add_manual_actions(retrospective, board, actions_list):
    """Add manually entered action items"""
    for action_text in actions_list:
        try:
            target_date = timezone.now().date() + timedelta(days=30)
            RetrospectiveActionItem.objects.create(
                retrospective=retrospective,
                board=board,
                title=action_text[:100],
                description=action_text,
                action_type='process_change',
                priority='medium',
                target_completion_date=target_date,
                ai_suggested=False,
                status='pending'
            )
        except Exception as e:
            logger.error(f"Error creating manual action: {e}")


@login_required
def retrospective_list(request, board_id):
    """List all retrospectives for a board"""
    board = get_object_or_404(Board, id=board_id)
    check_access_or_403(request.user, board)

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
    
    # Summary statistics — counts are always board-wide, unaffected by filters
    all_retrospectives = ProjectRetrospective.objects.filter(board=board)
    stats = {
        'total_retrospectives': all_retrospectives.count(),
        'finalized_count': all_retrospectives.filter(status='finalized').count(),
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
        'is_demo_mode': False,
        'is_demo_board': False,
    }
    
    return render(request, 'kanban/retrospective_list.html', context)


@login_required
def retrospective_detail(request, board_id, retro_id):
    """View detailed retrospective"""
    board = get_object_or_404(Board, id=board_id)
    check_access_or_403(request.user, board)
    retrospective = get_object_or_404(
        ProjectRetrospective.objects.select_related('created_by', 'finalized_by'),
        id=retro_id,
        board=board
    )
    
    # Get related data
    lessons = retrospective.lessons.all().order_by('-priority', '-created_at')
    action_items = retrospective.action_items.all().order_by('-priority', 'target_completion_date')
    metrics = retrospective.metrics.all().order_by('metric_type')
    
    # Calculate statistics
    snapshot = retrospective.metrics_snapshot or {}
    total_tasks = snapshot.get('total_tasks', 0)
    completion_rate = snapshot.get('completion_rate', 0)
    
    # Recalculate from live board data if snapshot has zero tasks
    if total_tasks == 0:
        live_tasks = Task.objects.filter(column__board=board)
        total_tasks = live_tasks.count()
        if total_tasks > 0:
            done_count = live_tasks.filter(progress=100).count()
            completion_rate = round(done_count / total_tasks * 100, 1)
    
    stats = {
        'lessons_count': lessons.count(),
        'lessons_implemented': lessons.filter(status__in=['implemented', 'validated']).count(),
        'actions_count': action_items.count(),
        'actions_completed': action_items.filter(status='completed').count(),
        'actions_overdue': action_items.filter(
            target_completion_date__lt=timezone.now().date(),
            status__in=['pending', 'in_progress']
        ).count(),
        'total_tasks': total_tasks,
        'completion_rate': completion_rate,
    }

    # Scope label for the stat tiles. A milestone/sprint retrospective reports on
    # its own period, not the whole board — without this, "8 tasks / 100%
    # complete" reads as a claim about a board the Burndown page says is 36%
    # done, and the two features look like they disagree.
    scope_label = (snapshot.get('phase_tag')
                   or retrospective.get_retrospective_type_display())

    # Velocity is stored as tasks-completed-per-period (see
    # _refresh_retrospective_metrics), so express the period alongside it rather
    # than leaving a bare "8.00 tasks" to be read as a weekly rate.
    period_weeks = None
    velocity_per_week = None
    if retrospective.period_start and retrospective.period_end:
        period_days = (retrospective.period_end - retrospective.period_start).days
        if period_days > 0:
            period_weeks = period_days / 7
            velocity = snapshot.get('velocity')
            if velocity:
                velocity_per_week = velocity / period_weeks

    context = {
        'board': board,
        'retrospective': retrospective,
        'lessons': lessons,
        'action_items': action_items,
        'metrics': metrics,
        'stats': stats,
        'scope_label': scope_label,
        'period_weeks': period_weeks,
        'velocity_per_week': velocity_per_week,
        'is_demo_mode': False,
        'is_demo_board': False,
        'is_favorited': _is_fav(request.user, 'retrospective', retrospective.pk),
    }
    
    return render(request, 'kanban/retrospective_detail.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def retrospective_create(request, board_id):
    """Create a new retrospective"""
    board = get_object_or_404(Board, id=board_id)
    check_modify_or_403(request.user, board)

    if request.method == 'GET':
        # Show form for date selection
        # Suggest default period (last 14 days for sprint, last 30 for project)
        suggested_end = timezone.now().date()
        suggested_start = suggested_end - timedelta(days=14)
        
        context = {
            'board': board,
            'suggested_start': suggested_start,
            'suggested_end': suggested_end,
            'is_demo_mode': False,
            'is_demo_board': False,
        }
        return render(request, 'kanban/retrospective_create.html', context)
    
    else:  # POST
        start_time = time.time()
        try:
            # Check AI quota
            has_quota, quota, remaining = check_ai_quota(request.user)
            if not has_quota:
                messages.error(request, "AI usage quota exceeded. Please upgrade or wait for quota reset.")
                return redirect('retrospective_create', board_id=board_id)
            
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
            
            # Get manual inputs (if provided)
            manual_lessons = request.POST.getlist('manual_lessons[]')
            manual_actions = request.POST.getlist('manual_actions[]')
            
            # Filter out empty entries
            manual_lessons = [lesson.strip() for lesson in manual_lessons if lesson.strip()]
            manual_actions = [action.strip() for action in manual_actions if action.strip()]
            
            # Generate retrospective
            generator = RetrospectiveGenerator(board, period_start, period_end, user=request.user)
            
            retrospective = generator.create_retrospective(
                created_by=request.user,
                retrospective_type=retrospective_type
            )
            
            # Add manual lessons and actions
            if manual_lessons:
                _add_manual_lessons(retrospective, board, manual_lessons)
            if manual_actions:
                _add_manual_actions(retrospective, board, manual_actions)
            
            # Track successful AI request
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='retrospective_generation',
                request_type='generate',
                board_id=board.id,
                success=True,
                response_time_ms=response_time_ms
            )
            
            messages.success(
                request,
                f"Retrospective generated successfully! AI analyzed {retrospective.metrics_snapshot.get('total_tasks', 0)} tasks."
            )
            return redirect('retrospective_detail', board_id=board_id, retro_id=retrospective.id)
            
        except Exception as e:
            # Track failed request (doesn't count against quota)
            response_time_ms = int((time.time() - start_time) * 1000)
            track_ai_request(
                user=request.user,
                feature='retrospective_generation',
                request_type='generate',
                board_id=board.id,
                success=False,
                error_message=str(e),
                response_time_ms=response_time_ms
            )
            logger.error(f"Error creating retrospective: {e}")
            messages.error(request, f"Error generating retrospective: {str(e)}")
            return redirect('retrospective_create', board_id=board_id)


@login_required
@require_http_methods(["POST"])
def retrospective_finalize(request, board_id, retro_id):
    """Finalize a retrospective"""
    board = get_object_or_404(Board, id=board_id)
    check_modify_or_403(request.user, board)
    retrospective = get_object_or_404(ProjectRetrospective, id=retro_id, board=board)

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
    check_access_or_403(request.user, board)
    
    # Get recent retrospectives
    retrospectives = ProjectRetrospective.objects.filter(
        board=board,
        status__in=['reviewed', 'finalized']
    ).order_by('-period_end')[:10]
    
    # Aggregate statistics
    all_lessons = LessonLearned.objects.filter(board=board)
    all_actions = RetrospectiveActionItem.objects.filter(board=board)
    
    total_retrospectives = ProjectRetrospective.objects.filter(board=board).count()

    # "Recurring" means the same issue surfaced in 2+ retrospectives, so the
    # claim is only supportable once the board has 2+ retrospectives to compare.
    # With a single retro the panel was asserting a recurrence its own data
    # could not evidence (a "2x" badge with nothing to recur against).
    if total_retrospectives >= 2:
        recurring_lessons = all_lessons.filter(
            is_recurring_issue=True
        ).order_by('-recurrence_count', '-priority')
    else:
        recurring_lessons = all_lessons.none()

    stats = {
        'total_retrospectives': total_retrospectives,
        'total_lessons': all_lessons.count(),
        'lessons_implemented': all_lessons.filter(status__in=['implemented', 'validated']).count(),
        'implementation_rate': 0,
        'total_actions': all_actions.count(),
        'actions_completed': all_actions.filter(status='completed').count(),
        'completion_rate': 0,
        'recurring_issues': recurring_lessons.count(),
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
    
    # Get urgent actions — overdue, or due within 48 hours.
    #
    # This used to filter on priority alone, so a high-priority item due in 8
    # days appeared under "Urgent" on a board that also had genuinely overdue
    # work. Urgency is a function of the clock, not the priority label: an
    # untouched critical item due next month is important, not urgent.
    # Items with no target date can never be overdue, so they are excluded.
    _today = timezone.now().date()
    _imminent_cutoff = _today + timedelta(days=2)
    urgent_actions = all_actions.filter(
        status__in=['pending', 'in_progress'],
        target_completion_date__isnull=False,
        target_completion_date__lte=_imminent_cutoff,
    ).order_by('target_completion_date', '-priority')[:10]

    # Everything else still worth surfacing: high/critical work that is not yet
    # urgent. Keeps the important-but-not-urgent items visible without
    # mislabelling them.
    upcoming_actions = all_actions.filter(
        status__in=['pending', 'in_progress'],
        priority__in=['high', 'critical'],
    ).exclude(
        id__in=urgent_actions.values_list('id', flat=True)
    ).order_by('target_completion_date', '-priority')[:5]
    
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
        'upcoming_actions': upcoming_actions,
        'trend': trend,
        'recurring_lessons': recurring_lessons,
        'is_demo_mode': False,
        'is_demo_board': False,
    }
    
    return render(request, 'kanban/retrospective_dashboard.html', context)


@login_required
@require_http_methods(["POST"])
def lesson_update_status(request, board_id, lesson_id):
    """Update lesson learned status"""
    board = get_object_or_404(Board, id=board_id)
    check_modify_or_403(request.user, board)
    lesson = get_object_or_404(LessonLearned, id=lesson_id, board=board)
    
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
    check_modify_or_403(request.user, board)
    action = get_object_or_404(RetrospectiveActionItem, id=action_id, board=board)
    
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
    check_access_or_403(request.user, board)

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
        'is_demo_mode': False,
        'is_demo_board': False,
    }
    
    return render(request, 'kanban/lessons_learned_list.html', context)


@login_required
def retrospective_actions_list(request, board_id):
    """View all action items across all retrospectives for a board"""
    board = get_object_or_404(Board, id=board_id)
    check_access_or_403(request.user, board)

    all_board_actions = RetrospectiveActionItem.objects.filter(board=board)

    # Summary stats (before filtering)
    completed_count = all_board_actions.filter(status='completed').count()
    pending_count = all_board_actions.filter(status__in=['pending', 'in_progress']).count()
    overdue_count = all_board_actions.filter(
        status__in=['pending', 'in_progress'],
        target_completion_date__lt=timezone.now().date()
    ).count()

    actions = all_board_actions.select_related(
        'retrospective', 'assigned_to'
    ).order_by('status', 'target_completion_date')

    status_filter = request.GET.get('status')
    if status_filter:
        actions = actions.filter(status=status_filter)

    priority_filter = request.GET.get('priority')
    if priority_filter:
        actions = actions.filter(priority=priority_filter)

    paginator = Paginator(actions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    priority_choices = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    context = {
        'board': board,
        'page_obj': page_obj,
        'actions': page_obj,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'status_choices': RetrospectiveActionItem.STATUS_CHOICES,
        'priority_choices': priority_choices,
        'completed_count': completed_count,
        'pending_count': pending_count,
        'overdue_count': overdue_count,
    }
    return render(request, 'kanban/retrospective_actions_list.html', context)


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
    """Export retrospective as PDF"""
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    from io import BytesIO
    from django.http import HttpResponse

    board = get_object_or_404(Board, id=board_id)
    check_access_or_403(request.user, board)
    retrospective = get_object_or_404(ProjectRetrospective, id=retro_id, board=board)
    
    # Get related data
    lessons = retrospective.lessons.all().order_by('-priority', '-created_at')
    action_items = retrospective.action_items.all().order_by('-priority', 'target_completion_date')
    
    # Create PDF in memory
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=18)
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1f77b4'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=12,
        spaceBefore=12,
        leftIndent=0
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=6,
        spaceBefore=6
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=10,
        alignment=TA_JUSTIFY,
        spaceAfter=12
    )
    
    # Title
    elements.append(Paragraph(retrospective.title, title_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Header information
    generated_at_local = timezone.localtime(retrospective.ai_generated_at) if retrospective.ai_generated_at else None
    info_data = [
        ['Board:', board.name],
        ['Type:', retrospective.get_retrospective_type_display()],
        ['Period:', f"{retrospective.period_start.strftime('%B %d, %Y')} - {retrospective.period_end.strftime('%B %d, %Y')}"],
        ['Status:', retrospective.get_status_display()],
        ['Generated:', generated_at_local.strftime('%B %d, %Y at %I:%M %p') if generated_at_local else 'N/A'],
    ]
    
    if retrospective.team_morale_indicator:
        info_data.append(['Team Morale:', retrospective.get_team_morale_indicator_display()])
    
    if retrospective.overall_sentiment_score:
        sentiment_pct = float(retrospective.overall_sentiment_score) * 100
        info_data.append(['Sentiment Score:', f"{sentiment_pct:.1f}%"])
    
    info_table = Table(info_data, colWidths=[1.5*inch, 4.5*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.3 * inch))
    
    # Key Metrics
    if retrospective.metrics_snapshot:
        elements.append(Paragraph("Key Metrics", heading_style))
        metrics = retrospective.metrics_snapshot
        
        metrics_data = [['Metric', 'Value']]
        if 'total_tasks' in metrics:
            metrics_data.append(['Total Tasks', str(metrics.get('total_tasks', 0))])
        if 'completed_tasks' in metrics:
            metrics_data.append(['Completed Tasks', str(metrics.get('completed_tasks', 0))])
        if 'completion_rate' in metrics:
            metrics_data.append(['Completion Rate', f"{metrics.get('completion_rate', 0):.1f}%"])
        if 'average_completion_time' in metrics:
            metrics_data.append(['Avg Completion Time', f"{metrics.get('average_completion_time', 0):.1f} days"])
        if 'team_velocity' in metrics:
            metrics_data.append(['Team Velocity', f"{metrics.get('team_velocity', 0):.1f} tasks"])
        
        metrics_table = Table(metrics_data, colWidths=[3*inch, 3*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        elements.append(metrics_table)
        elements.append(Spacer(1, 0.3 * inch))
    
    # What Went Well
    if retrospective.what_went_well:
        elements.append(Paragraph("✅ What Went Well", heading_style))
        elements.append(Paragraph(retrospective.what_went_well.replace('\n', '<br/>'), body_style))
        elements.append(Spacer(1, 0.2 * inch))
    
    # What Needs Improvement
    if retrospective.what_needs_improvement:
        elements.append(Paragraph("⚠️ What Needs Improvement", heading_style))
        elements.append(Paragraph(retrospective.what_needs_improvement.replace('\n', '<br/>'), body_style))
        elements.append(Spacer(1, 0.2 * inch))
    
    # Lessons Learned
    if lessons.exists():
        elements.append(Paragraph("🎓 Lessons Learned", heading_style))
        
        for i, lesson in enumerate(lessons, 1):
            lesson_text = f"<b>{i}. {lesson.title}</b><br/>"
            if lesson.description and lesson.description != lesson.title:
                lesson_text += f"{lesson.description}<br/>"
            lesson_text += f"<i>Category: {lesson.get_category_display()} | Priority: {lesson.get_priority_display()}"
            if not lesson.ai_suggested:
                lesson_text += " | Manual Entry"
            lesson_text += "</i>"
            elements.append(Paragraph(lesson_text, body_style))
        
        elements.append(Spacer(1, 0.2 * inch))
    
    # Action Items
    if action_items.exists():
        elements.append(Paragraph("📋 Action Items", heading_style))
        
        for i, action in enumerate(action_items, 1):
            action_text = f"<b>{i}. {action.title}</b><br/>"
            if action.description and action.description != action.title:
                action_text += f"{action.description}<br/>"
            action_text += f"<i>Priority: {action.get_priority_display()} | "
            if action.target_completion_date:
                action_text += f"Target: {action.target_completion_date.strftime('%B %d, %Y')} | "
            action_text += f"Status: {action.get_status_display()}"
            if action.assigned_to:
                action_text += f" | Assigned to: {action.assigned_to.get_full_name() or action.assigned_to.username}"
            if not action.ai_suggested:
                action_text += " | Manual Entry"
            action_text += "</i>"
            elements.append(Paragraph(action_text, body_style))
        
        elements.append(Spacer(1, 0.2 * inch))
    
    # Footer
    elements.append(Spacer(1, 0.3 * inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.grey,
        alignment=TA_CENTER
    )
    elements.append(Paragraph(
        f"Generated on {timezone.localtime(timezone.now()).strftime('%B %d, %Y at %I:%M %p')} | PrizMAI Project Management",
        footer_style
    ))
    
    # Build PDF
    doc.build(elements)
    
    # Get PDF from buffer
    pdf = buffer.getvalue()
    buffer.close()
    
    # Create response
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="retrospective_{board.name.replace(" ", "_")}_{retrospective.period_start}.pdf"'
    response.write(pdf)
    
    return response

