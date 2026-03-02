I want to add a new feature to PrizmAI called "Scheduled Automations." 
This extends the existing automation system to support time-based rules 
that fire on a recurring schedule set by the user, rather than being 
triggered by task events.

Before writing any code, read the entire prompt carefully and confirm 
you understand it before starting.

---

## UNDERSTAND THE EXISTING AUTOMATION SYSTEM FIRST

Before touching anything, read and understand these files:
- kanban/automation_models.py (BoardAutomation model)
- kanban/automation_views.py (existing automation creation and validation logic)
- kanban/signals.py (run_board_automations and _apply_automation_action)
- kanban/tasks/automation_tasks.py (existing Celery scheduled task for due_date_approaching)
- celery.py or celery_config.py (existing Celery Beat schedule configuration)
- requirements.txt (check if django-celery-beat is already installed)

The existing automation system has two types of triggers:
1. Immediate triggers - fire on task save via Django signals (signals.py)
2. Time-based trigger - due_date_approaching fires via a Celery Beat job hourly

You are extending type 2. Do NOT touch type 1 at all.

---

## WHAT YOU ARE BUILDING

Users can create automation rules that fire on a recurring schedule:
- Daily at a specific time (e.g. every day at 9:00 AM)
- Weekly on a specific day and time (e.g. every Monday at 8:00 AM)
- Monthly on a specific date and time (e.g. 1st of every month at 9:00 AM)

These rules are not triggered by anything happening to a task. 
They fire purely based on the clock.

---

## SCOPE LIMITS - STRICTLY FOLLOW THESE

Version 1 supports ONLY these three schedule patterns:
- Daily at [time]
- Weekly on [day] at [time]
- Monthly on [date] at [time]

Do NOT build:
- Custom cron expressions
- Hourly schedules
- One-time scheduled actions (not recurring)
- Any schedule pattern beyond the three above

Version 1 supports ONLY these actions when a schedule fires:
- send_notification: send a summary notification to board members, 
  assignees, or creators about tasks matching a filter
- set_priority: change priority on all tasks matching a filter

Do NOT build any new action types beyond these two for version 1.

---

## DATABASE: CHECK django-celery-beat FIRST

Check requirements.txt to see if django-celery-beat is already installed.

If NOT installed:
1. Add django-celery-beat to requirements.txt
2. Install it: pip install django-celery-beat
3. Add 'django_celery_beat' to INSTALLED_APPS in settings.py
4. Run migrations: python manage.py migrate
5. Update the Celery configuration to use the database scheduler:
   CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

If already installed, skip the above and just confirm it's configured correctly.

django-celery-beat stores schedules IN THE DATABASE rather than hardcoded 
in Python files. This is essential because users create and modify their 
own schedules at runtime - a developer cannot hardcode them.

---

## DATA MODEL

Extend the existing BoardAutomation model by adding a new model called 
ScheduledAutomation. Do NOT modify the existing BoardAutomation model.
```python
class ScheduledAutomation(models.Model):
    
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
        ('all_members', 'All Board Members'),
        ('assignees', 'Task Assignees Only'),
        ('creator', 'Task Creator Only'),
    ]
    
    board = models.ForeignKey('kanban.Board', on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    
    # Schedule definition
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPE_CHOICES)
    scheduled_time = models.TimeField()  # e.g. 09:00
    scheduled_day = models.IntegerField(null=True, blank=True)
    # For weekly: 0=Monday, 1=Tuesday... 6=Sunday
    # For monthly: 1-31 (day of month)
    # For daily: leave null
    
    # Action definition
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    action_value = models.CharField(max_length=200, blank=True)
    # For set_priority: 'urgent', 'high', 'medium', 'low'
    # For send_notification: notification message text
    notify_target = models.CharField(
        max_length=50, 
        choices=NOTIFY_TARGET_CHOICES,
        default='all_members'
    )
    
    # Task filter - which tasks does this apply to
    task_filter = models.CharField(max_length=50, default='all')
    # Options: 'all', 'overdue', 'incomplete', 'high_priority'
    
    # Celery Beat link
    periodic_task = models.OneToOneField(
        'django_celery_beat.PeriodicTask',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Tracking
    run_count = models.IntegerField(default=0)
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.board.name})"
```

After creating this model, run migrations before doing anything else.

---

## HOW SCHEDULING WORKS (IMPORTANT - READ CAREFULLY)

When a user creates a ScheduledAutomation, your code must:

1. Create the ScheduledAutomation record in the database
2. ALSO create a corresponding PeriodicTask record in django-celery-beat

The PeriodicTask tells Celery Beat exactly when to fire. When Celery Beat 
fires, it calls a specific Celery task function you will write called 
`run_scheduled_automation`. That function receives the ScheduledAutomation 
ID, looks it up, and executes the action.

