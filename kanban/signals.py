"""
Signal handlers for automatic workload and performance profile updates
"""
from django.db.models.signals import post_save, pre_save
from django.db.models import Q
from django.dispatch import receiver
from django.contrib.auth.models import User
from kanban.models import Task, TaskActivity
from kanban.resource_leveling_models import UserPerformanceProfile, TaskAssignmentHistory

# Phase 1a refactor: condition and action evaluation now lives in dedicated
# registry modules. The dispatchers below delegate to them. Import side-effects
# register every handler — keep the imports even if the symbols look unused.
from kanban import automation_conditions as _ac
from kanban import automation_actions as _aa
from kanban.automation_conditions import TriggerTarget
from kanban.automation_actions import _ActionNoOp, _ActionSkip  # re-exported

# Custom-field change handlers — registered for their side effects.
from kanban import custom_field_signals as _cfs  # noqa: F401

import threading
from contextlib import contextmanager

# ── Automation re-entrancy guard ─────────────────────────────────────────────
# Actions can call .create()/.save() (e.g. add_subtask creates a Task,
# post_comment creates a Comment, add_label/flag_for_review touch the m2m
# through-table). Those writes re-emit the very signals that fire automation
# rules, so without a guard a "task_created → add_subtask" rule explodes
# exponentially and a "comment_added → post_comment" rule recurses until
# RecursionError. Every automation receiver checks _in_automation() at entry and
# returns early; the rule runners set the flag while executing actions. Net
# effect: a rule's own side effects never re-trigger automation (self-induced
# events are filtered). Field-change chains via .update() already don't cascade,
# so this only tightens an existing boundary.
_automation_state = threading.local()


def _in_automation():
    """True while an automation rule's actions are executing on this thread."""
    return getattr(_automation_state, 'active', False)


@contextmanager
def _automation_guard():
    """Mark the current thread as 'inside automation' for the duration of the
    block so nested model writes don't re-trigger automation receivers."""
    previous = getattr(_automation_state, 'active', False)
    _automation_state.active = True
    try:
        yield
    finally:
        _automation_state.active = previous


@contextmanager
def automation_silent():
    """Public context manager for *system / derived* writes that must NOT run
    user-facing automation rules.

    Use it to wrap saves that aren't a direct expression of user intent —
    prediction refreshes, read-path recomputations, background housekeeping —
    so they don't spam the automation engine (e.g. ``schedule_status_changed``
    firing because a GET request recomputed a prediction). It shares the same
    thread flag as ``_automation_guard`` (``run_board_automations`` early-returns
    when ``_in_automation()`` is true); the separate public name documents the
    *why* at the call site.

        from kanban.signals import automation_silent
        with automation_silent():
            task.save()  # prediction fields only — no rules fire
    """
    with _automation_guard():
        yield

# Pre-save field snapshot — populated by track_field_changes() below and
# consumed in Phase 1b by triggers that fire on "X changed to Y".
TRACKED_FIELDS = (
    'risk_level',
    'predicted_completion_date',
    'progress',
    'workload_impact',
    'lss_classification',
    'milestone_status',
    'phase',
    'complexity_score',
    'due_date',
    'start_date',
    'description',
    'item_type',
)

# Datetime fields whose equality must be compared at minute granularity, with
# naive/aware values normalised. The task form re-submits every field on save,
# so a raw ``!=`` on these picks up tz/microsecond/round-trip noise and records
# a phantom change — firing e.g. task_due_date_changed when only progress moved.
_DATETIME_FIELDS = ('due_date',)

# Width (seconds) of the time bucket in AutomationLog.dedupe_key. Two emissions
# of the same (rule, task, trigger, assignee) within one bucket collapse to a
# single rule run via the unique constraint — this is what makes the engine
# resilient to a concurrent frontend double-submit. Kept small so a deliberate
# repeat of the same action a few seconds later still fires; mirrors the intent
# of the existing 3s fast-path guard below.
_DEDUPE_WINDOW_SECONDS = 3


@receiver(pre_save, sender=Task)
def track_task_assignment_change(sender, instance, **kwargs):
    """
    Track assignment changes before task is saved
    Store the old assignee in a temporary attribute for post_save processing
    """
    if instance.pk:  # Only for existing tasks (updates)
        try:
            old_task = Task.objects.get(pk=instance.pk)
            instance._old_assigned_to = old_task.assigned_to
            instance._assignment_changed = (old_task.assigned_to != instance.assigned_to)
        except Task.DoesNotExist:
            instance._old_assigned_to = None
            instance._assignment_changed = False
    else:  # New task
        instance._old_assigned_to = None
        instance._assignment_changed = bool(instance.assigned_to)


@receiver(pre_save, sender=Task)
def track_priority_and_progress_change(sender, instance, **kwargs):
    """
    Track priority and progress changes before task is saved so automation
    signals can fire on 'priority_changed' and 'task_completed' triggers.
    """
    if instance.pk:
        try:
            old_task = Task.objects.get(pk=instance.pk)
            instance._old_priority = old_task.priority
            instance._priority_changed = (old_task.priority != instance.priority)
            instance._old_progress = old_task.progress

            # Also detect when a task is being moved to a Done/Complete column.
            # auto_update_progress_for_done_column runs as a later pre_save signal
            # and will set instance.progress = 100, but at this point instance.progress
            # still holds the old value, so we must detect the column change here.
            column_name = instance.column.name.lower() if instance.column else ''
            moving_to_done_column = (
                ('done' in column_name or 'complete' in column_name)
                and old_task.progress < 100
                and old_task.column_id != instance.column_id
            )
            instance._just_completed = (
                (old_task.progress < 100 and instance.progress >= 100)
                or moving_to_done_column
            )
        except Task.DoesNotExist:
            instance._old_priority = None
            instance._priority_changed = False
            instance._old_progress = 0
            instance._just_completed = False
    else:
        instance._old_priority = None
        instance._priority_changed = False
        instance._old_progress = 0
        instance._just_completed = False


@receiver(pre_save, sender=Task)
def track_column_entry_time(sender, instance, **kwargs):
    """
    Record when a task enters a new column so WIP age can be calculated.
    Sets column_entered_at on first save or when the task changes column.
    Also stores _old_column_id for use by the automation signal.
    """
    from django.utils import timezone
    if instance.pk:
        try:
            old_task = Task.objects.get(pk=instance.pk)
            instance._old_column_id = old_task.column_id
            if old_task.column_id != instance.column_id:
                instance.column_entered_at = timezone.now()
        except Task.DoesNotExist:
            instance._old_column_id = None
            if not instance.column_entered_at:
                instance.column_entered_at = timezone.now()
    else:
        instance._old_column_id = None
        # Brand-new task
        if not instance.column_entered_at:
            instance.column_entered_at = timezone.now()


@receiver(pre_save, sender=Task)
def track_field_changes(sender, instance, **kwargs):
    """Snapshot the (old, new) value for every field in ``TRACKED_FIELDS`` that
    actually changed on this save. Result is stored on ``instance._field_changes``
    so automation triggers like 'risk_level_changed' or 'task_description_updated'
    can detect transitions without re-querying the DB.

    Phase 1a writes the snapshot; Phase 1b is the first consumer.
    """
    if not instance.pk:
        instance._field_changes = {}
        return
    try:
        old = Task.objects.only(*TRACKED_FIELDS).get(pk=instance.pk)
    except Task.DoesNotExist:
        instance._field_changes = {}
        return

    changes = {}
    for field in TRACKED_FIELDS:
        old_val = getattr(old, field, None)
        new_val = getattr(instance, field, None)
        if field in _DATETIME_FIELDS:
            if _datetime_equal(old_val, new_val):
                continue
        elif old_val == new_val:
            continue
        changes[field] = (old_val, new_val)
    instance._field_changes = changes


def _datetime_equal(a, b):
    """Compare two datetimes as 'the same instant to the minute', treating
    naive and aware values as equivalent. Returns True when they should NOT be
    counted as a change. Guards task_due_date_changed against phantom changes
    from the form re-saving an untouched due_date (BUG-04)."""
    if a is None or b is None:
        return a is b or a == b
    from django.utils import timezone as _tz
    try:
        if _tz.is_naive(a):
            a = _tz.make_aware(a)
        if _tz.is_naive(b):
            b = _tz.make_aware(b)
        return a.replace(second=0, microsecond=0) == b.replace(second=0, microsecond=0)
    except Exception:
        return a == b


