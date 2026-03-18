"""
Data migration for the Automation Engine Redesign.

1. Converts existing BoardAutomation records → AutomationRule
   (with auto-generated rule_definition JSON tree).
2. Converts existing ScheduledAutomation records → AutomationRule
   (with scheduled trigger type and auto-generated rule_definition).
3. Seeds 10 built-in AutomationTemplate records.
"""
import uuid
from django.db import migrations


# ── helpers ────────────────────────────────────────────────────

def _make_id():
    return str(uuid.uuid4())


def _build_simple_rule_definition(trigger_type, trigger_config, action_type, action_config):
    """Build a minimal two-block (trigger → action) rule_definition JSON tree."""
    action_block = {
        'id': _make_id(),
        'type': 'action',
        'block_type': action_type,
        'config': action_config,
        'children': [],
        'else_children': [],
    }
    trigger_block = {
        'id': _make_id(),
        'type': 'trigger',
        'block_type': trigger_type,
        'config': trigger_config,
        'children': [action_block],
        'else_children': [],
    }
    return trigger_block


def _build_condition_rule_definition(trigger_type, trigger_config,
                                     condition_type, condition_config,
                                     true_action_type, true_action_config,
                                     false_action_type=None, false_action_config=None):
    """Build a three-block (trigger → condition → action) tree, optionally with an else branch."""
    true_action = {
        'id': _make_id(),
        'type': 'action',
        'block_type': true_action_type,
        'config': true_action_config,
        'children': [],
        'else_children': [],
    }
    else_children = []
    if false_action_type:
        else_children.append({
            'id': _make_id(),
            'type': 'action',
            'block_type': false_action_type,
            'config': false_action_config or {},
            'children': [],
            'else_children': [],
        })
    condition_block = {
        'id': _make_id(),
        'type': 'condition',
        'block_type': condition_type,
        'config': condition_config,
        'children': [true_action],
        'else_children': else_children,
    }
    trigger_block = {
        'id': _make_id(),
        'type': 'trigger',
        'block_type': trigger_type,
        'config': trigger_config,
        'children': [condition_block],
        'else_children': [],
    }
    return trigger_block


def _build_multi_action_rule_definition(trigger_type, trigger_config,
                                        condition_type=None, condition_config=None,
                                        actions=None):
    """Build a tree with optional condition and multiple chained actions."""
    if actions is None:
        actions = []
    # Build action chain from last to first (children linking)
    action_blocks = []
    for act in actions:
        action_blocks.append({
            'id': _make_id(),
            'type': 'action',
            'block_type': act['type'],
            'config': act['config'],
            'children': [],
            'else_children': [],
        })
    # Chain actions: each action's children = [next action]
    for i in range(len(action_blocks) - 1):
        action_blocks[i]['children'] = [action_blocks[i + 1]]

    first_child = action_blocks[0] if action_blocks else None

    if condition_type:
        condition_block = {
            'id': _make_id(),
            'type': 'condition',
            'block_type': condition_type,
            'config': condition_config or {},
            'children': [first_child] if first_child else [],
            'else_children': [],
        }
        first_child = condition_block

    trigger_block = {
        'id': _make_id(),
        'type': 'trigger',
        'block_type': trigger_type,
        'config': trigger_config,
        'children': [first_child] if first_child else [],
        'else_children': [],
    }
    return trigger_block


# ── trigger-type mapping for ScheduledAutomation ───────────────

SCHEDULE_TYPE_TO_TRIGGER = {
    'daily': 'scheduled_daily',
    'weekly': 'scheduled_weekly',
    'monthly': 'scheduled_monthly',
}


# ── forward migration ─────────────────────────────────────────

