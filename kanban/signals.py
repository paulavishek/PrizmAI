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
def track_priority_and_progress_change(sender, instance, **kwargs):
    """
    Track priority and progress changes before task is saved so automation
    signals can fire on 'priority_changed' and 'task_completed' triggers.
    """
    if instance.pk:
        try:
            old_task = Task.objects.get(pk=instance.pk)
            instance._old_priority = old_task.priority
            instance._priority_changed = (old_task.priority != instance.priority)
            instance._old_progress = old_task.progress

            # Also detect when a task is being moved to a Done/Complete column.
            # auto_update_progress_for_done_column runs as a later pre_save signal
            # and will set instance.progress = 100, but at this point instance.progress
            # still holds the old value, so we must detect the column change here.
            column_name = instance.column.name.lower() if instance.column else ''
            moving_to_done_column = (
                ('done' in column_name or 'complete' in column_name)
                and old_task.progress < 100
                and old_task.column_id != instance.column_id
            )
            instance._just_completed = (
                (old_task.progress < 100 and instance.progress >= 100)
                or moving_to_done_column
            )
        except Task.DoesNotExist:
            instance._old_priority = None
            instance._priority_changed = False
            instance._old_progress = 0
            instance._just_completed = False
    else:
        instance._old_priority = None
        instance._priority_changed = False
        instance._old_progress = 0
        instance._just_completed = False


@receiver(pre_save, sender=Task)
def track_column_entry_time(sender, instance, **kwargs):
    """
    Record when a task enters a new column so WIP age can be calculated.
    Sets column_entered_at on first save or when the task changes column.
    Also stores _old_column_id for use by the automation signal.
    """
    from django.utils import timezone
    if instance.pk:
        try:
            old_task = Task.objects.get(pk=instance.pk)
            instance._old_column_id = old_task.column_id
            if old_task.column_id != instance.column_id:
                instance.column_entered_at = timezone.now()
        except Task.DoesNotExist:
            instance._old_column_id = None
            if not instance.column_entered_at:
                instance.column_entered_at = timezone.now()
    else:
        instance._old_column_id = None
        # Brand-new task
        if not instance.column_entered_at:
            instance.column_entered_at = timezone.now()


@receiver(post_save, sender=Task)
def run_board_automations(sender, instance, created, **kwargs):
    """
    Fire active BoardAutomation rules after a task is saved.
    Handles two triggers:
      - moved_to_column: fires when a task changes column
      - task_overdue: fires when an uncompleted task's due date has passed
    """
    from django.utils import timezone as tz
    try:
        from kanban.automation_models import BoardAutomation
        from kanban.models import TaskLabel

        board = instance.column.board if instance.column_id else None
        if not board:
            return

        automations = BoardAutomation.objects.filter(board=board, is_active=True)
        if not automations.exists():
            return

        now = tz.now()

        old_column_id = getattr(instance, '_old_column_id', None)
        column_changed = (not created) and (old_column_id != instance.column_id)
        priority_changed = getattr(instance, '_priority_changed', False)
        just_completed   = getattr(instance, '_just_completed', False)
        assignment_changed = getattr(instance, '_assignment_changed', False)

        for rule in automations:
            fired = False

            # --- Trigger: moved_to_column ---
            if rule.trigger_type == 'moved_to_column' and column_changed:
                col_name = instance.column.name.lower()
                if rule.trigger_value.lower() in col_name:
                    fired = True

            # --- Trigger: task_overdue ---
            elif rule.trigger_type == 'task_overdue':
                if (
                    instance.due_date
                    and instance.due_date < now
                    and instance.progress < 100
                ):
                    fired = True

            # --- Trigger: task_created ---
            elif rule.trigger_type == 'task_created' and created:
                fired = True

            # --- Trigger: task_completed ---
            elif rule.trigger_type == 'task_completed' and just_completed:
                fired = True

            # --- Trigger: priority_changed ---
            elif rule.trigger_type == 'priority_changed' and priority_changed:
                if instance.priority.lower() == rule.trigger_value.lower():
                    fired = True

            # --- Trigger: task_assigned ---
            elif rule.trigger_type == 'task_assigned' and assignment_changed and instance.assigned_to:
                fired = True

            if fired:
                _apply_automation_action(instance, rule)
                rule.run_count += 1
                rule.last_run_at = now
                BoardAutomation.objects.filter(pk=rule.pk).update(
                    run_count=rule.run_count,
                    last_run_at=rule.last_run_at,
                )

    except Exception:
        # Never let automations crash core task saves
        import logging
        logging.getLogger(__name__).exception("BoardAutomation runner failed silently")


def _apply_automation_action(task, rule):
    """Apply the action defined in a BoardAutomation rule to a task."""
    import logging
    from django.utils import timezone as tz
    log = logging.getLogger(__name__)
    VALID_PRIORITIES = {'low', 'medium', 'high', 'urgent'}

    if rule.action_type == 'set_priority':
        new_priority = rule.action_value.lower()
        if new_priority in VALID_PRIORITIES and task.priority != new_priority:
            Task.objects.filter(pk=task.pk).update(priority=new_priority)

    elif rule.action_type == 'add_label':
        from kanban.models import TaskLabel
        label = TaskLabel.objects.filter(
            board=task.column.board,
            name__iexact=rule.action_value,
        ).first()
        if label:
            task.labels.add(label)

    elif rule.action_type == 'send_notification':
        _send_automation_notification(task, rule)

    elif rule.action_type == 'move_to_column':
        from kanban.models import Column
        target_col = Column.objects.filter(
            board=task.column.board,
            name__icontains=rule.action_value,
        ).exclude(pk=task.column_id).first()
        if target_col:
            Task.objects.filter(pk=task.pk).update(column=target_col)

    elif rule.action_type == 'assign_to_user':
        from django.contrib.auth.models import User as AuthUser
        user = AuthUser.objects.filter(username=rule.action_value).first()
        if user:
            Task.objects.filter(pk=task.pk).update(assigned_to=user)

    elif rule.action_type == 'set_due_date':
        try:
            days = int(rule.action_value)
            new_due = tz.now() + tz.timedelta(days=days)
            Task.objects.filter(pk=task.pk).update(due_date=new_due)
        except (ValueError, TypeError):
            log.warning("BoardAutomation set_due_date: couldn't parse days from '%s'", rule.action_value)


def _send_automation_notification(task, rule):
    """Send in-app notifications triggered by an automation rule."""
    try:
        from messaging.models import Notification
        from django.contrib.auth.models import User as AuthUser

        board = task.column.board
        # Determine sender: use the automation creator or board creator
        sender = rule.created_by or board.created_by
        if not sender:
            return

        recipient_key = rule.action_value.strip().lower()  # assignee / board_members / creator
        recipients = []

        if recipient_key == 'assignee' and task.assigned_to:
            recipients = [task.assigned_to]
        elif recipient_key == 'creator' and task.created_by:
            recipients = [task.created_by]
        elif recipient_key == 'board_members':
            recipients = list(board.members.all())
            if board.created_by and board.created_by not in recipients:
                recipients.append(board.created_by)

        text = (
            f'Automation "{rule.name}" was triggered for task "{task.title}" '
            f'on board "{board.name}".'
        )
        for recipient in recipients:
            Notification.objects.create(
                recipient=recipient,
                sender=sender,
                notification_type='ACTIVITY',
                text=text,
            )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("_send_automation_notification failed silently")


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
