"""
Views for Conflict Detection and Resolution
"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST
import json

from kanban.models import Board
from kanban.conflict_models import (
    ConflictDetection, ConflictResolution, ConflictNotification, ResolutionPattern
)
from kanban.tasks.conflict_tasks import detect_board_conflicts_task

logger = logging.getLogger(__name__)


@login_required
def conflict_dashboard(request):
    """
    Main dashboard showing all conflicts for user's boards.
    """
    try:
        profile = request.user.profile
        organization = profile.organization
        
        # Get boards user has access to
        boards = Board.objects.filter(
            Q(organization=organization) &
            (Q(created_by=request.user) | Q(members=request.user))
        ).distinct()
        
        # Get active conflicts
        active_conflicts = ConflictDetection.objects.filter(
            board__in=boards,
            status='active'
        ).select_related('board').prefetch_related(
            'tasks', 'affected_users', 'resolutions'
        ).order_by('-severity', '-detected_at')
        
        # Get user's notifications
        user_notifications = ConflictNotification.objects.filter(
            user=request.user,
            acknowledged=False
        ).select_related('conflict').order_by('-sent_at')[:10]
        
        # Statistics
        stats = {
            'total_active': active_conflicts.count(),
            'by_severity': {
                'critical': active_conflicts.filter(severity='critical').count(),
                'high': active_conflicts.filter(severity='high').count(),
                'medium': active_conflicts.filter(severity='medium').count(),
                'low': active_conflicts.filter(severity='low').count(),
            },
            'by_type': {
                'resource': active_conflicts.filter(conflict_type='resource').count(),
                'schedule': active_conflicts.filter(conflict_type='schedule').count(),
                'dependency': active_conflicts.filter(conflict_type='dependency').count(),
            },
            'unread_notifications': user_notifications.count(),
        }
        
        # Recent resolutions (for learning display)
        recent_resolutions = ConflictDetection.objects.filter(
            board__in=boards,
            status='resolved'
        ).select_related('chosen_resolution').order_by('-resolved_at')[:5]
        
        context = {
            'conflicts': active_conflicts,
            'notifications': user_notifications,
            'stats': stats,
            'recent_resolutions': recent_resolutions,
            'boards': boards,
        }
        
        return render(request, 'kanban/conflicts/dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error loading conflict dashboard: {e}", exc_info=True)
        messages.error(request, "Error loading conflict dashboard")
        return redirect('dashboard')


@login_required
def conflict_detail(request, conflict_id):
    """
    Detailed view of a specific conflict with resolution options.
    """
    try:
        profile = request.user.profile
        organization = profile.organization
        
        # Get conflict
        conflict = get_object_or_404(
            ConflictDetection.objects.select_related('board', 'chosen_resolution').prefetch_related(
                'tasks', 'affected_users', 'resolutions'
            ),
            id=conflict_id,
            board__organization=organization
        )
        
        # Check access
        if not (conflict.board.created_by == request.user or 
                request.user in conflict.board.members.all()):
            return HttpResponseForbidden("You don't have access to this conflict")
        
        # Get resolutions sorted by confidence
        resolutions = conflict.resolutions.all().order_by('-ai_confidence')
        
        # Mark notification as read if exists
        ConflictNotification.objects.filter(
            conflict=conflict,
            user=request.user
        ).update(read_at=timezone.now())
        
        # Get similar past conflicts for context
        similar_conflicts = ConflictDetection.objects.filter(
            board=conflict.board,
            conflict_type=conflict.conflict_type,
            status='resolved'
        ).exclude(id=conflict.id).select_related('chosen_resolution')[:5]
        
        context = {
            'conflict': conflict,
            'resolutions': resolutions,
            'similar_conflicts': similar_conflicts,
            'can_resolve': True,  # Could add permission check here
        }
        
        return render(request, 'kanban/conflicts/detail.html', context)
        
    except Exception as e:
        logger.error(f"Error loading conflict detail: {e}", exc_info=True)
        messages.error(request, "Error loading conflict details")
        return redirect('conflict_dashboard')


@login_required
@require_POST
def apply_resolution(request, conflict_id, resolution_id):
    """
    Apply a specific resolution to resolve a conflict.
    """
    try:
        profile = request.user.profile
        organization = profile.organization
        
        # Get conflict and resolution
        conflict = get_object_or_404(
            ConflictDetection,
            id=conflict_id,
            board__organization=organization,
            status='active'
        )
        
        resolution = get_object_or_404(
            ConflictResolution,
            id=resolution_id,
            conflict=conflict
        )
        
        # Check access
        if not (conflict.board.created_by == request.user or 
                request.user in conflict.board.members.all()):
            return JsonResponse({
                'success': False,
                'error': "You don't have permission to resolve this conflict"
            }, status=403)
        
        # Get optional feedback from request
        feedback = request.POST.get('feedback', '')
        effectiveness = request.POST.get('effectiveness')
        
        if effectiveness:
            try:
                effectiveness = int(effectiveness)
                if not (1 <= effectiveness <= 5):
                    effectiveness = None
            except (ValueError, TypeError):
                effectiveness = None
        
        # Apply resolution
        resolution.apply(request.user)
        
        # Update conflict with feedback
        conflict.resolve(resolution, request.user, feedback, effectiveness)
        
        messages.success(request, f"Resolution applied successfully: {resolution.title}")
        
        return JsonResponse({
            'success': True,
            'message': 'Resolution applied successfully',
            'redirect': f'/kanban/conflicts/{conflict.id}/'
        })
        
    except Exception as e:
        logger.error(f"Error applying resolution: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def ignore_conflict(request, conflict_id):
    """
    Mark a conflict as ignored.
    """
    try:
        profile = request.user.profile
        organization = profile.organization
        
        conflict = get_object_or_404(
            ConflictDetection,
            id=conflict_id,
            board__organization=organization,
            status='active'
        )
        
        # Check access
        if not (conflict.board.created_by == request.user or 
                request.user in conflict.board.members.all()):
            return JsonResponse({
                'success': False,
                'error': "You don't have permission"
            }, status=403)
        
        reason = request.POST.get('reason', '')
        conflict.ignore(request.user, reason)
        
        messages.info(request, "Conflict marked as ignored")
        
        return JsonResponse({
            'success': True,
            'message': 'Conflict ignored',
            'redirect': '/kanban/conflicts/'
        })
        
    except Exception as e:
        logger.error(f"Error ignoring conflict: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def acknowledge_notification(request, notification_id):
    """
    Acknowledge a conflict notification.
    """
    try:
        notification = get_object_or_404(
            ConflictNotification,
            id=notification_id,
            user=request.user
        )
        
        notification.acknowledge()
        
        return JsonResponse({
            'success': True,
            'message': 'Notification acknowledged'
        })
        
    except Exception as e:
        logger.error(f"Error acknowledging notification: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def trigger_detection_all(request):
    """
    Manually trigger conflict detection for all accessible boards.
    """
    try:
        profile = request.user.profile
        organization = profile.organization
        
        # Get all accessible boards
        boards = Board.objects.filter(
            Q(organization=organization) &
            (Q(created_by=request.user) | Q(members=request.user))
        ).distinct()
        
        # Trigger detection for each board
        count = 0
        for board in boards:
            detect_board_conflicts_task.delay(board.id)
            count += 1
        
        messages.success(request, f"Conflict detection started for {count} board(s)")
        
        return JsonResponse({
            'success': True,
            'message': f'Conflict detection started for {count} board(s). Results will appear shortly.',
            'boards_scanned': count
        })
        
    except Exception as e:
        logger.error(f"Error triggering detection for all boards: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
def trigger_detection(request, board_id):
    """
    Manually trigger conflict detection for a specific board.
    """
    try:
        profile = request.user.profile
        organization = profile.organization
        
        board = get_object_or_404(
            Board,
            id=board_id,
            organization=organization
        )
        
        # Check access
        if not (board.created_by == request.user or 
                request.user in board.members.all()):
            return JsonResponse({
                'success': False,
                'error': "You don't have permission"
            }, status=403)
        
        # Trigger async conflict detection
        detect_board_conflicts_task.delay(board.id)
        
        messages.success(request, f"Conflict detection started for {board.name}")
        
        return JsonResponse({
            'success': True,
            'message': 'Conflict detection started. Results will appear shortly.'
        })
        
    except Exception as e:
        logger.error(f"Error triggering detection: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def conflict_analytics(request):
    """
    Analytics view showing conflict patterns and resolution effectiveness.
    """
    try:
        profile = request.user.profile
        organization = profile.organization
        
        # Get boards
        boards = Board.objects.filter(
            Q(organization=organization) &
            (Q(created_by=request.user) | Q(members=request.user))
        ).distinct()
        
        # Get resolution patterns
        patterns = ResolutionPattern.objects.filter(
            Q(board__in=boards) | Q(board__isnull=True)
        ).order_by('-success_rate', '-times_used')[:20]
        
        # Historical data
        resolved_conflicts = ConflictDetection.objects.filter(
            board__in=boards,
            status='resolved'
        ).select_related('chosen_resolution')
        
        # Calculate metrics
        total_resolved = resolved_conflicts.count()
        avg_resolution_time = None
        
        if total_resolved > 0:
            from django.db.models import Avg, F, ExpressionWrapper, DurationField
            
            avg_resolution_time = resolved_conflicts.annotate(
                resolution_duration=ExpressionWrapper(
                    F('resolved_at') - F('detected_at'),
                    output_field=DurationField()
                )
            ).aggregate(avg=Avg('resolution_duration'))['avg']
        
        # Effectiveness ratings
        rated_conflicts = resolved_conflicts.filter(
            resolution_effectiveness__isnull=False
        )
        
        avg_effectiveness = rated_conflicts.aggregate(
            Avg('resolution_effectiveness')
        )['resolution_effectiveness__avg']
        
        context = {
            'patterns': patterns,
            'total_resolved': total_resolved,
            'avg_resolution_time': avg_resolution_time,
            'avg_effectiveness': avg_effectiveness,
            'rated_count': rated_conflicts.count(),
        }
        
        return render(request, 'kanban/conflicts/analytics.html', context)
        
    except Exception as e:
        logger.error(f"Error loading conflict analytics: {e}", exc_info=True)
        messages.error(request, "Error loading analytics")
        return redirect('conflict_dashboard')


@login_required
def get_conflict_notifications(request):
    """
    API endpoint to get user's unread conflict notifications.
    """
    try:
        notifications = ConflictNotification.objects.filter(
            user=request.user,
            acknowledged=False
        ).select_related('conflict__board').order_by('-sent_at')[:10]
        
        data = [{
            'id': n.id,
            'conflict_id': n.conflict.id,
            'title': n.conflict.title,
            'severity': n.conflict.severity,
            'board_name': n.conflict.board.name,
            'sent_at': n.sent_at.isoformat(),
        } for n in notifications]
        
        return JsonResponse({
            'success': True,
            'notifications': data,
            'count': len(data)
        })
        
    except Exception as e:
        logger.error(f"Error fetching notifications: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