When a user disables or deletes a ScheduledAutomation, you must also 
disable or delete the corresponding PeriodicTask. They must always stay 
in sync.

Helper function to create the Celery Beat schedule:
```python
from django_celery_beat.models import PeriodicTask, CrontabSchedule
import json

def create_periodic_task_for_automation(scheduled_automation):
    """
    Creates or updates a CrontabSchedule and PeriodicTask for a 
    ScheduledAutomation instance.
    """
    sa = scheduled_automation
    time = sa.scheduled_time
    
    if sa.schedule_type == 'daily':
        crontab_kwargs = {
            'minute': str(time.minute),
            'hour': str(time.hour),
            'day_of_week': '*',
            'day_of_month': '*',
            'month_of_year': '*',
        }
    elif sa.schedule_type == 'weekly':
        crontab_kwargs = {
            'minute': str(time.minute),
            'hour': str(time.hour),
            'day_of_week': str(sa.scheduled_day),
            'day_of_month': '*',
            'month_of_year': '*',
        }
    elif sa.schedule_type == 'monthly':
        crontab_kwargs = {
            'minute': str(time.minute),
            'hour': str(time.hour),
            'day_of_week': '*',
            'day_of_month': str(sa.scheduled_day),
            'month_of_year': '*',
        }
    
    schedule, _ = CrontabSchedule.objects.get_or_create(**crontab_kwargs)
    
    task_name = f'scheduled_automation_{sa.id}'
    
    periodic_task = PeriodicTask.objects.create(
        crontab=schedule,
        name=task_name,
        task='kanban.tasks.automation_tasks.run_scheduled_automation',
        args=json.dumps([sa.id]),
        enabled=sa.is_active,
    )
    
    sa.periodic_task = periodic_task
    sa.save(update_fields=['periodic_task'])
    
    return periodic_task
```

---

## THE CELERY TASK TO WRITE

Add this to kanban/tasks/automation_tasks.py:
```python
@shared_task
def run_scheduled_automation(scheduled_automation_id):
    """
    Executes a ScheduledAutomation when its schedule fires.
    Called by Celery Beat via the PeriodicTask linked to this automation.
    """
    try:
        from kanban.models import ScheduledAutomation
        
        sa = ScheduledAutomation.objects.select_related(
            'board', 'created_by'
        ).get(id=scheduled_automation_id, is_active=True)
        
        # Get tasks matching the filter
        tasks = get_filtered_tasks(sa.board, sa.task_filter)
        
        if not tasks.exists():
            return f"No tasks matched filter '{sa.task_filter}' for automation {sa.id}"
        
        # Execute the action
        if sa.action == 'send_notification':
            execute_scheduled_notification(sa, tasks)
        elif sa.action == 'set_priority':
            execute_scheduled_priority_change(sa, tasks)
        
        # Update tracking
        sa.run_count += 1
        sa.last_run_at = timezone.now()
        sa.save(update_fields=['run_count', 'last_run_at'])
        
        return f"Scheduled automation {sa.id} completed successfully"
        
    except ScheduledAutomation.DoesNotExist:
        return f"Scheduled automation {scheduled_automation_id} not found or inactive"
    except Exception as e:
        logger.error(f"Scheduled automation {scheduled_automation_id} failed: {e}")
        raise


def get_filtered_tasks(board, task_filter):
    """Returns queryset of tasks matching the filter."""
    from kanban.models import Task
    from django.utils import timezone
    
    tasks = Task.objects.filter(column__board=board)
    
    if task_filter == 'overdue':
        tasks = tasks.filter(
            due_date__lt=timezone.now().date(),
            progress__lt=100
        )
    elif task_filter == 'incomplete':
        tasks = tasks.filter(progress__lt=100)
    elif task_filter == 'high_priority':
        tasks = tasks.filter(priority__in=['high', 'urgent'])
    # 'all' returns everything
    
    return tasks


def execute_scheduled_notification(sa, tasks):
    """Sends notification about the matching tasks."""
    from messaging.models import Notification
    
    task_count = tasks.count()
    message = sa.action_value or f"{task_count} tasks require your attention on {sa.board.name}"
    
    # Determine recipients based on notify_target
    recipients = set()
    
    if sa.notify_target == 'all_members':
        recipients = set(sa.board.members.all())
    elif sa.notify_target == 'assignees':
        for task in tasks:
            if task.assignee:
                recipients.add(task.assignee)
    elif sa.notify_target == 'creator':
        recipients.add(sa.created_by)
    
    for recipient in recipients:
        Notification.objects.create(
            user=recipient,
            message=message,
            notification_type='automation',
            board=sa.board
        )


def execute_scheduled_priority_change(sa, tasks):
    """Changes priority on all matching tasks."""
    tasks.update(priority=sa.action_value)
```

---

## USER INTERFACE

Add a new section to the existing Automations page called 
"Scheduled Automations" below the existing Rules section.

