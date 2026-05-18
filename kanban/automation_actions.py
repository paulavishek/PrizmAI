"""
Automation Action Registry
==========================

This module holds every action handler the automation engine can execute.
Handlers are registered with the ``@register_action`` decorator and looked up
by the dispatcher in ``kanban/signals.py`` (function ``_execute_action_flat``).

Splitting handlers out of the dispatcher gives us:
    1. Independent unit testability per action.
    2. A single source of truth for "what does action X do?" — read one file.
    3. Future phases add an ``@register_action`` + a function; no dispatcher
       changes.

------------------------------------------------------------------------------
TARGET-RESOLUTION CONTRACT
------------------------------------------------------------------------------

(This contract is shared with ``automation_conditions.py``; the full text lives
there. The summary below covers the parts an action handler must care about.)

Every trigger receiver resolves the event to a ``TriggerTarget``:

    target_board : Board   (REQUIRED, non-null)
    target_task  : Task | None
    source       : Any     (original source object)
    source_type  : str

Handlers self-declare what they need with ``requires=``:

    requires='task'   → handler writes/reads task fields. Skipped when
                        target.target_task is None. (All Phase 1a handlers.)

    requires='board'  → handler operates on board-level state. Satisfied by
                        ANY target since every target carries a board.
                        Task-level triggers can still execute 'board' actions
                        — e.g. "when task created, generate status report
                        for board." NEVER skips on target availability.

                        IMPORTANT SEMANTIC: 'board' does NOT mean "only runs
                        on board-only triggers." It means "operates on
                        board-level state and is happy with any target."

    requires='either' → handler can target whichever is present. Picks
                        target_task when available, falls back to target_board.

Skip protocol — when ``requires`` cannot be satisfied:
    * The dispatcher does NOT call the handler.
    * The dispatcher raises ``_ActionSkip`` with a structured reason:
        f"Action '{name}' requires a {requires} target but trigger
         '{source_type}' resolved only {available}"
    * ``run_board_automations`` catches this and writes
      ``AutomationLog.outcome='skipped'`` with the reason.

When the handler runs but cannot complete (no recipients, demo board, etc.):
    * The handler raises ``_ActionNoOp(reason)`` — same as the existing
      pre-refactor behaviour.
    * The dispatcher records outcome='skipped' with that reason.

When the handler runs and crashes unexpectedly:
    * The handler raises any other exception.
    * The dispatcher records the error on AutomationLog.error_detail and the
      rule's overall outcome becomes 'failed'.

Phase 1a establishes this contract; every migrated handler uses
``requires='task'`` (the implicit pre-refactor default). Phase 2 starts using
``'board'``; Phase 5 introduces non-task source types.
"""

from typing import Any, Callable, Dict, Tuple


# ─── Exceptions shared with the dispatcher ───────────────────────────────────


class _ActionNoOp(Exception):
    """Raised by an action handler when it could not be applied for a non-error
    reason (e.g. send_notification resolved to zero recipients because the task
    has no assignee). The rule itself ran correctly — the action simply had
    nothing to do — so the audit log marks the outcome as 'skipped' rather
    than 'failed'.
    """


class _ActionSkip(Exception):
    """Raised by the dispatcher (not by handlers) when an action's ``requires``
    is not satisfied by the trigger's target. Distinguishes a target-shape skip
    from a "no recipients" no-op so logs can differentiate.
    """


# ─── Registry ────────────────────────────────────────────────────────────────

# Maps action_type → (handler_fn, requires)
# Handler signature: handler(target: TriggerTarget, rule, action_dict) -> None
ACTION_HANDLERS: Dict[str, Tuple[Callable, str]] = {}


def register_action(name: str, requires: str = 'task'):
    """Decorator: register an action handler under ``name``.

    ``requires`` is one of 'task' | 'board' | 'either'. See the contract block
    at the top of this file for semantics.
    """
    if requires not in ('task', 'board', 'either'):
        raise ValueError(f"register_action: invalid requires={requires!r}")

    def deco(fn):
        ACTION_HANDLERS[name] = (fn, requires)
        return fn
    return deco


def execute(action: dict, target, rule) -> None:
    """Dispatch entry point.

    Looks up the handler for ``action['type']``, checks its ``requires``
    against the target, and either calls the handler or raises ``_ActionSkip``
    with a descriptive reason that the caller logs.
    """
    action_type = action.get('type', '')
    entry = ACTION_HANDLERS.get(action_type)
    if entry is None:
        raise ValueError(f"Unknown action type: {action_type!r}")
    handler, requires = entry

    if requires == 'task' and target.target_task is None:
        raise _ActionSkip(
            f"Action '{action_type}' requires a task target but trigger "
            f"'{target.source_type}' resolved only a board"
        )

    handler(target, rule, action)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _substitute_vars(template, task):
    """Replace {task_title}, {board_name}, {due_date}, {assignee} in a string."""
    if task is None:
        return template
    board = task.column.board if task.column_id else None
    result = template
    result = result.replace('{task_title}', task.title or '')
    result = result.replace('{board_name}', board.name if board else '')
    result = result.replace('{task_id}', str(task.pk))
    if task.due_date:
        result = result.replace('{due_date}', task.due_date.strftime('%Y-%m-%d'))
    else:
        result = result.replace('{due_date}', 'not set')
    if task.assigned_to:
        assignee_name = task.assigned_to.get_full_name() or task.assigned_to.username
    else:
        assignee_name = 'unassigned'
    result = result.replace('{assignee}', assignee_name)
    return result


