"""
Resource Leveling Celery Tasks
Background tasks for updating performance profiles and tracking assignments
"""
from celery import shared_task
from django.utils import timezone
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)


@shared_task
def update_user_performance_profile(user_id, organization_id):
    """
    Update performance profile for a single user
    
    Args:
        user_id: User ID
        organization_id: Organization ID
    """
    try:
        from kanban.resource_leveling_models import UserPerformanceProfile
        from accounts.models import Organization
        
        user = User.objects.get(id=user_id)
        organization = Organization.objects.get(id=organization_id)
        
        profile, created = UserPerformanceProfile.objects.get_or_create(
            user=user,
            organization=organization
        )
        
        profile.update_metrics()
        
        logger.info(f"Updated performance profile for user {user.username}")
        return {'success': True, 'user': user.username}
        
    except Exception as e:
        logger.error(f"Error updating performance profile for user {user_id}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task
def update_board_performance_profiles(board_id):
    """
    Update performance profiles for all members of a board
    
    Args:
        board_id: Board ID
    """
    try:
        from kanban.models import Board
        from kanban.resource_leveling import ResourceLevelingService
        
        board = Board.objects.get(id=board_id)
        service = ResourceLevelingService(board.organization)
        
        result = service.update_all_profiles(board)
        
        logger.info(f"Updated {result['updated']} profiles for board {board.name}")
        return result
        
    except Exception as e:
        logger.error(f"Error updating board profiles for board {board_id}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task
def track_task_completion(task_id):
    """
    Track when a task is completed and update assignment history
    
    Args:
        task_id: Task ID
    """
    try:
        from kanban.models import Task
        from kanban.resource_leveling_models import TaskAssignmentHistory
        
        task = Task.objects.get(id=task_id)
        
        # Find the most recent assignment history for this task
        history = TaskAssignmentHistory.objects.filter(task=task).order_by('-changed_at').first()
        
        if history and not history.actual_completion_hours:
            history.calculate_actual_metrics()
            logger.info(f"Tracked completion for task {task.title}")
            
            # Update assignee's performance profile
            if task.assigned_to:
                update_user_performance_profile.delay(
                    task.assigned_to.id,
                    task.column.board.organization.id
                )
        
        return {'success': True, 'task': task.title}
        
    except Exception as e:
        logger.error(f"Error tracking task completion for task {task_id}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task
def track_task_assignment_change(task_id, old_assignee_id, new_assignee_id, changed_by_id):
    """
    Track when a task assignment changes
    
    Args:
        task_id: Task ID
        old_assignee_id: Previous assignee user ID (can be None)
        new_assignee_id: New assignee user ID (can be None)
        changed_by_id: User who made the change
    """
    try:
        from kanban.models import Task
        from kanban.resource_leveling_models import TaskAssignmentHistory
        from kanban.resource_leveling import ResourceLevelingService
        
        task = Task.objects.get(id=task_id)
        old_assignee = User.objects.get(id=old_assignee_id) if old_assignee_id else None
        new_assignee = User.objects.get(id=new_assignee_id) if new_assignee_id else None
        changed_by = User.objects.get(id=changed_by_id)
        
        organization = task.column.board.organization
        service = ResourceLevelingService(organization)
        
        # Predict completion time for new assignee
        predicted_hours = None
        if new_assignee:
            profile = service.get_or_create_profile(new_assignee)
            predicted_hours = profile.predict_completion_time(task)
        
        # Create assignment history
        TaskAssignmentHistory.objects.create(
            task=task,
            previous_assignee=old_assignee,
            new_assignee=new_assignee,
            changed_by=changed_by,
            reason='manual',
            predicted_completion_hours=predicted_hours,
            was_ai_suggested=False
        )
        
        # Update workload for both users
        if old_assignee:
            update_user_performance_profile.delay(old_assignee.id, organization.id)
        if new_assignee:
            update_user_performance_profile.delay(new_assignee.id, organization.id)
        
        logger.info(f"Tracked assignment change for task {task.title}")
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Error tracking assignment change for task {task_id}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task
def generate_board_suggestions(board_id):
    """
    Generate resource leveling suggestions for a board
    Scheduled task to run periodically
    
    Args:
        board_id: Board ID
    """
    try:
        from kanban.models import Board
        from kanban.resource_leveling import ResourceLevelingService
        
        board = Board.objects.get(id=board_id)
        service = ResourceLevelingService(board.organization)
        
        # First update all profiles
        service.update_all_profiles(board)
        
        # Generate suggestions
        suggestions = service.get_board_optimization_suggestions(board, limit=10)
        
        logger.info(f"Generated {len(suggestions)} suggestions for board {board.name}")
        return {
            'success': True,
            'board': board.name,
            'suggestions_count': len(suggestions)
        }
        
    except Exception as e:
        logger.error(f"Error generating suggestions for board {board_id}: {e}")
        return {'success': False, 'error': str(e)}


@shared_task
def expire_old_suggestions():
    """
    Mark expired suggestions as expired
    Scheduled task to run daily
    """
    try:
        from kanban.resource_leveling_models import ResourceLevelingSuggestion
        
        expired_count = ResourceLevelingSuggestion.objects.filter(
            status='pending',
            expires_at__lt=timezone.now()
        ).update(status='expired')
        
        logger.info(f"Marked {expired_count} suggestions as expired")
        return {'success': True, 'expired_count': expired_count}
        
    except Exception as e:
        logger.error(f"Error expiring old suggestions: {e}")
        return {'success': False, 'error': str(e)}


@shared_task
def daily_profile_update():
    """
    Update all performance profiles daily
    Scheduled task to run once per day
    """
    try:
        from kanban.resource_leveling_models import UserPerformanceProfile
        
        profiles = UserPerformanceProfile.objects.all()
        updated = 0
        
        for profile in profiles:
            try:
                profile.update_metrics()
                updated += 1
            except Exception as e:
                logger.error(f"Error updating profile for {profile.user.username}: {e}")
        
        logger.info(f"Daily update: Updated {updated} performance profiles")
        return {'success': True, 'updated': updated, 'total': profiles.count()}
        
    except Exception as e:
        logger.error(f"Error in daily profile update: {e}")
        return {'success': False, 'error': str(e)}


@shared_task
def auto_suggest_on_task_create(task_id):
    """
    Automatically generate suggestion when a new task is created
    
    Args:
        task_id: Task ID
    """
    try:
        from kanban.models import Task
        from kanban.resource_leveling import ResourceLevelingService
        
        task = Task.objects.get(id=task_id)
        
        # Only suggest if task is unassigned or assigned
        if not task.column:
            return {'success': False, 'message': 'Task not in a column yet'}
        
        organization = task.column.board.organization
        service = ResourceLevelingService(organization)
        
        # Create suggestion
        suggestion = service.create_suggestion(task, force_analysis=True)
        
        if suggestion:
            logger.info(f"Auto-created suggestion for new task {task.title}")
            return {
                'success': True,
                'suggestion_id': suggestion.id,
                'suggested_assignee': suggestion.suggested_assignee.username
            }
        else:
            return {'success': False, 'message': 'No beneficial assignment found'}
        
    except Exception as e:
        logger.error(f"Error auto-suggesting for task {task_id}: {e}")
        return {'success': False, 'error': str(e)}
