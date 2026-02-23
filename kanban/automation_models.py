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