def _send_notification(task, rule, target_key, message=''):
    """Send Notification objects for a send_notification action.

    Raises _ActionNoOp when the action cannot deliver to anyone (no assignee,
    demo board, etc.) so the audit log can record a 'skipped' outcome with a
    clear reason rather than a misleading 'success'.
    """
    from messaging.models import Notification
    from django.contrib.auth.models import User as AuthUser
    from django.urls import reverse

    board = task.column.board if task.column_id else None
    if not board:
        raise _ActionNoOp('task has no board')

    if getattr(board, 'is_official_demo_board', False):
        raise _ActionNoOp('demo board — notifications suppressed')

    sender = rule.created_by or (board.created_by if board else None)
    if not sender:
        raise _ActionNoOp('no sender (rule has no creator and board has no owner)')

    try:
        task_url = reverse('task_detail', args=[task.id])
    except Exception:
        task_url = None

    target_lower = (target_key or '').lower()
    recipients = []

    if target_lower == 'task_assignee':
        if task.assigned_to:
            recipients = [task.assigned_to]
    elif target_lower == 'all_board_members':
        recipients = list(AuthUser.objects.filter(board_memberships__board=board))
        if board.created_by and board.created_by not in recipients:
            recipients.append(board.created_by)
    elif target_lower == 'rule_creator':
        if rule.created_by:
            recipients = [rule.created_by]
    else:
        try:
            u = AuthUser.objects.get(pk=int(target_key))
            recipients = [u]
        except (AuthUser.DoesNotExist, ValueError, TypeError):
            pass

    if not recipients:
        if target_lower == 'task_assignee':
            raise _ActionNoOp('task has no assignee')
        raise _ActionNoOp(f'no recipients resolved for target {target_key!r}')

    raw = message or (
        f'Automation "{rule.name}" was triggered for task "{{task_title}}" '
        f'on board "{{board_name}}".'
    )
    text = _substitute_vars(raw, task)
    title = f'{rule.name} — {task.title}'[:255]

    for recipient in recipients:
        Notification.objects.create(
            recipient=recipient,
            sender=sender,
            notification_type='ACTIVITY',
            title=title,
            text=text,
            action_url=task_url,
            ai_summary=title[:200],
        )


# ─── Phase 1a — Migrated action handlers (all requires='task') ───────────────


# Defensive defaults applied when a rule was saved with an empty target field
# (legacy Unified Rule Builder bug — the visually-selected first dropdown
# option never fired a change event so state.target stayed empty).
_ACTION_DEFAULT_TARGETS = {
    'send_notification': 'task_assignee',
    'assign_to_user':    'task_assignee',
    'set_priority':      'urgent',
    'set_due_date':      'today',
}


def _resolve_target(action):
    """Return the effective ``target`` for an action dict, applying the legacy
    default-target fallback when needed.
    """
    target = action.get('target') or ''
    if not target:
        target = _ACTION_DEFAULT_TARGETS.get(action.get('type', ''), '')
    return target


_VALID_PRIORITIES = {'low', 'medium', 'high', 'urgent'}


@register_action('set_priority', requires='task')
def _act_set_priority(target, rule, action):
    from kanban.models import Task as TaskModel
    task = target.target_task
    prio = _resolve_target(action).lower()
    if prio in _VALID_PRIORITIES:
        TaskModel.objects.filter(pk=task.pk).update(priority=prio)


@register_action('add_label', requires='task')
def _act_add_label(target, rule, action):
    from kanban.models import TaskLabel
    task = target.target_task
    board = target.target_board
    name = _resolve_target(action)
    if board and name:
        label = TaskLabel.objects.filter(board=board, name__iexact=name).first()
        if label:
            task.labels.add(label)


@register_action('remove_label', requires='task')
def _act_remove_label(target, rule, action):
    from kanban.models import TaskLabel
    task = target.target_task
    board = target.target_board
    name = _resolve_target(action)
    if board and name:
        label = TaskLabel.objects.filter(board=board, name__iexact=name).first()
        if label:
            task.labels.remove(label)


@register_action('assign_to_user', requires='task')
def _act_assign_to_user(target, rule, action):
    from django.contrib.auth.models import User as AuthUser
    from kanban.models import Task as TaskModel
    task = target.target_task
    message = action.get('message') or ''
    target_value = _resolve_target(action)
    target_lower = target_value.lower()

    if target_lower == 'task_assignee':
        return  # already assigned — no-op
    if target_lower == 'rule_creator':
        if rule.created_by:
            TaskModel.objects.filter(pk=task.pk).update(assigned_to=rule.created_by)
        return
    if target_lower == 'all_board_members':
        # Assign-to-everyone is not meaningful for a single assignee field —
        # fall back to broadcasting a notification instead.
        _send_notification(task, rule, 'all_board_members', message)
        return

    try:
        user = AuthUser.objects.get(pk=int(target_value))
        TaskModel.objects.filter(pk=task.pk).update(assigned_to=user)
    except (AuthUser.DoesNotExist, ValueError, TypeError):
        raise ValueError(f"assign_to_user: user with id '{target_value}' not found")


