"""
Celery task for time-based automation triggers.
Currently handles:
  - due_date_approaching: fires when a task's due date is within N days and task is not done.
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
