"""
Signal handlers for automatic workload and performance profile updates
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from kanban.models import Task
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
    
    organization = instance.column.board.organization
    old_assignee = getattr(instance, '_old_assigned_to', None)
    new_assignee = instance.assigned_to
    
    # Update old assignee's workload (if they had this task)
    if old_assignee and old_assignee != new_assignee:
        profile, _ = UserPerformanceProfile.objects.get_or_create(
            user=old_assignee,
            organization=organization
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
            user=new_assignee,
            organization=organization
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


@receiver(post_save, sender=Task)
def update_profile_on_task_completion(sender, instance, **kwargs):
    """
    Update performance metrics when a task is completed
    """
    # Only process if task was just completed
    if instance.completed_at and instance.assigned_to:
        if not instance.column or not instance.column.board:
            return
        
        organization = instance.column.board.organization
        
        # Update the assignee's performance profile
        profile, _ = UserPerformanceProfile.objects.get_or_create(
            user=instance.assigned_to,
            organization=organization
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
