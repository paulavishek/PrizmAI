"""
Views for managing automation rules (AutomationRule).
Serves the four-tab automations page: Rules, Templates, Audit Log, Usage.
Provides JSON API endpoints for the unified rule builder (save/load/toggle/duplicate).
"""
import json
import uuid
import logging
from datetime import timedelta

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import Count, Q
from django.contrib.auth import get_user_model

User = get_user_model()

from kanban.models import Board, TaskLabel, Column
from kanban.automation_models import (
    AutomationRule, AutomationLog, AutomationTemplate,
    # Deprecated — kept for backward compat during transition
    BoardAutomation, ScheduledAutomation,
)
from kanban.simple_access import can_access_board

logger = logging.getLogger(__name__)

MAX_SCHEDULED_AUTOMATIONS_PER_BOARD = 10

VALID_TRIGGERS = {t[0] for t in AutomationRule.TRIGGER_CHOICES}
VALID_ACTIONS = {a[0] for a in AutomationRule.ACTION_CHOICES}

# Pull the authoritative attribute list from the registry so new condition
# handlers automatically become valid. Imported lazily inside the validator
# to avoid circular import at module load.
def _valid_attributes():
    from kanban.automation_conditions import CONDITION_HANDLERS
    return set(CONDITION_HANDLERS.keys())

VALID_OPERATORS = {
    # task-field operators (Phase 1a / 1b)
    'is', 'is_not', 'is_empty', 'is_not_empty', 'has', 'does_not_have',
    'gte', 'lte', 'equals', 'within_days', 'is_overdue', 'is_true', 'is_false',
    'is_past', 'is_today', 'contains', 'does_not_contain',
    'count_gte', 'count_lte',
    # AI & risk operators (Phase 2)
    'is_at_least', 'before_due', 'after_due', 'within_days_of_due',
    # hierarchy & dependencies operators (Phase 3)
    'all_complete', 'any_overdue', 'any_blocked',
}


# ───────────────────────────────────────────────────────
# Helper: build a simple two-block rule_definition tree
# (kept for backward compat with legacy form endpoints)
# ───────────────────────────────────────────────────────

def _make_id():
    return str(uuid.uuid4())


def _build_simple_rule_definition(trigger_type, trigger_config,
                                  action_type, action_config):
    """Build a minimal trigger → action rule_definition tree."""
    return {
        'id': _make_id(),
        'type': 'trigger',
        'block_type': trigger_type,
        'config': trigger_config,
        'children': [{
            'id': _make_id(),
            'type': 'action',
            'block_type': action_type,
            'config': action_config,
            'children': [],
            'else_children': [],
        }],
        'else_children': [],
    }


# ───────────────────────────────────────────────────────
# Helper: validate + create/update rule from unified format
# ───────────────────────────────────────────────────────

def _validate_unified_payload(data):
    """Validate the unified builder JSON payload. Returns list of error strings."""
    errors = []
    name = (data.get('name') or '').strip()
    if not name:
        errors.append('Rule name is required.')
    elif len(name) > 120:
        errors.append('Rule name must be 120 characters or fewer.')

    trigger_type = data.get('trigger_type', '').strip()
    if not trigger_type:
        errors.append('Please select a trigger in the WHEN section.')
    elif trigger_type not in VALID_TRIGGERS:
        errors.append(f'Unknown trigger type: {trigger_type}')

    if trigger_type == 'scheduled_daily':
        if not data.get('trigger_config', {}).get('time'):
            errors.append('Please set a time for the scheduled trigger.')
    elif trigger_type == 'scheduled_weekly':
        cfg = data.get('trigger_config', {})
        if not cfg.get('time'):
            errors.append('Please set a time for the scheduled trigger.')
        if not cfg.get('day'):
            errors.append('Please choose a day for the weekly schedule.')
    elif trigger_type == 'scheduled_monthly':
        cfg = data.get('trigger_config', {})
        if not cfg.get('time'):
            errors.append('Please set a time for the scheduled trigger.')
        dom = cfg.get('day_of_month')
        try:
            dom = int(dom)
            if not (1 <= dom <= 31):
                raise ValueError
        except (TypeError, ValueError):
            errors.append('Please enter a valid day of month (1–31).')

    actions = data.get('actions', [])
    if not actions:
        errors.append('Please add at least one action in the THEN section.')
    for i, a in enumerate(actions):
        if not a.get('type'):
            errors.append(f'Action {i + 1}: please select an action type.')
        elif a['type'] not in VALID_ACTIONS:
            errors.append(f'Action {i + 1}: unknown action type "{a["type"]}".')

    NO_VALUE_OPS = {
        'is_empty', 'is_not_empty', 'is_true', 'is_false',
        'is_overdue', 'is_past', 'is_today',
    }
    for i, c in enumerate(data.get('conditions', [])):
        if not c.get('attribute'):
            errors.append(f'Condition {i + 1}: please select an attribute.')
            continue
        op = c.get('operator')
        if not op:
            errors.append(f'Condition {i + 1}: please select an operator.')
            continue
        if op not in NO_VALUE_OPS:
            v = c.get('value')
            is_blank = v is None or (isinstance(v, str) and v.strip() == '')
            if is_blank:
                errors.append(
                    f'Condition {i + 1}: this operator needs a value to match against.'
                )

    # Trigger-config required-field validation parity with the client.
    cfg = data.get('trigger_config', {}) or {}
    if trigger_type == 'task_idle':
        try:
            if int(cfg.get('idle_days') or 0) < 1:
                raise ValueError
        except (TypeError, ValueError):
            errors.append('Please enter how many idle days should trigger the rule.')
    elif trigger_type == 'due_date_approaching':
        try:
            if int(cfg.get('days') or 0) < 1:
                raise ValueError
        except (TypeError, ValueError):
            errors.append('Please enter how many days ahead to watch for.')

    for i, a in enumerate(data.get('otherwise_actions', [])):
        if not a.get('type'):
            errors.append(f'Otherwise action {i + 1}: please select an action type.')

    return errors


