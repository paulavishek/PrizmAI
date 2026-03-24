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
    from django.urls import reverse

    # Do not send automated notifications for official demo boards.
    # Real users are added as board members when they browse the demo workspace,
    # so firing automations on demo boards would leak demo data into their
    # personal notification feed.
    if sa.board.is_official_demo_board:
        logger.info(
            "ScheduledAutomation pk=%s: skipped — board is an official demo board",
            sa.pk,
        )
        return

    task_count = tasks.count()
    message = sa.action_value or (
        f"{task_count} task{'s' if task_count != 1 else ''} require your "
        f"attention on {sa.board.name}"
    )
    sender = sa.created_by or sa.board.created_by
    if not sender:
        logger.warning("ScheduledAutomation pk=%s: no valid sender for notification", sa.pk)
        return

    # Build a clickable link to the board so recipients can act immediately.
    try:
        board_url = reverse('board_detail', args=[sa.board.id])
    except Exception:
        board_url = None

    # Determine recipients
    recipients = set()
    if sa.notify_target == 'board_members':
        from django.contrib.auth.models import User
        recipients = set(User.objects.filter(board_memberships__board=sa.board))
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
            action_url=board_url,
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


# ---------------------------------------------------------------------------
# New AutomationRule task (called by Celery Beat via PeriodicTask)
# ---------------------------------------------------------------------------

@shared_task(name='kanban.tasks.automation_tasks.run_automation_rule')
def run_automation_rule(rule_id):
    """
    Execute an AutomationRule when its Celery Beat schedule fires.

    Receives the AutomationRule PK, loads the record, filters matching
    tasks, walks the rule_definition tree, and writes AutomationLog entries.
    Auto-disables after 3 consecutive failures.
    """
    from kanban.automation_models import AutomationRule, AutomationLog
    from kanban.signals import _execute_rule_tree, _apply_automation_action

    try:
        rule = AutomationRule.objects.select_related(
            'board', 'created_by', 'periodic_task',
        ).get(id=rule_id, is_active=True)

        tasks = _get_filtered_tasks(rule.board, rule.task_filter or 'all')
        now = timezone.now()

        if not tasks.exists():
            logger.info(
                "AutomationRule pk=%s: no tasks matched filter '%s'",
                rule.pk, rule.task_filter,
            )
            rule.run_count += 1
            rule.last_run_at = now
            AutomationRule.objects.filter(pk=rule.pk).update(
                run_count=rule.run_count, last_run_at=now,
            )
            AutomationLog.objects.create(
                rule=rule,
                trigger_event=rule.trigger_type,
                task_affected=None,
                actions_summary='No tasks matched filter',
                outcome='passed',
            )
            return f"No tasks matched filter for automation rule {rule.id}"

        total_actions = 0
        total_errors = 0

        for task in tasks:
            actions_taken = []
            errors = []

            if rule.rule_definition:
                _execute_rule_tree(rule.rule_definition, task, rule, actions_taken, errors)
            else:
                try:
                    _apply_automation_action(task, rule)
                    actions_taken.append(f"{rule.action_type}: {rule.action_value}")
                except Exception as e:
                    errors.append(str(e))

            total_actions += len(actions_taken)
            total_errors += len(errors)

            try:
                AutomationLog.objects.create(
                    rule=rule,
                    trigger_event=rule.trigger_type,
                    task_affected=task,
                    actions_summary='; '.join(actions_taken) if actions_taken else 'No actions',
                    outcome='failed' if errors else 'passed',
                    error_detail='; '.join(errors) if errors else '',
                )
            except Exception:
                logger.exception("Failed to write AutomationLog for rule pk=%s", rule.pk)

        # Update tracking
        rule.run_count += 1
        rule.failure_count = 0
        rule.last_run_at = now
        AutomationRule.objects.filter(pk=rule.pk).update(
            run_count=rule.run_count,
            failure_count=0,
            last_run_at=now,
        )

        logger.info(
            "AutomationRule pk=%s completed: %d actions, %d errors across %d tasks",
            rule.pk, total_actions, total_errors, tasks.count(),
        )
        return f"Automation rule {rule.id} completed successfully"

    except AutomationRule.DoesNotExist:
        logger.warning("AutomationRule pk=%s not found or inactive", rule_id)
        return f"Automation rule {rule_id} not found or inactive"
    except Exception as exc:
        logger.exception("AutomationRule pk=%s failed: %s", rule_id, exc)
        # Increment failure_count; auto-disable at 3 consecutive failures
        try:
            rule = AutomationRule.objects.get(id=rule_id)
            rule.failure_count += 1
            update_fields = ['failure_count']
            if rule.failure_count >= 3:
                rule.is_active = False
                update_fields.append('is_active')
                if rule.periodic_task:
                    rule.periodic_task.enabled = False
                    rule.periodic_task.save(update_fields=['enabled'])
                _notify_rule_disabled(rule)
                logger.warning(
                    "AutomationRule pk=%s auto-disabled after %d failures",
                    rule.pk, rule.failure_count,
                )
            rule.save(update_fields=update_fields)
        except Exception:
            logger.exception("Failed to update failure_count for AutomationRule pk=%s", rule_id)
        raise


def _notify_rule_disabled(rule):
    """Notify the board owner that an automation rule was auto-disabled."""
    from messaging.models import Notification

    owner = rule.board.created_by
    sender = rule.created_by or owner
    if not owner or not sender:
        return
    Notification.objects.create(
        recipient=owner,
        sender=sender,
        notification_type='ACTIVITY',
        text=(
            f'Automation rule "{rule.name}" on board "{rule.board.name}" '
            f'was automatically disabled after 3 consecutive failures.'
        ),
    )
