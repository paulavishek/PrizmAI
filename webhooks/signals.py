"""
Django Signals for Webhook Event Triggers
Automatically fires webhooks when specific events occur
"""
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from kanban.models import Task, Comment, Board
from webhooks.models import Webhook, WebhookDelivery, WebhookEvent
from webhooks.tasks import deliver_webhook


def trigger_webhooks(event_type, board, object_id, data, triggered_by=None):
    """
    Trigger all webhooks subscribed to a specific event type for a board
    
    Args:
        event_type: Type of event (e.g., 'task.created')
        board: Board object
        object_id: ID of the object that triggered the event
        data: Event data to send
        triggered_by: User who triggered the event
    """
    # Create event log
    event = WebhookEvent.objects.create(
        event_type=event_type,
        board=board,
        object_id=object_id,
        data=data,
        triggered_by=triggered_by
    )
    
    # Find all active webhooks for this board and event type
    webhooks = Webhook.objects.filter(
        board=board,
        is_active=True,
        status='active'
    )
    
    # Filter by event type (workaround for SQLite not supporting contains on JSONField)
    webhooks = [w for w in webhooks if event_type in w.events]
    
    triggered_count = 0
    for webhook in webhooks:
        # Create delivery record
        delivery = WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=event_type,
            payload=data,
            status='pending'
        )
        
        # Queue delivery task (async)
        deliver_webhook.delay(delivery.id)
        triggered_count += 1
    
    # Update event log
    event.webhooks_triggered = triggered_count
    event.save()
    
    return triggered_count


# Task Signals

@receiver(post_save, sender=Task)
def task_saved(sender, instance, created, **kwargs):
    """
    Triggered when a task is created or updated
    """
    task = instance
    board = task.column.board
    
    # Prepare task data
    task_data = {
        'id': task.id,
        'title': task.title,
        'description': task.description,
        'column': {
            'id': task.column.id,
            'name': task.column.name
        },
        'board': {
            'id': board.id,
            'name': board.name
        },
        'priority': task.priority,
        'progress': task.progress,
        'due_date': task.due_date.isoformat() if task.due_date else None,
        'assigned_to': {
            'id': task.assigned_to.id,
            'username': task.assigned_to.username,
            'email': task.assigned_to.email
        } if task.assigned_to else None,
        'created_by': {
            'id': task.created_by.id,
            'username': task.created_by.username,
            'email': task.created_by.email
        },
        'created_at': task.created_at.isoformat(),
        'updated_at': task.updated_at.isoformat()
    }
    
    if created:
        # Task was just created
        trigger_webhooks(
            event_type='task.created',
            board=board,
            object_id=task.id,
            data=task_data,
            triggered_by=task.created_by
        )
    else:
        # Task was updated
        trigger_webhooks(
            event_type='task.updated',
            board=board,
            object_id=task.id,
            data=task_data,
            triggered_by=task.created_by  # Could track who updated in the future
        )
        
        # Check if task was completed (progress = 100)
        if task.progress == 100:
            trigger_webhooks(
                event_type='task.completed',
                board=board,
                object_id=task.id,
                data=task_data,
                triggered_by=task.created_by
            )


@receiver(pre_save, sender=Task)
def task_column_changed(sender, instance, **kwargs):
    """
    Detect when a task is moved to a different column
    """
    if instance.pk:  # Only for existing tasks
        try:
            old_task = Task.objects.get(pk=instance.pk)
            if old_task.column_id != instance.column_id:
                # Task was moved to different column
                # Store this info for post_save signal
                instance._column_changed = True
                instance._old_column = old_task.column
        except Task.DoesNotExist:
            pass