@receiver(post_save, sender=Task)
def run_board_automations(sender, instance, created, **kwargs):
    """
    Fire active automation rules after a task is saved.
    Queries both legacy BoardAutomation and new AutomationRule models.
    """
    # Re-entrancy guard: a Task created/saved by another rule's action (e.g.
    # add_subtask) must not re-trigger automation rules.
    if _in_automation():
        return
    from django.utils import timezone as tz
    try:
        from kanban.automation_models import BoardAutomation, AutomationRule, AutomationLog
        from kanban.models import TaskLabel

        board = instance.column.board if instance.column_id else None
        if not board:
            return

        now = tz.now()
        old_column_id = getattr(instance, '_old_column_id', None)
        column_changed = (not created) and (old_column_id != instance.column_id)
        priority_changed = getattr(instance, '_priority_changed', False)
        just_completed   = getattr(instance, '_just_completed', False)
        assignment_changed = getattr(instance, '_assignment_changed', False)

        # ── Fire legacy BoardAutomation rules ──
        legacy_rules = BoardAutomation.objects.filter(board=board, is_active=True)
        for rule in legacy_rules:
            fired = _check_trigger(rule, instance, created, column_changed,
                                   priority_changed, just_completed, assignment_changed, now)
            if fired:
                with _automation_guard():
                    _apply_automation_action(instance, rule)
                rule.run_count += 1
                rule.last_run_at = now
                BoardAutomation.objects.filter(pk=rule.pk).update(
                    run_count=rule.run_count,
                    last_run_at=rule.last_run_at,
                )

        # ── Fire new AutomationRule rules ──
        new_rules = AutomationRule.objects.filter(board=board, is_active=True).exclude(
            trigger_type__startswith='scheduled_',
        )
        # Per-request dedupe: track which rules have already fired for this
        # in-memory Task instance so a second .save() in the same request (e.g.,
        # via update_task_prediction, refresh_from_db + save) does not re-fire
        # the same rule.  This is the in-process belt; the DB check below is
        # the cross-process suspenders.
        fired_this_request = getattr(instance, '_automation_rules_fired', None)
        if fired_this_request is None:
            fired_this_request = set()
            instance._automation_rules_fired = fired_this_request

        for rule in new_rules:
            fired = _check_trigger(rule, instance, created, column_changed,
                                   priority_changed, just_completed, assignment_changed, now)
            if not fired:
                continue

            # In-memory guard
            if rule.pk in fired_this_request:
                continue

            # DB safety net: catches cross-request duplicate emissions (e.g.,
            # a follow-up update_task_prediction() task.save() in a separate
            # request). 3s window is wide enough to absorb realistic re-save
            # latency yet narrow enough that a deliberate second user change
            # still fires the rule normally.
            try:
                from datetime import timedelta as _td
                db_guard = AutomationLog.objects.filter(
                    rule_id=rule.pk,
                    task_affected_id=instance.pk,
                    trigger_event=rule.trigger_type,
                    triggered_at__gte=now - _td(seconds=3),
                )
                # task_assigned owns an assignee-aware per-day guard in
                # _check_trigger. Scope this 3s net to the same assignee so a
                # genuine reassignment to a different user within the window
                # still fires instead of being swallowed as a "duplicate".
                if rule.trigger_type == 'task_assigned':
                    db_guard = db_guard.filter(
                        execution_detail__assignee_id=instance.assigned_to_id,
                    )
                if db_guard.exists():
                    fired_this_request.add(rule.pk)
                    continue
            except Exception:
                pass

            fired_this_request.add(rule.pk)

            # ── Idempotent claim (race-proof backstop) ───────────────
            # Reserve this emission via the AutomationLog.dedupe_key unique
            # constraint BEFORE running any actions. Two *concurrent* duplicate
            # requests — e.g. a frontend double-submit that POSTs the same
            # change twice in the same instant — both reach this point because
            # neither has committed its log row yet, so the in-memory and 3s
            # checks above don't catch them. The unique INSERT lets exactly one
            # win; the loser skips entirely (no action, no duplicate log). The
            # key includes trigger_event, so EVERY trigger dedupes
            # independently — task_assigned, task_progress_changed,
            # schedule_status_changed, and the rest; the assignee, so a genuine
            # reassignment to a different user still fires; and a short time
            # bucket, so a deliberate repeat seconds later still fires.
            bucket = int(now.timestamp()) // _DEDUPE_WINDOW_SECONDS
            dedupe_key = (
                f"{rule.pk}:{instance.pk}:{rule.trigger_type}:"
                f"{instance.assigned_to_id or ''}:{bucket}"
            )
            claim_log = None
            try:
                claim_log, claim_created = AutomationLog.objects.get_or_create(
                    dedupe_key=dedupe_key,
                    defaults={
                        'rule': rule,
                        'rule_name_snapshot': rule.name,
                        'board': board,
                        'trigger_event': rule.trigger_type,
                        'task_affected': instance,
                        'task_title_snapshot': instance.title or '',
                        'outcome': 'success',
                        'execution_detail': {'assignee_id': instance.assigned_to_id},
                    },
                )
                if not claim_created:
                    # A concurrent/duplicate emission already claimed this
                    # action this bucket — skip without running actions again.
                    continue
            except Exception:
                # Never let a dedupe hiccup drop a legitimate rule run: fall
                # back to firing and logging the old (unclaimed) way.
                claim_log = None

            actions_taken = []
            errors = []
            outcome = 'success'
            skip_reason = ''
            branch = 'then'

            if rule.actions:
                # ── New unified flat format ──────────────────────
                outcome, skip_reason, branch = _execute_flat_rule(
                    rule, instance, actions_taken, errors,
                )
            elif rule.rule_definition:
                # ── Legacy canvas block tree ─────────────────────
                with _automation_guard():
                    _execute_rule_tree(rule.rule_definition, instance, rule, actions_taken, errors)
                outcome = 'failed' if errors else 'success'
            else:
                # ── Legacy single action (very old rules) ────────
                try:
                    with _automation_guard():
                        _apply_automation_action(instance, rule)
                    actions_taken.append(f"{rule.action_type}: {rule.action_value}")
                except Exception as e:
                    errors.append(str(e))
                    outcome = 'failed'

            AutomationRule.objects.filter(pk=rule.pk).update(
                run_count=rule.run_count + 1,
                last_run_at=now,
                last_execution_result=outcome,
            )

            log_fields = {
                'rule': rule,
                'rule_name_snapshot': rule.name,
                'board': board,
                'trigger_event': rule.trigger_type,
                'task_affected': instance,
                'task_title_snapshot': instance.title or '',
                'actions_summary': '; '.join(actions_taken) if actions_taken else 'No actions',
                'outcome': outcome,
                'skip_reason': skip_reason,
                'error_detail': '; '.join(errors) if errors else '',
                'execution_detail': {
                    'trigger_type': rule.trigger_type,
                    'conditions_evaluated': len(rule.conditions),
                    'actions_count': len(rule.actions),
                    'branch': branch,
                    # Recorded so the assignee-scoped 3s guard above (and the
                    # dedupe_key) can tell a redundant re-save of the same
                    # assignment from a genuine re-assignment to a different user.
                    'assignee_id': instance.assigned_to_id,
                },
            }
            try:
                if claim_log is not None:
                    # Finalize the row we already claimed with the real result.
                    for _field, _value in log_fields.items():
                        setattr(claim_log, _field, _value)
                    claim_log.save()
                else:
                    AutomationLog.objects.create(dedupe_key=dedupe_key, **log_fields)
            except Exception:
                import logging
                logging.getLogger(__name__).exception("Failed to write AutomationLog")

    except Exception:
        # Never let automations crash core task saves
        import logging
        logging.getLogger(__name__).exception("Automation runner failed silently")