@register_action('move_to_column', requires='task')
def _act_move_to_column(target, rule, action):
    from kanban.models import Column, Task as TaskModel
    task = target.target_task
    board = target.target_board
    name = _resolve_target(action)
    if board and name:
        col = Column.objects.filter(board=board, name__icontains=name).exclude(
            pk=task.column_id
        ).order_by('position').first()
        if col:
            TaskModel.objects.filter(pk=task.pk).update(column=col)
        else:
            raise ValueError(f"move_to_column: no column matching '{name}' found on board")


@register_action('set_due_date', requires='task')
def _act_set_due_date(target, rule, action):
    from django.utils import timezone as tz
    from kanban.models import Task as TaskModel
    task = target.target_task
    value = _resolve_target(action)
    DUE_DATE_MAP = {
        'today': 0, 'in_2_days': 2, 'in_7_days': 7,
        'in_14_days': 14, 'in_30_days': 30,
    }
    days = DUE_DATE_MAP.get(value.lower())
    if days is None:
        try:
            days = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"set_due_date: invalid target '{value}'")
    new_due = tz.now().date() + tz.timedelta(days=days)
    TaskModel.objects.filter(pk=task.pk).update(due_date=new_due)


@register_action('close_task', requires='task')
def _act_close_task(target, rule, action):
    from kanban.models import Task as TaskModel
    TaskModel.objects.filter(pk=target.target_task.pk).update(progress=100)


@register_action('send_notification', requires='task')
def _act_send_notification(target, rule, action):
    _send_notification(
        target.target_task, rule,
        _resolve_target(action),
        action.get('message') or '',
    )


@register_action('post_comment', requires='task')
def _act_post_comment(target, rule, action):
    from kanban.models import Comment
    task = target.target_task
    if not rule.created_by:
        raise ValueError("post_comment: rule has no creator, cannot post comment")
    message = action.get('message') or f'Automated comment by rule "{rule.name}".'
    text = _substitute_vars(message, task)
    Comment.objects.create(task=task, user=rule.created_by, content=text)


@register_action('log_time_entry', requires='task')
def _act_log_time_entry(target, rule, action):
    from kanban.budget_models import TimeEntry
    task = target.target_task
    value = _resolve_target(action)
    user = rule.created_by or task.assigned_to
    if not user:
        raise ValueError(
            "log_time_entry: no user available "
            "(rule has no creator and task has no assignee)"
        )
    try:
        hours = float(value or 1)
    except (TypeError, ValueError):
        raise ValueError(f"log_time_entry: invalid hours value '{value}'")
    TimeEntry.objects.create(
        task=task,
        user=user,
        hours_spent=hours,
        description=f'Auto-logged by automation "{rule.name}"',
    )


# ─── Phase 1b — Core task field actions ──────────────────────────────────────


@register_action('set_description', requires='task')
def _act_set_description(target, rule, action):
    from kanban.models import Task as TaskModel
    task = target.target_task
    template = action.get('message') or _resolve_target(action) or ''
    new_desc = _substitute_vars(template, task)
    TaskModel.objects.filter(pk=task.pk).update(description=new_desc)


@register_action('append_to_description', requires='task')
def _act_append_to_description(target, rule, action):
    from kanban.models import Task as TaskModel
    task = target.target_task
    template = action.get('message') or _resolve_target(action) or ''
    addition = _substitute_vars(template, task)
    current = task.description or ''
    sep = '\n' if current else ''
    TaskModel.objects.filter(pk=task.pk).update(description=current + sep + addition)


@register_action('set_progress', requires='task')
def _act_set_progress(target, rule, action):
    from kanban.models import Task as TaskModel
    value = _resolve_target(action)
    try:
        pct = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"set_progress: invalid value '{value}'")
    pct = max(0, min(100, pct))
    TaskModel.objects.filter(pk=target.target_task.pk).update(progress=pct)


@register_action('set_start_date', requires='task')
def _act_set_start_date(target, rule, action):
    from django.utils import timezone as tz
    from kanban.models import Task as TaskModel
    value = _resolve_target(action)
    DUE_DATE_MAP = {
        'today': 0, 'in_2_days': 2, 'in_7_days': 7,
        'in_14_days': 14, 'in_30_days': 30,
    }
    days = DUE_DATE_MAP.get(value.lower())
    if days is None:
        try:
            days = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"set_start_date: invalid target '{value}'")
    new_start = tz.now().date() + tz.timedelta(days=days)
    TaskModel.objects.filter(pk=target.target_task.pk).update(start_date=new_start)


