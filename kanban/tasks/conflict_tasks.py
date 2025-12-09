"""
Celery tasks for automated conflict detection and resolution.
"""
from celery import shared_task
from django.utils import timezone
from kanban.models import Board
from kanban.conflict_models import ConflictDetection, ConflictNotification
from kanban.utils.conflict_detection import ConflictDetectionService, ConflictResolutionSuggester
from kanban.utils.ai_conflict_resolution import AIConflictResolutionEngine
import logging

logger = logging.getLogger(__name__)


@shared_task(name='kanban.detect_conflicts')
def detect_conflicts_task():
    """
    Periodic task to detect conflicts across all active boards.
    Runs every hour to identify resource, schedule, and dependency conflicts.
    """
    logger.info("Starting automated conflict detection...")
    
    try:
        # Run conflict detection
        service = ConflictDetectionService()
        results = service.detect_all_conflicts()
        
        logger.info(f"Conflict detection completed: {results['total_conflicts']} conflicts found")
        logger.info(f"By type: {results['by_type']}")
        logger.info(f"By severity: {results['by_severity']}")
        
        # Generate resolution suggestions for new conflicts
        for conflict in results['conflicts']:
            generate_resolution_suggestions_task.delay(conflict.id)
        
        # Notify affected users
        notify_conflict_users_task.delay(results['detection_run_id'])
        
        return {
            'status': 'success',
            'conflicts_detected': results['total_conflicts'],
            'run_id': results['detection_run_id']
        }
        
    except Exception as e:
        logger.error(f"Error in conflict detection: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task(name='kanban.generate_resolution_suggestions')
def generate_resolution_suggestions_task(conflict_id):
    """
    Generate resolution suggestions for a specific conflict.
    
    Args:
        conflict_id: ID of ConflictDetection instance
    """
    try:
        conflict = ConflictDetection.objects.get(id=conflict_id)
        
        logger.info(f"Generating resolutions for conflict: {conflict.title}")
        
        # Generate basic rule-based suggestions
        suggester = ConflictResolutionSuggester(conflict)
        basic_suggestions = suggester.generate_suggestions()
        
        logger.info(f"Generated {len(basic_suggestions)} basic suggestions")
        
        # Enhance with AI if enabled
        try:
            ai_engine = AIConflictResolutionEngine()
            
            # Option 1: Generate completely new AI suggestions
            ai_suggestions = ai_engine.generate_advanced_resolutions(conflict)
            logger.info(f"Generated {len(ai_suggestions)} AI suggestions")
            
            # Option 2: Enhance basic suggestions with AI insights
            if basic_suggestions:
                enhanced = ai_engine.enhance_basic_suggestions(conflict, basic_suggestions)
                logger.info(f"Enhanced {len(enhanced)} suggestions with AI insights")
            
        except Exception as ai_error:
            logger.warning(f"AI enhancement failed: {ai_error}. Using basic suggestions only.")
        
        return {
            'status': 'success',
            'conflict_id': conflict_id,
            'suggestions_generated': len(basic_suggestions)
        }
        
    except ConflictDetection.DoesNotExist:
        logger.error(f"Conflict {conflict_id} not found")
        return {
            'status': 'error',
            'error': 'Conflict not found'
        }
    except Exception as e:
        logger.error(f"Error generating suggestions for conflict {conflict_id}: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task(name='kanban.notify_conflict_users')
def notify_conflict_users_task(detection_run_id):
    """
    Notify users about conflicts detected in a specific run.
    Prevents duplicate notifications.
    
    Args:
        detection_run_id: Unique ID for the detection batch run
    """
    try:
        # Get new conflicts from this run
        new_conflicts = ConflictDetection.objects.filter(
            detection_run_id=detection_run_id,
            status='active'
        ).prefetch_related('affected_users')
        
        notifications_sent = 0
        
        for conflict in new_conflicts:
            for user in conflict.affected_users.all():
                # Check if user already notified about this conflict
                existing = ConflictNotification.objects.filter(
                    conflict=conflict,
                    user=user
                ).exists()
                
                if not existing:
                    # Create notification
                    ConflictNotification.objects.create(
                        conflict=conflict,
                        user=user,
                        notification_type='in_app'
                    )
                    notifications_sent += 1
                    
                    logger.info(f"Notified {user.username} about conflict: {conflict.title}")
        
        logger.info(f"Sent {notifications_sent} notifications for run {detection_run_id}")
        
        return {
            'status': 'success',
            'notifications_sent': notifications_sent
        }
        
    except Exception as e:
        logger.error(f"Error sending notifications: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task(name='kanban.cleanup_resolved_conflicts')
def cleanup_resolved_conflicts_task():
    """
    Cleanup old resolved conflicts and notifications.
    Runs daily to keep database clean.
    """
    try:
        from datetime import timedelta
        
        # Delete resolved conflicts older than 90 days
        ninety_days_ago = timezone.now() - timedelta(days=90)
        
        old_conflicts = ConflictDetection.objects.filter(
            status__in=['resolved', 'ignored'],
            resolved_at__lt=ninety_days_ago
        )
        
        conflict_count = old_conflicts.count()
        old_conflicts.delete()
        
        # Delete old notifications
        old_notifications = ConflictNotification.objects.filter(
            sent_at__lt=ninety_days_ago,
            acknowledged=True
        )
        
        notification_count = old_notifications.count()
        old_notifications.delete()
        
        logger.info(f"Cleaned up {conflict_count} old conflicts and {notification_count} notifications")
        
        return {
            'status': 'success',
            'conflicts_deleted': conflict_count,
            'notifications_deleted': notification_count
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }


@shared_task(name='kanban.detect_board_conflicts')
def detect_board_conflicts_task(board_id):
    """
    Detect conflicts for a specific board on-demand.
    Can be triggered manually or after major changes.
    
    Args:
        board_id: ID of the Board to analyze
    """
    try:
        board = Board.objects.get(id=board_id)
        
        logger.info(f"Starting on-demand conflict detection for board: {board.name}")
        
        # Run detection for this board only
        service = ConflictDetectionService(board=board)
        results = service.detect_all_conflicts()
        
        # Generate suggestions for new conflicts
        for conflict in results['conflicts']:
            generate_resolution_suggestions_task.delay(conflict.id)
        
        logger.info(f"Board conflict detection completed: {results['total_conflicts']} conflicts found")
        
        return {
            'status': 'success',
            'board_id': board_id,
            'board_name': board.name,
            'conflicts_detected': results['total_conflicts'],
            'by_type': results['by_type']
        }
        
    except Board.DoesNotExist:
        logger.error(f"Board {board_id} not found")
        return {
            'status': 'error',
            'error': 'Board not found'
        }
    except Exception as e:
        logger.error(f"Error detecting conflicts for board {board_id}: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }
