"""
Views for managing ScheduledAutomation rules.

Follows the same patterns as automation_views.py (function-based,
@login_required, POST for toggle/delete, Django messages for feedback).
"""
import logging

from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from kanban.models import Board
from kanban.automation_models import ScheduledAutomation
from kanban.simple_access import can_access_board
from kanban.scheduled_automation_utils import (
    create_periodic_task_for_automation,
    delete_periodic_task_for_automation,
    toggle_periodic_task,
)

logger = logging.getLogger(__name__)

MAX_SCHEDULED_AUTOMATIONS_PER_BOARD = 10


# ---------------------------------------------------------------------------
# Create (POST) — called from the automations page form
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(['POST'])
def scheduled_automation_create(request, board_id):
    """Validate and create a new ScheduledAutomation + its PeriodicTask."""
    board = get_object_or_404(Board, id=board_id)

    if not can_access_board(request.user, board):
        messages.error(request, 'You do not have access to this board.')
        return redirect('automations_list', board_id=board_id)

    # --- Gather form data ---
    name = request.POST.get('sched_name', '').strip()
    schedule_type = request.POST.get('schedule_type', '')
    scheduled_time = request.POST.get('scheduled_time', '').strip()
    scheduled_day = request.POST.get('scheduled_day', '').strip() or None
    action = request.POST.get('sched_action', '')
    action_value = request.POST.get('sched_action_value', '').strip()
    notify_target = request.POST.get('notify_target', 'board_members')
    task_filter = request.POST.get('task_filter', 'all')

    valid_schedule_types = {c[0] for c in ScheduledAutomation.SCHEDULE_TYPE_CHOICES}
    valid_actions = {c[0] for c in ScheduledAutomation.ACTION_CHOICES}
    valid_notify_targets = {c[0] for c in ScheduledAutomation.NOTIFY_TARGET_CHOICES}
    valid_task_filters = {c[0] for c in ScheduledAutomation.TASK_FILTER_CHOICES}
    valid_priorities = {'low', 'medium', 'high', 'urgent'}

    errors = []

    # --- Validation ---
    if not name:
        errors.append('Rule name is required.')
    elif ScheduledAutomation.objects.filter(board=board, name=name).exists():
        errors.append(f'A scheduled rule named "{name}" already exists on this board.')

    if schedule_type not in valid_schedule_types:
        errors.append('Invalid schedule type.')

    # Time
    import datetime
    parsed_time = None
    if not scheduled_time:
        errors.append('Scheduled time is required.')
    else:
        try:
            parsed_time = datetime.datetime.strptime(scheduled_time, '%H:%M').time()
        except ValueError:
            errors.append('Invalid time format. Use HH:MM.')

    # Day validation
    parsed_day = None
    if schedule_type in ('weekly', 'monthly'):
        if scheduled_day is None:
            errors.append(f'Day is required for {schedule_type} schedules.')
        else:
            try:
                parsed_day = int(scheduled_day)
            except (ValueError, TypeError):
                errors.append('Invalid day value.')
            else:
                if schedule_type == 'weekly' and not (0 <= parsed_day <= 6):
                    errors.append('Weekly day must be 0 (Monday) through 6 (Sunday).')
                if schedule_type == 'monthly' and not (1 <= parsed_day <= 28):
                    errors.append('Monthly day must be between 1 and 28.')

    if action not in valid_actions:
        errors.append('Invalid action type.')
    if action == 'set_priority' and action_value.lower() not in valid_priorities:
        errors.append(f'Priority must be one of: {", ".join(sorted(valid_priorities))}.')
    if action == 'set_priority':
        action_value = action_value.lower()

    if notify_target not in valid_notify_targets:
        errors.append('Invalid notification target.')
    if task_filter not in valid_task_filters:
        errors.append('Invalid task filter.')

    # Max 10 per board
    if ScheduledAutomation.objects.filter(board=board).count() >= MAX_SCHEDULED_AUTOMATIONS_PER_BOARD:
        errors.append(f'Maximum {MAX_SCHEDULED_AUTOMATIONS_PER_BOARD} scheduled automations per board.')

    if errors:
        for e in errors:
            messages.error(request, e)
        return redirect('automations_list', board_id=board_id)

    # --- Create ---
    sa = ScheduledAutomation.objects.create(
        board=board,
        created_by=request.user,
        name=name,
        is_active=True,
        schedule_type=schedule_type,
        scheduled_time=parsed_time,
        scheduled_day=parsed_day,
        action=action,
        action_value=action_value,
        notify_target=notify_target,
        task_filter=task_filter,
    )

    # Create the linked PeriodicTask so Celery Beat picks it up
    try:
        create_periodic_task_for_automation(sa)
    except Exception:
        logger.exception("Failed to create PeriodicTask for ScheduledAutomation pk=%s", sa.pk)
        messages.warning(
            request,
            f'Rule "{name}" was saved but its schedule could not be registered. '
            f'Please delete and re-create it.',
        )
        return redirect('automations_list', board_id=board_id)

    messages.success(request, f'Scheduled rule "{name}" created successfully.')
    return redirect('automations_list', board_id=board_id)


# ---------------------------------------------------------------------------
# Toggle (POST) — enable / disable
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(['POST'])
def scheduled_automation_toggle(request, board_id, automation_id):
    """Toggle is_active on a ScheduledAutomation and its PeriodicTask."""
    board = get_object_or_404(Board, id=board_id)
    if not can_access_board(request.user, board):
        messages.error(request, 'You do not have access to this board.')
        return redirect('automations_list', board_id=board_id)

    sa = get_object_or_404(ScheduledAutomation, id=automation_id, board=board)
    sa.is_active = not sa.is_active
    sa.save(update_fields=['is_active'])
    toggle_periodic_task(sa)

    status = 'enabled' if sa.is_active else 'paused'
    messages.success(request, f'Scheduled rule "{sa.name}" {status}.')
    return redirect('automations_list', board_id=board_id)


# ---------------------------------------------------------------------------
# Delete (POST)
# ---------------------------------------------------------------------------

@login_required
@require_http_methods(['POST'])
def scheduled_automation_delete(request, board_id, automation_id):
    """Delete a ScheduledAutomation and its linked PeriodicTask."""
    board = get_object_or_404(Board, id=board_id)
    if not can_access_board(request.user, board):
        messages.error(request, 'You do not have access to this board.')
        return redirect('automations_list', board_id=board_id)

    sa = get_object_or_404(ScheduledAutomation, id=automation_id, board=board)
    name = sa.name

    # Delete PeriodicTask first (+ orphaned CrontabSchedule)
    delete_periodic_task_for_automation(sa)
    sa.delete()

    messages.success(request, f'Scheduled rule "{name}" deleted.')
    return redirect('automations_list', board_id=board_id)
