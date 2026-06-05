"""
Trigger-based automation rules for Kanban boards.

Triggers:
  task_overdue         → fires when a task's due date has passed and progress < 100
  moved_to_column      → fires when a task is moved to a column whose name contains trigger_value
  task_created         → fires when a task is created on this board
  task_completed       → fires when a task reaches 100% progress
  priority_changed     → fires when a task's priority changes to trigger_value (low/medium/high/urgent)
  task_assigned        → fires when a task is assigned to any team member
  due_date_approaching → fires (via scheduled task) when due_date is within trigger_value days

Actions:
  set_priority      → changes task.priority to action_value (low/medium/high/urgent)
  add_label         → adds the label matching action_value name to the task
  send_notification → notifies action_value recipients (assignee / board_members / creator)
  move_to_column    → moves the task to the column whose name contains action_value
  assign_to_user    → assigns the task to the user whose username == action_value
  set_due_date      → sets due_date = now + action_value days (int string)
"""
import uuid

from django.db import models
from django.contrib.auth.models import User


# ──────────────────────────────────────────────────────────────
# DEPRECATED — kept for rollback safety; migrate data to
# AutomationRule via 0095 data migration then remove in a
# future cleanup migration.
# ──────────────────────────────────────────────────────────────
class BoardAutomation(models.Model):
    TRIGGER_CHOICES = [
        ('task_overdue',         'Task becomes overdue (due date passed, not done)'),
        ('moved_to_column',      'Task moved to a column'),
        ('task_created',         'Task is created'),
        ('task_completed',       'Task is marked as complete / done (100%)'),
        ('priority_changed',     'Task priority changes to…'),
        ('task_assigned',        'Task is assigned to a team member'),
        ('due_date_approaching', 'Task due date is approaching (X days before)'),
    ]
    ACTION_CHOICES = [
        ('set_priority',      'Set priority'),
        ('add_label',         'Add label'),
        ('send_notification', 'Send notification'),
        ('move_to_column',    'Move task to column'),
        ('assign_to_user',    'Assign to a specific person'),
        ('set_due_date',      'Set due date (now + N days)'),
    ]

    # Triggers that require trigger_value
    TRIGGERS_WITH_VALUE = {'moved_to_column', 'priority_changed', 'due_date_approaching'}

    board = models.ForeignKey(
        'kanban.Board',
        on_delete=models.CASCADE,
        related_name='automations',
    )
    name = models.CharField(max_length=120, help_text="Short description, e.g. 'Mark overdue as Urgent'")

    # Trigger
    trigger_type = models.CharField(max_length=30, choices=TRIGGER_CHOICES)
    trigger_value = models.CharField(
        max_length=100,
        blank=True,
        help_text="For 'moved_to_column': the column name fragment to match (e.g. 'Review'). Leave blank for 'task_overdue'."
    )

    # Action
    action_type = models.CharField(max_length=30, choices=ACTION_CHOICES)
    action_value = models.CharField(
        max_length=100,
        help_text="For 'set_priority': one of low/medium/high/urgent. For 'add_label': exact label name."
    )

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_automations')
    created_at = models.DateTimeField(auto_now_add=True)
    run_count = models.IntegerField(default=0, help_text="Number of times this rule has fired")
    last_run_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.board.name})"


