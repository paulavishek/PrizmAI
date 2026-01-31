"""
Demo data management tasks.
Handles keeping demo data current with proper dates.
"""
from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(name='kanban.refresh_demo_dates')
def refresh_demo_dates_task():
    """
    Celery task wrapper for refreshing demo dates.
    Keeps demo data looking current by adjusting dates relative to today.
    Runs daily at 3 AM via Celery Beat.
    """
    from django.core.management import call_command
    from io import StringIO
    
    out = StringIO()
    try:
        call_command('refresh_demo_dates', stdout=out)
        result = out.getvalue()
        logger.info(f"Demo dates refreshed: {result}")
        return {'status': 'success', 'output': result}
    except Exception as e:
        logger.error(f"Failed to refresh demo dates: {e}")
        return {'status': 'error', 'error': str(e)}