@register_action('clear_due_date', requires='task')
def _act_clear_due_date(target, rule, action):
    from kanban.models import Task as TaskModel
    TaskModel.objects.filter(pk=target.target_task.pk).update(due_date=None)


@register_action('clear_assignee', requires='task')
def _act_clear_assignee(target, rule, action):
    from kanban.models import Task as TaskModel
    TaskModel.objects.filter(pk=target.target_task.pk).update(assigned_to=None)


@register_action('add_checklist_item', requires='task')
def _act_add_checklist_item(target, rule, action):
    from kanban.models import ChecklistItem
    task = target.target_task
    title = (action.get('message') or _resolve_target(action) or '').strip()
    if not title:
        raise ValueError("add_checklist_item: title is empty")
    title = _substitute_vars(title, task)
    last_position = (
        ChecklistItem.objects.filter(task=task)
        .order_by('-position').values_list('position', flat=True).first()
    )
    next_pos = (last_position or 0) + 1
    ChecklistItem.objects.create(
        task=task,
        title=title[:200],
        position=next_pos,
        source='ai_generated',
    )


@register_action('add_subtask', requires='task')
def _act_add_subtask(target, rule, action):
    from django.utils import timezone as tz
    from kanban.models import Task as TaskModel
    task = target.target_task
    title = (action.get('message') or _resolve_target(action) or '').strip()
    if not title:
        raise ValueError("add_subtask: title is empty")
    title = _substitute_vars(title, task)
    # Place the subtask in the same column as the parent so the kanban view
    # has somewhere to render it; user can move it after.
    due = None
    raw_offset = action.get('due_offset_days')
    if raw_offset is not None:
        try:
            due = tz.now().date() + tz.timedelta(days=int(raw_offset))
        except (TypeError, ValueError):
            due = None
    TaskModel.objects.create(
        title=title[:200],
        column=task.column,
        parent_task=task,
        due_date=due,
        created_by=rule.created_by,
    )


# Note: archive_task was planned for Phase 1b but Task has no is_archived field
# in the current schema. Use close_task (sets progress=100) or move_to_column
# with a "Done"/"Archive" column instead. Revisit when a soft-archive field
# is added to Task.


# ─── Phase 2 — Risk & AI prediction actions ──────────────────────────────────


_VALID_RISK_LEVELS = {'low', 'medium', 'high', 'critical'}


@register_action('set_risk_level', requires='task')
def _act_set_risk_level(target, rule, action):
    from kanban.models import Task as TaskModel
    rl = _resolve_target(action).lower()
    if rl not in _VALID_RISK_LEVELS:
        raise ValueError(f"set_risk_level: invalid level '{rl}'")
    TaskModel.objects.filter(pk=target.target_task.pk).update(risk_level=rl)


@register_action('request_ai_analysis', requires='task')
def _act_request_ai_analysis(target, rule, action):
    """Schedules an AI analysis for the task. We mark last_ai_analysis=None to
    signal "needs analysis" — the next time the AI service runs against the
    task it will refresh ai_summary, ai_recommendations, etc. Doesn't block
    rule execution on the AI call itself.
    """
    from kanban.models import Task as TaskModel
    TaskModel.objects.filter(pk=target.target_task.pk).update(last_ai_analysis=None)


@register_action('flag_for_review', requires='task')
def _act_flag_for_review(target, rule, action):
    from kanban.models import TaskLabel, Comment
    task = target.target_task
    board = target.target_board
    if board:
        label, _ = TaskLabel.objects.get_or_create(
            board=board, name='Needs Review',
            defaults={'color': '#ffc107'},
        )
        task.labels.add(label)
    if rule.created_by:
        reason = action.get('message') or f'Flagged by automation "{rule.name}"'
        reason = _substitute_vars(reason, task)
        Comment.objects.create(task=task, user=rule.created_by, content=reason)


@register_action('add_risk_indicator', requires='task')
def _act_add_risk_indicator(target, rule, action):
    from kanban.models import Task as TaskModel
    task = target.target_task
    value = _resolve_target(action) or action.get('message') or ''
    if not value:
        raise ValueError("add_risk_indicator: empty indicator")
    indicators = list(task.risk_indicators or [])
    indicators.append(_substitute_vars(value, task))
    TaskModel.objects.filter(pk=task.pk).update(risk_indicators=indicators)


@register_action('add_mitigation_strategy', requires='task')
def _act_add_mitigation_strategy(target, rule, action):
    """Task has no dedicated mitigation_strategies field on the current schema
    so we store the strategy as a tagged comment on the task. The Risk
    Assessment UI shows comments tagged 'mitigation:' separately.
    """
    from kanban.models import Comment
    task = target.target_task
    value = _resolve_target(action) or action.get('message') or ''
    if not value:
        raise ValueError("add_mitigation_strategy: empty strategy")
    if not rule.created_by:
        raise ValueError("add_mitigation_strategy: rule has no creator")
    content = 'mitigation: ' + _substitute_vars(value, task)
    Comment.objects.create(task=task, user=rule.created_by, content=content)


