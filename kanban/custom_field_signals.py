"""
Signals for custom-field value changes — emit a "field changed" event that
Scope Autopsy's history collector can pick up.

GUARDRAIL — bulk/system writes must NOT pollute autopsy history.
    Django signals fire on EVERY save, including:
      • Data migrations
      • Bulk imports (e.g., kanban-board-import management command)
      • Demo data seeding (populate_all_demo_data.py)
      • Programmatic backfills
    These should be invisible to the audit/autopsy timeline.

    Guard: only record an audit event when `instance.updated_by_id` is set
    (i.e., a real, authenticated user touched the value through a UI flow).
    System paths leave updated_by=None and are silently skipped.

    Convention: any code path that wants its change to count in autopsy
    MUST set `value_row.updated_by = request.user` before .save().
"""

import logging

from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver

from .custom_field_models import TaskCustomFieldValue

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TaskCustomFieldValue)
def record_custom_field_change(sender, instance, created, **kwargs):
    """Log a custom-field change to the TaskActivity stream when a real
    user made the change. Scope Autopsy consumes TaskActivity entries to
    build its timeline."""
    if instance.updated_by_id is None:
        # Bulk/system write — skip silently. This is the documented guard.
        return

    try:
        from .models import TaskActivity
    except ImportError:
        return

    field_name = instance.field.name if instance.field_id else 'custom field'
    display = instance.display_value() or '(cleared)'
    verb = 'set' if created else 'updated'

    try:
        TaskActivity.objects.create(
            task=instance.task,
            user_id=instance.updated_by_id,
            activity_type='custom_field',
            description=f"{verb} {field_name} to {display}",
        )
    except Exception as exc:  # noqa: BLE001 — never break the save path
        logger.warning(
            "Failed to record TaskActivity for custom-field change "
            "(task_id=%s, field_id=%s): %s",
            instance.task_id, instance.field_id, exc,
        )


@receiver(post_delete, sender=TaskCustomFieldValue)
def record_custom_field_clear(sender, instance, **kwargs):
    """Same guard: only log explicit user clears (not cascading deletes)."""
    if instance.updated_by_id is None:
        return

    try:
        from .models import TaskActivity
    except ImportError:
        return

    field_name = instance.field.name if instance.field_id else 'custom field'
    try:
        TaskActivity.objects.create(
            task_id=instance.task_id,
            user_id=instance.updated_by_id,
            activity_type='custom_field',
            description=f"cleared {field_name}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to record clear: %s", exc)