@receiver(post_save, sender=Task)
def task_moved(sender, instance, created, **kwargs):
    """
    Triggered when a task is moved to a different column
    """
    if not created and hasattr(instance, '_column_changed'):
        task = instance
        board = task.column.board
        
        task_data = {
            'id': task.id,
            'title': task.title,
            'from_column': {
                'id': instance._old_column.id,
                'name': instance._old_column.name
            },
            'to_column': {
                'id': task.column.id,
                'name': task.column.name
            },
            'board': {
                'id': board.id,
                'name': board.name
            },
            'moved_at': task.updated_at.isoformat()
        }
        
        trigger_webhooks(
            event_type='task.moved',
            board=board,
            object_id=task.id,
            data=task_data,
            triggered_by=task.created_by
        )
        
        # Clean up temporary attributes
        delattr(instance, '_column_changed')
        delattr(instance, '_old_column')


@receiver(pre_save, sender=Task)
def task_assignment_changed(sender, instance, **kwargs):
    """
    Detect when a task is assigned to someone
    """
    if instance.pk:  # Only for existing tasks
        try:
            old_task = Task.objects.get(pk=instance.pk)
            if old_task.assigned_to_id != instance.assigned_to_id:
                # Task assignment changed
                instance._assignment_changed = True
                instance._old_assignee = old_task.assigned_to
        except Task.DoesNotExist:
            pass


@receiver(post_save, sender=Task)
def task_assigned(sender, instance, created, **kwargs):
    """
    Triggered when a task is assigned to a user
    """
    if not created and hasattr(instance, '_assignment_changed'):
        task = instance
        board = task.column.board
        
        task_data = {
            'id': task.id,
            'title': task.title,
            'board': {
                'id': board.id,
                'name': board.name
            },
            'assigned_to': {
                'id': task.assigned_to.id,
                'username': task.assigned_to.username,
                'email': task.assigned_to.email
            } if task.assigned_to else None,
            'previous_assignee': {
                'id': instance._old_assignee.id,
                'username': instance._old_assignee.username,
                'email': instance._old_assignee.email
            } if instance._old_assignee else None,
            'assigned_at': task.updated_at.isoformat()
        }
        
        trigger_webhooks(
            event_type='task.assigned',
            board=board,
            object_id=task.id,
            data=task_data,
            triggered_by=task.created_by
        )
        
        # Clean up temporary attributes
        delattr(instance, '_assignment_changed')
        delattr(instance, '_old_assignee')


@receiver(post_delete, sender=Task)
def task_deleted(sender, instance, **kwargs):
    """
    Triggered when a task is deleted
    """
    task = instance
    board = task.column.board
    
    task_data = {
        'id': task.id,
        'title': task.title,
        'board': {
            'id': board.id,
            'name': board.name
        },
        'deleted_at': timezone.now().isoformat()
    }
    
    trigger_webhooks(
        event_type='task.deleted',
        board=board,
        object_id=task.id,
        data=task_data,
        triggered_by=None  # Can't determine who deleted it from signal
    )


# Comment Signals

@receiver(post_save, sender=Comment)
def comment_added(sender, instance, created, **kwargs):
    """
    Triggered when a comment is added to a task
    """
    if created:
        comment = instance
        task = comment.task
        board = task.column.board
        
        comment_data = {
            'id': comment.id,
            'content': comment.content,
            'task': {
                'id': task.id,
                'title': task.title
            },
            'board': {
                'id': board.id,
                'name': board.name
            },
            'user': {
                'id': comment.user.id,
                'username': comment.user.username,
                'email': comment.user.email
            },
            'created_at': comment.created_at.isoformat()
        }
        
        trigger_webhooks(
            event_type='comment.added',
            board=board,
            object_id=comment.id,
            data=comment_data,
            triggered_by=comment.user
        )


# Board Signals

@receiver(post_save, sender=Board)
def board_updated(sender, instance, created, **kwargs):
    """
    Triggered when a board is updated (not created)
    """
    if not created:
        board = instance
        
        board_data = {
            'id': board.id,
            'name': board.name,
            'description': board.description,
            'updated_at': timezone.now().isoformat()
        }
        
        trigger_webhooks(
            event_type='board.updated',
            board=board,
            object_id=board.id,
            data=board_data,
            triggered_by=board.created_by
        )


# Import timezone for timestamp
from django.utils import timezone
