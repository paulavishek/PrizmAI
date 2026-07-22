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
    Checks all active 'due_date_approaching' AutomationRule records and fires
    actions on tasks whose due date falls within the configured number of days.

    Handles both new flat format (trigger_config) and legacy trigger_value field.
    Runs via Celery Beat (every hour by default).
    """
    from kanban.automation_models import AutomationRule, AutomationLog
    from kanban.models import Task
    from kanban.signals import _execute_flat_rule, _apply_automation_action

    rules = AutomationRule.objects.filter(
        trigger_type='due_date_approaching',
        is_active=True,
    ).select_related('board', 'created_by')

    if not rules.exists():
        return 0

    now = timezone.now()
    today = now.date()
    fired_total = 0

    for rule in rules:
        # Resolve days from new trigger_config or legacy trigger_value
        days = rule.trigger_config.get('days') if rule.trigger_config else None
        if days is None:
            try:
                days = int(rule.trigger_value)
            except (ValueError, TypeError):
                logger.warning(
                    "AutomationRule pk=%s: invalid days config for due_date_approaching",
                    rule.pk,
                )
                continue

        window_end = now.date() + timezone.timedelta(days=int(days))
        tasks = Task.objects.filter(
            column__board=rule.board,
            due_date__gte=now.date(),
            due_date__lte=window_end,
        ).exclude(progress=100)

        # Per-day dedupe so the hourly sweep doesn't fire the same task 24×.
        already_fired_today = set(
            AutomationLog.objects.filter(
                rule=rule,
                triggered_at__date=today,
            ).values_list('task_affected_id', flat=True)
        )

        for task in tasks:
            if task.pk in already_fired_today:
                continue
            actions_taken = []
            errors = []
            try:
                if rule.actions:
                    outcome, skip_reason, _branch = _execute_flat_rule(rule, task, actions_taken, errors)
                else:
                    _apply_automation_action(task, rule)
                    actions_taken.append(f"{rule.action_type}: {rule.action_value}")
                    outcome, skip_reason = 'success', ''
                fired_total += 1
            except Exception:
                logger.exception(
                    "due_date_approaching automation (rule pk=%s) failed on task pk=%s",
                    rule.pk, task.pk,
                )
                outcome, skip_reason = 'failed', ''
                errors.append('Execution error')

            try:
                AutomationLog.objects.create(
                    rule=rule,
                    rule_name_snapshot=rule.name,
                    board=rule.board,
                    trigger_event=rule.trigger_type,
                    task_affected=task,
                    task_title_snapshot=task.title or '',
                    actions_summary='; '.join(actions_taken) if actions_taken else 'No actions',
                    outcome=outcome,
                    skip_reason=skip_reason,
                    error_detail='; '.join(errors) if errors else '',
                )
            except Exception:
                logger.exception("Failed to write AutomationLog for rule pk=%s", rule.pk)

        fired_for_rule = tasks.exclude(pk__in=already_fired_today).count()
        if fired_for_rule:
            AutomationRule.objects.filter(pk=rule.pk).update(
                run_count=rule.run_count + fired_for_rule,
                last_run_at=now,
            )

    logger.info("run_due_date_approaching_automations: fired %d actions", fired_total)
    return fired_total


@shared_task(name='kanban.run_overdue_task_automations')
def run_overdue_task_automations():
    """
    Checks all active 'task_overdue' AutomationRule records and fires actions
    on tasks whose due date has passed and are not yet complete.

    Deduplicates per rule+task per day so the same task doesn't get notified
    multiple times in a single day. Runs via Celery Beat (every hour by default).
    """
    from kanban.automation_models import AutomationRule, AutomationLog
    from kanban.models import Task
    from kanban.signals import _execute_flat_rule, _apply_automation_action

    rules = AutomationRule.objects.filter(
        trigger_type='task_overdue',
        is_active=True,
    ).select_related('board', 'created_by')

    if not rules.exists():
        return 0

    now = timezone.now()
    today = now.date()
    fired_total = 0

    for rule in rules:
        tasks = Task.objects.filter(
            column__board=rule.board,
            due_date__lt=today,
        ).exclude(progress=100)

        # Collect task IDs already processed today (success OR skipped) to avoid
        # re-firing. Skipping over 'failed' too is deliberate: retrying an action
        # that just failed with the same inputs an hour later rarely helps, and
        # spamming the audit log with hourly retries is worse than the missed
        # transient. The user can re-enable the rule or re-save the task to retry.
        already_fired_today = set(
            AutomationLog.objects.filter(
                rule=rule,
                triggered_at__date=today,
            ).values_list('task_affected_id', flat=True)
        )

        for task in tasks:
            if task.pk in already_fired_today:
                continue

            actions_taken = []
            errors = []
            try:
                if rule.actions:
                    outcome, skip_reason, _branch = _execute_flat_rule(rule, task, actions_taken, errors)
                else:
                    _apply_automation_action(task, rule)
                    actions_taken.append(f"{rule.action_type}: {rule.action_value}")
                    outcome, skip_reason = 'success', ''
                fired_total += 1
            except Exception:
                logger.exception(
                    "task_overdue automation (rule pk=%s) failed on task pk=%s",
                    rule.pk, task.pk,
                )
                outcome, skip_reason = 'failed', ''
                errors.append('Execution error')

            try:
                AutomationLog.objects.create(
                    rule=rule,
                    rule_name_snapshot=rule.name,
                    board=rule.board,
                    trigger_event=rule.trigger_type,
                    task_affected=task,
                    task_title_snapshot=task.title or '',
                    actions_summary='; '.join(actions_taken) if actions_taken else 'No actions',
                    outcome=outcome,
                    skip_reason=skip_reason,
                    error_detail='; '.join(errors) if errors else '',
                )
            except Exception:
                logger.exception("Failed to write AutomationLog for rule pk=%s", rule.pk)

        fired_for_rule = tasks.exclude(pk__in=already_fired_today).count()
        if fired_for_rule:
            AutomationRule.objects.filter(pk=rule.pk).update(
                run_count=rule.run_count + fired_for_rule,
                last_run_at=now,
            )

    logger.info("run_overdue_task_automations: fired %d actions", fired_total)
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

    # Restrict to actual tasks only — milestones share the same table but
    # should never be included in automation runs (the dashboard uses the
    # same item_type='task' guard and users expect consistent counts).
    tasks = Task.objects.filter(column__board=board, item_type='task')

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

    notification_title = f"{sa.name}: {sa.board.name}" if sa.name else f"Automation alert on {sa.board.name}"

    for recipient in recipients:
        Notification.objects.create(
            recipient=recipient,
            sender=sender,
            notification_type='ACTIVITY',
            title=notification_title,
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

    Handles both the new flat format (conditions/actions) and the legacy
    rule_definition canvas tree format for backward compatibility.
    Auto-disables after 3 consecutive failures.
    """
    from kanban.automation_models import AutomationRule, AutomationLog
    from kanban.signals import _execute_rule_tree, _apply_automation_action, _execute_flat_rule

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
            AutomationRule.objects.filter(pk=rule.pk).update(
                run_count=rule.run_count + 1,
                last_run_at=now,
                last_execution_result='skipped',
            )
            AutomationLog.objects.create(
                rule=rule,
                rule_name_snapshot=rule.name,
                board=rule.board,
                trigger_event=rule.trigger_type,
                task_affected=None,
                actions_summary='No tasks matched filter',
                outcome='skipped',
                skip_reason='No matching tasks',
            )
            return f"No tasks matched filter for automation rule {rule.id}"

        total_actions = 0
        total_errors = 0

        for task in tasks:
            actions_taken = []
            errors = []
            outcome = 'success'
            skip_reason = ''

            if rule.actions:
                # New unified flat format
                outcome, skip_reason, _branch = _execute_flat_rule(
                    rule, task, actions_taken, errors,
                )
            elif rule.rule_definition:
                # Legacy canvas tree format
                _execute_rule_tree(rule.rule_definition, task, rule, actions_taken, errors)
                outcome = 'failed' if errors else 'success'
            else:
                # Very old single-action format
                try:
                    _apply_automation_action(task, rule)
                    actions_taken.append(f"{rule.action_type}: {rule.action_value}")
                except Exception as e:
                    errors.append(str(e))
                    outcome = 'failed'

            total_actions += len(actions_taken)
            total_errors += len(errors)

            try:
                AutomationLog.objects.create(
                    rule=rule,
                    rule_name_snapshot=rule.name,
                    board=rule.board,
                    trigger_event=rule.trigger_type,
                    task_affected=task,
                    task_title_snapshot=task.title or '',
                    actions_summary='; '.join(actions_taken) if actions_taken else 'No actions',
                    outcome=outcome,
                    skip_reason=skip_reason,
                    error_detail='; '.join(errors) if errors else '',
                )
            except Exception:
                logger.exception("Failed to write AutomationLog for rule pk=%s", rule.pk)

        overall_outcome = 'failed' if total_errors > 0 else 'success'
        AutomationRule.objects.filter(pk=rule.pk).update(
            run_count=rule.run_count + 1,
            failure_count=0,
            last_run_at=now,
            last_execution_result=overall_outcome,
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


# ─── Phase 1b — new periodic tasks ───────────────────────────────────────────


def _run_scheduled_task_scan(trigger_type, task_queryset_for_rule_fn):
    """Shared driver for periodic scans modelled on run_overdue_task_automations.

    ``task_queryset_for_rule_fn(rule, now) -> queryset`` returns the tasks the
    rule should fire on. Per-task: dedupe per-day, execute via _execute_flat_rule,
    write an AutomationLog, update rule.run_count/last_run_at.
    """
    from kanban.automation_models import AutomationRule, AutomationLog
    from kanban.signals import _execute_flat_rule, _apply_automation_action

    rules = AutomationRule.objects.filter(
        trigger_type=trigger_type,
        is_active=True,
    ).select_related('board', 'created_by')
    if not rules.exists():
        return 0

    now = timezone.now()
    fired_total = 0

    for rule in rules:
        try:
            tasks = task_queryset_for_rule_fn(rule, now)
        except Exception:
            logger.exception(
                "%s automation (rule pk=%s) failed building queryset",
                trigger_type, rule.pk,
            )
            continue

        fired_for_rule = 0
        for task in tasks:
            # Per-day dedupe so a single idle/predicted task doesn't accumulate
            # multiple log rows across hourly Celery sweeps.
            if AutomationLog.objects.filter(
                rule_id=rule.pk,
                task_affected_id=task.pk,
                triggered_at__date=now.date(),
            ).exists():
                continue

            fired_for_rule += 1
            actions_taken = []
            errors = []
            outcome, skip_reason = 'success', ''
            try:
                if rule.actions:
                    outcome, skip_reason, _branch = _execute_flat_rule(
                        rule, task, actions_taken, errors,
                    )
                else:
                    _apply_automation_action(task, rule)
                    actions_taken.append(f"{rule.action_type}: {rule.action_value}")
            except Exception:
                logger.exception(
                    "%s automation (rule pk=%s) failed on task pk=%s",
                    trigger_type, rule.pk, task.pk,
                )
                outcome = 'failed'
                errors.append('Execution error')

            try:
                AutomationLog.objects.create(
                    rule=rule,
                    rule_name_snapshot=rule.name,
                    board=rule.board,
                    trigger_event=rule.trigger_type,
                    task_affected=task,
                    task_title_snapshot=task.title or '',
                    actions_summary='; '.join(actions_taken) if actions_taken else 'No actions',
                    outcome=outcome,
                    skip_reason=skip_reason,
                    error_detail='; '.join(errors) if errors else '',
                )
            except Exception:
                logger.exception(
                    "Failed to write AutomationLog for rule pk=%s", rule.pk,
                )
            fired_total += 1

        # Count only the tasks that actually fired this sweep (exclude per-day
        # dedupe skips) so the rule card's "Fired N times" stays accurate.
        if fired_for_rule:
            AutomationRule.objects.filter(pk=rule.pk).update(
                run_count=rule.run_count + fired_for_rule,
                last_run_at=now,
            )

    logger.info('%s: fired %d actions', trigger_type, fired_total)
    return fired_total


@shared_task(name='kanban.run_idle_task_automations')
def run_idle_task_automations():
    """Fires task_idle rules — tasks not updated for ``trigger_config.days`` days."""
    from kanban.models import Task

    def qs(rule, now):
        # The rule builder persists the interval as ``idle_days`` (see
        # automation_views validation); accept ``days`` too for back-compat.
        cfg = rule.trigger_config or {}
        try:
            days = int(cfg.get('idle_days', cfg.get('days', 7)))
        except (TypeError, ValueError):
            days = 7
        cutoff = now - timezone.timedelta(days=days)
        return Task.objects.filter(
            column__board=rule.board,
            updated_at__lt=cutoff,
        ).exclude(progress=100)

    return _run_scheduled_task_scan('task_idle', qs)


@shared_task(name='kanban.run_start_date_reached_automations')
def run_start_date_reached_automations():
    """Fires task_start_date_reached rules — tasks whose start_date <= today
    and progress < 100."""
    from kanban.models import Task

    def qs(rule, now):
        return Task.objects.filter(
            column__board=rule.board,
            start_date__lte=now.date(),
        ).exclude(progress=100).exclude(start_date__isnull=True)

    return _run_scheduled_task_scan('task_start_date_reached', qs)


@shared_task(name='kanban.run_predicted_late_automations')
def run_predicted_late_automations():
    """Phase 2: fires predicted_late rules — tasks whose AI-predicted completion
    date exceeds the due date. Skips tasks without both fields populated."""
    from kanban.models import Task
    from django.db.models import F

    def qs(rule, now):
        return Task.objects.filter(
            column__board=rule.board,
            predicted_completion_date__isnull=False,
            due_date__isnull=False,
            predicted_completion_date__gt=F('due_date'),
        ).exclude(progress=100)

    return _run_scheduled_task_scan('predicted_late', qs)


@shared_task(name='kanban.run_dependency_overdue_automations')
def run_dependency_overdue_automations():
    """Phase 3: fires dependency_overdue rules — tasks that have at least one
    blocking dependency which is itself overdue (due date passed, progress < 100).

    The post_save signal can't evaluate this cleanly (it only sees the saved
    task, not its blockers' state over time), so it's swept here like the other
    relationship/time-based triggers. Fires on the *blocked* task so a
    "notify me / flag for review" rule lands where the user is waiting.
    """
    from kanban.models import Task

    def qs(rule, now):
        today = now.date()
        return Task.objects.filter(
            column__board=rule.board,
            dependencies__due_date__lt=today,
            dependencies__progress__lt=100,
        ).exclude(progress=100).distinct()

    return _run_scheduled_task_scan('dependency_overdue', qs)