def _check_trigger(rule, task, created, column_changed, priority_changed,
                   just_completed, assignment_changed, now):
    """Check whether a rule's trigger matches the current task save event."""
    from django.utils import timezone as tz
    trigger_type = rule.trigger_type
    cfg = rule.trigger_config if hasattr(rule, 'trigger_config') else {}

    # ── task_moved_to_column (new name) or moved_to_column (old name) ──
    if trigger_type in ('task_moved_to_column', 'moved_to_column') and column_changed:
        col_name = task.column.name.lower() if task.column else ''
        # New format: match by column_name config key
        target = (cfg.get('column_name') or rule.trigger_value or '').lower()
        if not target or target in col_name:
            return True

    elif trigger_type == 'task_overdue':
        # Task.due_date is a DateTimeField — coerce to date for a calendar-day
        # comparison so a datetime/date TypeError can't silently break the signal.
        task_due_date = task.due_date.date() if hasattr(task.due_date, 'date') else task.due_date
        if task_due_date and task_due_date < now.date() and task.progress < 100:
            # Per-day dedupe: an overdue task should produce at most one log
            # entry per rule per calendar day, regardless of how many times
            # the task is saved. Matches the Celery Beat sweep behavior so a
            # user editing the same overdue task several times doesn't get
            # spammed with duplicate notifications.
            try:
                from kanban.automation_models import AutomationLog
                if AutomationLog.objects.filter(
                    rule_id=rule.pk,
                    task_affected_id=task.pk,
                    triggered_at__date=now.date(),
                ).exists():
                    return False
            except Exception:
                pass
            return True

    elif trigger_type == 'task_created' and created:
        return True

    elif trigger_type == 'task_completed' and just_completed:
        # Per-day dedupe: bouncing a task 100 → 50 → 100 in the same calendar day
        # should fire the rule at most once (matches the overdue sweep's guard and
        # the spam-guard the test plan expects for T-02).
        try:
            from kanban.automation_models import AutomationLog
            if AutomationLog.objects.filter(
                rule_id=rule.pk,
                task_affected_id=task.pk,
                trigger_event='task_completed',
                triggered_at__date=now.date(),
            ).exists():
                return False
        except Exception:
            pass
        return True

    # ── task_priority_changed (new name) or priority_changed (old name) ──
    elif trigger_type in ('task_priority_changed', 'priority_changed') and priority_changed:
        target_priority = (cfg.get('priority') or rule.trigger_value or '').lower()
        if not target_priority or task.priority.lower() == target_priority:
            return True

    elif trigger_type == 'task_assigned' and assignment_changed and task.assigned_to:
        # Fire on every genuine assignment change (old != new assignee, enforced
        # by the assignment_changed pre_save flag). The "single assignment ->
        # 2 task.save()" burst is now collapsed by the AutomationLog.dedupe_key
        # unique constraint + 3s-window guard in run_board_automations (both
        # assignee-scoped), so we no longer need a per-(task, assignee, DAY)
        # block here. That per-day block was both redundant (it raced and let
        # concurrent duplicates through anyway) and wrong: it suppressed a
        # legitimate re-assignment to the same person later the same day, and —
        # when several rules watch task_assigned — it silently dropped any rule
        # that had already fired for that assignee today (3 rules logged only 2).
        return True

    # ── task_completion_threshold (new name) or task_completion_reached (old) ──
    elif trigger_type in ('task_completion_threshold', 'task_completion_reached'):
        threshold = int(cfg.get('threshold', rule.trigger_value or 100))
        old_progress = getattr(task, '_old_progress', 0)
        if old_progress < threshold <= (task.progress or 0):
            return True

    elif trigger_type == 'due_date_approaching':
        # This is handled by a Celery Beat task, not the post_save signal.
        # Returning False here prevents accidental double-firing.
        return False

    # ── Phase 1b: task_unassigned ──────────────────────────────
    elif trigger_type == 'task_unassigned' and assignment_changed and not task.assigned_to:
        return True

    # ── Phase 1b: task_status_changed (generic column change) ──
    elif trigger_type == 'task_status_changed' and column_changed:
        # Optional from/to filters in trigger_config
        cfg_from = (cfg.get('from') or '').lower()
        cfg_to = (cfg.get('to') or '').lower()
        col_name = task.column.name.lower() if task.column else ''
        if cfg_to and cfg_to not in col_name:
            return False
        # 'from' filter requires the old column name — we don't have it here
        # by name, only id. If cfg_from is empty, accept the change; otherwise
        # we cannot evaluate it cleanly without a name lookup.
        if cfg_from:
            old_col_id = getattr(task, '_old_column_id', None)
            if old_col_id:
                try:
                    from kanban.models import Column
                    old_col = Column.objects.filter(pk=old_col_id).only('name').first()
                    if not old_col or cfg_from not in old_col.name.lower():
                        return False
                except Exception:
                    return False
        return True

    # ── Phase 1b: field-change triggers (use _field_changes snapshot) ──
    elif trigger_type == 'task_progress_changed':
        changes = getattr(task, '_field_changes', {}) or {}
        if 'progress' not in changes:
            return False
        old_v, new_v = changes['progress']
        try:
            min_delta = int(cfg.get('min_delta', 0))
        except (TypeError, ValueError):
            min_delta = 0
        return abs(int(new_v or 0) - int(old_v or 0)) >= min_delta

    elif trigger_type == 'task_description_updated':
        return 'description' in (getattr(task, '_field_changes', {}) or {})

    elif trigger_type == 'task_due_date_changed':
        return 'due_date' in (getattr(task, '_field_changes', {}) or {})

    # ── Phase 1b: scheduled checks (handled by celery, not post_save) ──
    elif trigger_type in ('task_idle', 'task_start_date_reached'):
        # Periodic celery tasks fire these.
        return False

    elif trigger_type == 'task_label_added':
        # Fired by the m2m_changed receiver (run_task_label_added_automations),
        # not by Task.save() — labels are attached via the m2m through-table.
        return False

    # ── Phase 2: AI/Risk triggers (use _field_changes snapshot) ──
    elif trigger_type == 'risk_level_changed':
        return 'risk_level' in (getattr(task, '_field_changes', {}) or {})

    elif trigger_type == 'risk_level_critical':
        changes = getattr(task, '_field_changes', {}) or {}
        if 'risk_level' not in changes:
            return False
        _, new_v = changes['risk_level']
        return str(new_v).lower() == 'critical'

    elif trigger_type == 'complexity_increased':
        changes = getattr(task, '_field_changes', {}) or {}
        if 'complexity_score' not in changes:
            return False
        old_v, new_v = changes['complexity_score']
        try:
            return int(new_v or 0) > int(old_v or 0)
        except (TypeError, ValueError):
            return False

    elif trigger_type == 'schedule_status_changed':
        # progress_status is a computed badge (late/at_risk/on_track/None). Fire
        # only when that badge actually *transitions*, not on every progress or
        # due_date save — otherwise it fires on almost every edit (BUG-05).
        changes = getattr(task, '_field_changes', {}) or {}
        if 'progress' not in changes and 'due_date' not in changes:
            return False
        old_progress = changes['progress'][0] if 'progress' in changes else task.progress
        old_due = changes['due_date'][0] if 'due_date' in changes else task.due_date
        old_status = task.compute_progress_status(old_progress, old_due, task.start_date)
        new_status = task.compute_progress_status(task.progress, task.due_date, task.start_date)
        return old_status != new_status

    elif trigger_type == 'predicted_late':
        # Periodic check — not fired on save.
        return False

    # ── Phase 3: hierarchy / dependency triggers ──────────────
    elif trigger_type == 'subtask_completed' and just_completed and task.parent_task_id:
        # Fires on the completing CHILD task; the rule's board is presumed to
        # be the same board (parent and child should share a board).
        return True

    elif trigger_type == 'all_subtasks_completed' and just_completed and task.parent_task_id:
        from kanban.models import Task as TaskModel
        parent = task.parent_task
        if not parent:
            return False
        siblings = TaskModel.objects.filter(parent_task=parent).exclude(pk=task.pk)
        return not siblings.filter(progress__lt=100).exists()

    elif trigger_type == 'dependency_completed' and just_completed:
        # Fires for each task that depends on this one. Multi-target — but the
        # post_save signal is per-task, so we only fire the rule once per save.
        # The rule should have a "blocked tasks" action to fan out.
        from kanban.models import Task as TaskModel
        return TaskModel.objects.filter(dependencies=task).exists()

    elif trigger_type == 'dependency_overdue':
        # Handled by the run_overdue_task_automations sweep — fires per task
        # in that periodic context, not the post_save signal.
        return False

    elif trigger_type == 'checklist_completed':
        # Wired via the checklist post_save receiver (see below). The
        # post_save on Task is not the firing event.
        return False

    elif trigger_type == 'checklist_item_added':
        return False  # see ChecklistItem post_save receiver

    elif trigger_type == 'milestone_reached':
        # A milestone "is reached" when a Milestone-type task hits 100%. The old
        # code gated solely on ``just_completed``, which is always False for a
        # task *created* at 100% and for an existing 100% task whose item_type is
        # only now switched to Milestone — so the trigger never fired (BUG-01).
        # Fire whenever the task is a milestone, sits at 100%, and reached that
        # state on THIS save by any path.
        if (task.item_type or '').lower() != 'milestone':
            return False
        if (task.progress or 0) < 100:
            return False
        changes = getattr(task, '_field_changes', {}) or {}
        reached_now = (
            just_completed                                  # progress crossed to 100
            or (created and (task.progress or 0) >= 100)    # created already complete
            or 'item_type' in changes                       # newly typed as milestone
            or 'progress' in changes                        # progress edited to/at 100
        )
        if not reached_now:
            return False
        # Per-day dedupe (mirrors task_completed) so bouncing progress doesn't spam.
        try:
            from kanban.automation_models import AutomationLog
            if AutomationLog.objects.filter(
                rule_id=rule.pk,
                task_affected_id=task.pk,
                trigger_event='milestone_reached',
                triggered_at__date=now.date(),
            ).exists():
                return False
        except Exception:
            pass
        return True

    elif trigger_type == 'parent_status_changed' and column_changed and task.parent_task_id is None:
        # Fires on the PARENT task's column change. Rules on this trigger
        # cascade to subtasks via the cascade_* actions.
        return True

    # ── Phase 5/6 non-task triggers — not fired by Task post_save ──
    elif trigger_type in (
        'coach_suggestion_created', 'conflict_detected',
        'discovery_idea_scored', 'discovery_idea_submitted',
        'immunity_score_dropped', 'hospice_risk_triggered',
        'scope_creep_detected', 'prediction_confidence_dropped',
        'retrospective_finalized',
        'comment_added', 'mention_received', 'attachment_added',
        'task_thread_message',
    ):
        return False

    return False


# _ActionNoOp and _ActionSkip are imported from kanban.automation_actions at the
# top of this file and re-exported for callers (e.g., kanban/tasks/automation_tasks.py)
# that catch them.


def _execute_flat_rule(rule, task, actions_taken, errors):
    """
    Execute a rule stored in the new unified flat format
    (rule.conditions / rule.actions / rule.otherwise_actions).
    Returns (outcome, skip_reason, branch) where outcome is
    'success'/'skipped'/'failed' and branch is 'then'/'otherwise'/'skipped' — the
    actual branch taken, so the audit log can distinguish a fired OTHERWISE branch
    from a fired THEN branch (NOTE-1D-01).
    """
    # Evaluate conditions
    if rule.conditions:
        results = [_evaluate_condition_flat(c, task) for c in rule.conditions]
        if rule.condition_logic == 'OR':
            conditions_met = any(results)
        else:
            conditions_met = all(results)
    else:
        conditions_met = True

    if conditions_met:
        branch_actions = rule.actions
        branch = 'then'
    elif rule.otherwise_actions:
        branch_actions = rule.otherwise_actions
        branch = 'otherwise'
    else:
        return 'skipped', 'Condition not met', 'skipped'

    had_error = False
    skip_reasons = []
    # Guard: actions that create/save models (add_subtask, post_comment, …) must
    # not re-trigger automation receivers. See _automation_guard at module top.
    with _automation_guard():
        for action in branch_actions:
            try:
                _execute_action_flat(action, task, rule)
                actions_taken.append(f"{action.get('type')}")
            except _ActionNoOp as warn:
                skip_reasons.append(f"{action.get('type')}: {warn}")
            except _ActionSkip as skip:
                # Action declared requires=X but the trigger's target couldn't
                # satisfy it. Record as a skip with the structured reason.
                skip_reasons.append(f"{action.get('type')}: {skip}")
            except Exception as exc:
                errors.append(f"{action.get('type')} failed: {exc}")
                had_error = True

    if had_error:
        return 'failed', '', branch
    if not actions_taken and skip_reasons:
        return 'skipped', '; '.join(skip_reasons)[:100], branch
    return 'success', '', branch


def _build_target(task):
    """Construct a TriggerTarget for a task-level trigger event.

    Phase 1a only fires task-level triggers, so source_type is always 'task'
    and target_task is always populated. Phase 5 will introduce other builders
    for non-task sources (Coach suggestion, Conflict detection, etc.).
    """
    board = task.column.board if task.column_id else None
    return TriggerTarget(
        target_board=board,
        target_task=task,
        source=task,
        source_type='task',
    )