The UI needs:

1. A "Create Scheduled Rule" form with these fields:
   - Rule name (text input, required)
   - Schedule type (dropdown: Daily / Weekly / Monthly)
   - Time (time picker)
   - Day (appears only for Weekly: dropdown Mon-Sun)
   - Date (appears only for Monthly: dropdown 1-31)
   - Action (dropdown: Send Notification / Set Priority)
   - Action value (text for notification message, OR priority dropdown)
   - Who to notify (dropdown: All Members / Assignees Only / Creator)
   - Apply to tasks (dropdown: All Tasks / Overdue Only / Incomplete / High Priority)

2. A list of existing scheduled rules showing:
   - Rule name
   - Schedule description in plain English 
     (e.g. "Every Monday at 9:00 AM" not "weekly, day=0, time=09:00")
   - Last run time
   - Run count
   - Enable/Disable toggle
   - Delete button

3. A plain English schedule preview that updates as the user fills the form:
   "This rule will run: Every Monday at 9:00 AM"

DO NOT build a separate page for scheduled automations. Add it to the 
existing automations page to keep everything in one place.

---

## API ENDPOINTS NEEDED

Add these new URL endpoints in kanban/urls.py:

POST   /boards/<board_id>/scheduled-automations/create/
GET    /boards/<board_id>/scheduled-automations/list/
PATCH  /boards/<board_id>/scheduled-automations/<id>/toggle/
DELETE /boards/<board_id>/scheduled-automations/<id>/delete/

These should follow the same pattern as the existing automation endpoints 
in automation_views.py.

---

## PERMISSIONS AND VALIDATION

Only board members with edit rights can create scheduled automations.
Apply the same permission checks used in automation_views.py.

Validation rules:
- Rule name is required and must be unique per board
- scheduled_time is required for all schedule types
- scheduled_day is required for weekly and monthly types
- For monthly: scheduled_day must be between 1 and 28 
  (not 29-31 to avoid months with fewer days causing missed runs)
- action_value is required for set_priority action
- Maximum 10 scheduled automations per board (prevent abuse)

---

## ERROR HANDLING

If django-celery-beat is not running (Celery Beat worker is down), 
scheduled tasks simply will not fire. The UI should show a warning banner 
on the Scheduled Automations section:
"Note: Scheduled automations require the Celery Beat worker to be running."

If a scheduled automation fails during execution, log the error to Django 
logs and increment a failure_count field on the model. If failure_count 
reaches 3, automatically disable the automation and notify the board owner.

Add failure_count = models.IntegerField(default=0) to the model.

---

## WHAT NOT TO CHANGE

- Do not modify the existing BoardAutomation model
- Do not modify existing automation signals in signals.py
- Do not modify the existing due_date_approaching Celery task
- Do not change any existing automation UI elements
- Do not change any existing URL patterns

---

## BUILD ORDER

Phase 1: Install and configure django-celery-beat if not already present.
Confirm it is working before proceeding.

Phase 2: Create the ScheduledAutomation model and run migrations.
Create the create_periodic_task_for_automation() helper function.
Test that a PeriodicTask can be created and linked successfully.

Phase 3: Write the run_scheduled_automation Celery task and all helper 
functions. Test it can be called manually with a hardcoded ID before 
hooking up to the schedule.

Phase 4: Build the API endpoints for create, list, toggle, and delete.
Ensure that toggling and deleting also updates the linked PeriodicTask.

Phase 5: Build the UI on the existing automations page.
Include the plain English schedule preview.
Test the full flow: create rule → see it in list → toggle on/off → delete.

Phase 6: End-to-end test.
Create a daily rule set to fire 2 minutes from now.
Confirm Celery Beat fires the task at the right time.
Confirm the notification or priority change actually happens.
Confirm run_count increments.

---

## TESTING CHECKLIST

Before telling me the feature is complete, verify each of these:

- [ ] django-celery-beat is installed and configured correctly
- [ ] ScheduledAutomation model created and migrated
- [ ] Creating a scheduled automation also creates a PeriodicTask
- [ ] Disabling a scheduled automation also disables its PeriodicTask
- [ ] Deleting a scheduled automation also deletes its PeriodicTask
- [ ] run_scheduled_automation task executes correctly when called manually
- [ ] Daily schedule fires at the correct time
- [ ] Weekly schedule fires on the correct day and time
- [ ] Monthly schedule fires on the correct date and time
- [ ] send_notification action creates Notification records correctly
- [ ] set_priority action updates task priorities correctly
- [ ] Task filters (overdue, incomplete, high_priority, all) work correctly
- [ ] Maximum 10 automations per board is enforced
- [ ] Only board members with edit rights can create rules
- [ ] UI shows plain English schedule description
- [ ] Toggle enable/disable works from UI
- [ ] Delete works from UI
- [ ] Existing automation system is completely unaffected

