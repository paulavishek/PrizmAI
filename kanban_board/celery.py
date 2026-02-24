"""
Celery configuration for the kanban_board project.
"""
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kanban_board.settings')

app = Celery('kanban_board')

# Load configuration from Django settings, all celery configuration should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()

# Celery Beat Schedule for Periodic Tasks
app.conf.beat_schedule = {
    # Conflict detection - runs every hour
    'detect-conflicts-hourly': {
        'task': 'kanban.detect_conflicts',
        'schedule': crontab(minute=0),  # Every hour at minute 0
    },
    # Cleanup old resolved conflicts - runs daily at 2 AM
    'cleanup-resolved-conflicts': {
        'task': 'kanban.cleanup_resolved_conflicts',
        'schedule': crontab(hour=2, minute=0),  # Daily at 2:00 AM
    },
    # Refresh demo dates - runs daily at 3 AM to keep demo data current
    'refresh-demo-dates-daily': {
        'task': 'kanban.refresh_demo_dates',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3:00 AM
    },
    # Time tracking reminder - runs at 5 PM on weekdays
    'time-tracking-reminder': {
        'task': 'kanban.send_time_tracking_reminders',
        'schedule': crontab(hour=17, minute=0, day_of_week='1-5'),  # 5 PM Mon-Fri
    },
    # Time anomaly detection - runs daily at 9 AM
    'time-anomaly-detection': {
        'task': 'kanban.detect_time_anomalies',
        'schedule': crontab(hour=9, minute=0),  # Daily at 9:00 AM
    },
    # Weekly time summary - runs Monday at 8 AM
    'weekly-time-summary': {
        'task': 'kanban.weekly_time_summary',
        'schedule': crontab(hour=8, minute=0, day_of_week='1'),  # Monday at 8 AM
    },
    # Due-date approaching automations - runs every hour
    'due-date-approaching-automations': {
        'task': 'kanban.run_due_date_approaching_automations',
        'schedule': crontab(minute=30),  # Every hour at :30 (offset from conflict detection)
    },
    # Daily executive briefing - 08:00 IST (CELERY_TIMEZONE = 'Asia/Kolkata')
    'daily-executive-briefing': {
        'task': 'kanban.ai_summary.generate_daily_executive_briefing',
        'schedule': crontab(hour=8, minute=0),
    },
}

# Route all AI summary tasks to a dedicated 'summaries' queue so they never
# compete with user-facing operations (auth, data saves, conflict detection).
app.conf.task_routes = {
    'kanban.ai_summary.*': {'queue': 'summaries'},
}


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
