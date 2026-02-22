"""
Views for managing BoardAutomation rules.
"""
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_http_methods

from kanban.models import Board, TaskLabel
from kanban.automation_models import BoardAutomation


@login_required
def automations_list(request, board_id):
    """List all automation rules for a board; create a new one via POST."""
    board = get_object_or_404(Board, id=board_id)
    automations = BoardAutomation.objects.filter(board=board).order_by('-created_at')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        trigger_type = request.POST.get('trigger_type', '')
        trigger_value = request.POST.get('trigger_value', '').strip()
        action_type = request.POST.get('action_type', '')
        action_value = request.POST.get('action_value', '').strip()

        # Basic validation
        valid_triggers = [t[0] for t in BoardAutomation.TRIGGER_CHOICES]
        valid_actions = [a[0] for a in BoardAutomation.ACTION_CHOICES]
        valid_priorities = {'low', 'medium', 'high', 'urgent'}

        errors = []
        if not name:
            errors.append('Rule name is required.')
        if trigger_type not in valid_triggers:
            errors.append('Invalid trigger type.')
        if trigger_type == 'moved_to_column' and not trigger_value:
            errors.append('Column name fragment is required for "moved to column" trigger.')
        if action_type not in valid_actions:
            errors.append('Invalid action type.')
        if action_type == 'set_priority' and action_value.lower() not in valid_priorities:
            errors.append(f'Priority must be one of: {", ".join(valid_priorities)}.')
        if action_type == 'add_label':
            label_exists = TaskLabel.objects.filter(
                board=board, name__iexact=action_value
            ).exists()
            if not label_exists:
                errors.append(f'Label "{action_value}" does not exist on this board.')

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
            messages.success(request, f'Automation "{name}" created.')
            return redirect('automations_list', board_id=board_id)

    labels = TaskLabel.objects.filter(board=board).order_by('name')
    context = {
        'board': board,
        'automations': automations,
        'labels': labels,
        'trigger_choices': BoardAutomation.TRIGGER_CHOICES,
        'action_choices': BoardAutomation.ACTION_CHOICES,
    }
    return render(request, 'kanban/automations.html', context)


@login_required
@require_http_methods(['POST'])
def automation_delete(request, board_id, automation_id):
    """Delete a single automation rule."""
    board = get_object_or_404(Board, id=board_id)
    rule = get_object_or_404(BoardAutomation, id=automation_id, board=board)
    name = rule.name
    rule.delete()
    messages.success(request, f'Automation "{name}" deleted.')
    return redirect('automations_list', board_id=board_id)


@login_required
@require_http_methods(['POST'])
def automation_toggle(request, board_id, automation_id):
    """Toggle is_active on a rule."""
    board = get_object_or_404(Board, id=board_id)
    rule = get_object_or_404(BoardAutomation, id=automation_id, board=board)
    rule.is_active = not rule.is_active
    rule.save(update_fields=['is_active'])
    status = 'enabled' if rule.is_active else 'paused'
    messages.success(request, f'Automation "{rule.name}" {status}.')
    return redirect('automations_list', board_id=board_id)