# ─── Phase 3 — Hierarchy & Dependency actions ────────────────────────────────


@register_action('cascade_due_date', requires='task')
def _act_cascade_due_date(target, rule, action):
    """Push all direct subtasks' due dates by N days, or match the parent's
    due date if value is 'match_parent'.
    """
    from django.utils import timezone as tz
    from kanban.models import Task as TaskModel
    task = target.target_task
    value = _resolve_target(action) or 'match_parent'
    subtasks = TaskModel.objects.filter(parent_task=task)
    if value == 'match_parent':
        if not task.due_date:
            raise _ActionNoOp('parent has no due date to cascade')
        subtasks.update(due_date=task.due_date)
    else:
        try:
            days = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"cascade_due_date: invalid value '{value}'")
        # Shift each subtask's due date individually
        for sub in subtasks:
            if sub.due_date:
                new_due = sub.due_date + tz.timedelta(days=days)
                TaskModel.objects.filter(pk=sub.pk).update(due_date=new_due)


@register_action('cascade_priority', requires='task')
def _act_cascade_priority(target, rule, action):
    from kanban.models import Task as TaskModel
    task = target.target_task
    TaskModel.objects.filter(parent_task=task).update(priority=task.priority)


@register_action('assign_subtasks_to', requires='task')
def _act_assign_subtasks_to(target, rule, action):
    from django.contrib.auth.models import User as AuthUser
    from kanban.models import Task as TaskModel
    task = target.target_task
    tgt = _resolve_target(action)
    if tgt == 'rule_creator':
        user = rule.created_by
    elif tgt == 'task_assignee':
        user = task.assigned_to
    else:
        try:
            user = AuthUser.objects.get(pk=int(tgt))
        except (AuthUser.DoesNotExist, ValueError, TypeError):
            raise ValueError(f"assign_subtasks_to: user '{tgt}' not found")
    if not user:
        raise _ActionNoOp('no user to assign subtasks to')
    TaskModel.objects.filter(parent_task=task).update(assigned_to=user)


@register_action('complete_parent_if_all_subtasks_done', requires='task')
def _act_complete_parent_if_all_subtasks_done(target, rule, action):
    from kanban.models import Task as TaskModel
    task = target.target_task
    parent = task.parent_task
    if not parent:
        raise _ActionNoOp('task has no parent')
    siblings = TaskModel.objects.filter(parent_task=parent)
    if siblings.filter(progress__lt=100).exclude(pk=task.pk).exists():
        raise _ActionNoOp('not all sibling subtasks are complete')
    TaskModel.objects.filter(pk=parent.pk).update(progress=100)


@register_action('notify_blocked_tasks', requires='task')
def _act_notify_blocked_tasks(target, rule, action):
    """For every task that depends on this one, send its assignee a notification."""
    from kanban.models import Task as TaskModel
    task = target.target_task
    message = action.get('message') or (
        f'A blocking dependency on task "{{task_title}}" updated.'
    )
    blocked = TaskModel.objects.filter(dependencies=task)
    sent = 0
    for blocked_task in blocked:
        if not blocked_task.assigned_to:
            continue
        try:
            _send_notification(blocked_task, rule, str(blocked_task.assigned_to_id), message)
            sent += 1
        except _ActionNoOp:
            continue
    if sent == 0:
        raise _ActionNoOp('no blocked tasks with assignees')


@register_action('auto_check_checklist', requires='task')
def _act_auto_check_checklist(target, rule, action):
    from django.utils import timezone as tz
    from kanban.models import ChecklistItem
    task = target.target_task
    needle = _resolve_target(action) or action.get('message') or ''
    if not needle:
        raise ValueError('auto_check_checklist: which checklist item title?')
    item = ChecklistItem.objects.filter(
        task=task, title__icontains=needle, is_completed=False,
    ).first()
    if not item:
        raise _ActionNoOp(f'no unchecked checklist item matching {needle!r}')
    ChecklistItem.objects.filter(pk=item.pk).update(
        is_completed=True,
        completed_at=tz.now(),
        completed_by=rule.created_by,
    )


# ─── Phase 4 — Resource, Cost & Workload actions ─────────────────────────────


@register_action('set_workload_impact', requires='task')
def _act_set_workload_impact(target, rule, action):
    from kanban.models import Task as TaskModel
    valid = {'low', 'medium', 'high', 'critical'}
    value = _resolve_target(action).lower()
    if value not in valid:
        raise ValueError(f"set_workload_impact: invalid value '{value}'")
    TaskModel.objects.filter(pk=target.target_task.pk).update(workload_impact=value)


@register_action('set_estimated_hours', requires='task')
def _act_set_estimated_hours(target, rule, action):
    from kanban.budget_models import TaskCost
    value = _resolve_target(action)
    try:
        hours = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"set_estimated_hours: invalid value '{value}'")
    cost, _ = TaskCost.objects.get_or_create(task=target.target_task)
    TaskCost.objects.filter(pk=cost.pk).update(estimated_hours=hours)