def _evaluate_condition_flat(condition, task):
    """Dispatch a single condition through the registry.

    condition = {"attribute": "priority", "operator": "is", "value": "Urgent"}
    Returns True or False.
    """
    return _ac.evaluate(
        condition.get('attribute', ''),
        condition.get('operator', ''),
        condition.get('value'),
        _build_target(task),
    )


def _execute_action_flat(action, task, rule):
    """Dispatch a single action through the registry.

    action = {"type": "set_priority", "target": "Urgent", "message": null}
    Raises ``_ActionNoOp`` when the handler had nothing to do (caller treats
    as a skip), or ``_ActionSkip`` when the target shape doesn't satisfy the
    handler's ``requires``.
    """
    _aa.execute(action, _build_target(task), rule)


def _execute_rule_tree(node, task, rule, actions_taken, errors):
    """
    Recursively walk the rule_definition JSON tree, evaluate conditions,
    and execute actions.  Fail-and-continue: individual action failures
    are logged but do not stop remaining actions.
    """
    from django.utils import timezone as tz

    node_type = node.get('type', '')
    block_type = node.get('block_type', '')
    config = node.get('config', {})

    if node_type == 'trigger':
        # Trigger already matched — process children
        for child in node.get('children', []):
            _execute_rule_tree(child, task, rule, actions_taken, errors)

    elif node_type == 'condition':
        # Evaluate the condition
        condition_met = _evaluate_condition(block_type, config, task)
        if condition_met:
            for child in node.get('children', []):
                _execute_rule_tree(child, task, rule, actions_taken, errors)
        else:
            for child in node.get('else_children', []):
                _execute_rule_tree(child, task, rule, actions_taken, errors)

    elif node_type == 'action':
        try:
            _execute_action(block_type, config, task, rule)
            action_desc = f"{block_type}"
            if config.get('value'):
                action_desc += f": {config['value']}"
            actions_taken.append(action_desc)
        except Exception as e:
            errors.append(f"{block_type} failed: {e}")

        # Continue to chained actions
        for child in node.get('children', []):
            _execute_rule_tree(child, task, rule, actions_taken, errors)


def _evaluate_condition(block_type, config, task):
    """Evaluate a condition block against a task. Returns True/False."""
    from django.utils import timezone as tz

    if block_type == 'assignee_is':
        operator = config.get('operator', 'is')
        value = config.get('value', '')
        if operator == 'is_empty':
            return task.assigned_to is None
        elif operator == 'is_not_empty':
            return task.assigned_to is not None
        # Sentinel value "none" means "Unassigned"
        if str(value).lower() == 'none':
            if operator == 'is':
                return task.assigned_to is None
            elif operator == 'is_not':
                return task.assigned_to is not None
        if operator == 'is':
            return task.assigned_to and task.assigned_to.username == value
        elif operator == 'is_not':
            return not task.assigned_to or task.assigned_to.username != value

    elif block_type == 'priority_equals':
        return task.priority.lower() == config.get('value', '').lower()

    elif block_type == 'column_equals':
        if task.column:
            return task.column.name.lower() == config.get('value', '').lower()
        return False

    elif block_type == 'due_date_within':
        if task.due_date:
            days = int(config.get('days', 0))
            return task.due_date <= tz.now() + tz.timedelta(days=days)
        return False

    elif block_type == 'task_has_label':
        label_name = config.get('value', '')
        return task.labels.filter(name__iexact=label_name).exists()

    elif block_type == 'all_children_complete':
        children = task.subtasks.all() if hasattr(task, 'subtasks') else None
        if children is None:
            from kanban.models import Task as TaskModel
            children = TaskModel.objects.filter(parent_task=task)
        if not children.exists():
            return False
        return not children.filter(progress__lt=100).exists()

    elif block_type == 'progress_gte':
        threshold = int(config.get('value', 100))
        return (task.progress or 0) >= threshold

    elif block_type == 'stale_high_priority':
        if task.priority not in ('high', 'urgent'):
            return False
        days_stale = int(config.get('days_stale', 3))
        if hasattr(task, 'updated_at') and task.updated_at:
            return task.updated_at < tz.now() - tz.timedelta(days=days_stale)
        return False

    return False


def _execute_action(block_type, config, task, rule):
    """Execute a single action block against a task."""
    from django.utils import timezone as tz
    from kanban.models import Task as TaskModel

    VALID_PRIORITIES = {'low', 'medium', 'high', 'urgent'}

    if block_type == 'set_priority':
        new_priority = config.get('value', '').lower()
        if new_priority in VALID_PRIORITIES and task.priority != new_priority:
            TaskModel.objects.filter(pk=task.pk).update(priority=new_priority)

    elif block_type == 'add_label':
        from kanban.models import TaskLabel
        label = TaskLabel.objects.filter(
            board=task.column.board,
            name__iexact=config.get('value', ''),
        ).first()
        if label:
            task.labels.add(label)

    elif block_type == 'remove_label':
        from kanban.models import TaskLabel
        label = TaskLabel.objects.filter(
            board=task.column.board,
            name__iexact=config.get('value', ''),
        ).first()
        if label:
            task.labels.remove(label)

    elif block_type == 'send_notification':
        _send_automation_notification(task, rule, config)

    elif block_type == 'move_to_column':
        from kanban.models import Column
        target_col = Column.objects.filter(
            board=task.column.board,
            name__icontains=config.get('value', ''),
        ).exclude(pk=task.column_id).first()
        if target_col:
            TaskModel.objects.filter(pk=task.pk).update(column=target_col)

    elif block_type == 'assign_to_user':
        from django.contrib.auth.models import User as AuthUser
        value = config.get('value', '')
        if value == '__rule_owner__':
            user = rule.created_by
        else:
            user = AuthUser.objects.filter(username=value).first()
        if user:
            TaskModel.objects.filter(pk=task.pk).update(assigned_to=user)

    elif block_type in ('set_due_date', 'set_due_date_relative'):
        try:
            days = int(config.get('value', 0))
            new_due = tz.now() + tz.timedelta(days=days)
            TaskModel.objects.filter(pk=task.pk).update(due_date=new_due)
        except (ValueError, TypeError):
            pass

    elif block_type == 'close_task':
        from kanban.models import Column
        done_col = Column.objects.filter(
            board=task.column.board,
        ).filter(
            Q(name__icontains='done') | Q(name__icontains='complete')
        ).first()
        if done_col:
            TaskModel.objects.filter(pk=task.pk).update(column=done_col, progress=100)

    elif block_type in ('post_comment', 'create_comment'):
        from kanban.models import Comment
        text = config.get('text', config.get('value', ''))
        if not text:
            raise ValueError("Comment text is empty — edit the rule and add comment content.")
        text = _substitute_vars(text, task)
        Comment.objects.create(
            task=task,
            user=rule.created_by,
            content=text,
        )

    elif block_type == 'log_time_entry':
        try:
            from kanban.budget_models import TimeEntry
            hours = float(config.get('value', config.get('hours', 1)))
            TimeEntry.objects.create(
                task=task,
                user=rule.created_by or task.assigned_to,
                hours=hours,
                notes=f'Auto-logged by automation "{rule.name}"',
            )
        except Exception:
            pass


def _apply_automation_action(task, rule):
    """Apply the action defined in a BoardAutomation rule to a task."""
    import logging
    from django.utils import timezone as tz
    log = logging.getLogger(__name__)
    VALID_PRIORITIES = {'low', 'medium', 'high', 'urgent'}

    if rule.action_type == 'set_priority':
        new_priority = rule.action_value.lower()
        if new_priority in VALID_PRIORITIES and task.priority != new_priority:
            Task.objects.filter(pk=task.pk).update(priority=new_priority)

    elif rule.action_type == 'add_label':
        from kanban.models import TaskLabel
        label = TaskLabel.objects.filter(
            board=task.column.board,
            name__iexact=rule.action_value,
        ).first()
        if label:
            task.labels.add(label)

    elif rule.action_type == 'send_notification':
        _send_automation_notification(task, rule)

    elif rule.action_type == 'move_to_column':
        from kanban.models import Column
        target_col = Column.objects.filter(
            board=task.column.board,
            name__icontains=rule.action_value,
        ).exclude(pk=task.column_id).first()
        if target_col:
            Task.objects.filter(pk=task.pk).update(column=target_col)

    elif rule.action_type == 'assign_to_user':
        from django.contrib.auth.models import User as AuthUser
        user = AuthUser.objects.filter(username=rule.action_value).first()
        if user:
            Task.objects.filter(pk=task.pk).update(assigned_to=user)

    elif rule.action_type == 'set_due_date':
        try:
            days = int(rule.action_value)
            new_due = tz.now() + tz.timedelta(days=days)
            Task.objects.filter(pk=task.pk).update(due_date=new_due)
        except (ValueError, TypeError):
            log.warning("BoardAutomation set_due_date: couldn't parse days from '%s'", rule.action_value)


def _substitute_vars(template, task):
    """Replace {task_title}, {board_name}, {due_date}, {assignee} in a template string."""
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


