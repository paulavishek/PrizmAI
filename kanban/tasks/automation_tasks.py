"""
Celery tasks for time-based automation triggers.
Handles:
  - due_date_approaching: fires when a task's due date is within N days and task is not done.
  - run_scheduled_automation: executes a ScheduledAutomation when Celery Beat fires.
"""
from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(name='kanban.run_due_date_approaching_automations')
def run_due_date_approaching_automations():
    """
    Checks all active 'due_date_approaching' automation rules and fires actions on
    tasks whose due date falls within the configured number of days.

    Runs via Celery Beat (every hour by default) so PMs get early-warning automations
    rather than only post-mortem 'task is already overdue' alerts.
    """
    from kanban.automation_models import BoardAutomation
    from kanban.models import Task
    from kanban.signals import _apply_automation_action

    rules = BoardAutomation.objects.filter(
        trigger_type='due_date_approaching',
        is_active=True,
    ).select_related('board')

    if not rules.exists():
        return

    now = timezone.now()
    fired_total = 0

    for rule in rules:
        try:
            days = int(rule.trigger_value)
        except (ValueError, TypeError):
            logger.warning(
                "BoardAutomation pk=%s has invalid trigger_value '%s' for due_date_approaching",
                rule.pk, rule.trigger_value,
            )
            continue

        window_start = now
        window_end   = now + timezone.timedelta(days=days)

        # Tasks on this board that are not done and due within the window
        tasks = Task.objects.filter(
            column__board=rule.board,
            due_date__gte=window_start,
            due_date__lte=window_end,
        ).exclude(progress=100)

        for task in tasks:
            try:
                _apply_automation_action(task, rule)
                fired_total += 1
            except Exception:
                logger.exception(
                    "due_date_approaching automation (rule pk=%s) failed on task pk=%s",
                    rule.pk, task.pk,
                )

        if tasks.exists():
            rule.run_count += tasks.count()
            rule.last_run_at = now
            BoardAutomation.objects.filter(pk=rule.pk).update(
                run_count=rule.run_count,
                last_run_at=rule.last_run_at,
            )

    logger.info("run_due_date_approaching_automations: fired %d actions", fired_total)
    return fired_total


# ---------------------------------------------------------------------------
# Scheduled Automation task (called by Celery Beat via PeriodicTask)
# ---------------------------------------------------------------------------