@register_action('set_estimated_cost', requires='task')
def _act_set_estimated_cost(target, rule, action):
    from kanban.budget_models import TaskCost
    value = _resolve_target(action)
    try:
        cost_val = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"set_estimated_cost: invalid value '{value}'")
    cost, _ = TaskCost.objects.get_or_create(task=target.target_task)
    TaskCost.objects.filter(pk=cost.pk).update(estimated_cost=cost_val)


@register_action('assign_to_best_skill_match', requires='task')
def _act_assign_to_best_skill_match(target, rule, action):
    """Assign to the board member whose UserProfile.skills overlap most with
    the task's required_skills. Falls back to a notification on the rule's
    creator if no match can be computed.
    """
    from django.contrib.auth.models import User as AuthUser
    from kanban.models import Task as TaskModel
    task = target.target_task
    board = target.target_board
    required = {str(s).lower() for s in (task.required_skills or [])}
    if not required or not board:
        raise _ActionNoOp('no required_skills or board to match against')

    members = AuthUser.objects.filter(board_memberships__board=board).select_related('profile')
    best_user = None
    best_score = -1
    for m in members:
        profile_skills = []
        if hasattr(m, 'profile') and getattr(m.profile, 'skills', None):
            profile_skills = m.profile.skills if isinstance(m.profile.skills, list) else []
        overlap = len(required & {str(s).lower() for s in profile_skills})
        if overlap > best_score:
            best_score = overlap
            best_user = m
    if not best_user or best_score <= 0:
        raise _ActionNoOp('no member with overlapping skills')
    TaskModel.objects.filter(pk=task.pk).update(assigned_to=best_user)


@register_action('assign_to_lightest_workload', requires='task')
def _act_assign_to_lightest_workload(target, rule, action):
    from django.contrib.auth.models import User as AuthUser
    from kanban.models import Task as TaskModel
    task = target.target_task
    board = target.target_board
    if not board:
        raise _ActionNoOp('task has no board')
    members = list(
        AuthUser.objects.filter(board_memberships__board=board)
    )
    if not members:
        raise _ActionNoOp('board has no members')
    lightest = min(
        members,
        key=lambda u: TaskModel.objects.filter(
            assigned_to=u,
        ).exclude(progress=100).count(),
    )
    TaskModel.objects.filter(pk=task.pk).update(assigned_to=lightest)


@register_action('add_required_skill', requires='task')
def _act_add_required_skill(target, rule, action):
    from kanban.models import Task as TaskModel
    task = target.target_task
    value = _resolve_target(action) or action.get('message') or ''
    if not value:
        raise ValueError("add_required_skill: empty skill name")
    skills = list(task.required_skills or [])
    if value not in skills:
        skills.append(value)
    TaskModel.objects.filter(pk=task.pk).update(required_skills=skills)


@register_action('escalate_to_owner', requires='task')
def _act_escalate_to_owner(target, rule, action):
    """Send a notification to the board owner."""
    task = target.target_task
    board = target.target_board
    if not board or not board.created_by:
        raise _ActionNoOp('board has no owner')
    message = action.get('message') or (
        f'Automation "{rule.name}" escalated task "{{task_title}}" to you.'
    )
    _send_notification(task, rule, str(board.created_by.pk), message)


# ─── Phase 5 — AI Tool integration actions (mix of 'task' and 'either') ──────


@register_action('acknowledge_coach_suggestion', requires='either')
def _act_acknowledge_coach_suggestion(target, rule, action):
    """Mark CoachingSuggestion(s) as acknowledged. If the trigger source was a
    specific CoachingSuggestion, acknowledge it. Otherwise acknowledge all
    active suggestions for the target's board.
    """
    from django.utils import timezone as tz
    from kanban.coach_models import CoachingSuggestion
    if target.source_type == 'coach' and target.source:
        CoachingSuggestion.objects.filter(pk=target.source.pk).update(
            status='acknowledged',
            acknowledged_by=rule.created_by,
            acknowledged_at=tz.now(),
        )
        return
    # Fall-through: acknowledge all active suggestions on the board
    updated = CoachingSuggestion.objects.filter(
        board=target.target_board, status='active',
    ).update(
        status='acknowledged',
        acknowledged_by=rule.created_by,
        acknowledged_at=tz.now(),
    )
    if updated == 0:
        raise _ActionNoOp('no active coach suggestions to acknowledge')


@register_action('resolve_conflict', requires='either')
def _act_resolve_conflict(target, rule, action):
    """Mark a ConflictDetection resolved. If the trigger source was a specific
    conflict, resolve that one; otherwise resolve all active conflicts on the
    board.
    """
    from django.utils import timezone as tz
    from kanban.conflict_models import ConflictDetection
    if target.source_type == 'conflict' and target.source:
        ConflictDetection.objects.filter(pk=target.source.pk).update(
            status='resolved',
            resolved_at=tz.now(),
            resolution_feedback=action.get('message') or 'Auto-resolved by automation',
        )
        return
    updated = ConflictDetection.objects.filter(
        board=target.target_board, status='active',
    ).update(
        status='resolved',
        resolved_at=tz.now(),
        resolution_feedback=action.get('message') or 'Auto-resolved by automation',
    )
    if updated == 0:
        raise _ActionNoOp('no active conflicts to resolve')


