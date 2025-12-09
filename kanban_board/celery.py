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
}


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
