"""
Signal handlers for automatic workload and performance profile updates
"""
from django.db.models.signals import post_save, pre_save
from django.db.models import Q
from django.dispatch import receiver
from django.contrib.auth.models import User
from kanban.models import Task, TaskActivity
from kanban.resource_leveling_models import UserPerformanceProfile, TaskAssignmentHistory


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


@receiver(post_save, sender=Task)
def run_board_automations(sender, instance, created, **kwargs):
    """
    Fire active automation rules after a task is saved.
    Queries both legacy BoardAutomation and new AutomationRule models.
    """
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
        for rule in new_rules:
            fired = _check_trigger(rule, instance, created, column_changed,
                                   priority_changed, just_completed, assignment_changed, now)
            if not fired:
                continue

            actions_taken = []
            errors = []
            outcome = 'success'
            skip_reason = ''

            if rule.actions:
                # ── New unified flat format ──────────────────────
                outcome, skip_reason = _execute_flat_rule(
                    rule, instance, actions_taken, errors,
                )
            elif rule.rule_definition:
                # ── Legacy canvas block tree ─────────────────────
                _execute_rule_tree(rule.rule_definition, instance, rule, actions_taken, errors)
                outcome = 'failed' if errors else 'success'
            else:
                # ── Legacy single action (very old rules) ────────
                try:
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

            try:
                AutomationLog.objects.create(
                    rule=rule,
                    rule_name_snapshot=rule.name,
                    board=board,
                    trigger_event=rule.trigger_type,
                    task_affected=instance,
                    task_title_snapshot=instance.title or '',
                    actions_summary='; '.join(actions_taken) if actions_taken else 'No actions',
                    outcome=outcome,
                    skip_reason=skip_reason,
                    error_detail='; '.join(errors) if errors else '',
                    execution_detail={
                        'trigger_type': rule.trigger_type,
                        'conditions_evaluated': len(rule.conditions),
                        'actions_count': len(rule.actions),
                        'branch': 'then' if outcome != 'skipped' else 'skipped',
                    },
                )
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
        if task.due_date and task.due_date < now.date() and task.progress < 100:
            # 10-second dedup window
            try:
                from kanban.automation_models import AutomationLog
                if AutomationLog.objects.filter(
                    rule_id=rule.pk,
                    task_affected_id=task.pk,
                    triggered_at__gte=now - tz.timedelta(seconds=10),
                ).exists():
                    return False
            except Exception:
                pass
            return True

    elif trigger_type == 'task_created' and created:
        return True

    elif trigger_type == 'task_completed' and just_completed:
        return True

    # ── task_priority_changed (new name) or priority_changed (old name) ──
    elif trigger_type in ('task_priority_changed', 'priority_changed') and priority_changed:
        target_priority = (cfg.get('priority') or rule.trigger_value or '').lower()
        if not target_priority or task.priority.lower() == target_priority:
            return True

    elif trigger_type == 'task_assigned' and assignment_changed and task.assigned_to:
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

    return False


