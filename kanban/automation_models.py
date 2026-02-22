"""
Simple trigger-based automation rules for Kanban boards.

Supported workflow:
  - Trigger: task_overdue  → fires when a task's due date has passed and progress < 100
  - Trigger: moved_to_column → fires when a task is moved to a column whose name contains
                                the trigger_value string (case-insensitive)

  - Action: set_priority   → changes task.priority to action_value (e.g., 'urgent')
  - Action: add_label      → adds the label matching action_value name to the task
"""
from django.db import models
from django.contrib.auth.models import User


class BoardAutomation(models.Model):
    TRIGGER_CHOICES = [
        ('task_overdue',     'Task becomes overdue (due date passed, not done)'),
        ('moved_to_column',  'Task moved to a column'),
    ]
    ACTION_CHOICES = [
        ('set_priority', 'Set priority'),
        ('add_label',    'Add label'),
    ]

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
