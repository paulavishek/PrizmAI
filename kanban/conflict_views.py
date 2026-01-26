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
from kanban.utils.conflict_detection import ConflictDetectionService
from kanban.utils.demo_permissions import DemoPermissions

logger = logging.getLogger(__name__)


def check_demo_access_for_conflicts(request, require_write=False):
    """
    Check if demo user has access to conflict features.
    
    Args:
        request: Django request object
        require_write: If True, check for write permissions (e.g., resolving conflicts)
        
    Returns:
        tuple: (has_access: bool, error_response: HttpResponse or None, is_demo_mode: bool)
    """
    is_demo_mode = request.session.get('is_demo_mode', False)
    demo_mode_type = request.session.get('demo_mode', 'solo')
    
    # If not in demo mode, require authentication
    if not is_demo_mode:
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return False, redirect_to_login(request.get_full_path()), False
        return True, None, False
    
    # SOLO MODE: Full admin access, no restrictions
    if demo_mode_type == 'solo':
        return True, None, True
    
    # TEAM MODE: Check role-based permissions
    action = 'can_edit_tasks' if require_write else 'can_view_board'
    if not DemoPermissions.can_perform_action(request, action):
        error_msg = "You don't have permission to perform this action in your current demo role."
        return False, HttpResponseForbidden(error_msg), True
    
    return True, None, True


def conflict_dashboard(request):
    """
    Main dashboard showing all conflicts for user's boards.
    Optional board_id parameter to filter by specific board.
    Supports demo mode - shows demo boards when in demo mode.
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    try:
        # Check demo access first
        has_access, error_response, is_demo_mode = check_demo_access_for_conflicts(request)
        if not has_access:
            return error_response
        
        demo_mode_type = request.session.get('demo_mode', 'solo')
        
        # Get boards user has access to
        if is_demo_mode:
            # In demo mode, only show demo organization boards
            demo_org_names = ['Demo - Acme Corporation']
            from kanban.models import Organization
            demo_orgs = Organization.objects.filter(name__in=demo_org_names)
            boards = Board.objects.filter(organization__in=demo_orgs).distinct()
        else:
            from accounts.models import Organization
            profile = request.user.profile
            organization = profile.organization
            
            # Include demo organization boards for all authenticated users
            demo_org = Organization.objects.filter(name='Demo - Acme Corporation').first()
            org_filter = Q(organization=organization)
            if demo_org:
                org_filter |= Q(organization=demo_org)
            
            boards = Board.objects.filter(
                org_filter &
                (Q(created_by=request.user) | Q(members=request.user))
            ).distinct()
        
        # Check if filtering by specific board
        board_filter_id = request.GET.get('board_id')
        selected_board = None
        if board_filter_id:
            try:
                selected_board = boards.get(id=board_filter_id)
                boards_to_show = [selected_board]
            except Board.DoesNotExist:
                boards_to_show = boards
        else:
            boards_to_show = boards
        
        # Get active conflicts
        active_conflicts = ConflictDetection.objects.filter(
            board__in=boards_to_show,
            status='active'
        ).select_related('board').prefetch_related(
            'tasks', 'affected_users', 'resolutions'
        ).order_by('-severity', '-detected_at')
        
        # Get user's notifications (only for authenticated users)
        # Filter by board if a specific board is selected
        if request.user.is_authenticated:
            notification_query = ConflictNotification.objects.filter(
                user=request.user,
                acknowledged=False,
                conflict__board__in=boards_to_show  # Filter by selected board(s)
            ).select_related('conflict').order_by('-sent_at')[:10]
            user_notifications = notification_query
        else:
            user_notifications = []
        
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
            board__in=boards_to_show,
            status='resolved'
        ).select_related('chosen_resolution').order_by('-resolved_at')[:5]
        
        context = {
            'conflicts': active_conflicts,
            'notifications': user_notifications,
            'stats': stats,
            'recent_resolutions': recent_resolutions,
            'boards': boards,
            'selected_board': selected_board,
            'is_demo_mode': is_demo_mode,
            'demo_mode_type': demo_mode_type,
        }
        
        return render(request, 'kanban/conflicts/dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error loading conflict dashboard: {e}", exc_info=True)
        messages.error(request, "Error loading conflict dashboard")
        return redirect('dashboard')


def conflict_detail(request, conflict_id):
    """
    Detailed view of a specific conflict with resolution options.
    Supports demo mode.
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    try:
        # Check demo access first
        has_access, error_response, is_demo_mode = check_demo_access_for_conflicts(request)
        if not has_access:
            return error_response
        
        demo_mode_type = request.session.get('demo_mode', 'solo')
        
        # Get conflict - for demo mode, allow access to demo org conflicts
        if is_demo_mode:
            demo_org_names = ['Demo - Acme Corporation']
            from kanban.models import Organization
            demo_orgs = Organization.objects.filter(name__in=demo_org_names)
            conflict = get_object_or_404(
                ConflictDetection.objects.select_related('board', 'chosen_resolution').prefetch_related(
                    'tasks', 'affected_users', 'resolutions'
                ),
                id=conflict_id,
                board__organization__in=demo_orgs
            )
        else:
            profile = request.user.profile
            organization = profile.organization
            conflict = get_object_or_404(
                ConflictDetection.objects.select_related('board', 'chosen_resolution').prefetch_related(
                    'tasks', 'affected_users', 'resolutions'
                ),
                id=conflict_id,
                board__organization=organization
            )
        
        # Check access (skip for demo mode)
        if not is_demo_mode:
            if not (conflict.board.created_by == request.user or 
                    request.user in conflict.board.members.all()):
                return HttpResponseForbidden("You don't have access to this conflict")
        
        # Get resolutions sorted by confidence
        resolutions = conflict.resolutions.all().order_by('-ai_confidence')
        
        # Mark notification as read if exists (only for authenticated users)
        if request.user.is_authenticated:
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
        
        # TEAM MODE: Check if user can resolve conflicts (requires edit permission)
        can_resolve = True
        if is_demo_mode and demo_mode_type == 'team':
            can_resolve = DemoPermissions.can_perform_action(request, 'can_edit_tasks')
        
        context = {
            'conflict': conflict,
            'resolutions': resolutions,
            'similar_conflicts': similar_conflicts,
            'can_resolve': can_resolve,
            'is_demo_mode': is_demo_mode,
            'demo_mode_type': demo_mode_type,
        }
        
        return render(request, 'kanban/conflicts/detail.html', context)
        
    except Exception as e:
        logger.error(f"Error loading conflict detail: {e}", exc_info=True)
        messages.error(request, "Error loading conflict details")
        return redirect('conflict_dashboard')