# ──────────────────────────────────────────────────────────────
# DEPRECATED — see deprecation notice on BoardAutomation above.
# ──────────────────────────────────────────────────────────────
class ScheduledAutomation(models.Model):
    """
    DEPRECATED — Time-based automation rules that fire on a recurring schedule
    (daily / weekly / monthly) rather than being triggered by task events.

    Each instance is linked to a django-celery-beat PeriodicTask that
    tells Celery Beat exactly when to fire.
    """

    SCHEDULE_TYPE_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    ACTION_CHOICES = [
        ('send_notification', 'Send Notification'),
        ('set_priority', 'Set Priority'),
    ]

    NOTIFY_TARGET_CHOICES = [
        ('assignee', 'Task Assignee'),
        ('board_members', 'All Board Members'),
        ('creator', 'Task Creator'),
    ]

    TASK_FILTER_CHOICES = [
        ('all', 'All Tasks'),
        ('overdue', 'Overdue Tasks'),
        ('incomplete', 'Incomplete Tasks'),
        ('high_priority', 'High Priority Tasks'),
    ]

    board = models.ForeignKey(
        'kanban.Board',
        on_delete=models.CASCADE,
        related_name='scheduled_automations',
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_scheduled_automations',
    )
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    # Schedule definition
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPE_CHOICES)
    scheduled_time = models.TimeField(help_text='Time of day to run (HH:MM)')
    scheduled_day = models.IntegerField(
        null=True,
        blank=True,
        help_text=(
            'For weekly: 0=Monday … 6=Sunday. '
            'For monthly: 1–28 (day of month). '
            'Leave null for daily.'
        ),
    )

    # Action definition
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    action_value = models.CharField(
        max_length=200,
        blank=True,
        help_text=(
            "For set_priority: 'urgent', 'high', 'medium', 'low'. "
            "For send_notification: custom notification message text (optional)."
        ),
    )
    notify_target = models.CharField(
        max_length=50,
        choices=NOTIFY_TARGET_CHOICES,
        default='board_members',
        help_text='Who receives the notification (only used for send_notification action).',
    )

    # Task filter – which tasks does this apply to
    task_filter = models.CharField(
        max_length=50,
        choices=TASK_FILTER_CHOICES,
        default='all',
    )

    # Celery Beat link
    periodic_task = models.OneToOneField(
        'django_celery_beat.PeriodicTask',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    # Tracking
    run_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.board.name})"

    def get_schedule_description(self):
        """Return a plain-English schedule description, e.g. 'Every Monday at 9:00 AM'."""
        time_str = self.scheduled_time.strftime('%I:%M %p').lstrip('0')
        if self.schedule_type == 'daily':
            return f"Every day at {time_str}"
        elif self.schedule_type == 'weekly':
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_name = day_names[self.scheduled_day] if self.scheduled_day is not None else '?'
            return f"Every {day_name} at {time_str}"
        elif self.schedule_type == 'monthly':
            day = self.scheduled_day or '?'
            # ordinal suffix
            if day in (1, 21):
                suffix = 'st'
            elif day in (2, 22):
                suffix = 'nd'
            elif day in (3, 23):
                suffix = 'rd'
            else:
                suffix = 'th'
            return f"Every month on the {day}{suffix} at {time_str}"
        return str(self.schedule_type)


# ══════════════════════════════════════════════════════════════
# NEW MODELS — Automation Engine Redesign (March 2026)
# ══════════════════════════════════════════════════════════════