def _rule_to_json(rule):
    """Serialize an AutomationRule to the JSON response format."""
    created_by_data = None
    if rule.created_by:
        created_by_data = {
            'id': rule.created_by.id,
            'name': rule.created_by.get_full_name() or rule.created_by.username,
        }
    return {
        'id': rule.id,
        'name': rule.name,
        'is_active': rule.is_active,
        'trigger_type': rule.trigger_type,
        'trigger_config': rule.trigger_config,
        'condition_logic': rule.condition_logic,
        'conditions': rule.conditions,
        'actions': rule.actions,
        'otherwise_actions': rule.otherwise_actions,
        'run_count': rule.run_count,
        'last_run_at': rule.last_run_at.isoformat() if rule.last_run_at else None,
        'last_execution_result': rule.last_execution_result,
        'created_by': created_by_data,
        'created_at': rule.created_at.isoformat(),
        'updated_at': rule.updated_at.isoformat(),
    }


# ───────────────────────────────────────────────────────
# Workspace-level automations hub (linked from sidebar)
# ───────────────────────────────────────────────────────

@login_required
def workspace_automations(request):
    """
    Show an overview of all automation rules across every board the user
    can access in the current workspace.  Groups by board and surfaces
    active/inactive/scheduled counts so users get a bird's-eye view before
    drilling into a specific board's automations page.
    """
    from kanban.utils.demo_protection import get_user_boards
    from kanban.automation_models import AutomationRule, ScheduledAutomation

    accessible_boards = get_user_boards(request.user).prefetch_related(
        'automation_rules',
    ).order_by('name')

    # Build a summary card per board that has at least some rules, plus
    # include boards with zero rules (so users can navigate to create their first)
    board_summaries = []
    for board in accessible_boards:
        active_count = AutomationRule.objects.filter(board=board, is_active=True).count()
        inactive_count = AutomationRule.objects.filter(board=board, is_active=False).count()
        scheduled_count = ScheduledAutomation.objects.filter(board=board).count()
        total_count = active_count + inactive_count
        board_summaries.append({
            'board': board,
            'active_count': active_count,
            'inactive_count': inactive_count,
            'scheduled_count': scheduled_count,
            'total_count': total_count,
        })

    # Sort: boards with automations first, then alphabetically
    board_summaries.sort(key=lambda x: (-x['total_count'], x['board'].name.lower()))

    context = {
        'board_summaries': board_summaries,
        'total_rules': sum(s['active_count'] + s['inactive_count'] for s in board_summaries),
        'total_active': sum(s['active_count'] for s in board_summaries),
    }
    return render(request, 'kanban/workspace_automations.html', context)


# ───────────────────────────────────────────────────────
# Main automations page (four tabs)
# ───────────────────────────────────────────────────────