def _send_automation_notification(task, rule, config=None):
    """Send in-app notifications triggered by an automation rule."""
    try:
        from messaging.models import Notification
        from django.contrib.auth.models import User as AuthUser
        from django.urls import reverse

        board = task.column.board

        # Do not send automated notifications for official demo boards.
        # Real users are added as board members when they browse the demo, so
        # firing automations on those boards would leak demo data to real users.
        if board.is_official_demo_board:
            raise ValueError(
                "Notifications are not sent in demo workspaces — "
                "create your own workspace and board to test real notifications."
            )

        # Determine sender: use the automation creator or board creator
        sender = rule.created_by or board.created_by
        if not sender:
            return

        # Build a clickable link directly to the task detail page.
        # Fall back to the board URL only if the task URL cannot be resolved.
        try:
            task_url = reverse('task_detail', args=[task.id])
        except Exception:
            try:
                task_url = reverse('board_detail', args=[board.id])
            except Exception:
                task_url = None

        # config['value'] takes precedence over rule.action_value
        recipient_key = ''
        if config and config.get('notify_target'):
            # Scheduled rules store the target in config['notify_target']
            recipient_key = config['notify_target'].strip().lower()
        elif config and config.get('value'):
            recipient_key = config['value'].strip().lower()
        elif hasattr(rule, 'notify_target') and rule.notify_target:
            # Fallback: use the dedicated notify_target field on AutomationRule
            recipient_key = rule.notify_target.strip().lower()
        elif rule.action_value:
            recipient_key = rule.action_value.strip().lower()
        recipients = []

        if recipient_key == 'assignee' and task.assigned_to:
            recipients = [task.assigned_to]
        elif recipient_key == 'creator' and task.created_by:
            recipients = [task.created_by]
        elif recipient_key == 'board_members':
            recipients = list(User.objects.filter(board_memberships__board=board))
            if board.created_by and board.created_by not in recipients:
                recipients.append(board.created_by)
        elif recipient_key == 'specific_member':
            target_username = (config or {}).get('target_user', '').strip()
            if target_username:
                from django.contrib.auth.models import User as AuthUser
                specific_user = AuthUser.objects.filter(username=target_username).first()
                if specific_user:
                    recipients = [specific_user]

        if not recipients:
            known_keys = {'assignee', 'board_members', 'creator', 'specific_member'}
            if recipient_key not in known_keys:
                raise ValueError(
                    f"No Notify recipient configured — open the rule in the Canvas Builder "
                    f"and set the Notify field (Task Assignee / All Board Members / Specific Member)."
                )
            raise ValueError(
                f"No recipients resolved for notify_target='{recipient_key}' "
                f"(e.g. task has no assignee, or specific member username not found)."
            )

        # Use the custom message if one was set on the rule, otherwise build a
        # clean professional default.  config['value'] holds the custom message
        # for scheduled rules (it is distinct from config['notify_target'] which
        # holds the recipient key).
        custom_message = ''
        if config:
            # When notify_target is set (Canvas Builder rules), the message is
            # stored separately as 'value'; for scheduled rules 'value' doubles
            # as the recipient key, so only treat it as a message when it isn't
            # a known recipient keyword.
            val = config.get('text', config.get('value', '')).strip()
            if val and val.lower() not in ('assignee', 'board_members', 'creator', 'specific_member'):
                custom_message = val

        raw_text = custom_message or (
            f'Automation "{rule.name}" was triggered for task "{{task_title}}" '
            f'on board "{{board_name}}".'
        )
        text = _substitute_vars(raw_text, task)

        # Build a fixed, programmatic title in the format '[Rule Name] — [Task Name]'.
        # Setting `title` ensures the template uses it directly and never falls
        # back to the AI-generated ai_summary, keeping all automation notifications
        # from the same rule visually consistent.
        notification_title = f'{rule.name} — {task.title}'
        if len(notification_title) > 255:
            notification_title = notification_title[:252] + '...'

        # Also pre-fill ai_summary with the same value so the background
        # AI-generation thread never fires for automation notifications
        # (it only generates when ai_summary is blank on creation).
        ai_summary_text = notification_title[:200]

        for recipient in recipients:
            Notification.objects.create(
                recipient=recipient,
                sender=sender,
                notification_type='ACTIVITY',
                title=notification_title,
                text=text,
                action_url=task_url,
                ai_summary=ai_summary_text,
            )
    except ValueError:
        raise  # Surface actionable errors in the audit log
    except Exception:
        import logging
        logging.getLogger(__name__).exception("_send_automation_notification failed silently")


@receiver(pre_save, sender=Task)
def auto_update_progress_for_done_column(sender, instance, **kwargs):
    """
    Automatically set progress to 100% when a task is moved to a Done or Complete column
    This ensures the progress bar always shows full when tasks are in completion columns
    """
    if instance.column:
        column_name_lower = instance.column.name.lower()
        # Check if column name contains 'done' or 'complete'
        if ('done' in column_name_lower or 'complete' in column_name_lower) and instance.progress < 100:
            instance.progress = 100


@receiver(post_save, sender=Task)
def update_workload_on_assignment_change(sender, instance, created, **kwargs):
    """
    Automatically update UserPerformanceProfile workload when task assignment changes
    This ensures the AI Resource Optimization board stays in sync
    """
    # Only process if assignment changed or task was just created with an assignee
    if not getattr(instance, '_assignment_changed', False) and not created:
        return
    
    # Skip if no column/board (shouldn't happen in normal flow)
    if not instance.column or not instance.column.board:
        return
    
    old_assignee = getattr(instance, '_old_assigned_to', None)
    new_assignee = instance.assigned_to
    
    # Update old assignee's workload (if they had this task)
    if old_assignee and old_assignee != new_assignee:
        profile, _ = UserPerformanceProfile.objects.get_or_create(
            user=old_assignee
        )
        profile.update_current_workload()
        
        # Create assignment history record if not already created by AI suggestion
        if not hasattr(instance, '_ai_suggestion_accepted'):
            TaskAssignmentHistory.objects.create(
                task=instance,
                previous_assignee=old_assignee,
                new_assignee=new_assignee,
                changed_by=getattr(instance, '_changed_by_user', None),
                reason='manual'
            )
    
    # Update new assignee's workload (if task now has an assignee)
    if new_assignee:
        profile, _ = UserPerformanceProfile.objects.get_or_create(
            user=new_assignee
        )
        profile.update_current_workload()
        
        # Create assignment history for new tasks with assignees
        if created and new_assignee:
            TaskAssignmentHistory.objects.create(
                task=instance,
                previous_assignee=None,
                new_assignee=new_assignee,
                changed_by=getattr(instance, '_changed_by_user', instance.created_by),
                reason='manual'
            )
            
            # Log assignment activity for new tasks
            changed_by = getattr(instance, '_changed_by_user', instance.created_by)
            if changed_by:
                TaskActivity.objects.create(
                    task=instance,
                    user=changed_by,
                    activity_type='assigned',
                    description=f"assigned this task to {new_assignee.get_full_name() or new_assignee.username}"
                )
    
    # Log activity for assignment changes on existing tasks
    if not created and getattr(instance, '_assignment_changed', False):
        changed_by = getattr(instance, '_changed_by_user', None)
        if changed_by:
            if new_assignee:
                if old_assignee:
                    TaskActivity.objects.create(
                        task=instance,
                        user=changed_by,
                        activity_type='assigned',
                        description=f"reassigned this task from {old_assignee.get_full_name() or old_assignee.username} to {new_assignee.get_full_name() or new_assignee.username}"
                    )
                else:
                    TaskActivity.objects.create(
                        task=instance,
                        user=changed_by,
                        activity_type='assigned',
                        description=f"assigned this task to {new_assignee.get_full_name() or new_assignee.username}"
                    )
            elif old_assignee:
                TaskActivity.objects.create(
                    task=instance,
                    user=changed_by,
                    activity_type='assigned',
                    description=f"unassigned this task from {old_assignee.get_full_name() or old_assignee.username}"
                )
    
    # Invalidate stale AI suggestions after assignment change
    _invalidate_related_suggestions(instance, old_assignee, new_assignee)


def _invalidate_related_suggestions(task, old_assignee, new_assignee):
    """
    Invalidate AI suggestions that are no longer relevant after an assignment change
    """
    from kanban.resource_leveling_models import ResourceLevelingSuggestion
    
    # Expire pending suggestions for this specific task
    ResourceLevelingSuggestion.objects.filter(
        task=task,
        status='pending'
    ).update(status='expired')
    
    # Expire suggestions recommending the new assignee if they're now overloaded
    if new_assignee:
        profile = UserPerformanceProfile.objects.filter(
            user=new_assignee
        ).first()
        
        if profile and profile.utilization_percentage > 85:
            # This user is now overloaded, expire all pending suggestions recommending them
            ResourceLevelingSuggestion.objects.filter(
                suggested_assignee=new_assignee,
                status='pending'
            ).update(status='expired')
    
    # Also check if old assignee is now underutilized and could take more work
    if old_assignee:
        old_profile = UserPerformanceProfile.objects.filter(
            user=old_assignee
        ).first()
        
        if old_profile and old_profile.utilization_percentage < 60:
            # Old assignee now has capacity - expire suggestions moving work AWAY from them
            ResourceLevelingSuggestion.objects.filter(
                current_assignee=old_assignee,
                status='pending'
            ).update(status='expired')


@receiver(post_save, sender=Task)
def update_profile_on_task_completion(sender, instance, **kwargs):
    """
    Update performance metrics when a task is completed
    """
    # Only process if task was just completed
    if instance.completed_at and instance.assigned_to:
        if not instance.column or not instance.column.board:
            return
        
        # Update the assignee's performance profile
        profile, _ = UserPerformanceProfile.objects.get_or_create(
            user=instance.assigned_to
        )
        
        # Update metrics (completion rate, velocity, etc.)
        profile.update_metrics()
        
        # Update assignment history with actual completion data
        latest_assignment = TaskAssignmentHistory.objects.filter(
            task=instance,
            new_assignee=instance.assigned_to
        ).order_by('-changed_at').first()
        
        if latest_assignment:
            latest_assignment.calculate_actual_metrics()


