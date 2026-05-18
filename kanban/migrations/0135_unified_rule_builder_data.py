"""
Data migration for the Unified Rule Builder redesign.

1. Rename trigger types in all AutomationRule records to new internal names.
2. Rename action type create_comment → post_comment in all AutomationRule records.
3. Populate trigger_config from trigger_value / schedule fields.
4. Populate actions array from action_type + action_value.
5. Rename AutomationLog outcomes: 'passed' → 'success'.
6. Populate rule_name_snapshot on existing AutomationLog records.
7. Populate board FK on AutomationLog via rule → board.
8. Reseed the 10 built-in AutomationTemplate records with new flat format.
"""

from django.db import migrations


TRIGGER_RENAMES = {
    'moved_to_column':       'task_moved_to_column',
    'priority_changed':      'task_priority_changed',
    'task_completion_reached': 'task_completion_threshold',
}

ACTION_RENAMES = {
    'create_comment': 'post_comment',
}

# 10 built-in templates in new flat format
BUILTIN_TEMPLATES = [
    {
        'name': 'Alert assignee 2 days before deadline',
        'description': 'Sends a notification to the task assignee 2 days before the due date.',
        'category': 'deadlines',
        'trigger_type': 'due_date_approaching',
        'trigger_config': {'days': 2},
        'condition_logic': 'AND',
        'conditions': [],
        'actions': [
            {'type': 'send_notification', 'target': 'task_assignee',
             'message': 'Task {task_title} is due in 2 days.'},
        ],
    },
    {
        'name': 'Notify creator on completion',
        'description': 'Notifies the rule creator when any task on this board is completed.',
        'category': 'notifications',
        'trigger_type': 'task_completed',
        'trigger_config': {},
        'condition_logic': 'AND',
        'conditions': [],
        'actions': [
            {'type': 'send_notification', 'target': 'rule_creator',
             'message': 'Task {task_title} has been completed.'},
        ],
    },
    {
        'name': 'Welcome comment on task creation',
        'description': 'Posts a welcome comment whenever a new task is created.',
        'category': 'notifications',
        'trigger_type': 'task_created',
        'trigger_config': {},
        'condition_logic': 'AND',
        'conditions': [],
        'actions': [
            {'type': 'post_comment', 'target': None,
             'message': 'Welcome to this task, {task_assignee}! Check the description for details.'},
        ],
    },
    {
        'name': 'Daily overdue summary',
        'description': 'Sends a daily notification to all board members listing overdue tasks.',
        'category': 'scheduled',
        'trigger_type': 'scheduled_daily',
        'trigger_config': {'time': '09:00'},
        'condition_logic': 'AND',
        'conditions': [],
        'actions': [
            {'type': 'send_notification', 'target': 'all_board_members',
             'message': 'Daily reminder: check overdue tasks on {board_name}.'},
        ],
    },
    {
        'name': 'Weekly team progress digest',
        'description': 'Sends a weekly progress notification to all board members every Monday.',
        'category': 'scheduled',
        'trigger_type': 'scheduled_weekly',
        'trigger_config': {'day': 'Monday', 'time': '09:00'},
        'condition_logic': 'AND',
        'conditions': [],
        'actions': [
            {'type': 'send_notification', 'target': 'all_board_members',
             'message': 'Weekly digest: review progress on {board_name} for this week.'},
        ],
    },
    {
        'name': 'Move blocked tasks to review',
        'description': 'Moves a task to the Review column when it is assigned to a team member.',
        'category': 'sprint',
        'trigger_type': 'task_assigned',
        'trigger_config': {},
        'condition_logic': 'AND',
        'conditions': [],
        'actions': [
            {'type': 'move_to_column', 'target': 'Review', 'message': None},
        ],
    },
    {
        'name': 'Auto-assign on column entry',
        'description': 'Sends a notification to all board members when a task moves to a column.',
        'category': 'task_management',
        'trigger_type': 'task_moved_to_column',
        'trigger_config': {},
        'condition_logic': 'AND',
        'conditions': [],
        'actions': [
            {'type': 'send_notification', 'target': 'all_board_members',
             'message': 'Task {task_title} has moved columns on {board_name}.'},
        ],
    },
    {
        'name': 'Auto-close when all sub-tasks done',
        'description': 'Closes the task automatically when all its subtasks are completed.',
        'category': 'task_management',
        'trigger_type': 'task_completion_threshold',
        'trigger_config': {'threshold': 100},
        'condition_logic': 'AND',
        'conditions': [
            {'attribute': 'all_subtasks_done', 'operator': 'is_true', 'value': None},
        ],
        'actions': [
            {'type': 'close_task', 'target': None, 'message': None},
        ],
    },
    {
        'name': 'Escalate high-priority stale tasks',
        'description': 'Sends a daily notification for high-priority tasks that have not been updated recently.',
        'category': 'task_management',
        'trigger_type': 'scheduled_daily',
        'trigger_config': {'time': '08:00'},
        'condition_logic': 'AND',
        'conditions': [
            {'attribute': 'priority', 'operator': 'is', 'value': 'Urgent'},
            {'attribute': 'stale_high_priority', 'operator': 'is_true', 'value': None},
        ],
        'actions': [
            {'type': 'send_notification', 'target': 'all_board_members',
             'message': 'Stale high-priority task: {task_title} on {board_name} needs attention.'},
        ],
    },
    {
        'name': 'Mark overdue tasks as Urgent',
        'description': 'Sets the priority to Urgent when a task becomes overdue.',
        'category': 'task_management',
        'trigger_type': 'task_overdue',
        'trigger_config': {},
        'condition_logic': 'AND',
        'conditions': [],
        'actions': [
            {'type': 'set_priority', 'target': 'Urgent', 'message': None},
        ],
    },
]


