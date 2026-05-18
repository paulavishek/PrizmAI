"""
Automation Condition Registry
=============================

This module holds every condition handler the automation engine can evaluate.
Handlers are registered with the ``@register_condition`` decorator and looked
up by the dispatcher in ``kanban/signals.py`` (function ``_evaluate_condition_flat``).

Splitting handlers out of the dispatcher does two things:
    1. Each handler is independently unit-testable.
    2. New phases of the automation roadmap add an ``@register_condition`` and
       a function; the dispatcher never changes.

------------------------------------------------------------------------------
TARGET-RESOLUTION CONTRACT (shared with automation_actions.py)
------------------------------------------------------------------------------

The engine was originally task-centric: every condition read ``task.field`` and
every action wrote ``task.field``. Future phases introduce non-Task triggers
(Coach suggestion, Conflict detection, Discovery idea scored, Hospice risk,
Scope creep, Stress Test immunity) where there may be no natural single task
target. The contract below makes the target shape explicit so non-Task triggers
can be added without breaking task-only handlers.

``TriggerTarget`` dataclass — every trigger receiver resolves the event to:

    target_board : Board   (REQUIRED. Always non-null. Task triggers
                            read task.column.board; non-task triggers
                            derive board from the source object.)
    target_task  : Task | None  (Populated when the trigger naturally
                                 has one task. None for board-level
                                 sources like coach_suggestion_created.)
    source       : Any     (Original source object — Task, CoachingSuggestion,
                            ConflictDetection, DiscoveryIdea, etc.)
    source_type  : str     ('task' | 'coach' | 'conflict' | 'discovery' |
                            'hospice' | 'scope' | 'stress' | 'burndown' | ...)

``requires=`` keyword on each handler — handlers self-declare their target needs:

    requires='task'   → handler needs ``target.target_task`` populated. Skips
                        when target_task is None.

    requires='board'  → handler operates on board-level state. Satisfied by ANY
                        target (every target has a board). Task triggers can
                        evaluate 'board' conditions — e.g. gating "task created"
                        by "board has active conflicts". NEVER skips on target
                        availability.

                        IMPORTANT SEMANTIC: 'board' does NOT mean "only runs on
                        board-only triggers." It means "operates on board-level
                        state and is happy with any target."

    requires='either' → handler can use whichever target is present. Picks
                        target_task when available, falls back to target_board.
                        Never skips on target availability.

Skip protocol — when a handler's ``requires`` cannot be satisfied:
    * Dispatcher does NOT call the handler.
    * For conditions, the dispatcher returns ``False`` for that condition and
      records the skip reason at DEBUG log level. The rule's AND/OR logic then
      decides the overall outcome — a single skipped condition does NOT
      short-circuit other conditions.
    * For actions (see automation_actions.py), the dispatcher records
      ``AutomationLog.outcome='skipped'`` with a ``skip_reason``.

Phase 1a establishes this contract but every migrated handler in this file
uses ``requires='task'`` (the implicit current default). Phase 2 starts using
``'board'``. Phase 5 introduces non-task source types.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, Callable, Dict, Tuple


# ─── Target dataclass ────────────────────────────────────────────────────────

@dataclass
class TriggerTarget:
    """Resolved target of an automation trigger. Always carries a board."""
    target_board: Any                       # kanban.Board (required, non-null)
    target_task: Optional[Any] = None       # kanban.Task or None
    source: Any = None                      # Original source object
    source_type: str = 'task'               # 'task' | 'coach' | 'conflict' | ...


# ─── Registry ────────────────────────────────────────────────────────────────

# Maps attribute name → (handler_fn, requires)
# Handler signature: handler(target: TriggerTarget, operator: str, value: Any) -> bool
CONDITION_HANDLERS: Dict[str, Tuple[Callable, str]] = {}


def register_condition(name: str, requires: str = 'task'):
    """Decorator: register a condition handler under ``name``.

    ``requires`` is one of 'task' | 'board' | 'either'. See the contract block
    at the top of this file for semantics.
    """
    if requires not in ('task', 'board', 'either'):
        raise ValueError(f"register_condition: invalid requires={requires!r}")

    def deco(fn):
        CONDITION_HANDLERS[name] = (fn, requires)
        return fn
    return deco


def evaluate(attribute: str, operator: str, value: Any, target: TriggerTarget) -> bool:
    """Dispatch entry point.

    Looks up the handler for ``attribute``, checks its ``requires`` against the
    target, and either calls the handler or returns False with a DEBUG-level
    log entry explaining the skip.
    """
    entry = CONDITION_HANDLERS.get(attribute)
    if entry is None:
        return False
    handler, requires = entry

    if requires == 'task' and target.target_task is None:
        import logging
        logging.getLogger(__name__).debug(
            "Condition '%s' requires a task target but trigger '%s' resolved only a board",
            attribute, target.source_type,
        )
        return False

    try:
        return handler(target, operator, value)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Condition '%s' (operator=%s) raised; treating as False", attribute, operator,
        )
        return False


# ─── Phase 1a — Migrated condition handlers (all requires='task') ────────────


@register_condition('priority', requires='task')
def _cond_priority(target, operator, value):
    task = target.target_task
    task_val = (task.priority or '').lower()
    cmp_val = (value or '').lower() if value is not None else ''
    if operator == 'is':           return task_val == cmp_val
    if operator == 'is_not':       return task_val != cmp_val
    if operator == 'is_empty':     return not task.priority
    if operator == 'is_not_empty': return bool(task.priority)
    return False


@register_condition('assignee', requires='task')
def _cond_assignee(target, operator, value):
    task = target.target_task
    has_assignee = task.assigned_to_id is not None
    if operator == 'is_empty':     return not has_assignee
    if operator == 'is_not_empty': return has_assignee
    # Sentinel value "none" means "Unassigned" — match tasks with no assignee.
    if str(value).lower() == 'none':
        if operator == 'is':       return not has_assignee
        if operator == 'is_not':   return has_assignee
    if operator == 'is':           return str(task.assigned_to_id) == str(value)
    if operator == 'is_not':       return str(task.assigned_to_id) != str(value)
    return False


@register_condition('column', requires='task')
def _cond_column(target, operator, value):
    task = target.target_task
    col_name = (task.column.name if task.column else '').lower()
    cmp_val = (value or '').lower() if value is not None else ''
    if operator == 'is':     return col_name == cmp_val
    if operator == 'is_not': return col_name != cmp_val
    return False


@register_condition('label', requires='task')
def _cond_label(target, operator, value):
    task = target.target_task
    task_labels = set(task.labels.values_list('name', flat=True))
    if operator == 'has':           return value in task_labels
    if operator == 'does_not_have': return value not in task_labels
    if operator == 'is_empty':      return len(task_labels) == 0
    if operator == 'is_not_empty':  return len(task_labels) > 0
    return False


@register_condition('progress', requires='task')
def _cond_progress(target, operator, value):
    task = target.target_task
    progress = task.progress or 0
    try:
        cmp_int = int(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte':    return progress >= cmp_int
    if operator == 'lte':    return progress <= cmp_int
    if operator == 'equals': return progress == cmp_int
    return False


@register_condition('all_subtasks_done', requires='task')
def _cond_all_subtasks_done(target, operator, value):
    from kanban.models import Task as TaskModel
    task = target.target_task
    subtasks = TaskModel.objects.filter(parent_task=task)
    if not subtasks.exists():
        result = False
    else:
        result = not subtasks.filter(progress__lt=100).exists()
    if operator == 'is_true':  return result
    if operator == 'is_false': return not result
    return False


@register_condition('due_date', requires='task')
def _cond_due_date(target, operator, value):
    from django.utils import timezone as tz
    task = target.target_task
    if operator == 'is_empty':     return task.due_date is None
    if operator == 'is_not_empty': return task.due_date is not None
    # Coerce datetime → date for calendar-day comparisons.
    due_date_value = (
        task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
    ) if task.due_date else None
    if operator == 'is_overdue':
        return due_date_value is not None and due_date_value < tz.now().date()
    if operator == 'within_days':
        if not due_date_value:
            return False
        try:
            days = int(value or 0)
        except (TypeError, ValueError):
            return False
        return 0 <= (due_date_value - tz.now().date()).days <= days
    return False


@register_condition('stale_high_priority', requires='task')
def _cond_stale_high_priority(target, operator, value):
    from django.utils import timezone as tz
    task = target.target_task
    if task.priority not in ('high', 'urgent'):
        result = False
    elif hasattr(task, 'updated_at') and task.updated_at:
        result = task.updated_at < tz.now() - tz.timedelta(days=7)
    else:
        result = False
    if operator == 'is_true':  return result
    if operator == 'is_false': return not result
    return False


# ─── Phase 1b — Core task field conditions ───────────────────────────────────


@register_condition('status', requires='task')
def _cond_status(target, operator, value):
    """Column name — cleaner alias of 'column' that matches the UI label."""
    task = target.target_task
    col_name = (task.column.name if task.column else '').lower()
    cmp_val = (value or '').lower() if value is not None else ''
    if operator == 'is':     return col_name == cmp_val
    if operator == 'is_not': return col_name != cmp_val
    return False


@register_condition('created_by', requires='task')
def _cond_created_by(target, operator, value):
    task = target.target_task
    creator_id = getattr(task, 'created_by_id', None)
    if operator == 'is_empty':     return creator_id is None
    if operator == 'is_not_empty': return creator_id is not None
    if operator == 'is':           return str(creator_id) == str(value)
    if operator == 'is_not':       return str(creator_id) != str(value)
    return False


@register_condition('start_date', requires='task')
def _cond_start_date(target, operator, value):
    from django.utils import timezone as tz
    task = target.target_task
    if operator == 'is_empty':     return task.start_date is None
    if operator == 'is_not_empty': return task.start_date is not None
    sd = task.start_date
    if sd is None:
        return False
    sd_date = sd.date() if hasattr(sd, 'date') else sd
    today = tz.now().date()
    if operator == 'is_past':   return sd_date < today
    if operator == 'is_today':  return sd_date == today
    if operator == 'within_days':
        try:
            days = int(value or 0)
        except (TypeError, ValueError):
            return False
        return 0 <= (sd_date - today).days <= days
    return False


@register_condition('description', requires='task')
def _cond_description(target, operator, value):
    task = target.target_task
    desc = (task.description or '')
    needle = (value or '')
    if operator == 'contains':         return needle.lower() in desc.lower()
    if operator == 'does_not_contain': return needle.lower() not in desc.lower()
    if operator == 'is_empty':         return not desc.strip()
    if operator == 'is_not_empty':     return bool(desc.strip())
    return False


@register_condition('title', requires='task')
def _cond_title(target, operator, value):
    task = target.target_task
    title = (task.title or '')
    needle = (value or '')
    if operator == 'contains':         return needle.lower() in title.lower()
    if operator == 'does_not_contain': return needle.lower() not in title.lower()
    return False


@register_condition('checklist_progress', requires='task')
def _cond_checklist_progress(target, operator, value):
    """Reuses Task.checklist_percentage — returns 0 when no checklist exists."""
    task = target.target_task
    pct = getattr(task, 'checklist_percentage', 0) or 0
    try:
        cmp_int = int(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte':    return pct >= cmp_int
    if operator == 'lte':    return pct <= cmp_int
    if operator == 'equals': return pct == cmp_int
    return False


@register_condition('has_comments', requires='task')
def _cond_has_comments(target, operator, value):
    task = target.target_task
    try:
        count = task.comments.count()
    except Exception:
        count = 0
    if operator == 'is_true':  return count > 0
    if operator == 'is_false': return count == 0
    try:
        cmp_int = int(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'count_gte': return count >= cmp_int
    if operator == 'count_lte': return count <= cmp_int
    return False


@register_condition('has_attachments', requires='task')
def _cond_has_attachments(target, operator, value):
    task = target.target_task
    try:
        count = task.files.count() if hasattr(task, 'files') else task.taskfile_set.count()
    except Exception:
        count = 0
    if operator == 'is_true':  return count > 0
    if operator == 'is_false': return count == 0
    return False


@register_condition('idle_days', requires='task')
def _cond_idle_days(target, operator, value):
    from django.utils import timezone as tz
    task = target.target_task
    if not getattr(task, 'updated_at', None):
        return False
    days_idle = (tz.now() - task.updated_at).days
    try:
        cmp_int = int(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte': return days_idle >= cmp_int
    if operator == 'lte': return days_idle <= cmp_int
    return False


@register_condition('time_in_column', requires='task')
def _cond_time_in_column(target, operator, value):
    from django.utils import timezone as tz
    task = target.target_task
    if not getattr(task, 'column_entered_at', None):
        return False
    days = (tz.now() - task.column_entered_at).days
    try:
        cmp_int = int(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte': return days >= cmp_int
    if operator == 'lte': return days <= cmp_int
    return False


# ─── Phase 2 — Risk & AI prediction conditions ───────────────────────────────


_RISK_ORDER = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}


@register_condition('risk_level', requires='task')
def _cond_risk_level(target, operator, value):
    task = target.target_task
    rl = (task.risk_level or '').lower()
    cmp = (value or '').lower() if value is not None else ''
    if operator == 'is':         return rl == cmp
    if operator == 'is_not':     return rl != cmp
    if operator == 'is_at_least':
        return _RISK_ORDER.get(rl, -1) >= _RISK_ORDER.get(cmp, -1)
    return False


@register_condition('risk_score', requires='task')
def _cond_risk_score(target, operator, value):
    task = target.target_task
    score = task.risk_score or 0
    try:
        cmp_int = int(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte':    return score >= cmp_int
    if operator == 'lte':    return score <= cmp_int
    if operator == 'equals': return score == cmp_int
    return False


@register_condition('predicted_completion', requires='task')
def _cond_predicted_completion(target, operator, value):
    task = target.target_task
    pc = task.predicted_completion_date
    due = task.due_date
    if pc is None or due is None:
        return False
    pc_d = pc.date() if hasattr(pc, 'date') else pc
    due_d = due.date() if hasattr(due, 'date') else due
    if operator == 'before_due': return pc_d < due_d
    if operator == 'after_due':  return pc_d > due_d
    if operator == 'within_days_of_due':
        try:
            days = int(value or 0)
        except (TypeError, ValueError):
            return False
        return abs((pc_d - due_d).days) <= days
    return False


@register_condition('prediction_confidence', requires='task')
def _cond_prediction_confidence(target, operator, value):
    task = target.target_task
    pc = task.prediction_confidence or 0
    try:
        cmp_int = int(value or 0)
    except (TypeError, ValueError):
        return False
    # Stored as 0-1.0 in the model? Normalize either way: if value < 2, treat as fraction.
    pc_pct = pc * 100 if pc <= 1 else pc
    if operator == 'gte': return pc_pct >= cmp_int
    if operator == 'lte': return pc_pct <= cmp_int
    return False


@register_condition('complexity_score', requires='task')
def _cond_complexity_score(target, operator, value):
    task = target.target_task
    cs = task.complexity_score or 0
    try:
        cmp_int = int(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte':    return cs >= cmp_int
    if operator == 'lte':    return cs <= cmp_int
    if operator == 'equals': return cs == cmp_int
    return False


@register_condition('schedule_status', requires='task')
def _cond_schedule_status(target, operator, value):
    task = target.target_task
    status = getattr(task, 'progress_status', None) or ''
    cmp = (value or '').lower() if value is not None else ''
    if operator == 'is': return status.lower() == cmp
    return False


@register_condition('lss_classification', requires='task')
def _cond_lss_classification(target, operator, value):
    task = target.target_task
    lc = (task.lss_classification or '').lower()
    cmp = (value or '').lower() if value is not None else ''
    if operator == 'is':     return lc == cmp
    if operator == 'is_not': return lc != cmp
    return False


@register_condition('ai_risk_score', requires='task')
def _cond_ai_risk_score(target, operator, value):
    task = target.target_task
    score = task.ai_risk_score or 0
    try:
        cmp_int = int(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte': return score >= cmp_int
    if operator == 'lte': return score <= cmp_int
    return False


# ─── Phase 3 — Hierarchy & Dependency conditions ─────────────────────────────


@register_condition('parent_status', requires='task')
def _cond_parent_status(target, operator, value):
    task = target.target_task
    parent = task.parent_task
    if not parent or not parent.column:
        return False
    pname = parent.column.name.lower()
    cmp = (value or '').lower() if value is not None else ''
    if operator == 'is':     return pname == cmp
    if operator == 'is_not': return pname != cmp
    return False


@register_condition('subtask_count', requires='task')
def _cond_subtask_count(target, operator, value):
    from kanban.models import Task as TaskModel
    task = target.target_task
    count = TaskModel.objects.filter(parent_task=task).count()
    try:
        cmp_int = int(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte':    return count >= cmp_int
    if operator == 'lte':    return count <= cmp_int
    if operator == 'equals': return count == cmp_int
    return False


@register_condition('subtask_completion_pct', requires='task')
def _cond_subtask_completion_pct(target, operator, value):
    from kanban.models import Task as TaskModel
    task = target.target_task
    subtasks = TaskModel.objects.filter(parent_task=task)
    total = subtasks.count()
    if total == 0:
        pct = 0
    else:
        done = subtasks.filter(progress=100).count()
        pct = int((done / total) * 100)
    try:
        cmp_int = int(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte': return pct >= cmp_int
    if operator == 'lte': return pct <= cmp_int
    return False


@register_condition('has_dependencies', requires='task')
def _cond_has_dependencies(target, operator, value):
    task = target.target_task
    try:
        has_deps = task.dependencies.exists()
    except Exception:
        has_deps = False
    if operator == 'is_true':  return has_deps
    if operator == 'is_false': return not has_deps
    return False


@register_condition('has_blocked_tasks', requires='task')
def _cond_has_blocked_tasks(target, operator, value):
    from kanban.models import Task as TaskModel
    task = target.target_task
    # Tasks where this task is in their dependencies list
    try:
        is_blocking = TaskModel.objects.filter(dependencies=task).exists()
    except Exception:
        is_blocking = False
    if operator == 'is_true':  return is_blocking
    if operator == 'is_false': return not is_blocking
    return False


@register_condition('dependency_status', requires='task')
def _cond_dependency_status(target, operator, value):
    from django.utils import timezone as tz
    task = target.target_task
    try:
        deps = list(task.dependencies.all())
    except Exception:
        deps = []
    if not deps:
        return False
    today = tz.now().date()
    if operator == 'all_complete':
        return all((d.progress or 0) >= 100 for d in deps)
    if operator == 'any_overdue':
        return any(
            d.due_date and (d.due_date.date() if hasattr(d.due_date, 'date') else d.due_date) < today
            and (d.progress or 0) < 100
            for d in deps
        )
    if operator == 'any_blocked':
        # A dependency is "blocked" if it itself has uncompleted dependencies.
        return any(
            d.dependencies.exists() and any(
                (dd.progress or 0) < 100 for dd in d.dependencies.all()
            )
            for d in deps
        )
    return False


@register_condition('item_type', requires='task')
def _cond_item_type(target, operator, value):
    task = target.target_task
    it = (task.item_type or '').lower()
    cmp = (value or '').lower() if value is not None else ''
    if operator == 'is': return it == cmp
    return False


@register_condition('phase', requires='task')
def _cond_phase(target, operator, value):
    task = target.target_task
    ph = (task.phase or '').lower()
    cmp = (value or '').lower() if value is not None else ''
    if operator == 'is':     return ph == cmp
    if operator == 'is_not': return ph != cmp
    return False


@register_condition('is_root_task', requires='task')
def _cond_is_root_task(target, operator, value):
    task = target.target_task
    is_root = task.parent_task_id is None
    if operator == 'is_true':  return is_root
    if operator == 'is_false': return not is_root
    return False


# ─── Phase 4 — Resource, Cost & Workload conditions ──────────────────────────


_WORKLOAD_ORDER = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}


@register_condition('workload_impact', requires='task')
def _cond_workload_impact(target, operator, value):
    task = target.target_task
    wl = (task.workload_impact or '').lower()
    cmp = (value or '').lower() if value is not None else ''
    if operator == 'is': return wl == cmp
    if operator == 'is_at_least':
        return _WORKLOAD_ORDER.get(wl, -1) >= _WORKLOAD_ORDER.get(cmp, -1)
    return False


@register_condition('skill_match_score', requires='task')
def _cond_skill_match_score(target, operator, value):
    task = target.target_task
    sm = task.skill_match_score or 0
    try:
        cmp_int = int(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte': return sm >= cmp_int
    if operator == 'lte': return sm <= cmp_int
    return False


@register_condition('required_skills', requires='task')
def _cond_required_skills(target, operator, value):
    task = target.target_task
    skills = task.required_skills or []
    if operator == 'is_empty':     return not skills
    if operator == 'is_not_empty': return bool(skills)
    if operator == 'contains':
        needle = (value or '').lower()
        return any(needle in str(s).lower() for s in skills)
    if operator == 'count_gte':
        try:
            cmp_int = int(value or 0)
        except (TypeError, ValueError):
            return False
        return len(skills) >= cmp_int
    return False


@register_condition('collaboration_required', requires='task')
def _cond_collaboration_required(target, operator, value):
    task = target.target_task
    flag = bool(task.collaboration_required)
    if operator == 'is_true':  return flag
    if operator == 'is_false': return not flag
    return False


@register_condition('estimated_cost', requires='task')
def _cond_estimated_cost(target, operator, value):
    task = target.target_task
    try:
        cost = float(getattr(task.cost, 'estimated_cost', 0) or 0)
    except Exception:
        cost = 0.0
    try:
        cmp_f = float(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte': return cost >= cmp_f
    if operator == 'lte': return cost <= cmp_f
    return False


@register_condition('estimated_hours', requires='task')
def _cond_estimated_hours(target, operator, value):
    task = target.target_task
    try:
        hours = float(getattr(task.cost, 'estimated_hours', 0) or 0)
    except Exception:
        hours = 0.0
    try:
        cmp_f = float(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte': return hours >= cmp_f
    if operator == 'lte': return hours <= cmp_f
    return False


@register_condition('hours_logged', requires='task')
def _cond_hours_logged(target, operator, value):
    from kanban.budget_models import TimeEntry
    from django.db.models import Sum
    task = target.target_task
    total = TimeEntry.objects.filter(task=task).aggregate(
        s=Sum('hours_spent'),
    ).get('s') or 0
    total = float(total)
    try:
        cmp_f = float(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte': return total >= cmp_f
    if operator == 'lte': return total <= cmp_f
    return False


@register_condition('cost_variance_pct', requires='task')
def _cond_cost_variance_pct(target, operator, value):
    task = target.target_task
    try:
        est = float(getattr(task.cost, 'estimated_cost', 0) or 0)
        actual = float(getattr(task.cost, 'actual_cost', 0) or 0)
    except Exception:
        return False
    if est == 0:
        return False
    variance_pct = ((actual - est) / est) * 100
    try:
        cmp_f = float(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte': return variance_pct >= cmp_f
    if operator == 'lte': return variance_pct <= cmp_f
    return False


@register_condition('assignee_workload', requires='task')
def _cond_assignee_workload(target, operator, value):
    from kanban.models import Task as TaskModel
    task = target.target_task
    if not task.assigned_to_id:
        return False
    open_count = TaskModel.objects.filter(
        assigned_to_id=task.assigned_to_id,
    ).exclude(progress=100).count()
    try:
        cmp_int = int(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte': return open_count >= cmp_int
    if operator == 'lte': return open_count <= cmp_int
    return False


# ─── Phase 5 — Board-scoped conditions (first use of requires='board') ──────
# These gate rules based on board-level state. Because they declare
# requires='board' (not 'task'), they fire for task-level triggers too —
# every target has a board. See the contract block at the top of this file.


@register_condition('board_has_active_conflicts', requires='board')
def _cond_board_has_active_conflicts(target, operator, value):
    from kanban.conflict_models import ConflictDetection
    count = ConflictDetection.objects.filter(
        board=target.target_board, status='active',
    ).count()
    if operator == 'is_true':  return count > 0
    if operator == 'is_false': return count == 0
    if operator == 'count_gte':
        try:
            cmp_int = int(value or 0)
        except (TypeError, ValueError):
            return False
        return count >= cmp_int
    return False


@register_condition('board_immunity_score', requires='board')
def _cond_board_immunity_score(target, operator, value):
    try:
        from kanban.stress_test_models import ImmunityScore
    except Exception:
        return False
    latest = ImmunityScore.objects.filter(
        session__board=target.target_board,
    ).order_by('-id').first()
    if not latest:
        return False
    score = getattr(latest, 'overall_score', 0) or 0
    try:
        cmp_int = int(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte': return score >= cmp_int
    if operator == 'lte': return score <= cmp_int
    return False


@register_condition('board_scope_creep_pct', requires='board')
def _cond_board_scope_creep_pct(target, operator, value):
    board = target.target_board
    try:
        status = board.get_current_scope_status()
        pct = abs(status.get('scope_change_percentage', 0) or 0)
    except Exception:
        return False
    try:
        cmp_f = float(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte': return pct >= cmp_f
    if operator == 'lte': return pct <= cmp_f
    return False


@register_condition('board_velocity_trend', requires='board')
def _cond_board_velocity_trend(target, operator, value):
    """Velocity trend is 'improving' | 'stable' | 'declining'. We sniff for a
    velocity snapshot model; if absent, return False rather than crash."""
    try:
        from kanban.burndown_models import TeamVelocitySnapshot
    except Exception:
        return False
    snapshots = TeamVelocitySnapshot.objects.filter(
        board=target.target_board,
    ).order_by('-snapshot_date')[:3]
    snapshots = list(snapshots)
    if len(snapshots) < 2:
        return False
    latest = snapshots[0].velocity_value or 0
    prior = snapshots[-1].velocity_value or 0
    if latest > prior * 1.10:
        trend = 'improving'
    elif latest < prior * 0.90:
        trend = 'declining'
    else:
        trend = 'stable'
    cmp = (value or '').lower()
    if operator == 'is': return trend == cmp
    return False


@register_condition('board_predicted_overrun_days', requires='board')
def _cond_board_predicted_overrun_days(target, operator, value):
    try:
        from kanban.burndown_models import BurndownPrediction
    except Exception:
        return False
    pred = BurndownPrediction.objects.filter(
        board=target.target_board,
    ).order_by('-id').first()
    if not pred:
        return False
    project_deadline = getattr(target.target_board, 'project_deadline', None)
    predicted = getattr(pred, 'predicted_completion_date', None)
    if not project_deadline or not predicted:
        return False
    pd = project_deadline.date() if hasattr(project_deadline, 'date') else project_deadline
    pp = predicted.date() if hasattr(predicted, 'date') else predicted
    overrun_days = (pp - pd).days
    try:
        cmp_int = int(value or 0)
    except (TypeError, ValueError):
        return False
    if operator == 'gte': return overrun_days >= cmp_int
    return False