# ---------------------------------------------------------------------------
# AI summary debounce trigger
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Task)
def trigger_debounced_board_summary(sender, instance, created, **kwargs):
    """
    Enqueue a background Celery task to refresh the board's AI summary whenever
    a "major event" occurs on any task:
      - Task moved to a different column
      - Priority escalated to urgent or high
      - Task completed (progress → 100)

    Race-condition guard: cache.add() maps to Redis SET NX (atomic set-if-not-
    exists).  If two tasks are saved simultaneously on the same board, only the
    first cache.add() call succeeds and returns True; the second returns False and
    silently skips.  This guarantees exactly ONE Celery task is queued per board
    per debounce window — regardless of web-worker concurrency.

    The Celery task itself deletes the lock key when it finishes so the board can
    be re-queued immediately after the previous summary completes.
    """
    if created:
        # New tasks don't have pre-save change flags — skip
        return

    if not instance.column or not instance.column.board_id:
        return

    # Check whether a "major event" happened (flags set by pre_save receivers)
    column_changed = (
        getattr(instance, '_old_column_id', None) is not None
        and instance._old_column_id != instance.column_id
    )
    priority_escalated = (
        getattr(instance, '_priority_changed', False)
        and instance.priority in ('urgent', 'high')
    )
    just_completed = getattr(instance, '_just_completed', False)

    if not (column_changed or priority_escalated or just_completed):
        return  # Minor edit — no need to refresh the board summary

    board_id = instance.column.board_id
    debounce_seconds = _get_debounce_seconds()
    lock_key = f'board_ai_lock_{board_id}'

    try:
        from django.core.cache import caches
        try:
            ai_cache = caches['ai_cache']
        except Exception:
            from django.core.cache import cache as ai_cache

        # Atomic SET NX — only the first concurrent caller gets True
        acquired = ai_cache.add(lock_key, True, timeout=debounce_seconds)
        if not acquired:
            # Another event already queued the task for this board — skip
            return

        # Import here to avoid circular imports at module load time
        from kanban.tasks.ai_summary_tasks import generate_board_summary_task
        generate_board_summary_task.apply_async(
            args=[board_id],
            countdown=debounce_seconds,
        )

    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).warning(
            f"trigger_debounced_board_summary: could not enqueue task for "
            f"board {board_id}: {exc}"
        )


def _get_debounce_seconds():
    """Read AI_SUMMARY_DEBOUNCE_SECONDS from settings, default 600 (10 min)."""
    try:
        from django.conf import settings
        return getattr(settings, 'AI_SUMMARY_DEBOUNCE_SECONDS', 600)
    except Exception:
        return 600


# ---------------------------------------------------------------------------
# Shadow Board Signal Handlers — Live Recalculation Triggers
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Task)
def trigger_branch_recalculation_on_task_completion(sender, instance, created, **kwargs):
    """
    Trigger shadow branch recalculation when a task is completed.
    
    When a task reaches 100% progress (completion), all active shadow branches
    on the board should recalculate their feasibility scores to reflect the
    real-world project progress.
    """
    if created:
        # Skip new task creation
        return
    
    if not hasattr(instance, '_just_completed'):
        return
    
    if not instance._just_completed:
        # Task progress didn't reach completion
        return
    
    if not instance.column or not instance.column.board:
        return
    
    try:
        from kanban.tasks.shadow_branch_tasks import recalculate_branches_for_board
        board_id = instance.column.board_id
        task_title = instance.title or 'Unknown task'

        # The recalc is the single source of truth for branch feasibility.
        # We used to also write a synchronous +1.0 "micro-nudge" in place on
        # the latest snapshot so the trend chart moved instantly, but that
        # mutated a historical snapshot's score (Snapshot N's captured_at
        # said 07:56 with score 40.75, while the row silently re-read 41.75
        # after the nudge) — breaking audit-trail integrity AND causing
        # apparent two-stage updates (cosmetic +1, then real recalc).
        # Shortened countdown from 5s → 2s to keep the perceived latency
        # close to the old nudge-then-recalc UX without polluting history.
        recalculate_branches_for_board.apply_async(
            args=[board_id],
            kwargs={'trigger_event': f'Task "{task_title}" completed'},
            countdown=2,
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(
            f'Error triggering branch recalculation for task completion: {e}',
            exc_info=True
        )


@receiver(pre_save, sender='kanban.Board')
def trigger_branch_recalculation_on_deadline_change(sender, instance, **kwargs):
    """
    Trigger shadow branch recalculation when the board deadline changes.
    
    The project deadline is part of the Time constraint. When it changes,
    the feasibility of all shadow branches may shift.
    """
    if not instance.pk:
        # Skip new board creation
        return
    
    try:
        from kanban.models import Board
        old_board = Board.objects.get(pk=instance.pk)
        
        if old_board.project_deadline != instance.project_deadline:
            # Deadline changed
            from kanban.tasks.shadow_branch_tasks import recalculate_branches_for_board
            
            old_date_str = old_board.project_deadline.strftime('%b %d, %Y') if old_board.project_deadline else 'Not set'
            new_date_str = instance.project_deadline.strftime('%b %d, %Y') if instance.project_deadline else 'Not set'
            
            recalculate_branches_for_board.apply_async(
                args=[instance.id],
                kwargs={'trigger_event': f'Project deadline changed from {old_date_str} to {new_date_str}'},
                countdown=5,
            )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f'Error triggering branch recalculation for deadline change: {e}',
            exc_info=True
        )


@receiver(post_save, sender='kanban.BoardMembership')
def trigger_branch_recalculation_on_membership_added(sender, instance, created, **kwargs):
    """
    Trigger shadow branch recalculation when a team member is added to the board.
    
    Changes to team size affect capacity, velocity, and feasibility calculations.
    """
    if not created:
        # Skip membership updates
        return
    
    try:
        board = instance.board
        user_name = instance.user.get_full_name() or instance.user.username
        
        from kanban.tasks.shadow_branch_tasks import recalculate_branches_for_board
        
        recalculate_branches_for_board.apply_async(
            args=[board.id],
            kwargs={'trigger_event': f'Team member "{user_name}" added to board'},
            countdown=5,
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f'Error triggering branch recalculation for membership add: {e}',
            exc_info=True
        )


from django.db.models.signals import post_delete, pre_delete

@receiver(post_delete, sender='kanban.BoardMembership')
def trigger_branch_recalculation_on_membership_deleted(sender, instance, **kwargs):
    """
    Trigger shadow branch recalculation when a team member is removed from the board.
    
    Changes to team size affect capacity, velocity, and feasibility calculations.
    """
    try:
        board = instance.board
        user_name = instance.user.get_full_name() or instance.user.username
        
        from kanban.tasks.shadow_branch_tasks import recalculate_branches_for_board
        
        recalculate_branches_for_board.apply_async(
            args=[board.id],
            kwargs={'trigger_event': f'Team member "{user_name}" removed from board'},
            countdown=5,
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f'Error triggering branch recalculation for membership removal: {e}',
            exc_info=True
        )


# ---------------------------------------------------------------------------
# Project Signals — unified event tracking for confidence scoring
# Replaces the old commitment-specific signal triggers.
# ---------------------------------------------------------------------------

@receiver(post_save, sender='kanban.Task')
def record_project_signal_on_task_save(sender, instance, created, **kwargs):
    """
    When a task is completed or newly created, record a ProjectSignal
    so the confidence score reflects the change.
    """
    try:
        board = instance.column.board if instance.column_id else None
        if board is None:
            return

        if created:
            # New task added — potential scope growth (mild negative signal)
            from kanban.project_confidence_service import ProjectConfidenceService
            ProjectConfidenceService.record_signal(
                board=board,
                signal_type='task_added',
                strength=-0.05,
                description=f'Task "{instance.title}" added to the board.',
                task=instance,
                ai_generated=True,
            )
        elif getattr(instance, '_just_completed', False):
            # Task transitioned to completed — positive signal.
            # Using _just_completed (set by track_priority_and_progress_change
            # pre_save) rather than progress == 100 prevents duplicate signals
            # when an already-completed task is re-saved (e.g. after updating
            # actual_duration_days during demo data population).
            from kanban.project_confidence_service import ProjectConfidenceService
            ProjectConfidenceService.record_signal(
                board=board,
                signal_type='task_completed',
                strength=0.15,
                description=f'Task "{instance.title}" completed.',
                task=instance,
                ai_generated=True,
            )
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            'record_project_signal_on_task_save: unexpected error',
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Auto-assign color to new columns based on common naming conventions
# ---------------------------------------------------------------------------
_COLUMN_COLOR_MAP = {
    'done': 'green', 'complete': 'green', 'completed': 'green', 'finished': 'green',
    'in progress': 'blue', 'working on it': 'blue', 'doing': 'blue', 'active': 'blue',
    'stuck': 'red', 'blocked': 'red',
    'not started': 'gray', 'backlog': 'gray', 'to do': 'gray', 'todo': 'gray',
    'review': 'purple', 'testing': 'purple', 'qa': 'purple',
    'ready': 'teal', 'approved': 'teal',
    'on hold': 'orange', 'waiting': 'orange', 'pending': 'orange',
    'urgent': 'red', 'critical': 'red',
}


@receiver(pre_save, sender='kanban.Column')
def auto_assign_column_color(sender, instance, **kwargs):
    """Auto-assign a color to new columns based on their name."""
    if instance.pk:
        return  # Only for new columns
    if instance.color != 'blue':
        return  # User already picked a color
    name_lower = instance.name.strip().lower()
    for pattern, color in _COLUMN_COLOR_MAP.items():
        if pattern in name_lower:
            instance.color = color
            break


# ── Board-deletion guard ────────────────────────────────────────────────────
# Deleting a Board cascades to its Tasks, and each Task delete fires
# record_project_signal_on_task_delete (below), which inserts a fresh
# ProjectSignal referencing the board.  Those rows are born *during* the cascade,
# after Django's collector has already chosen what to delete, so at COMMIT they
# point at a board that no longer exists → "FOREIGN KEY constraint failed".
# We track boards currently being deleted in a thread-local set (populated in
# pre_delete, which Django fires for ALL instances before any row is removed) and
# skip signal creation for them.
_board_delete_state = threading.local()


def _boards_being_deleted():
    ids = getattr(_board_delete_state, 'ids', None)
    if ids is None:
        ids = set()
        _board_delete_state.ids = ids
    return ids