def migrate_rules_and_logs(apps, schema_editor):
    AutomationRule = apps.get_model('kanban', 'AutomationRule')
    AutomationLog = apps.get_model('kanban', 'AutomationLog')

    # 1. Rename trigger types
    for old_name, new_name in TRIGGER_RENAMES.items():
        AutomationRule.objects.filter(trigger_type=old_name).update(trigger_type=new_name)

    # 2. Rename action type
    for old_name, new_name in ACTION_RENAMES.items():
        AutomationRule.objects.filter(action_type=old_name).update(action_type=new_name)

    # 3 & 4. Populate trigger_config and actions from legacy flat fields
    for rule in AutomationRule.objects.all():
        changed = False

        # Populate trigger_config if not already set
        if not rule.trigger_config:
            tt = rule.trigger_type
            tv = rule.trigger_value or ''
            if tt == 'task_moved_to_column' and tv:
                rule.trigger_config = {'column_name': tv}
                changed = True
            elif tt == 'due_date_approaching' and tv:
                try:
                    rule.trigger_config = {'days': int(tv)}
                    changed = True
                except (ValueError, TypeError):
                    pass
            elif tt == 'task_priority_changed' and tv:
                rule.trigger_config = {'priority': tv}
                changed = True
            elif tt == 'task_completion_threshold' and tv:
                try:
                    rule.trigger_config = {'threshold': int(tv)}
                    changed = True
                except (ValueError, TypeError):
                    pass
            elif tt == 'scheduled_daily' and rule.scheduled_time:
                rule.trigger_config = {'time': rule.scheduled_time.strftime('%H:%M')}
                changed = True
            elif tt == 'scheduled_weekly' and rule.scheduled_time:
                day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                             'Friday', 'Saturday', 'Sunday']
                day_name = day_names[rule.scheduled_day] if rule.scheduled_day is not None else 'Monday'
                rule.trigger_config = {
                    'time': rule.scheduled_time.strftime('%H:%M'),
                    'day': day_name,
                }
                changed = True
            elif tt == 'scheduled_monthly' and rule.scheduled_time:
                rule.trigger_config = {
                    'time': rule.scheduled_time.strftime('%H:%M'),
                    'day_of_month': rule.scheduled_day or 1,
                }
                changed = True

        # Populate actions if not already set and action_type exists
        if not rule.actions and rule.action_type:
            rule.actions = [{
                'type': rule.action_type,
                'target': rule.action_value or None,
                'message': None,
            }]
            changed = True

        if changed:
            rule.save(update_fields=['trigger_config', 'actions'])

    # 5. Rename AutomationLog outcomes: 'passed' → 'success'
    AutomationLog.objects.filter(outcome='passed').update(outcome='success')

    # 6 & 7. Populate rule_name_snapshot and board FK on AutomationLog
    for log in AutomationLog.objects.filter(rule__isnull=False).select_related('rule__board'):
        changed = False
        if not log.rule_name_snapshot and log.rule:
            log.rule_name_snapshot = log.rule.name
            changed = True
        if log.board_id is None and log.rule and log.rule.board_id:
            log.board_id = log.rule.board_id
            changed = True
        if changed:
            log.save(update_fields=['rule_name_snapshot', 'board_id'])


def reseed_templates(apps, schema_editor):
    AutomationTemplate = apps.get_model('kanban', 'AutomationTemplate')
    AutomationTemplate.objects.filter(is_builtin=True).delete()
    for tpl in BUILTIN_TEMPLATES:
        AutomationTemplate.objects.create(
            name=tpl['name'],
            description=tpl['description'],
            category=tpl['category'],
            trigger_type=tpl['trigger_type'],
            trigger_config=tpl['trigger_config'],
            condition_logic=tpl['condition_logic'],
            conditions=tpl['conditions'],
            actions=tpl['actions'],
            rule_definition=None,
            is_builtin=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('kanban', '0134_unified_rule_builder_schema'),
    ]

    operations = [
        migrations.RunPython(migrate_rules_and_logs, migrations.RunPython.noop),
        migrations.RunPython(reseed_templates, migrations.RunPython.noop),
    ]