class AutomationRule(models.Model):
    """
    Unified automation rule — replaces both BoardAutomation (trigger-based)
    and ScheduledAutomation (time-based).  The full flowchart is stored in
    ``rule_definition`` as a JSON block tree.  Legacy CharField fields
    (trigger_type, action_type etc.) are kept for backward compatibility
    with rules migrated from the old models.
    """

    # ── trigger groups (seven-group UI taxonomy) ───────────────
    # Each entry: (group_name, [(value, label), ...])
    # The template iterates this to render <optgroup> blocks.
    TRIGGER_GROUPS = [
        ('Task State', [
            ('task_created',              'Task is created'),
            ('task_completed',            'Task is completed'),
            ('task_assigned',             'Task is assigned'),
            ('task_unassigned',           'Task is unassigned'),
            ('task_moved_to_column',      'Task is moved to a column'),
            ('task_status_changed',       'Task status (column) changed'),
            ('task_priority_changed',     'Task priority changes'),
            ('task_progress_changed',     'Task progress changed'),
            ('task_description_updated',  'Task description updated'),
            ('task_due_date_changed',     'Task due date changed'),
            ('task_label_added',          'Task label added'),
        ]),
        ('Time & Activity', [
            ('task_overdue',              'Task becomes overdue'),
            ('task_idle',                 'Task is idle (no updates for N days)'),
            ('task_start_date_reached',   'Task start date reached'),
            ('task_completion_threshold', 'Completion threshold reached'),
            ('due_date_approaching',      'Due date is approaching'),
        ]),
        ('AI & Risk', [
            ('risk_level_changed',        'Risk level changed'),
            ('risk_level_critical',       'Risk level becomes critical'),
            ('predicted_late',            'Predicted to miss due date'),
            ('schedule_status_changed',   'Schedule status changed'),
            ('complexity_increased',      'Complexity increased'),
        ]),
        ('Hierarchy & Dependencies', [
            ('subtask_completed',         'A subtask completed'),
            ('all_subtasks_completed',    'All subtasks completed'),
            ('dependency_completed',      'A blocking dependency completed'),
            ('dependency_overdue',        'A blocking dependency became overdue'),
            ('checklist_completed',       'Checklist fully completed'),
            ('checklist_item_added',      'Checklist item added'),
            ('milestone_reached',         'Milestone reached'),
            ('parent_status_changed',     'Parent task status changed'),
        ]),
        ('AI Tools & Platform', [
            ('coach_suggestion_created',  'AI Coach suggestion created'),
            ('conflict_detected',         'Conflict detected'),
            ('discovery_idea_scored',     'Discovery idea AI-scored'),
            ('discovery_idea_submitted',  'Discovery idea submitted'),
            # Deferred — no receiver wired yet; hidden from the builder until
            # implemented (see automation audit, June 2026):
            #   immunity_score_dropped, hospice_risk_triggered,
            #   scope_creep_detected, prediction_confidence_dropped,
            #   retrospective_finalized
        ]),
        ('Communications', [
            ('comment_added',             'Comment added to a task'),
            ('mention_received',          'Assignee was @-mentioned'),
            ('attachment_added',          'Attachment added to a task'),
            # Deferred — task_thread_message has no receiver yet; hidden.
        ]),
        ('Scheduled', [
            ('scheduled_daily',           'Every day at a set time'),
            ('scheduled_weekly',          'Every week on a set day'),
            ('scheduled_monthly',         'Every month on a set date'),
        ]),
    ]

    ACTION_GROUPS = [
        ('Task State', [
            ('set_priority',             'Set priority'),
            ('set_progress',             'Set progress %'),
            ('set_description',          'Set description'),
            ('append_to_description',    'Append to description'),
            ('add_label',                'Add label'),
            ('remove_label',             'Remove label'),
            ('assign_to_user',           'Assign to user'),
            ('clear_assignee',           'Clear assignee'),
            ('move_to_column',           'Move to column'),
            ('set_due_date',             'Set due date'),
            ('set_start_date',           'Set start date'),
            ('clear_due_date',           'Clear due date'),
            ('close_task',               'Close task'),
        ]),
        ('AI & Risk', [
            ('set_risk_level',           'Set risk level'),
            ('request_ai_analysis',      'Request AI analysis'),
            ('flag_for_review',          'Flag for review'),
            ('add_risk_indicator',       'Add risk indicator'),
            ('add_mitigation_strategy',  'Add mitigation strategy'),
        ]),
        ('Hierarchy & Dependencies', [
            ('cascade_due_date',         'Cascade due date to subtasks'),
            ('cascade_priority',         'Cascade priority to subtasks'),
            ('assign_subtasks_to',       'Assign all subtasks'),
            ('complete_parent_if_all_subtasks_done',
                                          'Complete parent if all subtasks done'),
            ('notify_blocked_tasks',     'Notify tasks blocked by this one'),
            ('auto_check_checklist',     'Auto-check a checklist item'),
            ('add_checklist_item',       'Add a checklist item'),
            ('add_subtask',              'Add a subtask'),
        ]),
        ('Resources & Workload', [
            ('set_workload_impact',      'Set workload impact'),
            ('set_estimated_hours',      'Set estimated hours'),
            ('set_estimated_cost',       'Set estimated cost'),
            ('assign_to_best_skill_match', 'Assign to best skill match'),
            ('assign_to_lightest_workload', 'Assign to lightest workload'),
            ('add_required_skill',       'Add required skill'),
            ('escalate_to_owner',        'Escalate to board owner'),
        ]),
        ('AI Tools & Platform', [
            ('acknowledge_coach_suggestion', 'Acknowledge coach suggestion'),
            ('resolve_conflict',         'Mark conflict resolved'),
            ('promote_discovery_idea',   'Promote discovery idea to task'),
            ('apply_stress_test_vaccine','Apply stress-test vaccine'),
            ('create_memory_node',       'Create memory-graph node'),
            ('generate_status_report',   'Generate PrizmBrief status report'),
            ('add_stakeholder_engagement', 'Log stakeholder engagement'),
        ]),
        ('Communications & Memory', [
            ('send_notification',        'Send notification'),
            ('notify_stakeholders',      'Notify all stakeholders'),
            ('mention_users_in_comment', 'Mention users in a comment'),
            ('start_task_thread',        'Start a task thread'),
            ('link_wiki_page',           'Link an existing wiki page'),
            ('create_wiki_page',         'Create a new wiki page'),
            ('capture_decision',         'Capture decision as memory node'),
            ('capture_lesson',           'Capture lesson as memory node'),
            ('post_comment',             'Post a comment'),
            ('log_time_entry',           'Log time entry'),
        ]),
    ]

    # ── trigger choices ────────────────────────────────────────
    # Grouped per the seven-group UI taxonomy. The Python order also drives
    # the order of options in templates that iterate the choices directly.
    TRIGGER_CHOICES = [
        # ── Task State ─────────────────────────────────────────
        ('task_created',              'Task is created'),
        ('task_completed',            'Task is completed'),
        ('task_assigned',             'Task is assigned'),
        ('task_unassigned',           'Task is unassigned'),
        ('task_moved_to_column',      'Task is moved to a column'),
        ('task_status_changed',       'Task status (column) changed'),
        ('task_priority_changed',     'Task priority changes'),
        ('task_progress_changed',     'Task progress changed'),
        ('task_description_updated',  'Task description updated'),
        ('task_due_date_changed',     'Task due date changed'),
        ('task_label_added',          'Task label added'),
        # ── Time & Activity ────────────────────────────────────
        ('task_overdue',              'Task becomes overdue'),
        ('task_idle',                 'Task is idle (no updates for N days)'),
        ('task_start_date_reached',   'Task start date reached'),
        ('task_completion_threshold', 'Completion threshold reached'),
        ('due_date_approaching',      'Due date is approaching'),
        # ── AI & Risk ──────────────────────────────────────────
        ('risk_level_changed',        'Risk level changed'),
        ('risk_level_critical',       'Risk level becomes critical'),
        ('predicted_late',            'Predicted to miss due date'),
        ('schedule_status_changed',   'Schedule status changed (late/at-risk/on-track)'),
        ('complexity_increased',      'Complexity increased'),
        # ── Hierarchy & Dependencies ───────────────────────────
        ('subtask_completed',         'A subtask completed'),
        ('all_subtasks_completed',    'All subtasks completed'),
        ('dependency_completed',      'A blocking dependency completed'),
        ('dependency_overdue',        'A blocking dependency became overdue'),
        ('checklist_completed',       'Checklist fully completed'),
        ('checklist_item_added',      'Checklist item added'),
        ('milestone_reached',         'Milestone reached'),
        ('parent_status_changed',     'Parent task status changed'),
        # ── AI Tools & Platform ────────────────────────────────
        ('coach_suggestion_created',  'AI Coach suggestion created'),
        ('conflict_detected',         'Conflict detected'),
        ('discovery_idea_scored',     'Discovery idea AI-scored'),
        ('discovery_idea_submitted',  'Discovery idea submitted'),
        # Deferred triggers (no receiver wired) are intentionally omitted from
        # the selectable choices: immunity_score_dropped, hospice_risk_triggered,
        # scope_creep_detected, prediction_confidence_dropped,
        # retrospective_finalized, task_thread_message.
        # ── Communications ─────────────────────────────────────
        ('comment_added',             'Comment added to a task'),
        ('mention_received',          'Assignee was @-mentioned'),
        ('attachment_added',          'Attachment added to a task'),
        # ── Schedule-based ─────────────────────────────────────
        ('scheduled_daily',           'Every day at a set time'),
        ('scheduled_weekly',          'Every week on a set day'),
        ('scheduled_monthly',         'Every month on a set date'),
    ]

    # ── action choices ─────────────────────────────────────────
    ACTION_CHOICES = [
        # ── Task State ─────────────────────────────────────────
        ('set_priority',          'Set priority'),
        ('set_progress',          'Set progress %'),
        ('set_description',       'Set description'),
        ('append_to_description', 'Append to description'),
        ('add_label',             'Add label'),
        ('remove_label',          'Remove label'),
        ('assign_to_user',        'Assign to user'),
        ('clear_assignee',        'Clear assignee'),
        ('move_to_column',        'Move to column'),
        ('set_due_date',          'Set due date'),
        ('set_start_date',        'Set start date'),
        ('clear_due_date',        'Clear due date'),
        ('close_task',            'Close task'),
        # ── AI & Risk ──────────────────────────────────────────
        ('set_risk_level',        'Set risk level'),
        ('request_ai_analysis',   'Request AI analysis'),
        ('flag_for_review',       'Flag for review'),
        ('add_risk_indicator',    'Add risk indicator'),
        ('add_mitigation_strategy', 'Add mitigation strategy'),
        # ── Hierarchy & Dependencies ───────────────────────────
        ('cascade_due_date',      'Cascade due date to subtasks'),
        ('cascade_priority',      'Cascade priority to subtasks'),
        ('assign_subtasks_to',    'Assign all subtasks'),
        ('complete_parent_if_all_subtasks_done',
                                  'Complete parent if all subtasks done'),
        ('notify_blocked_tasks',  'Notify tasks blocked by this one'),
        ('auto_check_checklist',  'Auto-check a checklist item'),
        ('add_checklist_item',    'Add a checklist item'),
        ('add_subtask',           'Add a subtask'),
        # ── Resource, Cost & Workload ──────────────────────────
        ('set_workload_impact',   'Set workload impact'),
        ('set_estimated_hours',   'Set estimated hours'),
        ('set_estimated_cost',    'Set estimated cost'),
        ('assign_to_best_skill_match', 'Assign to best skill match'),
        ('assign_to_lightest_workload', 'Assign to lightest workload'),
        ('add_required_skill',    'Add required skill'),
        ('escalate_to_owner',     'Escalate to board owner'),
        # ── AI Tools & Platform ────────────────────────────────
        ('acknowledge_coach_suggestion', 'Acknowledge coach suggestion'),
        ('resolve_conflict',      'Mark conflict resolved'),
        ('promote_discovery_idea','Promote discovery idea to task'),
        ('apply_stress_test_vaccine', 'Apply stress-test vaccine'),
        ('create_memory_node',    'Create memory-graph node'),
        ('generate_status_report','Generate PrizmBrief status report'),
        ('add_stakeholder_engagement', 'Log stakeholder engagement'),
        # ── Communications & Memory ────────────────────────────
        ('send_notification',     'Send notification'),
        ('notify_stakeholders',   'Notify all stakeholders'),
        ('mention_users_in_comment', 'Mention users in a comment'),
        ('start_task_thread',     'Start a task thread'),
        ('link_wiki_page',        'Link an existing wiki page'),
        ('create_wiki_page',      'Create a new wiki page'),
        ('capture_decision',      'Capture decision as memory node'),
        ('capture_lesson',        'Capture lesson as memory node'),
        ('post_comment',          'Post a comment'),
        ('log_time_entry',        'Log time entry'),
    ]

    # ── core fields ────────────────────────────────────────────
    board = models.ForeignKey(
        'kanban.Board',
        on_delete=models.CASCADE,
        related_name='automation_rules',
    )
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='automation_rules_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── trigger ────────────────────────────────────────────────
    trigger_type = models.CharField(
        max_length=30, choices=TRIGGER_CHOICES,
        blank=True, default='',
    )
    trigger_config = models.JSONField(
        default=dict,
        help_text=(
            'Trigger-specific parameters. '
            'Examples: task_moved_to_column: {"column_name": "Review"}, '
            'due_date_approaching: {"days": 2}, '
            'scheduled_daily: {"time": "09:00"}, '
            'scheduled_weekly: {"day": "Monday", "time": "09:00"}'
        ),
    )

    # ── conditions (IF section) ────────────────────────────────
    condition_logic = models.CharField(
        max_length=3,
        choices=[('AND', 'AND'), ('OR', 'OR')],
        default='AND',
    )
    conditions = models.JSONField(
        default=list,
        help_text='[{"attribute": "priority", "operator": "is", "value": "Urgent"}, ...]',
    )

    # ── actions (THEN section) ─────────────────────────────────
    actions = models.JSONField(
        default=list,
        help_text='[{"type": "set_priority", "target": "Urgent", "message": null}, ...]',
    )

    # ── else branch (OTHERWISE section) ───────────────────────
    otherwise_actions = models.JSONField(
        default=list,
        help_text='Same format as actions. Empty list = no else branch.',
    )

    # ── legacy fields (deprecated — kept for backward compat) ──
    trigger_value = models.CharField(max_length=200, blank=True, default='')
    action_type = models.CharField(max_length=30, blank=True, default='')
    action_value = models.CharField(max_length=200, blank=True, default='')
    rule_definition = models.JSONField(blank=True, null=True)

    # ── schedule fields (carried from ScheduledAutomation) ─────
    schedule_type = models.CharField(
        max_length=20, blank=True, default='',
        choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')],
    )
    scheduled_time = models.TimeField(null=True, blank=True)
    scheduled_day = models.IntegerField(null=True, blank=True)
    notify_target = models.CharField(max_length=50, blank=True, default='')
    task_filter = models.CharField(max_length=50, blank=True, default='all')
    periodic_task = models.OneToOneField(
        'django_celery_beat.PeriodicTask',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='automation_rule',
    )

    # ── tracking ───────────────────────────────────────────────
    run_count = models.IntegerField(default=0)
    failure_count = models.IntegerField(default=0)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_execution_result = models.CharField(
        max_length=10, null=True, blank=True,
        # values: 'success', 'skipped', 'failed'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['board', 'is_active', 'trigger_type']),
        ]

    def __str__(self):
        return f"{self.name} ({self.board.name})"

    def get_schedule_description(self):
        """Return a plain-English schedule description."""
        if not self.scheduled_time:
            return ''
        time_str = self.scheduled_time.strftime('%I:%M %p').lstrip('0')
        if self.schedule_type == 'daily':
            return f"Every day at {time_str}"
        elif self.schedule_type == 'weekly':
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                         'Friday', 'Saturday', 'Sunday']
            day_name = day_names[self.scheduled_day] if self.scheduled_day is not None else '?'
            return f"Every {day_name} at {time_str}"
        elif self.schedule_type == 'monthly':
            day = self.scheduled_day or '?'
            if day in (1, 21):
                suffix = 'st'
            elif day in (2, 22):
                suffix = 'nd'
            elif day in (3, 23):
                suffix = 'rd'
            else:
                suffix = 'th'
            return f"Every month on the {day}{suffix} at {time_str}"
        return ''


