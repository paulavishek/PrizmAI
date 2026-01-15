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
    
    # Combine both lists for comprehensive cleanup
    identifiers_to_cleanup = expired_session_ids + expired_fingerprints
    
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
            orphan_tasks = Task.objects.filter(
                column__board__organization=demo_org,
                column__board__is_official_demo_board=True,  # Only on official demo boards
                created_at__lt=expiry_cutoff,  # Older than 48 hours
            ).filter(
                Q(is_seed_demo_data=False) | Q(is_seed_demo_data__isnull=True)
            ).exclude(
                is_seed_demo_data=True  # Explicitly exclude seed data
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
    """
    from kanban.models import Task, Board
    
    demo_boards = Board.objects.filter(
        organization=demo_org,
        is_official_demo_board=True
    )
    
    for board in demo_boards:
        tasks = list(Task.objects.filter(column__board=board))
        
        for task in tasks:
            # Reset progress based on column type
            if task.column.name in ['Done', 'Closed', 'Published']:
                task.progress = 100
            else:
                task.progress = 0
            # Clear any session assignments
            task.assigned_to = None
        
        # Bulk update for performance
        if tasks:
            Task.objects.bulk_update(tasks, ['progress', 'assigned_to'], batch_size=100)
    
    logger.info(f"Reset {demo_boards.count()} demo boards to original state")


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
