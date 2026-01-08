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
    # Demo session cleanup - runs every hour to reset expired sessions
    'cleanup-expired-demo-sessions': {
        'task': 'kanban.cleanup_expired_demo_sessions',
        'schedule': crontab(minute=30),  # Every hour at minute 30
    },
    # Demo expiry warnings - runs every 15 minutes to track expiring sessions
    'demo-expiry-warnings': {
        'task': 'kanban.send_demo_expiry_warning',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    # Refresh demo dates - runs daily at 3 AM to keep demo data current
    'refresh-demo-dates-daily': {
        'task': 'kanban.refresh_demo_dates',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3:00 AM
    },
    # Demo reminder emails (24h and 12h) - runs every 30 minutes
    'demo-reminder-emails': {
        'task': 'analytics.send_demo_reminder_emails',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
    # Inactivity re-engagement emails - runs every hour
    'inactivity-reengagement-emails': {
        'task': 'analytics.send_inactivity_reengagement_emails',
        'schedule': crontab(minute=15),  # Every hour at minute 15
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