@login_required
@ensure_csrf_cookie
def automations_page(request, board_id):
    """
    Render the full automations page with four tabs:
    Rules | Templates | Audit Log | Usage
    """
    board = get_object_or_404(Board, id=board_id)

    # RBAC: check board access
    if not request.user.has_perm('prizmai.view_board', board):
        from kanban.simple_access import get_spectra_denial_context
        ctx = get_spectra_denial_context(request.user, board, trigger='automations')
        from django.shortcuts import render as _render
        return _render(request, 'kanban/spectra_access_denied.html', ctx, status=403)

    tab = request.GET.get('tab', 'rules')

    # ── Common context ──
    rules = AutomationRule.objects.filter(board=board).order_by('-created_at')
    scheduled_automations = ScheduledAutomation.objects.filter(board=board).order_by('-created_at')
    labels = TaskLabel.objects.filter(board=board).order_by('name')
    columns = Column.objects.filter(board=board).order_by('position')
    members = list(User.objects.filter(board_memberships__board=board).order_by('username'))
    if board.created_by and board.created_by not in members:
        members.insert(0, board.created_by)

    context = {
        'board': board,
        'rules': rules,
        'scheduled_automations': scheduled_automations,
        'labels': labels,
        'columns': columns,
        'members': members,
        'trigger_choices': AutomationRule.TRIGGER_CHOICES,
        'action_choices': AutomationRule.ACTION_CHOICES,
        'trigger_groups': AutomationRule.TRIGGER_GROUPS,
        'action_groups': AutomationRule.ACTION_GROUPS,
        'active_tab': tab,
    }

    # ── Templates tab ──
    if tab == 'templates':
        templates = AutomationTemplate.objects.all()
        category = request.GET.get('category', '')
        if category:
            templates = templates.filter(category=category)
        context['templates'] = templates
        context['categories'] = AutomationTemplate.CATEGORY_CHOICES
        context['active_category'] = category

    # ── Audit Log tab ──
    elif tab == 'audit':
        logs_qs = AutomationLog.objects.filter(
            rule__board=board,
        ).select_related('rule', 'task_affected').order_by('-triggered_at')

        # Filters
        rule_filter = request.GET.get('rule', '')
        outcome_filter = request.GET.get('outcome', '')
        date_filter = request.GET.get('date_range', '')

        if rule_filter:
            logs_qs = logs_qs.filter(rule_id=rule_filter)
        if outcome_filter in ('success', 'skipped', 'failed', 'passed'):
            logs_qs = logs_qs.filter(outcome=outcome_filter)
        if date_filter == 'today':
            logs_qs = logs_qs.filter(triggered_at__date=timezone.now().date())
        elif date_filter == '7days':
            logs_qs = logs_qs.filter(triggered_at__gte=timezone.now() - timedelta(days=7))
        elif date_filter == '30days':
            logs_qs = logs_qs.filter(triggered_at__gte=timezone.now() - timedelta(days=30))

        paginator = Paginator(logs_qs, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
        context['logs'] = page_obj
        context['rule_filter'] = rule_filter
        context['outcome_filter'] = outcome_filter
        context['date_filter'] = date_filter

    # ── Usage tab ──
    elif tab == 'usage':
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        context['active_rules_count'] = rules.filter(is_active=True).count()
        context['total_rules_count'] = rules.count()
        context['runs_this_month'] = AutomationLog.objects.filter(
            rule__board=board,
            triggered_at__gte=month_start,
        ).count()
        context['passed_this_month'] = AutomationLog.objects.filter(
            rule__board=board,
            triggered_at__gte=month_start,
            outcome__in=('success', 'passed'),
        ).count()
        context['failed_this_month'] = AutomationLog.objects.filter(
            rule__board=board,
            triggered_at__gte=month_start,
            outcome='failed',
        ).count()

    # ── Also pass deprecated models for backward compat display ──
    context['legacy_automations'] = BoardAutomation.objects.filter(board=board).order_by('-created_at')
    context['scheduled_automations'] = ScheduledAutomation.objects.filter(board=board).order_by('-created_at')
    context['sched_schedule_types'] = ScheduledAutomation.SCHEDULE_TYPE_CHOICES
    context['sched_action_choices'] = ScheduledAutomation.ACTION_CHOICES
    context['sched_notify_targets'] = ScheduledAutomation.NOTIFY_TARGET_CHOICES
    context['sched_task_filters'] = ScheduledAutomation.TASK_FILTER_CHOICES

    return render(request, 'kanban/automations.html', context)


# ───────────────────────────────────────────────────────
# Rule CRUD (JSON API for canvas builder)
# ───────────────────────────────────────────────────────

@login_required
@require_http_methods(['POST'])
def rule_create(request, board_id):
    """
    Create a new AutomationRule from JSON.

    Accepts two formats:
    - Unified builder format: {name, trigger_type, trigger_config, conditions, actions, ...}
    - Legacy canvas format: {name, rule_definition}  (kept for backward compat)
    """
    board = get_object_or_404(Board, id=board_id)
    if not request.user.has_perm('prizmai.edit_board', board):
        return JsonResponse({'error': 'Access denied'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # ── Unified builder format ─────────────────────────────────
    if 'trigger_type' in data and 'rule_definition' not in data:
        errors = _validate_unified_payload(data)
        if errors:
            return JsonResponse({'errors': errors}, status=400)

        trigger_type = data['trigger_type'].strip()

        if trigger_type.startswith('scheduled_'):
            scheduled_count = AutomationRule.objects.filter(
                board=board, trigger_type__startswith='scheduled_',
            ).count()
            if scheduled_count >= MAX_SCHEDULED_AUTOMATIONS_PER_BOARD:
                return JsonResponse({
                    'errors': [f'Maximum {MAX_SCHEDULED_AUTOMATIONS_PER_BOARD} scheduled rules per board.']
                }, status=400)

        rule = AutomationRule.objects.create(
            board=board,
            name=data['name'].strip(),
            is_active=True,
            created_by=request.user,
            trigger_type=trigger_type,
            trigger_config=data.get('trigger_config') or {},
            condition_logic=data.get('condition_logic', 'AND'),
            conditions=data.get('conditions') or [],
            actions=data.get('actions') or [],
            otherwise_actions=data.get('otherwise_actions') or [],
        )

        if trigger_type.startswith('scheduled_'):
            _setup_scheduled_rule(rule, trigger_type, rule.trigger_config)

        return JsonResponse(_rule_to_json(rule), status=201)

    # ── Legacy canvas format ───────────────────────────────────
    name = (data.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'Rule name is required'}, status=400)

    rule_definition = data.get('rule_definition')
    if not rule_definition:
        return JsonResponse({'error': 'rule_definition is required'}, status=400)

    trigger_type = rule_definition.get('block_type', '')
    trigger_config = rule_definition.get('config', {})

    if trigger_type.startswith('scheduled_'):
        scheduled_count = AutomationRule.objects.filter(
            board=board, trigger_type__startswith='scheduled_',
        ).count()
        if scheduled_count >= MAX_SCHEDULED_AUTOMATIONS_PER_BOARD:
            return JsonResponse({
                'error': f'Maximum {MAX_SCHEDULED_AUTOMATIONS_PER_BOARD} scheduled rules per board.'
            }, status=400)

    rule = AutomationRule.objects.create(
        board=board,
        name=name,
        is_active=True,
        created_by=request.user,
        trigger_type=trigger_type,
        trigger_value=trigger_config.get('value', ''),
        rule_definition=rule_definition,
    )

    if trigger_type.startswith('scheduled_'):
        _setup_scheduled_rule(rule, trigger_type, trigger_config)

    return JsonResponse({'id': rule.id, 'name': rule.name, 'is_active': rule.is_active}, status=201)


@login_required
@require_http_methods(['POST', 'PATCH'])
def rule_update(request, board_id, rule_id):
    """
    Update an existing AutomationRule.

    Accepts two formats (same detection as rule_create):
    - Unified builder format: {name, trigger_type, trigger_config, conditions, actions, ...}
    - Legacy canvas format: {name, rule_definition}
    """
    board = get_object_or_404(Board, id=board_id)
    if not request.user.has_perm('prizmai.edit_board', board):
        return JsonResponse({'error': 'Access denied'}, status=403)

    rule = get_object_or_404(AutomationRule, id=rule_id, board=board)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # ── Unified builder format ─────────────────────────────────
    if 'trigger_type' in data and 'rule_definition' not in data:
        errors = _validate_unified_payload(data)
        if errors:
            return JsonResponse({'errors': errors}, status=400)

        old_is_scheduled = rule.trigger_type.startswith('scheduled_')
        new_trigger_type = data['trigger_type'].strip()
        new_is_scheduled = new_trigger_type.startswith('scheduled_')

        rule.name = data['name'].strip()
        rule.trigger_type = new_trigger_type
        rule.trigger_config = data.get('trigger_config') or {}
        rule.condition_logic = data.get('condition_logic', 'AND')
        rule.conditions = data.get('conditions') or []
        rule.actions = data.get('actions') or []
        rule.otherwise_actions = data.get('otherwise_actions') or []
        rule.save()

        if new_is_scheduled:
            _setup_scheduled_rule(rule, new_trigger_type, rule.trigger_config)
        elif old_is_scheduled:
            _cleanup_scheduled_rule(rule)

        return JsonResponse(_rule_to_json(rule))

    # ── Legacy canvas format ───────────────────────────────────
    name = data.get('name')
    if name is not None:
        name = name.strip()
        if not name:
            return JsonResponse({'error': 'Rule name cannot be empty'}, status=400)
        rule.name = name

    rule_definition = data.get('rule_definition')
    if rule_definition:
        rule.rule_definition = rule_definition
        trigger_type = rule_definition.get('block_type', '')
        trigger_config = rule_definition.get('config', {})
        rule.trigger_type = trigger_type
        rule.trigger_value = trigger_config.get('value', '')

        old_is_scheduled = rule.schedule_type != ''
        new_is_scheduled = trigger_type.startswith('scheduled_')

        if new_is_scheduled:
            _setup_scheduled_rule(rule, trigger_type, trigger_config)
        elif old_is_scheduled:
            _cleanup_scheduled_rule(rule)

    rule.save()
    return JsonResponse({'id': rule.id, 'name': rule.name, 'is_active': rule.is_active})


@login_required
@require_http_methods(['GET'])
def rule_detail(request, board_id, rule_id):
    """Return a single rule's full data as JSON (for unified builder load)."""
    board = get_object_or_404(Board, id=board_id)

    if not request.user.has_perm('prizmai.view_board', board):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    rule = get_object_or_404(AutomationRule, id=rule_id, board=board)
    return JsonResponse(_rule_to_json(rule))


@login_required
@require_http_methods(['POST'])
def rule_duplicate(request, board_id, rule_id):
    """Duplicate a rule, appending ' (copy)' to the name. Returns the new rule as JSON."""
    board = get_object_or_404(Board, id=board_id)
    if not request.user.has_perm('prizmai.edit_board', board):
        return JsonResponse({'error': 'Access denied'}, status=403)

    source = get_object_or_404(AutomationRule, id=rule_id, board=board)

    new_name = f'{source.name} (copy)'
    if len(new_name) > 120:
        new_name = new_name[:117] + '...'

    copy = AutomationRule.objects.create(
        board=board,
        name=new_name,
        is_active=False,
        created_by=request.user,
        trigger_type=source.trigger_type,
        trigger_config=source.trigger_config,
        condition_logic=source.condition_logic,
        conditions=source.conditions,
        actions=source.actions,
        otherwise_actions=source.otherwise_actions,
    )

    if copy.trigger_type.startswith('scheduled_') and copy.trigger_config:
        try:
            _setup_scheduled_rule(copy, copy.trigger_type, copy.trigger_config)
        except Exception:
            logger.exception('Failed to set up PeriodicTask for duplicated rule pk=%s', copy.pk)

    return JsonResponse(_rule_to_json(copy), status=201)


@login_required
@require_http_methods(['GET'])
def rule_builder_data(request, board_id):
    """Return board-specific context needed by the unified rule builder JS."""
    board = get_object_or_404(Board, id=board_id)
    if not request.user.has_perm('prizmai.view_board', board):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    members = list(
        User.objects.filter(board_memberships__board=board)
        .values('id', 'username')
        .order_by('username')
    )
    if board.created_by and not any(m['id'] == board.created_by_id for m in members):
        members.insert(0, {'id': board.created_by.id, 'username': board.created_by.username})

    columns = list(
        Column.objects.filter(board=board)
        .values('id', 'name')
        .order_by('position')
    )

    labels = list(
        TaskLabel.objects.filter(board=board)
        .values('id', 'name')
        .order_by('name')
    )

    return JsonResponse({
        'members': members,
        'columns': columns,
        'labels': labels,
        'is_official_demo_board': bool(getattr(board, 'is_official_demo_board', False)),
        'is_sandbox_copy': bool(getattr(board, 'is_sandbox_copy', False)),
    })


@login_required
@require_http_methods(['POST'])
def rule_delete(request, board_id, rule_id):
    """Delete an AutomationRule."""
    board = get_object_or_404(Board, id=board_id)
    if not request.user.has_perm('prizmai.edit_board', board):
        return JsonResponse({'error': 'Access denied'}, status=403)

    rule = get_object_or_404(AutomationRule, id=rule_id, board=board)
    name = rule.name

    # Clean up PeriodicTask if scheduled
    if rule.periodic_task:
        _cleanup_scheduled_rule(rule)

    rule.delete()

    if request.headers.get('Accept') == 'application/json':
        return JsonResponse({'deleted': True, 'name': name})
    messages.success(request, f'Automation "{name}" deleted.')
    return redirect('automations_list', board_id=board_id)


# ───────────────────────────────────────────────────────
# Toggle (PATCH → JSON or POST → redirect)
# ───────────────────────────────────────────────────────

@login_required
@require_http_methods(['POST', 'PATCH'])
def rule_toggle(request, board_id, rule_id):
    """Toggle is_active on an AutomationRule. Returns JSON for PATCH, redirects for POST."""
    board = get_object_or_404(Board, id=board_id)

    # RBAC: check board edit permission
    if not request.user.has_perm('prizmai.edit_board', board):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    rule = get_object_or_404(AutomationRule, id=rule_id, board=board)
    rule.is_active = not rule.is_active
    rule.save(update_fields=['is_active'])

    # Sync PeriodicTask if scheduled
    if rule.periodic_task:
        rule.periodic_task.enabled = rule.is_active
        rule.periodic_task.save(update_fields=['enabled'])

    if request.method == 'PATCH' or request.headers.get('Accept') == 'application/json':
        return JsonResponse({'is_active': rule.is_active, 'name': rule.name})

    status = 'enabled' if rule.is_active else 'paused'
    messages.success(request, f'Automation "{rule.name}" {status}.')
    return redirect('automations_list', board_id=board_id)


# ───────────────────────────────────────────────────────
# Template activation
# ───────────────────────────────────────────────────────

@login_required
@require_http_methods(['POST'])
def template_use(request, board_id, template_id):
    """Create an AutomationRule from a template and redirect to the builder."""
    board = get_object_or_404(Board, id=board_id)
    if not can_access_board(request.user, board):
        messages.error(request, 'Access denied.')
        return redirect('automations_list', board_id=board_id)

    template = get_object_or_404(AutomationTemplate, id=template_id)

    # Check scheduled rule limit
    trigger_type = template.trigger_type
    if trigger_type.startswith('scheduled_'):
        scheduled_count = AutomationRule.objects.filter(
            board=board,
            trigger_type__startswith='scheduled_',
        ).count()
        if scheduled_count >= MAX_SCHEDULED_AUTOMATIONS_PER_BOARD:
            messages.error(request, f'Maximum {MAX_SCHEDULED_AUTOMATIONS_PER_BOARD} scheduled rules per board.')
            return redirect('automations_list', board_id=board_id)

    rule, created = AutomationRule.objects.get_or_create(
        board=board,
        name=template.name,
        defaults={
            'trigger_type': template.trigger_type,
            # Copy the flat builder fields so the rule actually does something.
            # Built-in templates store their logic here (rule_definition is None);
            # omitting these created rules with no actions/conditions.
            'trigger_config': template.trigger_config,
            'condition_logic': template.condition_logic,
            'conditions': template.conditions,
            'actions': template.actions,
            'rule_definition': template.rule_definition,
            'is_active': True,
            'created_by': request.user,
        },
    )
    if created:
        # Set up PeriodicTask for scheduled templates. The schedule details live
        # in the flat trigger_config (time / day / day_of_month), not in the
        # legacy rule_definition (which is None for built-in templates).
        if trigger_type.startswith('scheduled_'):
            _setup_scheduled_rule(rule, trigger_type, template.trigger_config or {})
        messages.success(request, f'Rule "{template.name}" created from template!')
    else:
        messages.info(request, f'Rule "{template.name}" already exists on this board.')

    return redirect('automations_list', board_id=board_id)


# ───────────────────────────────────────────────────────
# Legacy: form-based rule creation (POST from old form)
# ───────────────────────────────────────────────────────

@login_required
@require_http_methods(['POST'])
def rule_create_form(request, board_id):
    """Create an AutomationRule from the traditional form (backward compat)."""
    board = get_object_or_404(Board, id=board_id)

    # RBAC: check board edit permission
    if not request.user.has_perm('prizmai.edit_board', board):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    name = request.POST.get('name', '').strip()
    trigger_type = request.POST.get('trigger_type', '')
    trigger_value = request.POST.get('trigger_value', '').strip()
    action_type = request.POST.get('action_type', '')
    action_value = request.POST.get('action_value', '').strip()

    valid_triggers = [t[0] for t in AutomationRule.TRIGGER_CHOICES]
    valid_actions = [a[0] for a in AutomationRule.ACTION_CHOICES]
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
        member_usernames = set(
            User.objects.filter(board_memberships__board=board).values_list('username', flat=True)
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
        return redirect('automations_list', board_id=board_id)

    # Build rule_definition from form fields
    trigger_config = {'value': trigger_value} if trigger_value else {}
    action_config = {'value': action_value} if action_value else {}
    rule_def = _build_simple_rule_definition(
        trigger_type, trigger_config, action_type, action_config,
    )

    AutomationRule.objects.create(
        board=board,
        name=name,
        trigger_type=trigger_type,
        trigger_value=trigger_value,
        action_type=action_type,
        action_value=action_value,
        rule_definition=rule_def,
        is_active=True,
        created_by=request.user,
    )
    messages.success(request, f'Automation "{name}" created successfully.')
    return redirect('automations_list', board_id=board_id)


# ───────────────────────────────────────────────────────
# Legacy: Scheduled automation create (form POST)
# ───────────────────────────────────────────────────────

@login_required
@require_http_methods(['POST'])
def scheduled_rule_create_form(request, board_id):
    """Create a scheduled AutomationRule from the form (backward compat)."""
    import datetime as dt
    board = get_object_or_404(Board, id=board_id)

    if not can_access_board(request.user, board):
        messages.error(request, 'You do not have access to this board.')
        return redirect('automations_list', board_id=board_id)

    name = request.POST.get('sched_name', '').strip()
    schedule_type = request.POST.get('schedule_type', '')
    scheduled_time = request.POST.get('scheduled_time', '').strip()
    scheduled_day = request.POST.get('scheduled_day', '').strip() or None
    action = request.POST.get('sched_action', '')
    action_value = request.POST.get('sched_action_value', '').strip()
    notify_target = request.POST.get('notify_target', 'board_members')
    task_filter = request.POST.get('task_filter', 'all')

    valid_schedule_types = {'daily', 'weekly', 'monthly'}
    valid_actions = {'send_notification', 'set_priority'}
    valid_priorities = {'low', 'medium', 'high', 'urgent'}

    errors = []
    if not name:
        errors.append('Rule name is required.')
    if schedule_type not in valid_schedule_types:
        errors.append('Invalid schedule type.')

    parsed_time = None
    if not scheduled_time:
        errors.append('Scheduled time is required.')
    else:
        try:
            parsed_time = dt.datetime.strptime(scheduled_time, '%H:%M').time()
        except ValueError:
            errors.append('Invalid time format. Use HH:MM.')

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

    # Check scheduled rule limit
    scheduled_count = AutomationRule.objects.filter(
        board=board,
        trigger_type__startswith='scheduled_',
    ).count()
    if scheduled_count >= MAX_SCHEDULED_AUTOMATIONS_PER_BOARD:
        errors.append(f'Maximum {MAX_SCHEDULED_AUTOMATIONS_PER_BOARD} scheduled rules per board.')

    if errors:
        for e in errors:
            messages.error(request, e)
        return redirect('automations_list', board_id=board_id)

    trigger_type = f'scheduled_{schedule_type}'
    trigger_config = {'time': scheduled_time}
    if parsed_day is not None:
        trigger_config['day'] = parsed_day

    action_config = {}
    if action_value:
        action_config['value'] = action_value
    if notify_target:
        action_config['notify_target'] = notify_target
    if task_filter and task_filter != 'all':
        action_config['task_filter'] = task_filter

    rule_def = _build_simple_rule_definition(
        trigger_type, trigger_config, action, action_config,
    )

    rule = AutomationRule.objects.create(
        board=board,
        name=name,
        is_active=True,
        created_by=request.user,
        trigger_type=trigger_type,
        rule_definition=rule_def,
        action_type=action,
        action_value=action_value,
        schedule_type=schedule_type,
        scheduled_time=parsed_time,
        scheduled_day=parsed_day,
        notify_target=notify_target,
        task_filter=task_filter,
    )

    try:
        _setup_scheduled_rule(rule, trigger_type, trigger_config)
    except Exception:
        logger.exception("Failed to create PeriodicTask for rule pk=%s", rule.pk)
        messages.warning(request, f'Rule "{name}" saved but schedule could not be registered.')
        return redirect('automations_list', board_id=board_id)

    messages.success(request, f'Scheduled rule "{name}" created successfully.')
    return redirect('automations_list', board_id=board_id)


# ───────────────────────────────────────────────────────
# Legacy: Scheduled automation toggle/delete
# ───────────────────────────────────────────────────────

@login_required
@require_http_methods(['POST'])
def scheduled_rule_toggle(request, board_id, rule_id):
    """Toggle a scheduled AutomationRule."""
    board = get_object_or_404(Board, id=board_id)

    # RBAC: check board edit permission
    if not request.user.has_perm('prizmai.edit_board', board):
        messages.error(request, "You don't have permission to modify automations on this board.")
        return redirect('automations_list', board_id=board_id)

    rule = get_object_or_404(AutomationRule, id=rule_id, board=board)
    rule.is_active = not rule.is_active
    rule.save(update_fields=['is_active'])
    if rule.periodic_task:
        rule.periodic_task.enabled = rule.is_active
        rule.periodic_task.save(update_fields=['enabled'])
    status = 'enabled' if rule.is_active else 'paused'
    messages.success(request, f'Rule "{rule.name}" {status}.')
    return redirect('automations_list', board_id=board_id)


@login_required
@require_http_methods(['POST'])
def scheduled_rule_delete(request, board_id, rule_id):
    """Delete a scheduled AutomationRule."""
    board = get_object_or_404(Board, id=board_id)

    # RBAC: check board edit permission
    if not request.user.has_perm('prizmai.edit_board', board):
        messages.error(request, "You don't have permission to modify automations on this board.")
        return redirect('automations_list', board_id=board_id)

    rule = get_object_or_404(AutomationRule, id=rule_id, board=board)
    name = rule.name
    _cleanup_scheduled_rule(rule)
    rule.delete()
    messages.success(request, f'Rule "{name}" deleted.')
    return redirect('automations_list', board_id=board_id)


# ───────────────────────────────────────────────────────
# Helpers: schedule management
# ───────────────────────────────────────────────────────

SCHEDULE_TYPE_MAP = {
    'scheduled_daily': 'daily',
    'scheduled_weekly': 'weekly',
    'scheduled_monthly': 'monthly',
}


_WEEKDAY_TO_CRON = {
    'sunday': 0, 'monday': 1, 'tuesday': 2, 'wednesday': 3,
    'thursday': 4, 'friday': 5, 'saturday': 6,
}


def _weekday_to_cron(raw):
    """Map a weekly 'day' value to a cron day_of_week number (Sun=0..Sat=6).

    Accepts a weekday name ('Saturday', case-insensitive) as sent by the rule
    builder, or an int already in cron form (back-compat). Returns None if it
    can't be resolved, so the caller leaves scheduled_day untouched.
    """
    if isinstance(raw, str):
        key = raw.strip().lower()
        if key in _WEEKDAY_TO_CRON:
            return _WEEKDAY_TO_CRON[key]
    try:
        n = int(raw)
    except (ValueError, TypeError):
        return None
    return n if 0 <= n <= 6 else None


def _setup_scheduled_rule(rule, trigger_type, trigger_config):
    """Configure schedule fields and create PeriodicTask for a scheduled rule."""
    import datetime as dt
    from kanban.scheduled_automation_utils import (
        create_periodic_task_for_rule,
        delete_periodic_task_for_rule,
    )

    schedule_type = SCHEDULE_TYPE_MAP.get(trigger_type, '')
    rule.schedule_type = schedule_type

    time_str = trigger_config.get('time', '')
    if time_str:
        try:
            rule.scheduled_time = dt.datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            pass

    # Resolve the day restriction into the cron value create_periodic_task_for_rule
    # expects in rule.scheduled_day. The builder sends weekly as a weekday *name*
    # ('Saturday') under 'day', and monthly as an int under 'day_of_month' — so the
    # old int(trigger_config['day']) silently dropped both, leaving dow/dom='*' and
    # making weekly/monthly rules fire every day.
    if schedule_type == 'weekly':
        raw = trigger_config.get('day')
        rule.scheduled_day = _weekday_to_cron(raw)
    elif schedule_type == 'monthly':
        raw = trigger_config.get('day_of_month', trigger_config.get('day'))
        try:
            rule.scheduled_day = int(raw)
        except (ValueError, TypeError):
            pass

    rule.save(update_fields=['schedule_type', 'scheduled_time', 'scheduled_day'])

    # Clean up old PeriodicTask if exists, then create new one
    if rule.periodic_task:
        delete_periodic_task_for_rule(rule)
    create_periodic_task_for_rule(rule)


def _cleanup_scheduled_rule(rule):
    """Remove PeriodicTask and reset schedule fields."""
    from kanban.scheduled_automation_utils import delete_periodic_task_for_rule
    if rule.periodic_task:
        delete_periodic_task_for_rule(rule)
    rule.schedule_type = ''
    rule.scheduled_time = None
    rule.scheduled_day = None
    rule.save(update_fields=['schedule_type', 'scheduled_time', 'scheduled_day'])


# ───────────────────────────────────────────────────────
# Backward compatibility aliases
# ───────────────────────────────────────────────────────

# The old URL name 'automations_list' maps here
automations_list = automations_page


def automation_delete(request, board_id, automation_id):
    """Legacy wrapper — routes automation_id to rule_delete(rule_id)."""
    return rule_delete(request, board_id, rule_id=automation_id)


def automation_toggle(request, board_id, automation_id):
    """Legacy wrapper — routes automation_id to rule_toggle(rule_id)."""
    return rule_toggle(request, board_id, rule_id=automation_id)


def automation_activate_template(request, board_id, template_id):
    """Legacy wrapper — routes string template_id to template_use(int)."""
    try:
        tid = int(template_id)
    except (ValueError, TypeError):
        from django.http import Http404
        raise Http404("Invalid template ID")
    return template_use(request, board_id, template_id=tid)
