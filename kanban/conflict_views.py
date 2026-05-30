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
from kanban.decorators import demo_write_guard
from kanban.utils.demo_protection import get_user_boards
from kanban.favorite_views import is_user_favorite as _is_fav
from kanban.conflict_models import (
    ConflictDetection, ConflictResolution, ConflictNotification, ResolutionPattern
)
from kanban.tasks.conflict_tasks import detect_board_conflicts_task
from kanban.utils.conflict_detection import ConflictDetectionService

logger = logging.getLogger(__name__)


@login_required
def conflict_dashboard(request):
    """
    Main dashboard showing all conflicts for user's boards.
    Optional board_id parameter to filter by specific board.
    """
    try:
        # Get boards user has access to (demo-aware)
        boards = get_user_boards(request.user)
        
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
        
        # Order by logical severity priority (critical -> low), not the raw
        # string value — alphabetical ordering would push 'critical' to the
        # bottom. Newest first within each severity tier.
        from django.db.models import Case, When, IntegerField, Value
        severity_rank = Case(
            When(severity='critical', then=Value(0)),
            When(severity='high', then=Value(1)),
            When(severity='medium', then=Value(2)),
            When(severity='low', then=Value(3)),
            default=Value(4),
            output_field=IntegerField(),
        )

        def _active_conflicts_qs():
            return ConflictDetection.objects.filter(
                board__in=boards_to_show,
                status='active'
            ).select_related('board').prefetch_related(
                'tasks', 'affected_users', 'resolutions'
            ).annotate(severity_rank=severity_rank).order_by(
                'severity_rank', '-detected_at'
            )

        active_conflicts = _active_conflicts_qs()

        # Demo workspace only: behave like every other pre-populated demo
        # feature. If the demo sandbox has no conflicts yet, run detection
        # synchronously on first visit so the dashboard isn't empty. This
        # NEVER runs for real workspaces — they keep the manual "Scan Now"
        # empty state.
        is_demo = getattr(getattr(request.user, 'profile', None), 'is_viewing_demo', False)
        if is_demo and active_conflicts.count() == 0:
            for board in boards_to_show:
                try:
                    ConflictDetectionService(board=board).detect_all_conflicts()
                except Exception as detect_err:
                    logger.warning(
                        f"Demo auto-detection failed for board {board.id}: {detect_err}"
                    )
            # Re-query now that detection has populated conflicts.
            active_conflicts = _active_conflicts_qs()

        # Ensure notifications exist for all active conflicts (safety check)
        for conflict in active_conflicts:
            conflict.ensure_notifications()
        
        # Get the user's notifications for conflicts that are STILL ACTIVE.
        #
        # We intentionally do NOT filter on ``acknowledged`` here. Acknowledging
        # a notification is not the same as resolving the conflict — a user who
        # has merely opened (or dismissed) an alert should still see it while the
        # underlying conflict remains active and unresolved. Once a conflict is
        # resolved or ignored its status changes and the notification naturally
        # drops out of this list. The ``acknowledged`` flag is still used purely
        # for read/unread styling in the template.
        user_notifications = ConflictNotification.objects.filter(
            user=request.user,
            conflict__status='active',
            conflict__board__in=boards_to_show  # Filter by selected board(s)
        ).select_related('conflict').order_by('acknowledged', '-conflict__detected_at')[:10]
        
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
        # Get boards user has access to (demo-aware)
        accessible_boards = get_user_boards(request.user)
        
        conflict = get_object_or_404(
            ConflictDetection.objects.select_related('board', 'chosen_resolution').prefetch_related(
                'tasks', 'affected_users', 'resolutions'
            ),
            id=conflict_id,
            board__in=accessible_boards
        )
        
        # Get resolutions sorted by confidence
        resolutions = conflict.resolutions.all().order_by('-ai_confidence')

        # Remove any placeholder "AI Analysis Completed" records that were created
        # by the old fallback code path when AI JSON parsing failed. These records
        # carry no useful information (title='AI Analysis Completed',
        # ai_reasoning='Generated from AI analysis') and should not be shown to
        # users. The new code no longer generates them, but legacy records may
        # still exist in the database.
        stale_fallback_ids = [
            r.pk for r in resolutions
            if r.title.strip().lower() == 'ai analysis completed'
            and (r.ai_reasoning or '').strip().lower() in ('generated from ai analysis', '')
        ]
        if stale_fallback_ids:
            conflict.resolutions.filter(pk__in=stale_fallback_ids).delete()
            resolutions = conflict.resolutions.all().order_by('-ai_confidence')
            logger.info(
                f"Removed {len(stale_fallback_ids)} stale AI fallback resolution(s) for conflict {conflict.id}"
            )

        # Detect resolutions with stale/missing substantive reasoning.
        # A resolution has only a historical note (or nothing) when its ai_reasoning
        # is either empty or starts with "Based on" (the pattern appended by
        # _apply_learned_patterns). Any resolution with real substantive text begins
        # with a sentence about the action itself, not a historical reference.
        # This silently self-heals for any user on first visit without requiring a
        # manual demo reset.
        def _has_stale_reasoning(resolution):
            text = (resolution.ai_reasoning or '').strip()
            return not text or text.startswith('Based on')

        if (
            conflict.status == 'active'
            and resolutions.exists()
            and all(_has_stale_reasoning(r) for r in resolutions)
        ):
            try:
                from kanban.utils.conflict_detection import ConflictResolutionSuggester
                logger.info(
                    f"Stale reasoning detected for conflict {conflict.id} — regenerating resolutions"
                )
                conflict.resolutions.all().delete()
                suggester = ConflictResolutionSuggester(conflict)
                suggester.generate_suggestions()
                resolutions = conflict.resolutions.all().order_by('-ai_confidence')
            except Exception as regen_error:
                logger.error(
                    f"Failed to regenerate stale resolutions for conflict {conflict.id}: {regen_error}",
                    exc_info=True,
                )

        # Generate resolutions on-demand if none exist
        if not resolutions.exists() and conflict.status == 'active':
            try:
                from kanban.utils.conflict_detection import ConflictResolutionSuggester
                logger.info(f"Generating resolutions on-demand for conflict {conflict.id}: {conflict.title}")
                suggester = ConflictResolutionSuggester(conflict)
                generated_resolutions = suggester.generate_suggestions()
                logger.info(f"Generated {len(generated_resolutions)} resolutions on-demand")
                # Refresh the queryset to include newly created resolutions
                resolutions = conflict.resolutions.all().order_by('-ai_confidence')
            except Exception as gen_error:
                logger.error(f"Failed to generate resolutions on-demand: {gen_error}", exc_info=True)
        
        # Mark notification as read if exists
        ConflictNotification.objects.filter(
            conflict=conflict,
            user=request.user
        ).update(read_at=timezone.now())

        # Display-side deduplication safety net: if the DB somehow still contains
        # duplicate suggestions (same resolution_type + title), keep only the first
        # one seen (highest confidence wins because the queryset is ordered by
        # -ai_confidence).
        deduplicated_resolutions = []
        seen_dedup_keys = set()
        for resolution in resolutions:
            dedup_key = (resolution.resolution_type, resolution.title.strip().lower())
            if dedup_key in seen_dedup_keys:
                continue
            seen_dedup_keys.add(dedup_key)
            deduplicated_resolutions.append(resolution)
        
        # Get similar past conflicts for context
        similar_conflicts = ConflictDetection.objects.filter(
            board=conflict.board,
            conflict_type=conflict.conflict_type,
            status='resolved'
        ).exclude(id=conflict.id).select_related('chosen_resolution')[:5]
        
        context = {
            'conflict': conflict,
            'resolutions': deduplicated_resolutions,
            'similar_conflicts': similar_conflicts,
            'can_resolve': True,
            'is_favorited': _is_fav(request.user, 'conflict', conflict.pk),
        }
        
        return render(request, 'kanban/conflicts/detail.html', context)
        
    except Exception as e:
        logger.error(f"Error loading conflict detail: {e}", exc_info=True)
        messages.error(request, "Error loading conflict details")
        return redirect('conflict_dashboard')


