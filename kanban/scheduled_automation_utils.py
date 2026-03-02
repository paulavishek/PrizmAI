"""
Utility functions for managing the django-celery-beat PeriodicTask
records linked to ScheduledAutomation instances.
"""
import json
import logging

from django_celery_beat.models import CrontabSchedule, PeriodicTask

logger = logging.getLogger(__name__)


def _build_crontab_kwargs(scheduled_automation):
    """
    Convert a ScheduledAutomation's schedule definition into
    keyword arguments suitable for CrontabSchedule.objects.get_or_create().
    """
    sa = scheduled_automation
    time = sa.scheduled_time

    if sa.schedule_type == 'daily':
        return {
            'minute': str(time.minute),
            'hour': str(time.hour),
            'day_of_week': '*',
            'day_of_month': '*',
            'month_of_year': '*',
        }
    elif sa.schedule_type == 'weekly':
        return {
            'minute': str(time.minute),
            'hour': str(time.hour),
            'day_of_week': str(sa.scheduled_day),
            'day_of_month': '*',
            'month_of_year': '*',
        }
    elif sa.schedule_type == 'monthly':
        return {
            'minute': str(time.minute),
            'hour': str(time.hour),
            'day_of_week': '*',
            'day_of_month': str(sa.scheduled_day),
            'month_of_year': '*',
        }
    raise ValueError(f"Unknown schedule_type: {sa.schedule_type}")


def create_periodic_task_for_automation(scheduled_automation):
    """
    Create a CrontabSchedule + PeriodicTask for a ScheduledAutomation.
    Saves the FK back onto the ScheduledAutomation instance.
    """
    sa = scheduled_automation
    crontab_kwargs = _build_crontab_kwargs(sa)
    schedule, _ = CrontabSchedule.objects.get_or_create(**crontab_kwargs)

    task_name = f'scheduled_automation_{sa.id}'
    periodic_task = PeriodicTask.objects.create(
        crontab=schedule,
        name=task_name,
        task='kanban.tasks.automation_tasks.run_scheduled_automation',
        args=json.dumps([sa.id]),
        enabled=sa.is_active,
    )

    sa.periodic_task = periodic_task
    sa.save(update_fields=['periodic_task'])

    logger.info("Created PeriodicTask '%s' for ScheduledAutomation pk=%s", task_name, sa.pk)
    return periodic_task


def update_periodic_task_for_automation(scheduled_automation):
    """
    Re-create the linked PeriodicTask when the schedule or active state changes.
    Simpler (and safer) than partial-updating crontab fields.
    """
    delete_periodic_task_for_automation(scheduled_automation)
    return create_periodic_task_for_automation(scheduled_automation)


def delete_periodic_task_for_automation(scheduled_automation):
    """
    Delete the PeriodicTask (and clean up orphaned CrontabSchedule)
    linked to a ScheduledAutomation.
    """
    sa = scheduled_automation
    pt = sa.periodic_task
    if pt is None:
        return

    crontab = pt.crontab

    # Unlink first so the SET_NULL doesn't leave stale data
    sa.periodic_task = None
    sa.save(update_fields=['periodic_task'])

    pt.delete()
    logger.info("Deleted PeriodicTask pk=%s for ScheduledAutomation pk=%s", pt.pk, sa.pk)

    # Clean up the CrontabSchedule if nothing else uses it
    if crontab and not PeriodicTask.objects.filter(crontab=crontab).exists():
        crontab.delete()
        logger.debug("Cleaned up orphaned CrontabSchedule pk=%s", crontab.pk)


def toggle_periodic_task(scheduled_automation):
    """
    Sync the PeriodicTask.enabled flag with ScheduledAutomation.is_active.
    """
    sa = scheduled_automation
    if sa.periodic_task:
        sa.periodic_task.enabled = sa.is_active
        sa.periodic_task.save(update_fields=['enabled'])