@shared_task(name='kanban.tasks.automation_tasks.run_scheduled_automation')
def run_scheduled_automation(scheduled_automation_id):
    """
    Execute a ScheduledAutomation when its Celery Beat schedule fires.

    Receives the ScheduledAutomation PK, loads the record, filters matching
    tasks, runs the configured action, and updates tracking fields.
    If the task fails 3 times consecutively the automation is auto-disabled.
    """
    from kanban.automation_models import ScheduledAutomation

    try:
        sa = ScheduledAutomation.objects.select_related(
            'board', 'created_by', 'periodic_task',
        ).get(id=scheduled_automation_id, is_active=True)

        tasks = _get_filtered_tasks(sa.board, sa.task_filter)

        if not tasks.exists():
            logger.info(
                "ScheduledAutomation pk=%s: no tasks matched filter '%s'",
                sa.pk, sa.task_filter,
            )
            # Still count as a successful run (no failure)
            sa.run_count += 1
            sa.last_run_at = timezone.now()
            sa.save(update_fields=['run_count', 'last_run_at'])
            return f"No tasks matched filter '{sa.task_filter}' for automation {sa.id}"

        # Execute the configured action
        if sa.action == 'send_notification':
            _execute_scheduled_notification(sa, tasks)
        elif sa.action == 'set_priority':
            _execute_scheduled_priority_change(sa, tasks)

        # Update tracking (reset failure count on success)
        sa.run_count += 1
        sa.failure_count = 0
        sa.last_run_at = timezone.now()
        sa.save(update_fields=['run_count', 'failure_count', 'last_run_at'])

        logger.info("ScheduledAutomation pk=%s completed successfully", sa.pk)
        return f"Scheduled automation {sa.id} completed successfully"

    except ScheduledAutomation.DoesNotExist:
        logger.warning(
            "ScheduledAutomation pk=%s not found or inactive", scheduled_automation_id,
        )
        return f"Scheduled automation {scheduled_automation_id} not found or inactive"
    except Exception as exc:
        logger.exception(
            "ScheduledAutomation pk=%s failed: %s", scheduled_automation_id, exc,
        )
        # Increment failure_count; auto-disable at 3 consecutive failures
        try:
            sa = ScheduledAutomation.objects.get(id=scheduled_automation_id)
            sa.failure_count += 1
            update_fields = ['failure_count']
            if sa.failure_count >= 3:
                sa.is_active = False
                update_fields.append('is_active')
                # Also disable the linked PeriodicTask
                if sa.periodic_task:
                    sa.periodic_task.enabled = False
                    sa.periodic_task.save(update_fields=['enabled'])
                # Notify the board owner
                _notify_automation_disabled(sa)
                logger.warning(
                    "ScheduledAutomation pk=%s auto-disabled after %d failures",
                    sa.pk, sa.failure_count,
                )
            sa.save(update_fields=update_fields)
        except Exception:
            logger.exception("Failed to update failure_count for ScheduledAutomation pk=%s", scheduled_automation_id)
        raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_filtered_tasks(board, task_filter):
    """Return a queryset of tasks on *board* matching *task_filter*."""
    from kanban.models import Task

    tasks = Task.objects.filter(column__board=board)

    if task_filter == 'overdue':
        tasks = tasks.filter(due_date__lt=timezone.now(), progress__lt=100)
    elif task_filter == 'incomplete':
        tasks = tasks.filter(progress__lt=100)
    elif task_filter == 'high_priority':
        tasks = tasks.filter(priority__in=['high', 'urgent'])
    # 'all' — return everything
    return tasks


def _execute_scheduled_notification(sa, tasks):
    """Create in-app Notification records for matching tasks."""
    from messaging.models import Notification

    task_count = tasks.count()
    message = sa.action_value or (
        f"{task_count} task{'s' if task_count != 1 else ''} require your "
        f"attention on {sa.board.name}"
    )
    sender = sa.created_by or sa.board.created_by
    if not sender:
        logger.warning("ScheduledAutomation pk=%s: no valid sender for notification", sa.pk)
        return

    # Determine recipients
    recipients = set()
    if sa.notify_target == 'board_members':
        recipients = set(sa.board.members.all())
        if sa.board.created_by:
            recipients.add(sa.board.created_by)
    elif sa.notify_target == 'assignee':
        for task in tasks:
            if task.assigned_to:
                recipients.add(task.assigned_to)
    elif sa.notify_target == 'creator':
        if sa.created_by:
            recipients.add(sa.created_by)

    for recipient in recipients:
        Notification.objects.create(
            recipient=recipient,
            sender=sender,
            notification_type='ACTIVITY',
            text=message,
        )

    logger.info(
        "ScheduledAutomation pk=%s: sent notification to %d recipient(s)",
        sa.pk, len(recipients),
    )


def _execute_scheduled_priority_change(sa, tasks):
    """Bulk-update priority on all matching tasks."""
    updated = tasks.update(priority=sa.action_value)
    logger.info(
        "ScheduledAutomation pk=%s: set priority to '%s' on %d task(s)",
        sa.pk, sa.action_value, updated,
    )


def _notify_automation_disabled(sa):
    """Notify the board owner that a scheduled automation was auto-disabled."""
    from messaging.models import Notification

    owner = sa.board.created_by
    sender = sa.created_by or owner
    if not owner or not sender:
        return
    Notification.objects.create(
        recipient=owner,
        sender=sender,
        notification_type='ACTIVITY',
        text=(
            f'Scheduled automation "{sa.name}" on board "{sa.board.name}" '
            f'was automatically disabled after 3 consecutive failures.'
        ),
    )