@receiver(pre_delete, sender='kanban.Board')
def _mark_board_deleting(sender, instance, **kwargs):
    _boards_being_deleted().add(instance.pk)


@receiver(post_delete, sender='kanban.Board')
def _unmark_board_deleting(sender, instance, **kwargs):
    _boards_being_deleted().discard(instance.pk)


@receiver(post_delete, sender='kanban.Task')
def record_project_signal_on_task_delete(sender, instance, **kwargs):
    """
    When a task is deleted, record a scope-change signal.
    """
    try:
        board = instance.column.board if instance.column_id else None
        if board is None:
            return

        # Skip when the board itself is being deleted — recording a signal here
        # would orphan it and break the cascade's COMMIT (FK constraint failure).
        if board.pk in _boards_being_deleted():
            return

        from kanban.project_confidence_service import ProjectConfidenceService
        ProjectConfidenceService.record_signal(
            board=board,
            signal_type='task_removed',
            strength=0.0,  # Neutral — removal is ambiguous (could be cleanup or scope cut)
            description=f'Task "{instance.title}" removed from the board.',
            task=None,  # Task is being deleted, can't reference
            ai_generated=True,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            'record_project_signal_on_task_delete: unexpected error',
            exc_info=True,
        )


# ── Workspace Preset auto-creation ─────────────────────────────────

@receiver(post_save, sender='accounts.Organization')
def create_workspace_preset_for_org(sender, instance, created, **kwargs):
    """Auto-create a WorkspacePreset when an Organization is created."""
    if created:
        from kanban.preset_models import WorkspacePreset
        WorkspacePreset.objects.get_or_create(
            organization=instance,
            defaults={'global_preset': 'professional'},
        )


@receiver(post_save, sender='kanban.Board')
def create_board_preset_for_board(sender, instance, created, **kwargs):
    """Auto-create a BoardPreset when a Board is created (local_preset=None → inherits global)."""
    if created:
        from kanban.preset_models import BoardPreset
        BoardPreset.objects.get_or_create(
            board=instance,
            defaults={'local_preset': None},
        )


# ---------------------------------------------------------------------------
# Workload tracking — keep UserProfile.current_workload_hours up to date
# ---------------------------------------------------------------------------

def _recalc_user_workload(user):
    """Recalculate and persist current_workload_hours for a user's profile."""
    from django.db.models import Q as _Q
    try:
        profile = user.profile
    except Exception:
        return
    active_count = user.assigned_tasks.exclude(
        _Q(column__name__icontains='done') | _Q(column__name__icontains='complete')
    ).count()
    profile.current_workload_hours = active_count * 8
    profile.save(update_fields=['current_workload_hours'])


@receiver(post_save, sender=Task)
def update_assignee_workload(sender, instance, created, **kwargs):
    """Keep UserProfile.current_workload_hours current when tasks are assigned or column changes."""
    from django.contrib.auth import get_user_model as _get_user_model
    AuthUser = _get_user_model()

    if instance.assigned_to_id:
        _recalc_user_workload(instance.assigned_to)

    old_id = getattr(instance, '_old_assigned_to_id', None)
    if old_id and old_id != instance.assigned_to_id:
        try:
            _recalc_user_workload(AuthUser.objects.get(pk=old_id))
        except AuthUser.DoesNotExist:
            pass


@receiver(post_delete, sender=Task)
def update_assignee_workload_on_delete(sender, instance, **kwargs):
    """Recalculate workload when a task is deleted."""
    if instance.assigned_to:
        _recalc_user_workload(instance.assigned_to)


# ---------------------------------------------------------------------------
# Google Calendar sync — track due_date changes before save
# ---------------------------------------------------------------------------

@receiver(pre_save, sender=Task)
def track_due_date_change(sender, instance, **kwargs):
    """
    Store old due_date and assigned_to_id so post_save signals can react to changes.
    """
    if instance.pk:
        try:
            old = Task.objects.get(pk=instance.pk)
            instance._old_due_date = old.due_date
            instance._old_assigned_to_id = old.assigned_to_id
        except Task.DoesNotExist:
            instance._old_due_date = None
            instance._old_assigned_to_id = None
    else:
        instance._old_due_date = None
        instance._old_assigned_to_id = None


@receiver(post_save, sender=Task)
def sync_due_date_to_google_calendar(sender, instance, created, **kwargs):
    """
    Queue a Celery task to sync this task's due_date to Google Calendar
    when the due_date has changed (or been set for the first time), or when
    the assigned user changes (so the event moves to the new assignee's calendar).

    Only fires when:
      - The due_date actually changed (or was just set on a new task), OR
        the assigned user changed.
      - The current (or previous) assignee has an active GoogleCalendarToken
        with sync_enabled=True.
    """
    try:
        from kanban.utils.demo_protection import calendar_sync_suppressed
        if calendar_sync_suppressed():
            return
    except Exception:
        pass

    old_due_date = getattr(instance, '_old_due_date', None)
    new_due_date = instance.due_date
    old_assigned_to_id = getattr(instance, '_old_assigned_to_id', None)

    due_date_changed = (created and new_due_date) or (old_due_date != new_due_date)
    assignee_changed = (not created) and (old_assigned_to_id != instance.assigned_to_id)

    if not due_date_changed and not assignee_changed:
        return

    # When the assignee changed, we may need to delete the stale event from the
    # old assignee's calendar.  The view stores the old event id on the instance
    # before clearing google_calendar_event_id.
    old_event_id = getattr(instance, '_prev_calendar_event_id', None)
    old_assignee_id_for_cleanup = (
        old_assigned_to_id if (assignee_changed and old_event_id) else None
    )

    try:
        from accounts.models import GoogleCalendarToken
        has_current_token = (
            instance.assigned_to_id and
            GoogleCalendarToken.objects.filter(
                user_id=instance.assigned_to_id, sync_enabled=True
            ).exists()
        )
        if not has_current_token and not old_assignee_id_for_cleanup:
            return

        from accounts.tasks import sync_task_to_calendar
        try:
            # Dispatch asynchronously when a Celery worker is running.
            sync_task_to_calendar.delay(
                instance.pk,
                old_assignee_id=old_assignee_id_for_cleanup,
                old_event_id=old_event_id,
            )
        except Exception as celery_exc:
            # Celery / Redis not reachable — run synchronously so the calendar
            # event is created immediately (Daphne-only / no-worker setup).
            import logging
            logging.getLogger(__name__).info(
                f"sync_due_date_to_google_calendar: Celery unavailable "
                f"({celery_exc}), running synchronously for task {instance.pk}."
            )
            sync_task_to_calendar(
                instance.pk,
                old_assignee_id=old_assignee_id_for_cleanup,
                old_event_id=old_event_id,
            )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            f"sync_due_date_to_google_calendar: could not sync for task {instance.pk}: {exc}"
        )


@receiver(post_delete, sender=Task)
def delete_google_calendar_event_on_task_delete(sender, instance, **kwargs):
    """
    When a task is deleted, remove its corresponding Google Calendar event so
    the user's calendar doesn't accumulate stale entries.

    Works for both individual deletes and bulk queryset deletes (demo reset,
    board deletion) because Django fires post_delete for each object.
    """
    try:
        from kanban.utils.demo_protection import calendar_sync_suppressed
        if calendar_sync_suppressed():
            return
    except Exception:
        pass

    event_id = getattr(instance, 'google_calendar_event_id', None)
    assignee_id = getattr(instance, 'assigned_to_id', None)
    if not event_id or not assignee_id:
        return

    try:
        from accounts.tasks import delete_calendar_event
        try:
            delete_calendar_event.delay(assignee_id, event_id)
        except Exception as celery_exc:
            import logging
            logging.getLogger(__name__).info(
                f"delete_google_calendar_event_on_task_delete: Celery unavailable "
                f"({celery_exc}), running synchronously for task {instance.pk}."
            )
            delete_calendar_event(assignee_id, event_id)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            f"delete_google_calendar_event_on_task_delete: could not queue "
            f"calendar cleanup for task {instance.pk}: {exc}"
        )


# ─── Phase 1b: Task label added (m2m_changed) ───────────────────────────────


from django.db.models.signals import m2m_changed  # noqa: E402


@receiver(m2m_changed, sender=Task.labels.through)
def run_task_label_added_automations(sender, instance, action, pk_set, **kwargs):
    """Fire 'task_label_added' rules when one or more labels are attached to a
    Task. Delegates rule execution to the same flat-rule path used by other
    triggers. Reverse side (label.tasks.add(task)) also dispatches here.
    """
    # Only fire on the forward post_add (Task → labels). The reverse direction
    # (TaskLabel → tasks) provides a TaskLabel as instance; handled below.
    if action != 'post_add' or not pk_set:
        return

    # Re-entrancy guard: labels attached by another rule's action (add_label,
    # flag_for_review) must not re-trigger task_label_added rules.
    if _in_automation():
        return

    try:
        from kanban.models import Task as TaskModel, TaskLabel
        from kanban.automation_models import AutomationRule, AutomationLog
        from django.utils import timezone as tz

        # Resolve (task, added_label_ids) tuples — instance type depends on
        # which side of the m2m relation triggered the change.
        if isinstance(instance, TaskModel):
            task_label_pairs = [(instance, pk_set)]
        elif isinstance(instance, TaskLabel):
            tasks = TaskModel.objects.filter(pk__in=pk_set)
            task_label_pairs = [(t, {instance.pk}) for t in tasks]
        else:
            return

        now = tz.now()
        for task, label_ids in task_label_pairs:
            if task.column_id is None:
                continue
            board = task.column.board
            if board is None:
                continue

            added_labels = list(
                TaskLabel.objects.filter(pk__in=label_ids).only('name')
            )
            added_names_lower = {l.name.lower() for l in added_labels}

            rules = AutomationRule.objects.filter(
                board=board, is_active=True, trigger_type='task_label_added',
            )

            for rule in rules:
                cfg = rule.trigger_config or {}
                cfg_label = (cfg.get('label_name') or '').strip().lower()
                if cfg_label and cfg_label not in added_names_lower:
                    continue

                actions_taken = []
                errors = []
                outcome, skip_reason = 'success', ''
                try:
                    if rule.actions:
                        outcome, skip_reason, _branch = _execute_flat_rule(
                            rule, task, actions_taken, errors,
                        )
                except Exception as exc:
                    outcome = 'failed'
                    errors.append(str(exc))

                AutomationRule.objects.filter(pk=rule.pk).update(
                    run_count=rule.run_count + 1,
                    last_run_at=now,
                    last_execution_result=outcome,
                )
                try:
                    AutomationLog.objects.create(
                        rule=rule,
                        rule_name_snapshot=rule.name,
                        board=board,
                        trigger_event='task_label_added',
                        task_affected=task,
                        task_title_snapshot=task.title or '',
                        actions_summary='; '.join(actions_taken) if actions_taken else 'No actions',
                        outcome=outcome,
                        skip_reason=skip_reason,
                        error_detail='; '.join(errors) if errors else '',
                        execution_detail={
                            'trigger_type': 'task_label_added',
                            'labels_added': sorted(added_names_lower),
                        },
                    )
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception("Failed to write AutomationLog for task_label_added")
    except Exception:
        import logging
        logging.getLogger(__name__).exception("task_label_added automation runner failed silently")