def _execute_flat_rule(rule, task, actions_taken, errors):
    """
    Execute a rule stored in the new unified flat format
    (rule.conditions / rule.actions / rule.otherwise_actions).
    Returns (outcome, skip_reason) where outcome is 'success'/'skipped'/'failed'.
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
        return 'skipped', 'Condition not met'

    had_error = False
    for action in branch_actions:
        try:
            _execute_action_flat(action, task, rule)
            actions_taken.append(f"{action.get('type')}")
        except Exception as exc:
            errors.append(f"{action.get('type')} failed: {exc}")
            had_error = True

    return ('failed' if had_error else 'success'), ''


def _evaluate_condition_flat(condition, task):
    """
    Evaluate a single condition dict from rule.conditions against a task.
    condition = {"attribute": "priority", "operator": "is", "value": "Urgent"}
    Returns True or False.
    """
    from django.utils import timezone as tz

    attr = condition.get('attribute', '')
    operator = condition.get('operator', '')
    value = condition.get('value')

    if attr == 'priority':
        task_val = (task.priority or '').lower()
        cmp_val = (value or '').lower()
        if operator == 'is':         return task_val == cmp_val
        if operator == 'is_not':     return task_val != cmp_val
        if operator == 'is_empty':   return not task.priority
        if operator == 'is_not_empty': return bool(task.priority)

    elif attr == 'assignee':
        has_assignee = task.assigned_to_id is not None
        if operator == 'is_empty':     return not has_assignee
        if operator == 'is_not_empty': return has_assignee
        if operator == 'is':           return str(task.assigned_to_id) == str(value)
        if operator == 'is_not':       return str(task.assigned_to_id) != str(value)

    elif attr == 'column':
        col_name = (task.column.name if task.column else '').lower()
        cmp_val = (value or '').lower()
        if operator == 'is':     return col_name == cmp_val
        if operator == 'is_not': return col_name != cmp_val

    elif attr == 'label':
        task_labels = set(task.labels.values_list('name', flat=True))
        if operator == 'has':            return value in task_labels
        if operator == 'does_not_have': return value not in task_labels
        if operator == 'is_empty':       return len(task_labels) == 0
        if operator == 'is_not_empty':   return len(task_labels) > 0

    elif attr == 'progress':
        progress = task.progress or 0
        try:
            cmp_int = int(value or 0)
        except (TypeError, ValueError):
            return False
        if operator == 'gte':    return progress >= cmp_int
        if operator == 'lte':    return progress <= cmp_int
        if operator == 'equals': return progress == cmp_int

    elif attr == 'all_subtasks_done':
        from kanban.models import Task as TaskModel
        subtasks = TaskModel.objects.filter(parent_task=task)
        if not subtasks.exists():
            result = False
        else:
            result = not subtasks.filter(progress__lt=100).exists()
        if operator == 'is_true':  return result
        if operator == 'is_false': return not result

    elif attr == 'due_date':
        if operator == 'is_empty':     return task.due_date is None
        if operator == 'is_not_empty': return task.due_date is not None
        if operator == 'is_overdue':
            return task.due_date is not None and task.due_date < tz.now().date()
        if operator == 'within_days':
            if not task.due_date:
                return False
            try:
                days = int(value or 0)
            except (TypeError, ValueError):
                return False
            return 0 <= (task.due_date - tz.now().date()).days <= days

    elif attr == 'stale_high_priority':
        if task.priority not in ('high', 'urgent'):
            result = False
        elif hasattr(task, 'updated_at') and task.updated_at:
            result = task.updated_at < tz.now() - tz.timedelta(days=7)
        else:
            result = False
        if operator == 'is_true':  return result
        if operator == 'is_false': return not result

    return False


def _execute_action_flat(action, task, rule):
    """
    Execute a single action dict from rule.actions / rule.otherwise_actions.
    action = {"type": "set_priority", "target": "Urgent", "message": null}
    """
    from django.utils import timezone as tz
    from django.db.models import Q
    from kanban.models import Task as TaskModel

    VALID_PRIORITIES = {'low', 'medium', 'high', 'urgent'}
    action_type = action.get('type', '')
    target = action.get('target') or ''
    message = action.get('message') or ''

    board = task.column.board if task.column_id else None

    if action_type == 'set_priority':
        prio = target.lower()
        if prio in VALID_PRIORITIES:
            TaskModel.objects.filter(pk=task.pk).update(priority=prio)

    elif action_type == 'add_label':
        from kanban.models import TaskLabel
        if board and target:
            label = TaskLabel.objects.filter(board=board, name__iexact=target).first()
            if label:
                task.labels.add(label)

    elif action_type == 'remove_label':
        from kanban.models import TaskLabel
        if board and target:
            label = TaskLabel.objects.filter(board=board, name__iexact=target).first()
            if label:
                task.labels.remove(label)

    elif action_type == 'assign_to_user':
        from django.contrib.auth.models import User as AuthUser
        target_lower = target.lower()
        if target_lower == 'task_assignee':
            pass  # already assigned — no-op
        elif target_lower == 'rule_creator':
            if rule.created_by:
                TaskModel.objects.filter(pk=task.pk).update(assigned_to=rule.created_by)
        elif target_lower == 'all_board_members':
            # Assign to each board member in turn (last-write wins; use notification instead)
            _send_notification_flat(task, rule, 'all_board_members', message)
            return
        else:
            # target is a user ID string
            try:
                user = AuthUser.objects.get(pk=int(target))
                TaskModel.objects.filter(pk=task.pk).update(assigned_to=user)
            except (AuthUser.DoesNotExist, ValueError, TypeError):
                raise ValueError(f"assign_to_user: user with id '{target}' not found")

    elif action_type == 'move_to_column':
        from kanban.models import Column
        if board and target:
            col = Column.objects.filter(board=board, name__icontains=target).exclude(
                pk=task.column_id
            ).order_by('position').first()
            if col:
                TaskModel.objects.filter(pk=task.pk).update(column=col)
            else:
                raise ValueError(f"move_to_column: no column matching '{target}' found on board")

    elif action_type == 'set_due_date':
        DUE_DATE_MAP = {
            'today': 0, 'in_2_days': 2, 'in_7_days': 7,
            'in_14_days': 14, 'in_30_days': 30,
        }
        days = DUE_DATE_MAP.get(target.lower())
        if days is None:
            try:
                days = int(target)
            except (TypeError, ValueError):
                raise ValueError(f"set_due_date: invalid target '{target}'")
        new_due = tz.now().date() + tz.timedelta(days=days)
        TaskModel.objects.filter(pk=task.pk).update(due_date=new_due)

    elif action_type == 'close_task':
        TaskModel.objects.filter(pk=task.pk).update(progress=100)

    elif action_type == 'send_notification':
        _send_notification_flat(task, rule, target, message)

    elif action_type == 'post_comment':
        from kanban.models import Comment
        if not rule.created_by:
            raise ValueError("post_comment: rule has no creator, cannot post comment")
        text = _substitute_vars(message or f'Automated comment by rule "{rule.name}".', task)
        Comment.objects.create(task=task, user=rule.created_by, content=text)

    elif action_type == 'log_time_entry':
        from kanban.budget_models import TimeEntry
        user = rule.created_by or task.assigned_to
        if not user:
            raise ValueError("log_time_entry: no user available (rule has no creator and task has no assignee)")
        try:
            hours = float(target or 1)
        except (TypeError, ValueError):
            raise ValueError(f"log_time_entry: invalid hours value '{target}'")
        TimeEntry.objects.create(
            task=task,
            user=user,
            hours=hours,
            notes=f'Auto-logged by automation "{rule.name}"',
        )


def _send_notification_flat(task, rule, target, message=''):
    """Send notification for a send_notification action in the new flat format."""
    try:
        from messaging.models import Notification
        from django.contrib.auth.models import User as AuthUser
        from django.urls import reverse

        board = task.column.board if task.column_id else None
        if not board:
            return

        if getattr(board, 'is_official_demo_board', False):
            return

        sender = rule.created_by or (board.created_by if board else None)
        if not sender:
            return

        try:
            task_url = reverse('task_detail', args=[task.id])
        except Exception:
            task_url = None

        target_lower = (target or '').lower()
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
            # target is a user ID
            try:
                u = AuthUser.objects.get(pk=int(target))
                recipients = [u]
            except (AuthUser.DoesNotExist, ValueError, TypeError):
                pass

        if not recipients:
            return

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
    except Exception:
        import logging
        logging.getLogger(__name__).exception('_send_notification_flat failed')


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
        elif operator == 'is':
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
        
        recalculate_branches_for_board.apply_async(
            args=[board_id],
            kwargs={'trigger_event': f'Task "{task_title}" completed'},
            countdown=5,  # 5-second delay to batch multiple completions
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


from django.db.models.signals import post_delete

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
        elif getattr(instance, 'progress', 0) == 100:
            # Task completed — positive signal
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


@receiver(post_delete, sender='kanban.Task')
def record_project_signal_on_task_delete(sender, instance, **kwargs):
    """
    When a task is deleted, record a scope-change signal.
    """
    try:
        board = instance.column.board if instance.column_id else None
        if board is None:
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
# Google Calendar sync — track due_date changes before save
# ---------------------------------------------------------------------------

@receiver(pre_save, sender=Task)
def track_due_date_change(sender, instance, **kwargs):
    """
    Store the old due_date on the instance so the post_save signal can decide
    whether to trigger a Calendar sync.
    """
    if instance.pk:
        try:
            old = Task.objects.get(pk=instance.pk)
            instance._old_due_date = old.due_date
        except Task.DoesNotExist:
            instance._old_due_date = None
    else:
        instance._old_due_date = None


@receiver(post_save, sender=Task)
def sync_due_date_to_google_calendar(sender, instance, created, **kwargs):
    """
    Queue a Celery task to sync this task's due_date to Google Calendar
    when the due_date has changed (or been set for the first time).

    Only fires when:
      - The task has an assigned user.
      - The due_date actually changed (or was just set on a new task).
      - The assigned user has an active GoogleCalendarToken with sync_enabled=True.
    """
    if not instance.assigned_to_id:
        return

    old_due_date = getattr(instance, '_old_due_date', None)
    new_due_date = instance.due_date

    due_date_changed = (created and new_due_date) or (old_due_date != new_due_date)
    if not due_date_changed:
        return

    try:
        from accounts.models import GoogleCalendarToken
        has_token = GoogleCalendarToken.objects.filter(
            user_id=instance.assigned_to_id, sync_enabled=True
        ).exists()
        if not has_token:
            return

        from accounts.tasks import sync_task_to_calendar
        try:
            # Dispatch asynchronously when a Celery worker is running.
            sync_task_to_calendar.delay(instance.pk)
        except Exception as celery_exc:
            # Celery / Redis not reachable — run synchronously so the calendar
            # event is created immediately (Daphne-only / no-worker setup).
            import logging
            logging.getLogger(__name__).info(
                f"sync_due_date_to_google_calendar: Celery unavailable "
                f"({celery_exc}), running synchronously for task {instance.pk}."
            )
            sync_task_to_calendar(instance.pk)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            f"sync_due_date_to_google_calendar: could not sync for task {instance.pk}: {exc}"
        )

