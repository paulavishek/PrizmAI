"""
Views for managing BoardAutomation rules.
"""
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from kanban.models import Board, TaskLabel, Column
from kanban.automation_models import BoardAutomation

# ---------------------------------------------------------------------------
# Pre-built template rules that users can activate with one click
# ---------------------------------------------------------------------------
TEMPLATE_RULES = [
    {
        'id': 'tpl_overdue_urgent',
        'name': 'Mark overdue tasks as Urgent',
        'description': 'When a task passes its due date without being completed, automatically escalate its priority.',
        'trigger_type': 'task_overdue',
        'trigger_value': '',
        'action_type': 'set_priority',
        'action_value': 'urgent',
        'icon': 'fa-fire',
        'color': 'danger',
    },
    {
        'id': 'tpl_done_notify',
        'name': 'Notify creator when task is completed',
        'description': 'When a task reaches 100% progress, notify the person who created it — useful for review workflows.',
        'trigger_type': 'task_completed',
        'trigger_value': '',
        'action_type': 'send_notification',
        'action_value': 'creator',
        'icon': 'fa-check-circle',
        'color': 'success',
    },
    {
        'id': 'tpl_approaching_notify',
        'name': 'Alert assignee 2 days before deadline',
        'description': 'Sends an in-app notification to the task assignee when the due date is only 2 days away.',
        'trigger_type': 'due_date_approaching',
        'trigger_value': '2',
        'action_type': 'send_notification',
        'action_value': 'assignee',
        'icon': 'fa-bell',
        'color': 'warning',
    },
]


@login_required
def automations_list(request, board_id):
    """List all automation rules for a board; create a new one via POST."""
    board = get_object_or_404(Board, id=board_id)
    automations = BoardAutomation.objects.filter(board=board).order_by('-created_at')

    if request.method == 'POST':
        name         = request.POST.get('name', '').strip()
        trigger_type = request.POST.get('trigger_type', '')
        trigger_value = request.POST.get('trigger_value', '').strip()
        action_type  = request.POST.get('action_type', '')
        action_value = request.POST.get('action_value', '').strip()

        valid_triggers  = [t[0] for t in BoardAutomation.TRIGGER_CHOICES]
        valid_actions   = [a[0] for a in BoardAutomation.ACTION_CHOICES]
        valid_priorities = {'low', 'medium', 'high', 'urgent'}
        valid_notify_targets = {'assignee', 'board_members', 'creator'}

        errors = []
        if not name:
            errors.append('Rule name is required.')
        if trigger_type not in valid_triggers:
            errors.append('Invalid trigger type.')
        if trigger_type == 'moved_to_column' and not trigger_value:
            errors.append('Column fragment is required for "moved to column" trigger.')
        if trigger_type == 'priority_changed' and trigger_value.lower() not in valid_priorities:
            errors.append(f'Priority trigger value must be one of: {", ".join(sorted(valid_priorities))}.')
        if trigger_type == 'due_date_approaching':
            try:
                days = int(trigger_value)
                if days < 1 or days > 365:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append('Due date approaching requires a whole number of days between 1 and 365.')
        if action_type not in valid_actions:
            errors.append('Invalid action type.')
        if action_type == 'set_priority' and action_value.lower() not in valid_priorities:
            errors.append(f'Priority must be one of: {", ".join(sorted(valid_priorities))}.')
        if action_type == 'add_label':
            if not TaskLabel.objects.filter(board=board, name__iexact=action_value).exists():
                errors.append(f'Label "{action_value}" does not exist on this board.')
        if action_type == 'send_notification' and action_value.lower() not in valid_notify_targets:
            errors.append(f'Notify target must be one of: {", ".join(sorted(valid_notify_targets))}.')
        if action_type == 'move_to_column' and not action_value:
            errors.append('Column fragment is required for "move to column" action.')
        if action_type == 'assign_to_user':
            from django.contrib.auth.models import User
            member_usernames = set(
                board.members.values_list('username', flat=True)
            ) | {board.created_by.username}
            if action_value not in member_usernames:
                errors.append(f'User "{action_value}" is not a member of this board.')
        if action_type == 'set_due_date':
            try:
                days = int(action_value)
                if days < 0 or days > 9999:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append('Set due date requires a whole number of days (0–9999).')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            BoardAutomation.objects.create(
                board=board,
                name=name,
                trigger_type=trigger_type,
                trigger_value=trigger_value,
                action_type=action_type,
                action_value=action_value,
                is_active=True,
                created_by=request.user,
            )
            messages.success(request, f'Automation "{name}" created successfully.')
            return redirect('automations_list', board_id=board_id)

    labels   = TaskLabel.objects.filter(board=board).order_by('name')
    columns  = Column.objects.filter(board=board).order_by('position')
    members  = list(board.members.all().order_by('username'))
    if board.created_by not in members:
        members.insert(0, board.created_by)

    # Determine which templates are already active on this board
    existing_names = set(automations.values_list('name', flat=True))
    templates = [
        dict(t, already_active=(t['name'] in existing_names))
        for t in TEMPLATE_RULES
    ]

    context = {
        'board': board,
        'automations': automations,
        'labels': labels,
        'columns': columns,
        'members': members,
        'trigger_choices': BoardAutomation.TRIGGER_CHOICES,
        'action_choices': BoardAutomation.ACTION_CHOICES,
        'templates': templates,
    }
    return render(request, 'kanban/automations.html', context)


@login_required
@require_http_methods(['POST'])
def automation_delete(request, board_id, automation_id):
    """Delete a single automation rule."""
    board = get_object_or_404(Board, id=board_id)
    rule  = get_object_or_404(BoardAutomation, id=automation_id, board=board)
    name  = rule.name
    rule.delete()
    messages.success(request, f'Automation "{name}" deleted.')
    return redirect('automations_list', board_id=board_id)


@login_required
@require_http_methods(['POST'])
def automation_toggle(request, board_id, automation_id):
    """Toggle is_active on a rule."""
    board = get_object_or_404(Board, id=board_id)
    rule  = get_object_or_404(BoardAutomation, id=automation_id, board=board)
    rule.is_active = not rule.is_active
    rule.save(update_fields=['is_active'])
    status = 'enabled' if rule.is_active else 'paused'
    messages.success(request, f'Automation "{rule.name}" {status}.')
    return redirect('automations_list', board_id=board_id)


@login_required
@require_http_methods(['POST'])
def automation_activate_template(request, board_id, template_id):
    """Instantly create an automation rule from a pre-built template."""
    board = get_object_or_404(Board, id=board_id)
    tpl   = next((t for t in TEMPLATE_RULES if t['id'] == template_id), None)
    if tpl is None:
        messages.error(request, 'Unknown template.')
        return redirect('automations_list', board_id=board_id)

    _, created = BoardAutomation.objects.get_or_create(
        board=board,
        name=tpl['name'],
        defaults=dict(
            trigger_type=tpl['trigger_type'],
            trigger_value=tpl['trigger_value'],
            action_type=tpl['action_type'],
            action_value=tpl['action_value'],
            is_active=True,
            created_by=request.user,
        ),
    )
    if created:
        messages.success(request, f'Template rule "{tpl["name"]}" activated!')
    else:
        messages.info(request, f'Rule "{tpl["name"]}" already exists on this board.')
    return redirect('automations_list', board_id=board_id)
