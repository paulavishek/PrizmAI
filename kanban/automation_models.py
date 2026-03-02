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
from django.db import models
from django.contrib.auth.models import User


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


class ScheduledAutomation(models.Model):
    """
    Time-based automation rules that fire on a recurring schedule
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