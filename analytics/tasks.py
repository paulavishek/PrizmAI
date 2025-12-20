"""
Celery tasks for analytics operations.
Async processing for HubSpot sync and other background jobs.
"""
from celery import shared_task
from .models import Feedback
from .utils import HubSpotIntegration
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_feedback_to_hubspot_task(self, feedback_id):
    """
    Async task to sync feedback to HubSpot.
    Retries up to 3 times with 60 second delay between retries.
    """
    try:
        feedback = Feedback.objects.get(id=feedback_id)
        hubspot = HubSpotIntegration()
        
        if hubspot.is_configured() and feedback.email:
            contact_id, engagement_id = hubspot.sync_feedback_to_hubspot(feedback)
            logger.info(f"Successfully synced feedback {feedback_id} to HubSpot")
            return {
                'success': True,
                'feedback_id': feedback_id,
                'contact_id': contact_id,
                'engagement_id': engagement_id
            }
        else:
            logger.warning(f"HubSpot not configured or no email for feedback {feedback_id}")
            return {'success': False, 'reason': 'No HubSpot config or email'}
    
    except Feedback.DoesNotExist:
        logger.error(f"Feedback {feedback_id} not found")
        return {'success': False, 'reason': 'Feedback not found'}
    
    except Exception as exc:
        logger.error(f"Error syncing feedback {feedback_id} to HubSpot: {exc}")
        # Retry the task
        raise self.retry(exc=exc)