@require_POST
def apply_resolution(request, conflict_id, resolution_id):
    """
    Apply a specific resolution to resolve a conflict.
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    try:
        # Check demo access first (requires write permission)
        has_access, error_response, is_demo_mode = check_demo_access_for_conflicts(request, require_write=True)
        if not has_access:
            if error_response:
                # Convert redirect to JSON error for AJAX
                return JsonResponse({
                    'success': False,
                    'error': 'Authentication required'
                }, status=401)
            return JsonResponse({
                'success': False,
                'error': "You don't have permission to resolve this conflict"
            }, status=403)
        
        demo_mode_type = request.session.get('demo_mode', 'solo')
        
        # Get conflict and resolution based on access mode
        if is_demo_mode:
            demo_org_names = ['Demo - Acme Corporation']
            from kanban.models import Organization
            demo_orgs = Organization.objects.filter(name__in=demo_org_names)
            conflict = get_object_or_404(
                ConflictDetection,
                id=conflict_id,
                board__organization__in=demo_orgs,
                status='active'
            )
        else:
            profile = request.user.profile
            organization = profile.organization
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
        
        # Check access (for non-demo mode)
        if not is_demo_mode:
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
        
        # Apply resolution (use authenticated user or None for demo)
        apply_user = request.user if request.user.is_authenticated else None
        resolution.apply(apply_user)
        
        # Update conflict with feedback
        conflict.resolve(resolution, apply_user, feedback, effectiveness)
        
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


@require_POST
def ignore_conflict(request, conflict_id):
    """
    Mark a conflict as ignored.
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    try:
        # Check demo access first (requires write permission)
        has_access, error_response, is_demo_mode = check_demo_access_for_conflicts(request, require_write=True)
        if not has_access:
            return JsonResponse({
                'success': False,
                'error': "You don't have permission"
            }, status=403)
        
        # Get conflict based on access mode
        if is_demo_mode:
            demo_org_names = ['Demo - Acme Corporation']
            from kanban.models import Organization
            demo_orgs = Organization.objects.filter(name__in=demo_org_names)
            conflict = get_object_or_404(
                ConflictDetection,
                id=conflict_id,
                board__organization__in=demo_orgs,
                status='active'
            )
        else:
            profile = request.user.profile
            organization = profile.organization
            conflict = get_object_or_404(
                ConflictDetection,
                id=conflict_id,
                board__organization=organization,
                status='active'
            )
        
        # Check access (for non-demo mode)
        if not is_demo_mode:
            if not (conflict.board.created_by == request.user or 
                    request.user in conflict.board.members.all()):
                return JsonResponse({
                    'success': False,
                    'error': "You don't have permission"
            }, status=403)
        
        reason = request.POST.get('reason', '')
        ignore_user = request.user if request.user.is_authenticated else None
        conflict.ignore(ignore_user, reason)
        
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