@login_required
@require_POST
@demo_write_guard
def apply_resolution(request, conflict_id, resolution_id):
    """
    Apply a specific resolution to resolve a conflict.
    """
    try:
        # Get boards user has access to (demo-aware)
        accessible_boards = get_user_boards(request.user)
        
        conflict = get_object_or_404(
            ConflictDetection,
            id=conflict_id,
            board__in=accessible_boards,
            status='active'
        )
        
        resolution = get_object_or_404(
            ConflictResolution,
            id=resolution_id,
            conflict=conflict
        )
        

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
@demo_write_guard
def ignore_conflict(request, conflict_id):
    """
    Mark a conflict as ignored.
    """
    try:
        # Get boards user has access to (demo-aware)
        accessible_boards = get_user_boards(request.user)
        
        conflict = get_object_or_404(
            ConflictDetection,
            id=conflict_id,
            board__in=accessible_boards,
            status='active'
        )
        
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
@demo_write_guard
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
@demo_write_guard
def conflict_feedback(request, conflict_id):
    """
    Add feedback and effectiveness rating to a resolved conflict.
    """
    try:
        # Get boards user has access to (demo-aware)
        accessible_boards = get_user_boards(request.user)
        
        conflict = get_object_or_404(
            ConflictDetection,
            id=conflict_id,
            board__in=accessible_boards,
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


@login_required
@require_POST
@demo_write_guard
def trigger_detection_all(request):
    """
    Manually trigger conflict detection for all accessible boards.
    Always runs synchronously so results are immediately visible. Also
    queues a Celery task (fire-and-forget) when workers are available so
    that resolution suggestions can be generated in the background.
    """
    try:
        # Get all accessible boards (demo-aware)
        boards = get_user_boards(request.user)

        count = 0
        total_conflicts = 0

        for board in boards:
            # Run detection synchronously — guarantees immediate results
            # regardless of whether Celery workers are running.
            service = ConflictDetectionService(board=board)
            results = service.detect_all_conflicts()
            total_conflicts += results['total_conflicts']

            # Also enqueue for background resolution-suggestion generation.
            try:
                detect_board_conflicts_task.delay(board.id)
            except Exception:
                pass  # Workers unavailable — sync results are already committed

            count += 1

        message = f'Conflict detection completed for {count} board(s). Found {total_conflicts} new conflict(s).'
        messages.success(request, message)

        return JsonResponse({
            'success': True,
            'message': message,
            'boards_scanned': count,
            'conflicts_found': total_conflicts,
        })
        
    except Exception as e:
        logger.error(f"Error triggering detection for all boards: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_POST
@demo_write_guard
def trigger_detection(request, board_id):
    """
    Manually trigger conflict detection for a specific board.
    Always runs synchronously so results are immediately visible.
    """
    try:
        # Get boards user has access to (demo-aware)
        accessible_boards = get_user_boards(request.user)

        board = get_object_or_404(
            Board,
            id=board_id,
            id__in=accessible_boards.values_list('id', flat=True)
        )

        # Run synchronously — immediate results guaranteed
        service = ConflictDetectionService(board=board)
        results = service.detect_all_conflicts()
        total_conflicts = results['total_conflicts']
        message = f"Conflict detection completed for '{board.name}': {total_conflicts} new conflict(s) found."

        # Also enqueue for background resolution-suggestion generation
        try:
            detect_board_conflicts_task.delay(board.id)
        except Exception:
            pass

        messages.success(request, message)

        return JsonResponse({
            'success': True,
            'message': message,
            'board_id': board.id,
            'board_name': board.name,
            'conflicts_found': total_conflicts,
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
        # Get boards user has access to (demo-aware)
        boards = get_user_boards(request.user)
        
        # Get resolution patterns (board-specific + global) for the learned
        # patterns list. The global ones are pre-seeded and shipped with the
        # system, which is why this list looks populated even for brand-new
        # users.
        patterns = ResolutionPattern.objects.filter(
            Q(board__in=boards) | Q(board__isnull=True)
        ).order_by('-success_rate', '-times_used')[:20]

        # Personal patterns only (board-specific = learned from THIS user's own
        # resolutions). Used for the Quick Stats panel so we never present a
        # global-derived success rate as if it were the user's own.
        personal_patterns = list(
            ResolutionPattern.objects.filter(board__in=boards)
        )
        
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
        
        # Quick Stats — user's OWN history only. If the user has resolved
        # nothing (or has no personal patterns), show "No data yet" rather than
        # a percentage derived from the global seeded patterns.
        personal_success_rate = None  # float 0..1 or None
        personal_most_used = None     # display string or None
        if total_resolved > 0 and personal_patterns:
            total_used = sum(p.times_used for p in personal_patterns)
            if total_used > 0:
                total_successful = sum(p.times_successful for p in personal_patterns)
                personal_success_rate = total_successful / total_used
                most_used = max(personal_patterns, key=lambda p: p.times_used)
                personal_most_used = most_used.get_resolution_type_display()

        context = {
            'patterns': patterns,
            'total_resolved': total_resolved,
            'avg_resolution_time': avg_resolution_time,
            'avg_effectiveness': avg_effectiveness,
            'rated_count': rated_conflicts.count(),
            'personal_success_rate': personal_success_rate,
            'personal_most_used': personal_most_used,
            'trend_labels_json': json.dumps(trend_labels),
            'trend_detected_json': json.dumps(trend_detected),
            'trend_resolved_json': json.dumps(trend_resolved),
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
        # RBAC: only show notifications for boards the user has access to
        accessible_boards = get_user_boards(request.user)
        notifications = ConflictNotification.objects.filter(
            user=request.user,
            acknowledged=False,
            conflict__board__in=accessible_boards
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
