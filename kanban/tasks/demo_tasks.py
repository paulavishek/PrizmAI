"""
Demo session management tasks
Handles automatic cleanup and reset of expired demo sessions
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)


# Demo content expires after this many hours
DEMO_CONTENT_EXPIRY_HOURS = 48


@shared_task(name='kanban.cleanup_expired_demo_sessions')
def cleanup_expired_demo_sessions():
    """
    Periodic task to cleanup expired demo sessions and their data.
    Runs every hour via Celery Beat.
    
    This task:
    1. Finds demo sessions that have expired (48+ hours old)
    2. Deletes content created during those sessions (tasks, boards, comments)
    3. Deletes user-created content on demo boards older than 48 hours (fallback cleanup)
    4. Resets demo organization data to original state
    5. Logs analytics about expired sessions
    
    IMPORTANT: This uses TWO cleanup mechanisms:
    - Session-based: Deletes content tagged with expired session IDs
    - Time-based fallback: Deletes non-seed content older than 48 hours
      (catches cases where session tracking failed)
    """
    from analytics.models import DemoSession, DemoAnalytics
    from kanban.models import Task, Board, Comment, Organization
    
    now = timezone.now()
    expiry_cutoff = now - timedelta(hours=DEMO_CONTENT_EXPIRY_HOURS)
    
    # Find expired demo sessions
    expired_sessions = DemoSession.objects.filter(expires_at__lt=now)
    expired_count = expired_sessions.count()
    
    # Get session IDs AND browser fingerprints for content cleanup
    expired_session_ids = list(expired_sessions.values_list('session_id', flat=True))
    expired_fingerprints = list(expired_sessions.exclude(
        browser_fingerprint__isnull=True
    ).values_list('browser_fingerprint', flat=True))
    
    # CRITICAL FIX: Get fingerprints that have ANY active (non-expired) session
    # These fingerprints should NOT be cleaned up, even if they also appear in expired sessions
    # This prevents deleting user content when they log in again with a new session
    active_sessions = DemoSession.objects.filter(expires_at__gte=now)
    active_fingerprints = set(active_sessions.exclude(
        browser_fingerprint__isnull=True
    ).values_list('browser_fingerprint', flat=True))
    active_session_ids = set(active_sessions.values_list('session_id', flat=True))
    
    # Remove fingerprints and session IDs that have active sessions from cleanup list
    safe_expired_fingerprints = [fp for fp in expired_fingerprints if fp not in active_fingerprints]
    safe_expired_session_ids = [sid for sid in expired_session_ids if sid not in active_session_ids]
    
    # Combine both lists for comprehensive cleanup (only truly orphaned identifiers)
    identifiers_to_cleanup = safe_expired_session_ids + safe_expired_fingerprints
    
    logger.info(f"Cleanup: {len(expired_fingerprints)} expired fingerprints, {len(active_fingerprints)} active fingerprints, {len(safe_expired_fingerprints)} safe to cleanup")
    
    # Track cleanup stats
    cleanup_stats = {
        'sessions': expired_count,
        'tasks_by_session': 0,
        'tasks_by_time': 0,
        'boards_by_session': 0,
        'boards_by_time': 0,
    }
    
    try:
        # Get demo organization
        demo_org = Organization.objects.filter(is_demo=True).first()
        
        if demo_org:
            # =========================================================
            # MECHANISM 1: Session-based cleanup (original mechanism)
            # =========================================================
            if identifiers_to_cleanup:
                # Delete tasks created by expired sessions
                deleted_tasks = Task.objects.filter(
                    created_by_session__in=identifiers_to_cleanup,
                    column__board__organization=demo_org
                ).delete()[0]
                cleanup_stats['tasks_by_session'] = deleted_tasks
                
                # Delete non-official boards created by expired sessions
                deleted_boards = Board.objects.filter(
                    created_by_session__in=identifiers_to_cleanup,
                    organization=demo_org,
                    is_official_demo_board=False
                ).delete()[0]
                cleanup_stats['boards_by_session'] = deleted_boards
                
                logger.info(f"Session-based cleanup: {deleted_tasks} tasks, {deleted_boards} boards")
            
            # =========================================================
            # MECHANISM 2: Time-based fallback cleanup
            # Catches user-created content that wasn't properly tagged
            # =========================================================
            # Delete tasks that:
            # - Are on demo boards
            # - Are NOT seed demo data (is_seed_demo_data=False or NULL)
            # - Are older than 48 hours
            # - Don't have a session ID (already handled above) OR have an expired session
            # - CRITICAL: Exclude tasks that belong to ACTIVE sessions
            
            # Build list of all active session identifiers (fingerprints + session IDs)
            all_active_identifiers = list(active_fingerprints) + list(active_session_ids)
            
            orphan_tasks = Task.objects.filter(
                column__board__organization=demo_org,
                column__board__is_official_demo_board=True,  # Only on official demo boards
                created_at__lt=expiry_cutoff,  # Older than 48 hours
            ).filter(
                Q(is_seed_demo_data=False) | Q(is_seed_demo_data__isnull=True)
            ).exclude(
                is_seed_demo_data=True  # Explicitly exclude seed data
            ).exclude(
                # CRITICAL FIX: Exclude tasks that belong to users with active sessions
                created_by_session__in=all_active_identifiers
            )
            
            # Delete related records first (in order to avoid FK constraint errors)
            orphan_task_ids = list(orphan_tasks.values_list('id', flat=True))
            if orphan_task_ids:
                # Import related models and delete their records
                from kanban.models import Comment, TaskActivity, TaskFile
                from kanban.resource_leveling_models import TaskAssignmentHistory
                from kanban.stakeholder_models import StakeholderTaskInvolvement
                
                # Delete task activities
                TaskActivity.objects.filter(task_id__in=orphan_task_ids).delete()
                
                # Delete comments  
                Comment.objects.filter(task_id__in=orphan_task_ids).delete()
                
                # Delete task files
                TaskFile.objects.filter(task_id__in=orphan_task_ids).delete()
                
                # Delete task assignment history
                TaskAssignmentHistory.objects.filter(task_id__in=orphan_task_ids).delete()
                
                # Delete stakeholder task involvement records
                StakeholderTaskInvolvement.objects.filter(task_id__in=orphan_task_ids).delete()
                
                # Clear dependencies (ManyToMany) - remove these tasks from dependency relationships
                for task in Task.objects.filter(id__in=orphan_task_ids):
                    task.dependencies.clear()
                    task.dependent_tasks.clear()
                    task.related_tasks.clear()
                    # Also remove from subtasks relationship
                    if task.parent_task:
                        task.parent_task = None
                        task.save(update_fields=['parent_task'])
                
                # Now delete the tasks
                deleted_orphan_tasks = Task.objects.filter(id__in=orphan_task_ids).delete()[0]
            else:
                deleted_orphan_tasks = 0
                
            cleanup_stats['tasks_by_time'] = deleted_orphan_tasks
            
            if deleted_orphan_tasks > 0:
                logger.info(f"Time-based fallback cleanup: {deleted_orphan_tasks} orphan tasks deleted")
            
            # Delete non-official boards that are:
            # - In demo org
            # - NOT official demo boards
            # - NOT seed data
            # - Older than 48 hours
            orphan_boards = Board.objects.filter(
                organization=demo_org,
                is_official_demo_board=False,
                created_at__lt=expiry_cutoff,
            ).filter(
                Q(is_seed_demo_data=False) | Q(is_seed_demo_data__isnull=True)
            ).exclude(
                is_seed_demo_data=True
            )
            
            deleted_orphan_boards = orphan_boards.delete()[0]
            cleanup_stats['boards_by_time'] = deleted_orphan_boards
            
            if deleted_orphan_boards > 0:
                logger.info(f"Time-based fallback cleanup: {deleted_orphan_boards} orphan boards deleted")
            
            # Note: Comments are automatically deleted via CASCADE when boards/tasks are deleted
            
            # Reset official demo boards to clean state
            _reset_demo_boards(demo_org)
        
        # Log analytics for each expired session
        for session_id in expired_session_ids:
            try:
                DemoAnalytics.objects.create(
                    session_id=session_id,
                    event_type='session_auto_expired',
                    event_data={
                        'expired_at': now.isoformat(),
                        'cleanup_stats': cleanup_stats
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to log analytics for session {session_id}: {e}")
        
        # Delete the expired session records
        if expired_count > 0:
            expired_sessions.delete()
        
        total_tasks = cleanup_stats['tasks_by_session'] + cleanup_stats['tasks_by_time']
        total_boards = cleanup_stats['boards_by_session'] + cleanup_stats['boards_by_time']
        
        logger.info(f"Cleanup complete: {expired_count} sessions, {total_tasks} tasks, {total_boards} boards")
        return {'status': 'success', **cleanup_stats}
        
    except Exception as e:
        logger.error(f"Error during demo session cleanup: {e}")
        return {'status': 'error', 'error': str(e)}


def _reset_demo_boards(demo_org):
    """
    Reset official demo boards to their original state.
    Called after expired session cleanup to ensure fresh demo data.
    
    IMPORTANT: This uses the same management commands as the manual reset button
    to ensure consistent demo data across both reset mechanisms.
    """
    from django.core.management import call_command
    from io import StringIO
    
    # Capture output for logging
    out = StringIO()
    
    try:
        # 1. Repopulate wiki demo data first (pages needed for task wiki links)
        try:
            call_command('populate_wiki_demo_data', '--reset', stdout=out, stderr=out)
            logger.info("Wiki demo data repopulated")
        except Exception as e:
            logger.warning(f"Wiki demo data repopulation failed (optional): {e}")
        
        # 2. Repopulate main demo tasks (with --reset to clear and recreate)
        call_command('populate_demo_data', '--reset', stdout=out, stderr=out)
        logger.info("Main demo data repopulated via populate_demo_data")
        
        # 3. Repopulate AI assistant data
        try:
            call_command('populate_ai_assistant_demo_data', '--reset', stdout=out, stderr=out)
            logger.info("AI assistant demo data repopulated")
        except Exception as e:
            logger.warning(f"AI assistant demo data repopulation failed (optional): {e}")
        
        # 4. Repopulate messaging data
        try:
            call_command('populate_messaging_demo_data', '--clear', stdout=out, stderr=out)
            logger.info("Messaging demo data repopulated")
        except Exception as e:
            logger.warning(f"Messaging demo data repopulation failed (optional): {e}")
        
        # 5. Refresh all dates to current (burndown, retrospectives, etc.)
        try:
            call_command('refresh_demo_dates', '--force', stdout=out, stderr=out)
            logger.info("Demo dates refreshed")
        except Exception as e:
            logger.warning(f"Demo dates refresh failed (optional): {e}")
        
        # 6. Detect conflicts for fresh data
        try:
            call_command('detect_conflicts', '--clear', stdout=out, stderr=out)
            logger.info("Conflicts detection completed")
        except Exception as e:
            logger.warning(f"Conflicts detection failed (optional): {e}")
        
        logger.info("Demo boards reset to original state via management commands")
        
    except Exception as e:
        logger.error(f"Critical error resetting demo boards: {e}")
        raise


@shared_task(name='kanban.send_demo_expiry_warning')
def send_demo_expiry_warning():
    """
    Log sessions nearing expiration for monitoring.
    Actual warnings are shown via context processor in the UI.
    """
    from analytics.models import DemoSession, DemoAnalytics
    
    now = timezone.now()
    warning_threshold = now + timedelta(hours=4)  # Sessions expiring in next 4 hours
    
    expiring_sessions = DemoSession.objects.filter(
        expires_at__gt=now,
        expires_at__lte=warning_threshold
    )
    
    expiring_count = expiring_sessions.count()
    
    # Log analytics for monitoring
    for session in expiring_sessions:
        try:
            # Check if we already logged a warning for this session
            existing_warning = DemoAnalytics.objects.filter(
                session_id=session.session_id,
                event_type='expiry_warning_logged'
            ).exists()
            
            if not existing_warning:
                DemoAnalytics.objects.create(
                    session_id=session.session_id,
                    event_type='expiry_warning_logged',
                    event_data={
                        'expires_at': session.expires_at.isoformat(),
                        'hours_remaining': (session.expires_at - now).total_seconds() / 3600
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to log expiry warning for session {session.session_id}: {e}")
    
    logger.info(f"Found {expiring_count} sessions expiring within 4 hours")
    return {'expiring_sessions': expiring_count}


@shared_task(name='kanban.refresh_demo_dates')
def refresh_demo_dates_task():
    """
    Celery task wrapper for refreshing demo dates.
    Keeps demo data looking current by adjusting dates relative to today.
    """
    from django.core.management import call_command
    from io import StringIO
    
    out = StringIO()
    try:
        call_command('refresh_demo_dates', stdout=out)
        result = out.getvalue()
        logger.info(f"Demo dates refreshed: {result}")
        return {'status': 'success', 'output': result}
    except Exception as e:
        logger.error(f"Failed to refresh demo dates: {e}")
        return {'status': 'error', 'error': str(e)}
