"""
Signal handlers for automatic workload and performance profile updates
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from kanban.models import Task, TaskActivity
from kanban.resource_leveling_models import UserPerformanceProfile, TaskAssignmentHistory


@receiver(pre_save, sender=Task)
def track_task_assignment_change(sender, instance, **kwargs):
    """
    Track assignment changes before task is saved
    Store the old assignee in a temporary attribute for post_save processing
    """
    if instance.pk:  # Only for existing tasks (updates)
        try:
            old_task = Task.objects.get(pk=instance.pk)
            instance._old_assigned_to = old_task.assigned_to
            instance._assignment_changed = (old_task.assigned_to != instance.assigned_to)
        except Task.DoesNotExist:
            instance._old_assigned_to = None
            instance._assignment_changed = False
    else:  # New task
        instance._old_assigned_to = None
        instance._assignment_changed = bool(instance.assigned_to)


@receiver(pre_save, sender=Task)
def auto_update_progress_for_done_column(sender, instance, **kwargs):
    """
    Automatically set progress to 100% when a task is moved to a Done or Complete column
    This ensures the progress bar always shows full when tasks are in completion columns
    """
    if instance.column:
        column_name_lower = instance.column.name.lower()
        # Check if column name contains 'done' or 'complete'
        if ('done' in column_name_lower or 'complete' in column_name_lower) and instance.progress < 100:
            instance.progress = 100


@receiver(post_save, sender=Task)
def update_workload_on_assignment_change(sender, instance, created, **kwargs):
    """
    Automatically update UserPerformanceProfile workload when task assignment changes
    This ensures the AI Resource Optimization board stays in sync
    """
    # Only process if assignment changed or task was just created with an assignee
    if not getattr(instance, '_assignment_changed', False) and not created:
        return
    
    # Skip if no column/board (shouldn't happen in normal flow)
    if not instance.column or not instance.column.board:
        return
    
    old_assignee = getattr(instance, '_old_assigned_to', None)
    new_assignee = instance.assigned_to
    
    # Update old assignee's workload (if they had this task)
    if old_assignee and old_assignee != new_assignee:
        profile, _ = UserPerformanceProfile.objects.get_or_create(
            user=old_assignee
        )
        profile.update_current_workload()
        
        # Create assignment history record if not already created by AI suggestion
        if not hasattr(instance, '_ai_suggestion_accepted'):
            TaskAssignmentHistory.objects.create(
                task=instance,
                previous_assignee=old_assignee,
                new_assignee=new_assignee,
                changed_by=getattr(instance, '_changed_by_user', None),
                reason='manual'
            )
    
    # Update new assignee's workload (if task now has an assignee)
    if new_assignee:
        profile, _ = UserPerformanceProfile.objects.get_or_create(
            user=new_assignee
        )
        profile.update_current_workload()
        
        # Create assignment history for new tasks with assignees
        if created and new_assignee:
            TaskAssignmentHistory.objects.create(
                task=instance,
                previous_assignee=None,
                new_assignee=new_assignee,
                changed_by=getattr(instance, '_changed_by_user', instance.created_by),
                reason='manual'
            )
            
            # Log assignment activity for new tasks
            changed_by = getattr(instance, '_changed_by_user', instance.created_by)
            if changed_by:
                TaskActivity.objects.create(
                    task=instance,
                    user=changed_by,
                    activity_type='assigned',
                    description=f"assigned this task to {new_assignee.get_full_name() or new_assignee.username}"
                )
    
    # Log activity for assignment changes on existing tasks
    if not created and getattr(instance, '_assignment_changed', False):
        changed_by = getattr(instance, '_changed_by_user', None)
        if changed_by:
            if new_assignee:
                if old_assignee:
                    TaskActivity.objects.create(
                        task=instance,
                        user=changed_by,
                        activity_type='assigned',
                        description=f"reassigned this task from {old_assignee.get_full_name() or old_assignee.username} to {new_assignee.get_full_name() or new_assignee.username}"
                    )
                else:
                    TaskActivity.objects.create(
                        task=instance,
                        user=changed_by,
                        activity_type='assigned',
                        description=f"assigned this task to {new_assignee.get_full_name() or new_assignee.username}"
                    )
            elif old_assignee:
                TaskActivity.objects.create(
                    task=instance,
                    user=changed_by,
                    activity_type='assigned',
                    description=f"unassigned this task from {old_assignee.get_full_name() or old_assignee.username}"
                )
    
    # Invalidate stale AI suggestions after assignment change
    _invalidate_related_suggestions(instance, old_assignee, new_assignee)


def _invalidate_related_suggestions(task, old_assignee, new_assignee):
    """
    Invalidate AI suggestions that are no longer relevant after an assignment change
    """
    from kanban.resource_leveling_models import ResourceLevelingSuggestion
    
    # Expire pending suggestions for this specific task
    ResourceLevelingSuggestion.objects.filter(
        task=task,
        status='pending'
    ).update(status='expired')
    
    # Expire suggestions recommending the new assignee if they're now overloaded
    if new_assignee:
        profile = UserPerformanceProfile.objects.filter(
            user=new_assignee
        ).first()
        
        if profile and profile.utilization_percentage > 85:
            # This user is now overloaded, expire all pending suggestions recommending them
            ResourceLevelingSuggestion.objects.filter(
                suggested_assignee=new_assignee,
                status='pending'
            ).update(status='expired')
    
    # Also check if old assignee is now underutilized and could take more work
    if old_assignee:
        old_profile = UserPerformanceProfile.objects.filter(
            user=old_assignee
        ).first()
        
        if old_profile and old_profile.utilization_percentage < 60:
            # Old assignee now has capacity - expire suggestions moving work AWAY from them
            ResourceLevelingSuggestion.objects.filter(
                current_assignee=old_assignee,
                status='pending'
            ).update(status='expired')


@receiver(post_save, sender=Task)
def update_profile_on_task_completion(sender, instance, **kwargs):
    """
    Update performance metrics when a task is completed
    """
    # Only process if task was just completed
    if instance.completed_at and instance.assigned_to:
        if not instance.column or not instance.column.board:
            return
        
        # Update the assignee's performance profile
        profile, _ = UserPerformanceProfile.objects.get_or_create(
            user=instance.assigned_to
        )
        
        # Update metrics (completion rate, velocity, etc.)
        profile.update_metrics()
        
        # Update assignment history with actual completion data
        latest_assignment = TaskAssignmentHistory.objects.filter(
            task=instance,
            new_assignee=instance.assigned_to
        ).order_by('-changed_at').first()
        
        if latest_assignment:
            latest_assignment.calculate_actual_metrics()