@register_action('promote_discovery_idea', requires='either')
def _act_promote_discovery_idea(target, rule, action):
    """Promote a DiscoveryIdea to an approved state. Real "promotion to task"
    flow requires picking a board/column UI side; this action marks the idea
    as approved and ready to promote, which the Discovery UI then renders
    as actionable.
    """
    from django.utils import timezone as tz
    from kanban.discovery_models import DiscoveryIdea
    if target.source_type != 'discovery' or not target.source:
        raise _ActionSkip(
            "promote_discovery_idea requires a 'discovery' trigger source"
        )
    DiscoveryIdea.objects.filter(pk=target.source.pk).update(
        stage='approved',
        promoted_by=rule.created_by,
        promoted_at=tz.now(),
    )


@register_action('apply_stress_test_vaccine', requires='board')
def _act_apply_stress_test_vaccine(target, rule, action):
    """Mark the most recent stress-test vaccine for this board as applied.
    No-op when no stress-test data is available."""
    try:
        from kanban.stress_test_models import StressTestVaccine
    except Exception:
        raise _ActionNoOp('stress test module not available')
    latest = StressTestVaccine.objects.filter(
        session__board=target.target_board, is_applied=False,
    ).order_by('-id').first()
    if not latest:
        raise _ActionNoOp('no unapplied vaccines on this board')
    StressTestVaccine.objects.filter(pk=latest.pk).update(is_applied=True)


@register_action('create_memory_node', requires='either')
def _act_create_memory_node(target, rule, action):
    """Capture a MemoryNode in the knowledge graph."""
    try:
        from knowledge_graph.models import MemoryNode
    except Exception:
        raise _ActionNoOp('knowledge_graph module not available')
    board = target.target_board
    node_type = (_resolve_target(action) or 'manual_log').lower()
    content = action.get('message') or f'Captured by rule "{rule.name}"'
    if target.target_task:
        content = _substitute_vars(content, target.target_task)
    MemoryNode.objects.create(
        board=board,
        node_type=node_type,
        title=f'Auto-captured: {rule.name}'[:200],
        content=content,
        created_by=rule.created_by,
        is_auto_captured=True,
        source_object_type=target.source_type,
        source_object_id=getattr(target.source, 'pk', None) if target.source else None,
    )


@register_action('generate_status_report', requires='board')
def _act_generate_status_report(target, rule, action):
    """Mark that a status report is requested for this board. Real generation
    happens asynchronously via the PrizmBrief service; here we just write a
    queued record so the next sweep picks it up.
    """
    try:
        from kanban.prizmbrief_models import SavedBrief
    except Exception:
        raise _ActionNoOp('prizmbrief module not available')
    audience = (_resolve_target(action) or 'team').lower()
    SavedBrief.objects.create(
        board=target.target_board,
        created_by=rule.created_by,
        audience=audience,
        purpose='status',
        mode='narrative',
        slides_json=[],
        full_text='Queued by automation — pending generation',
    )


@register_action('add_stakeholder_engagement', requires='either')
def _act_add_stakeholder_engagement(target, rule, action):
    """Log a StakeholderEngagementRecord for each active stakeholder on the
    board. Useful for "this milestone was reached → log engagement" rules.
    """
    try:
        from kanban.stakeholder_models import (
            ProjectStakeholder, StakeholderEngagementRecord,
        )
    except Exception:
        raise _ActionNoOp('stakeholder module not available')
    board = target.target_board
    stakeholders = ProjectStakeholder.objects.filter(board=board, is_active=True)
    notes = action.get('message') or f'Logged by automation "{rule.name}"'
    if target.target_task:
        notes = _substitute_vars(notes, target.target_task)
    created = 0
    for sh in stakeholders:
        try:
            StakeholderEngagementRecord.objects.create(
                stakeholder=sh,
                interaction_type='automated',
                notes=notes,
                logged_by=rule.created_by,
            )
            created += 1
        except Exception:
            continue
    if created == 0:
        raise _ActionNoOp('no active stakeholders on this board')


# ─── Phase 6 — Communications & Memory actions ───────────────────────────────


@register_action('notify_stakeholders', requires='board')
def _act_notify_stakeholders(target, rule, action):
    """Send a notification to every active stakeholder on the board who has a
    User account linked via email."""
    from django.contrib.auth.models import User as AuthUser
    from messaging.models import Notification
    try:
        from kanban.stakeholder_models import ProjectStakeholder
    except Exception:
        raise _ActionNoOp('stakeholder module not available')

    board = target.target_board
    if getattr(board, 'is_official_demo_board', False):
        raise _ActionNoOp('demo board — notifications suppressed')

    sender = rule.created_by or board.created_by
    if not sender:
        raise _ActionNoOp('no sender (rule has no creator and board has no owner)')

    stakeholders = ProjectStakeholder.objects.filter(board=board, is_active=True)
    raw = action.get('message') or f'Update from automation "{rule.name}" on board "{board.name}".'
    task = target.target_task
    if task is not None:
        raw = _substitute_vars(raw, task)
    sent = 0
    for sh in stakeholders:
        if not sh.email:
            continue
        user = AuthUser.objects.filter(email=sh.email).first()
        if not user:
            continue
        Notification.objects.create(
            recipient=user, sender=sender,
            notification_type='ACTIVITY',
            title=f'Stakeholder update — {board.name}'[:255],
            text=raw, ai_summary=raw[:200],
        )
        sent += 1
    if sent == 0:
        raise _ActionNoOp('no stakeholders with linked user accounts')