def migrate_forward(apps, schema_editor):
    BoardAutomation = apps.get_model('kanban', 'BoardAutomation')
    ScheduledAutomation = apps.get_model('kanban', 'ScheduledAutomation')
    AutomationRule = apps.get_model('kanban', 'AutomationRule')
    AutomationTemplate = apps.get_model('kanban', 'AutomationTemplate')

    # ─── 1. Convert BoardAutomation → AutomationRule ───────────
    for ba in BoardAutomation.objects.all():
        trigger_config = {}
        if ba.trigger_value:
            trigger_config['value'] = ba.trigger_value

        action_config = {}
        if ba.action_value:
            action_config['value'] = ba.action_value

        rule_def = _build_simple_rule_definition(
            trigger_type=ba.trigger_type,
            trigger_config=trigger_config,
            action_type=ba.action_type,
            action_config=action_config,
        )

        AutomationRule.objects.create(
            board=ba.board,
            name=ba.name,
            is_active=ba.is_active,
            created_by=ba.created_by,
            trigger_type=ba.trigger_type,
            trigger_value=ba.trigger_value or '',
            action_type=ba.action_type,
            action_value=ba.action_value or '',
            rule_definition=rule_def,
            run_count=ba.run_count,
            last_run_at=ba.last_run_at,
        )

    # ─── 2. Convert ScheduledAutomation → AutomationRule ───────
    for sa in ScheduledAutomation.objects.select_related('periodic_task').all():
        trigger_type = SCHEDULE_TYPE_TO_TRIGGER.get(sa.schedule_type, 'scheduled_daily')

        trigger_config = {
            'time': sa.scheduled_time.strftime('%H:%M') if sa.scheduled_time else '',
        }
        if sa.scheduled_day is not None:
            trigger_config['day'] = sa.scheduled_day

        action_config = {}
        if sa.action_value:
            action_config['value'] = sa.action_value
        if sa.notify_target:
            action_config['notify_target'] = sa.notify_target
        if sa.task_filter and sa.task_filter != 'all':
            action_config['task_filter'] = sa.task_filter

        rule_def = _build_simple_rule_definition(
            trigger_type=trigger_type,
            trigger_config=trigger_config,
            action_type=sa.action,
            action_config=action_config,
        )

        AutomationRule.objects.create(
            board=sa.board,
            name=sa.name,
            is_active=sa.is_active,
            created_by=sa.created_by,
            trigger_type=trigger_type,
            trigger_value='',
            action_type=sa.action,
            action_value=sa.action_value or '',
            rule_definition=rule_def,
            schedule_type=sa.schedule_type,
            scheduled_time=sa.scheduled_time,
            scheduled_day=sa.scheduled_day,
            notify_target=sa.notify_target or '',
            task_filter=sa.task_filter or 'all',
            periodic_task=sa.periodic_task,
            run_count=sa.run_count,
            failure_count=sa.failure_count,
            last_run_at=sa.last_run_at,
        )

    # ─── 3. Seed 10 built-in AutomationTemplate records ───────
    templates = [
        {
            'name': 'Mark overdue tasks as Urgent',
            'description': 'When a task becomes overdue, automatically set its priority to Urgent.',
            'category': 'task_management',
            'trigger_type': 'task_overdue',
            'rule_definition': _build_simple_rule_definition(
                'task_overdue', {},
                'set_priority', {'value': 'urgent'},
            ),
        },
        {
            'name': 'Notify creator on completion',
            'description': 'When a task is moved to the done column, send a notification to the task creator.',
            'category': 'notifications',
            'trigger_type': 'task_completed',
            'rule_definition': _build_simple_rule_definition(
                'task_completed', {},
                'send_notification', {'notify_target': 'creator'},
            ),
        },
        {
            'name': 'Alert assignee 2 days before deadline',
            'description': 'Every day, check if any task has a due date within 2 days and notify the assignee.',
            'category': 'deadlines',
            'trigger_type': 'scheduled_daily',
            'rule_definition': _build_condition_rule_definition(
                'scheduled_daily', {'time': '09:00'},
                'due_date_within', {'days': 2},
                'send_notification', {'notify_target': 'assignee'},
            ),
        },
        {
            'name': 'Auto-close when all sub-tasks done',
            'description': 'When a task is updated, check if all child tasks are complete and move the parent to the done column.',
            'category': 'task_management',
            'trigger_type': 'task_completed',
            'rule_definition': _build_condition_rule_definition(
                'task_completed', {},
                'all_children_complete', {},
                'close_task', {},
            ),
        },
        {
            'name': 'Daily overdue summary',
            'description': 'Every day at 9 AM, notify the board owner with a count of overdue tasks.',
            'category': 'scheduled',
            'trigger_type': 'scheduled_daily',
            'rule_definition': _build_simple_rule_definition(
                'scheduled_daily', {'time': '09:00'},
                'send_notification', {'notify_target': 'board_members', 'task_filter': 'overdue'},
            ),
        },
        {
            'name': 'Escalate high-priority stale tasks',
            'description': 'Every day, check for high-priority tasks with no updates in 3 days. Notify assignee and add a "Stale" label.',
            'category': 'task_management',
            'trigger_type': 'scheduled_daily',
            'rule_definition': _build_multi_action_rule_definition(
                'scheduled_daily', {'time': '09:00'},
                'stale_high_priority', {'days_stale': 3},
                actions=[
                    {'type': 'send_notification', 'config': {'notify_target': 'assignee'}},
                    {'type': 'add_label', 'config': {'value': 'Stale'}},
                ],
            ),
        },
        {
            'name': 'Welcome comment on task creation',
            'description': 'When a new task is created, automatically post a welcome comment prompting the user to assign an owner and set a due date.',
            'category': 'notifications',
            'trigger_type': 'task_created',
            'rule_definition': _build_simple_rule_definition(
                'task_created', {},
                'create_comment', {'text': 'Task created! Assign an owner and set a due date.'},
            ),
        },
        {
            'name': 'Move blocked tasks to review',
            'description': 'When a "Blocked" label is added to a task, move it to the "In Review" column and notify the creator.',
            'category': 'sprint',
            'trigger_type': 'task_assigned',
            'rule_definition': _build_multi_action_rule_definition(
                'task_assigned', {'label': 'Blocked'},
                actions=[
                    {'type': 'move_to_column', 'config': {'value': 'In Review'}},
                    {'type': 'send_notification', 'config': {'notify_target': 'creator'}},
                ],
            ),
        },
        {
            'name': 'Weekly team progress digest',
            'description': 'Every Friday at 5 PM, send a progress summary notification to all board members.',
            'category': 'scheduled',
            'trigger_type': 'scheduled_weekly',
            'rule_definition': _build_simple_rule_definition(
                'scheduled_weekly', {'time': '17:00', 'day': 4},
                'send_notification', {'notify_target': 'board_members'},
            ),
        },
        {
            'name': 'Auto-assign on column entry',
            'description': 'When a task is moved to the "In Progress" column and has no assignee, assign it to the rule owner.',
            'category': 'task_management',
            'trigger_type': 'moved_to_column',
            'rule_definition': _build_condition_rule_definition(
                'moved_to_column', {'value': 'In Progress'},
                'assignee_is', {'operator': 'is_empty'},
                'assign_to_user', {'value': '__rule_owner__'},
            ),
        },
    ]

    for tpl in templates:
        AutomationTemplate.objects.get_or_create(
            name=tpl['name'],
            defaults={
                'description': tpl['description'],
                'category': tpl['category'],
                'trigger_type': tpl['trigger_type'],
                'rule_definition': tpl['rule_definition'],
                'is_builtin': True,
            },
        )


def migrate_backward(apps, schema_editor):
    """
    Reverse: delete all AutomationRule and AutomationTemplate records
    that were created by the forward migration.  The original
    BoardAutomation and ScheduledAutomation records are untouched.
    """
    AutomationRule = apps.get_model('kanban', 'AutomationRule')
    AutomationTemplate = apps.get_model('kanban', 'AutomationTemplate')
    AutomationLog = apps.get_model('kanban', 'AutomationLog')

    AutomationLog.objects.all().delete()
    AutomationRule.objects.all().delete()
    AutomationTemplate.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('kanban', '0095_automation_engine_redesign_models'),
    ]

    operations = [
        migrations.RunPython(migrate_forward, migrate_backward),
    ]