@require_POST
def acknowledge_notification(request, notification_id):
    """
    Acknowledge a conflict notification.
    Requires authentication (notifications are user-specific).
    """
    # This requires authentication - notifications are tied to real users
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'error': 'Authentication required'
        }, status=401)
    
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


@require_POST
def conflict_feedback(request, conflict_id):
    """
    Add feedback and effectiveness rating to a resolved conflict.
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    try:
        # Check demo access first (requires write permission)
        has_access, error_response, is_demo_mode = check_demo_access_for_conflicts(request, require_write=True)
        if not has_access:
            return JsonResponse({
                'success': False,
                'error': "You don't have permission"
            }, status=403)
        
        # Get conflict based on access mode
        if is_demo_mode:
            demo_org_names = ['Demo - Acme Corporation']
            from kanban.models import Organization
            demo_orgs = Organization.objects.filter(name__in=demo_org_names)
            conflict = get_object_or_404(
                ConflictDetection,
                id=conflict_id,
                board__organization__in=demo_orgs,
                status='resolved'
            )
        else:
            profile = request.user.profile
            organization = profile.organization
            conflict = get_object_or_404(
                ConflictDetection,
                id=conflict_id,
                board__organization=organization,
                status='resolved'
            )
        
        # Get feedback and rating
        feedback = request.POST.get('feedback', '')
        effectiveness = request.POST.get('effectiveness')
        
        if effectiveness:
            try:
                effectiveness = int(effectiveness)
                if not (1 <= effectiveness <= 5):
                    effectiveness = None
            except (ValueError, TypeError):
                effectiveness = None
        
        # Update conflict with feedback
        if feedback:
            conflict.resolution_feedback = feedback
        if effectiveness:
            conflict.resolution_effectiveness = effectiveness
            # Update the resolution pattern learning
            if conflict.chosen_resolution:
                ResolutionPattern.learn_from_resolution(conflict, conflict.chosen_resolution, effectiveness)
        
        conflict.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Feedback saved'
        })
        
    except Exception as e:
        logger.error(f"Error saving conflict feedback: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    except Exception as e:
        logger.error(f"Error acknowledging notification: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
def trigger_detection_all(request):
    """
    Manually trigger conflict detection for all accessible boards.
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    try:
        # Check demo access first
        has_access, error_response, is_demo_mode = check_demo_access_for_conflicts(request, require_write=True)
        if not has_access:
            return JsonResponse({
                'success': False,
                'error': "You don't have permission"
            }, status=403)
        
        # Get all accessible boards
        if is_demo_mode:
            demo_org_names = ['Demo - Acme Corporation']
            from kanban.models import Organization
            demo_orgs = Organization.objects.filter(name__in=demo_org_names)
            boards = Board.objects.filter(organization__in=demo_orgs).distinct()
        else:
            profile = request.user.profile
            organization = profile.organization
            boards = Board.objects.filter(
                Q(organization=organization) &
                (Q(created_by=request.user) | Q(members=request.user))
            ).distinct()
        
        # Trigger detection for each board
        count = 0
        total_conflicts = 0
        sync_mode = False
        
        for board in boards:
            try:
                detect_board_conflicts_task.delay(board.id)
            except Exception as celery_error:
                # Fallback to synchronous detection if Celery/Redis unavailable
                if not sync_mode:
                    logger.warning(f"Celery unavailable, switching to sync detection: {celery_error}")
                    sync_mode = True
                
                service = ConflictDetectionService(board=board)
                results = service.detect_all_conflicts()
                total_conflicts += results['total_conflicts']
            
            count += 1
        
        if sync_mode:
            message = f'Conflict detection completed for {count} board(s). Found {total_conflicts} conflicts.'
        else:
            message = f'Conflict detection started for {count} board(s). Results will appear shortly.'
        
        messages.success(request, message)
        
        return JsonResponse({
            'success': True,
            'message': message,
            'boards_scanned': count
        })
        
    except Exception as e:
        logger.error(f"Error triggering detection for all boards: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST
def trigger_detection(request, board_id):
    """
    Manually trigger conflict detection for a specific board.
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    try:
        # Check demo access first
        has_access, error_response, is_demo_mode = check_demo_access_for_conflicts(request, require_write=True)
        if not has_access:
            return JsonResponse({
                'success': False,
                'error': "You don't have permission"
            }, status=403)
        
        # Get board based on access mode
        if is_demo_mode:
            demo_org_names = ['Demo - Acme Corporation']
            from kanban.models import Organization
            demo_orgs = Organization.objects.filter(name__in=demo_org_names)
            board = get_object_or_404(
                Board,
                id=board_id,
                organization__in=demo_orgs
            )
        else:
            profile = request.user.profile
            organization = profile.organization
            board = get_object_or_404(
                Board,
                id=board_id,
                organization=organization
            )
        
        # Check access (for non-demo mode)
        if not is_demo_mode:
            if not (board.created_by == request.user or 
                    request.user in board.members.all()):
                return JsonResponse({
                    'success': False,
                    'error': "You don't have permission"
                }, status=403)
        
        # Try async detection first, fallback to sync if Redis unavailable
        try:
            detect_board_conflicts_task.delay(board.id)
            message = 'Conflict detection started. Results will appear shortly.'
        except Exception as celery_error:
            # Fallback to synchronous detection if Celery/Redis unavailable
            logger.warning(f"Celery unavailable, running sync detection: {celery_error}")
            service = ConflictDetectionService(board=board)
            results = service.detect_all_conflicts()
            message = f"Conflict detection completed: {results['total_conflicts']} conflicts found"
        
        messages.success(request, f"Conflict detection started for {board.name}")
        
        return JsonResponse({
            'success': True,
            'message': message,
            'board_id': board.id,
            'board_name': board.name
        })
        
    except Exception as e:
        logger.error(f"Error triggering detection: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def conflict_analytics(request):
    """
    Analytics view showing conflict patterns and resolution effectiveness.
    Supports demo mode.
    ANONYMOUS ACCESS: Works for demo mode (Solo/Team)
    """
    try:
        # Check demo access first
        has_access, error_response, is_demo_mode = check_demo_access_for_conflicts(request)
        if not has_access:
            return error_response
        
        demo_mode_type = request.session.get('demo_mode', 'solo')
        
        # Get boards - filter to demo boards if in demo mode
        if is_demo_mode:
            demo_org_names = ['Demo - Acme Corporation']
            from kanban.models import Organization
            demo_orgs = Organization.objects.filter(name__in=demo_org_names)
            boards = Board.objects.filter(organization__in=demo_orgs).distinct()
        else:
            profile = request.user.profile
            organization = profile.organization
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
        
        # Import aggregation functions
        from django.db.models import Avg, F, ExpressionWrapper, DurationField
        
        # Calculate metrics
        total_resolved = resolved_conflicts.count()
        avg_resolution_time = None
        
        if total_resolved > 0:
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
        
        # Get trend data for last 30 days
        from datetime import timedelta
        from django.utils import timezone
        from django.db.models import Count
        from django.db.models.functions import TruncDate
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Get all conflicts for the boards
        all_conflicts = ConflictDetection.objects.filter(board__in=boards)
        
        # Handle potentially backwards dates in demo data
        # Count by using the earlier date as "detection" and later as "resolution"
        detected_by_date = {}
        resolved_by_date = {}
        
        for conflict in all_conflicts.filter(detected_at__isnull=False):
            # Determine which date is earlier (actual start) and later (actual end)
            if conflict.resolved_at:
                start_date = min(conflict.detected_at, conflict.resolved_at)
                end_date = max(conflict.detected_at, conflict.resolved_at)
                
                # Normalize to date only (remove time component) for consistent comparison
                start_date_only = start_date.date()
                end_date_only = end_date.date()
                thirty_days_ago_date = thirty_days_ago.date()
                
                # Count as detection on the earlier date
                if start_date_only >= thirty_days_ago_date:
                    date_key = start_date_only.strftime('%Y-%m-%d')
                    detected_by_date[date_key] = detected_by_date.get(date_key, 0) + 1
                
                # Count as resolution on the later date (only if resolved)
                if conflict.status == 'resolved' and end_date_only >= thirty_days_ago_date:
                    date_key = end_date_only.strftime('%Y-%m-%d')
                    resolved_by_date[date_key] = resolved_by_date.get(date_key, 0) + 1
            else:
                # No resolution, just count detection
                detected_date_only = conflict.detected_at.date()
                if detected_date_only >= thirty_days_ago.date():
                    date_key = detected_date_only.strftime('%Y-%m-%d')
                    detected_by_date[date_key] = detected_by_date.get(date_key, 0) + 1
        
        # Generate complete 30-day range with daily counts
        import json
        trend_labels = []
        trend_detected = []  # Daily count: conflicts detected each day
        trend_resolved = []  # Daily count: conflicts resolved each day
        
        # Use 31 days to ensure we capture data from today
        for i in range(31):
            date = (thirty_days_ago + timedelta(days=i)).date()
            date_str = date.strftime('%Y-%m-%d')
            label = date.strftime('%b %d').replace(' 0', ' ')
            
            # Get daily counts (not cumulative)
            daily_detected = detected_by_date.get(date_str, 0)
            daily_resolved = resolved_by_date.get(date_str, 0)
            
            trend_labels.append(label)
            trend_detected.append(daily_detected)
            trend_resolved.append(daily_resolved)
        
        context = {
            'patterns': patterns,
            'total_resolved': total_resolved,
            'avg_resolution_time': avg_resolution_time,
            'avg_effectiveness': avg_effectiveness,
            'rated_count': rated_conflicts.count(),
            'is_demo_mode': is_demo_mode,
            'demo_mode_type': demo_mode_type,
            'trend_labels_json': json.dumps(trend_labels),
            'trend_detected_json': json.dumps(trend_detected),
            'trend_resolved_json': json.dumps(trend_resolved),
        }
        
        return render(request, 'kanban/conflicts/analytics.html', context)
        
    except Exception as e:
        logger.error(f"Error loading conflict analytics: {e}", exc_info=True)
        messages.error(request, "Error loading analytics")
        return redirect('conflict_dashboard')


def get_conflict_notifications(request):
    """
    API endpoint to get user's unread conflict notifications.
    Requires authentication (notifications are user-specific).
    """
    # This requires authentication - notifications are tied to real users
    if not request.user.is_authenticated:
        return JsonResponse({
            'success': False,
            'error': 'Authentication required',
            'notifications': [],
            'count': 0
        }, status=401)
    
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