@register_action('mention_users_in_comment', requires='task')
def _act_mention_users_in_comment(target, rule, action):
    """Post a comment that @-mentions specific users. The `message` field
    should contain the comment text with @username tokens — the messaging
    app handles the actual mention notification on save.
    """
    from kanban.models import Comment
    task = target.target_task
    if not rule.created_by:
        raise ValueError("mention_users_in_comment: rule has no creator")
    text = action.get('message') or ''
    if not text:
        raise ValueError("mention_users_in_comment: empty message")
    text = _substitute_vars(text, task)
    Comment.objects.create(task=task, user=rule.created_by, content=text)


@register_action('start_task_thread', requires='task')
def _act_start_task_thread(target, rule, action):
    """Create a TaskThreadComment to seed a discussion on the task."""
    try:
        from messaging.models import TaskThreadComment
    except Exception:
        # Fall back to a plain Comment when the thread model isn't available.
        from kanban.models import Comment
        task = target.target_task
        Comment.objects.create(
            task=task, user=rule.created_by,
            content=action.get('message') or f'[Auto-thread] from rule "{rule.name}"',
        )
        return

    task = target.target_task
    if not rule.created_by:
        raise ValueError("start_task_thread: rule has no creator")
    content = action.get('message') or f'[Auto-thread] from rule "{rule.name}"'
    content = _substitute_vars(content, task)
    try:
        TaskThreadComment.objects.create(
            task=task, author=rule.created_by, content=content,
        )
    except Exception:
        # Field names vary across messaging app revisions; fall back to Comment.
        from kanban.models import Comment
        Comment.objects.create(task=task, user=rule.created_by, content=content)


@register_action('link_wiki_page', requires='task')
def _act_link_wiki_page(target, rule, action):
    """Link an existing WikiPage to the task by slug. Stored as a comment
    pointing at the wiki page since Task→Wiki is currently link-via-search.
    """
    try:
        from wiki.models import WikiPage
    except Exception:
        raise _ActionNoOp('wiki module not available')
    from kanban.models import Comment
    task = target.target_task
    slug = (_resolve_target(action) or '').strip()
    if not slug:
        raise ValueError("link_wiki_page: empty slug")
    page = WikiPage.objects.filter(slug__iexact=slug).first()
    if not page:
        raise _ActionNoOp(f'no wiki page with slug "{slug}"')
    if not rule.created_by:
        raise ValueError("link_wiki_page: rule has no creator")
    Comment.objects.create(
        task=task, user=rule.created_by,
        content=f'Linked wiki page: [{page.title}](/wiki/{page.slug}/)',
    )


@register_action('create_wiki_page', requires='board')
def _act_create_wiki_page(target, rule, action):
    """Create a new WikiPage on the board's organization."""
    try:
        from wiki.models import WikiPage
    except Exception:
        raise _ActionNoOp('wiki module not available')
    board = target.target_board
    title = (_resolve_target(action) or '').strip()
    if not title:
        raise ValueError("create_wiki_page: empty title")
    content = action.get('message') or ''
    if target.target_task:
        content = _substitute_vars(content, target.target_task)
    org = getattr(board, 'organization', None)
    if not org:
        raise _ActionNoOp('board has no organization')
    try:
        WikiPage.objects.create(
            organization=org,
            title=title[:200],
            content=content,
            created_by=rule.created_by,
        )
    except Exception as exc:
        raise ValueError(f"create_wiki_page: {exc}")


@register_action('capture_decision', requires='either')
def _act_capture_decision(target, rule, action):
    _capture_memory(target, rule, action, node_type='decision')


@register_action('capture_lesson', requires='either')
def _act_capture_lesson(target, rule, action):
    _capture_memory(target, rule, action, node_type='lesson')


def _capture_memory(target, rule, action, node_type):
    try:
        from knowledge_graph.models import MemoryNode
    except Exception:
        raise _ActionNoOp('knowledge_graph module not available')
    content = action.get('message') or f'Captured {node_type} from rule "{rule.name}"'
    if target.target_task:
        content = _substitute_vars(content, target.target_task)
    MemoryNode.objects.create(
        board=target.target_board,
        node_type=node_type,
        title=f'{node_type.title()}: {rule.name}'[:200],
        content=content,
        created_by=rule.created_by,
        is_auto_captured=True,
        source_object_type=target.source_type,
        source_object_id=getattr(target.source, 'pk', None) if target.source else None,
    )