class AutomationLog(models.Model):
    """
    Audit trail for every automation rule execution.
    Written by the Celery worker and signal handler when a rule fires.
    Entries older than 90 days are purged by a scheduled cleanup task.
    """
    OUTCOME_CHOICES = [
        ('success', 'Success'),
        ('skipped', 'Skipped'),
        ('failed',  'Failed'),
    ]

    rule = models.ForeignKey(
        AutomationRule,
        on_delete=models.SET_NULL,
        null=True,
        related_name='logs',
    )
    rule_name_snapshot = models.CharField(max_length=120, blank=True)
    board = models.ForeignKey(
        'kanban.Board',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='automation_logs',
    )
    triggered_at = models.DateTimeField(auto_now_add=True, db_index=True)
    trigger_event = models.CharField(max_length=100)
    task_affected = models.ForeignKey(
        'kanban.Task',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='automation_logs',
    )
    task_title_snapshot = models.CharField(max_length=255, blank=True)
    actions_summary = models.TextField(blank=True)
    outcome = models.CharField(
        max_length=10,
        choices=OUTCOME_CHOICES,
        db_index=True,
    )
    skip_reason = models.CharField(max_length=100, blank=True)
    error_detail = models.TextField(blank=True)
    execution_detail = models.JSONField(default=dict)

    # Idempotency key for one logical rule emission. Formatted as
    # "<rule_id>:<task_id>:<trigger_event>:<assignee_id>:<time_bucket>" by the
    # signal runner (kanban/signals.py). The unique constraint below lets two
    # *concurrent* duplicate emissions — e.g. a frontend double-submit that
    # sends the same POST twice in the same instant — collapse to a single rule
    # run: both pass the in-memory and short-window checks because neither has
    # committed its log yet, but only one INSERT can win the constraint. Null
    # for legacy rows and for any fire where the key could not be computed.
    dedupe_key = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        ordering = ['-triggered_at']
        indexes = [
            models.Index(fields=['board', 'triggered_at']),
            models.Index(fields=['rule', 'triggered_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['dedupe_key'],
                condition=models.Q(dedupe_key__isnull=False),
                name='uniq_automationlog_dedupe_key',
            ),
        ]

    def __str__(self):
        rule_name = self.rule.name if self.rule else (self.rule_name_snapshot or 'Deleted rule')
        return f"{rule_name} — {self.outcome} @ {self.triggered_at:%Y-%m-%d %H:%M}"


class AutomationTemplate(models.Model):
    """
    Pre-built automation rule templates.  Ten built-in templates are
    seeded by a data migration.  Each template stores a ``rule_definition``
    JSON tree identical in format to AutomationRule.rule_definition.
    """
    CATEGORY_CHOICES = [
        ('task_management', 'Task Management'),
        ('notifications',   'Notifications'),
        ('deadlines',        'Deadlines'),
        ('sprint',           'Sprint'),
        ('scheduled',        'Scheduled'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    trigger_type = models.CharField(max_length=30)
    trigger_config = models.JSONField(default=dict)
    condition_logic = models.CharField(max_length=3, default='AND')
    conditions = models.JSONField(default=list)
    actions = models.JSONField(default=list)
    rule_definition = models.JSONField(
        null=True, blank=True,
        help_text='Deprecated canvas block tree — kept for rollback safety.',
    )
    is_builtin = models.BooleanField(default=False)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return self.name