# ─── Phase 3: ChecklistItem-driven triggers ──────────────────────────────────


@receiver(post_save, sender='kanban.ChecklistItem')
def run_checklist_automations(sender, instance, created, **kwargs):
    """Fire 'checklist_item_added' (on create) and 'checklist_completed' (when
    every item on the parent task is now is_completed=True). Delegates rule
    execution to the same path used by Task automations.
    """
    if _in_automation():
        return
    try:
        from kanban.models import ChecklistItem
        from kanban.automation_models import AutomationRule, AutomationLog

        task = instance.task
        if task is None or task.column_id is None:
            return
        board = task.column.board

        triggers_to_fire = []
        if created:
            triggers_to_fire.append('checklist_item_added')

        all_items = ChecklistItem.objects.filter(task=task)
        if all_items.exists() and not all_items.filter(is_completed=False).exists():
            triggers_to_fire.append('checklist_completed')

        if not triggers_to_fire:
            return

        from django.utils import timezone as tz
        now = tz.now()
        for trigger_type in triggers_to_fire:
            rules = AutomationRule.objects.filter(
                board=board, is_active=True, trigger_type=trigger_type,
            )
            for rule in rules:
                actions_taken = []
                errors = []
                outcome, skip_reason = 'success', ''
                try:
                    if rule.actions:
                        outcome, skip_reason, _branch = _execute_flat_rule(
                            rule, task, actions_taken, errors,
                        )
                except Exception as exc:
                    outcome = 'failed'
                    errors.append(str(exc))

                AutomationRule.objects.filter(pk=rule.pk).update(
                    run_count=rule.run_count + 1,
                    last_run_at=now,
                    last_execution_result=outcome,
                )
                try:
                    AutomationLog.objects.create(
                        rule=rule,
                        rule_name_snapshot=rule.name,
                        board=board,
                        trigger_event=trigger_type,
                        task_affected=task,
                        task_title_snapshot=task.title or '',
                        actions_summary='; '.join(actions_taken) if actions_taken else 'No actions',
                        outcome=outcome,
                        skip_reason=skip_reason,
                        error_detail='; '.join(errors) if errors else '',
                        execution_detail={'trigger_type': trigger_type, 'source': 'checklist'},
                    )
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception(
                        "Failed to write AutomationLog for checklist trigger %s rule %s",
                        trigger_type, rule.pk,
                    )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("checklist automation runner failed silently")


# ─── Phase 5: non-task source receivers (first use of TriggerTarget with
#                                            non-task source_type) ────────────


def _run_source_rules(trigger_type, source_obj, board, target_task=None,
                       source_type='source'):
    """Generic driver to fire rules for a non-task source object.

    Mirrors the Task post_save runner but does not loop over a queryset of
    tasks. The TriggerTarget passed to action handlers carries the source
    object so action handlers (e.g., acknowledge_coach_suggestion) can act on
    it directly.
    """
    # Re-entrancy guard: covers all source receivers (coach/conflict/discovery/
    # comment/attachment). A comment posted by an action must not re-enter here.
    if _in_automation():
        return
    try:
        from kanban.automation_models import AutomationRule, AutomationLog
        from kanban.automation_conditions import TriggerTarget
        from django.utils import timezone as tz

        if board is None:
            return
        rules = AutomationRule.objects.filter(
            board=board, is_active=True, trigger_type=trigger_type,
        )
        if not rules.exists():
            return

        now = tz.now()
        target = TriggerTarget(
            target_board=board,
            target_task=target_task,
            source=source_obj,
            source_type=source_type,
        )

        for rule in rules:
            actions_taken = []
            errors = []
            outcome, skip_reason = 'success', ''

            # Conditions
            if rule.conditions:
                results = [
                    _ac.evaluate(c.get('attribute', ''), c.get('operator', ''),
                                 c.get('value'), target)
                    for c in rule.conditions
                ]
                if rule.condition_logic == 'OR':
                    conditions_met = any(results)
                else:
                    conditions_met = all(results)
            else:
                conditions_met = True

            if conditions_met:
                branch_actions = rule.actions
            elif rule.otherwise_actions:
                branch_actions = rule.otherwise_actions
            else:
                branch_actions = []
                outcome, skip_reason = 'skipped', 'Condition not met'

            with _automation_guard():
                for action in branch_actions:
                    try:
                        _aa.execute(action, target, rule)
                        actions_taken.append(action.get('type'))
                    except _ActionNoOp as warn:
                        skip_reason = (skip_reason + '; ' if skip_reason else '') + \
                                      f"{action.get('type')}: {warn}"
                    except _ActionSkip as skip:
                        skip_reason = (skip_reason + '; ' if skip_reason else '') + \
                                      f"{action.get('type')}: {skip}"
                    except Exception as exc:
                        errors.append(f"{action.get('type')} failed: {exc}")
                        outcome = 'failed'

            if not actions_taken and not errors and not skip_reason:
                outcome = 'success'
            elif not actions_taken and skip_reason:
                outcome = 'skipped'

            AutomationRule.objects.filter(pk=rule.pk).update(
                run_count=rule.run_count + 1,
                last_run_at=now,
                last_execution_result=outcome,
            )

            try:
                AutomationLog.objects.create(
                    rule=rule,
                    rule_name_snapshot=rule.name,
                    board=board,
                    trigger_event=trigger_type,
                    task_affected=target_task,
                    task_title_snapshot=(target_task.title if target_task else '') or '',
                    actions_summary='; '.join(actions_taken) if actions_taken else 'No actions',
                    outcome=outcome,
                    skip_reason=skip_reason[:200],
                    error_detail='; '.join(errors) if errors else '',
                    execution_detail={
                        'trigger_type': trigger_type,
                        'source_type': source_type,
                        'source_id': getattr(source_obj, 'pk', None),
                    },
                )
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "Failed to write AutomationLog for source rule %s", rule.pk,
                )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Source-rule runner failed for trigger %s", trigger_type,
        )


@receiver(post_save, sender='kanban.CoachingSuggestion')
def run_coach_suggestion_automations(sender, instance, created, **kwargs):
    if not created:
        return
    _run_source_rules(
        'coach_suggestion_created', instance, instance.board,
        target_task=instance.task, source_type='coach',
    )


@receiver(post_save, sender='kanban.ConflictDetection')
def run_conflict_detected_automations(sender, instance, created, **kwargs):
    if not created or instance.status != 'active':
        return
    # If the conflict naturally points at a single task, surface it.
    try:
        target_task = instance.tasks.first() if instance.tasks.count() == 1 else None
    except Exception:
        target_task = None
    _run_source_rules(
        'conflict_detected', instance, instance.board,
        target_task=target_task, source_type='conflict',
    )


@receiver(post_save, sender='kanban.DiscoveryIdea')
def run_discovery_idea_automations(sender, instance, created, **kwargs):
    """Fires `discovery_idea_submitted` on create, and
    `discovery_idea_scored` when ai_scored_at transitions to set."""
    from kanban.models import Board
    # DiscoveryIdea has organization but not directly a board. For automation
    # we use the org's most-recent board as the target_board (best-effort);
    # in practice rules on discovery_idea_* should be board-agnostic and rely
    # on the source object.
    board = Board.objects.filter(organization=instance.organization).order_by('-id').first()
    if not board:
        return
    if created:
        _run_source_rules(
            'discovery_idea_submitted', instance, board,
            source_type='discovery',
        )
    if not created and instance.ai_scored_at:
        _run_source_rules(
            'discovery_idea_scored', instance, board,
            source_type='discovery',
        )


# ─── Phase 6: Comment / TaskFile / TaskThreadComment receivers ───────────────


@receiver(post_save, sender='kanban.Comment')
def run_comment_added_automations(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        task = instance.task
        if task is None or task.column_id is None:
            return
        board = task.column.board
        _run_source_rules(
            'comment_added', instance, board,
            target_task=task, source_type='comment',
        )
        # @-mention sub-trigger when the comment includes the assignee's username
        if task.assigned_to and instance.content and ('@' + task.assigned_to.username) in instance.content:
            _run_source_rules(
                'mention_received', instance, board,
                target_task=task, source_type='comment',
            )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("comment automation runner failed silently")


@receiver(post_save, sender='kanban.TaskFile')
def run_attachment_added_automations(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        task = instance.task
        if task is None or task.column_id is None:
            return
        _run_source_rules(
            'attachment_added', instance, task.column.board,
            target_task=task, source_type='attachment',
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("attachment automation runner failed silently")
