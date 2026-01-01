"""
Demo session management tasks
Handles automatic cleanup and reset of expired demo sessions
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(name='kanban.cleanup_expired_demo_sessions')
def cleanup_expired_demo_sessions():
    """
    Periodic task to cleanup expired demo sessions and their data.
    Runs every hour via Celery Beat.
    
    This task:
    1. Finds demo sessions that have expired (48+ hours old)
    2. Deletes content created during those sessions (tasks, boards, comments)
    3. Resets demo organization data to original state
    4. Logs analytics about expired sessions
    """
    from analytics.models import DemoSession, DemoAnalytics
    from kanban.models import Task, Board, Comment, Organization
    
    now = timezone.now()
    
    # Find expired demo sessions
    expired_sessions = DemoSession.objects.filter(expires_at__lt=now)
    expired_count = expired_sessions.count()
    
    if expired_count == 0:
        logger.info("No expired demo sessions to cleanup")
        return {'cleaned_sessions': 0, 'status': 'no_expired_sessions'}
    
    logger.info(f"Found {expired_count} expired demo sessions to cleanup")
    
    # Get session IDs for content cleanup
    expired_session_ids = list(expired_sessions.values_list('session_id', flat=True))
    
    # Track cleanup stats
    cleanup_stats = {
        'sessions': expired_count,
        'tasks': 0,
        'boards': 0,
        'comments': 0,
    }
    
    try:
        # Get demo organization
        demo_org = Organization.objects.filter(is_demo=True).first()
        
        if demo_org:
            # Delete tasks created by expired sessions
            deleted_tasks = Task.objects.filter(
                created_by_session__in=expired_session_ids,
                column__board__organization=demo_org
            ).delete()[0]
            cleanup_stats['tasks'] = deleted_tasks
            
            # Delete non-official boards created by expired sessions
            deleted_boards = Board.objects.filter(
                created_by_session__in=expired_session_ids,
                organization=demo_org,
                is_official_demo_board=False
            ).delete()[0]
            cleanup_stats['boards'] = deleted_boards
            
            # Delete comments created by expired sessions
            deleted_comments = Comment.objects.filter(
                created_by_session__in=expired_session_ids
            ).delete()[0]
            cleanup_stats['comments'] = deleted_comments
            
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
        expired_sessions.delete()
        
        logger.info(f"Cleanup complete: {cleanup_stats}")
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
