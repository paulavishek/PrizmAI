"""
Celery tasks for analytics operations.
Background jobs for analytics processing.
"""
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


@shared_task
def cleanup_old_sessions():
    """
    Clean up old user sessions from the database.
    Run this periodically to keep database size manageable.
    """
    from .models import UserSession
    from django.utils import timezone
    from datetime import timedelta
    
    # Delete sessions older than 90 days
    cutoff_date = timezone.now() - timedelta(days=90)
    deleted_count = UserSession.objects.filter(session_start__lt=cutoff_date).delete()[0]
    
    logger.info(f"Cleaned up {deleted_count} old sessions")
    return deleted_count


@shared_task
def generate_daily_analytics_report():
    """
    Generate daily analytics summary.
    Can be extended to send email reports.
    """
    from .models import UserSession, Feedback
    from django.utils import timezone
    from django.db.models import Avg
    from datetime import timedelta
    
    yesterday = timezone.now() - timedelta(days=1)
    start_of_day = yesterday.replace(hour=0, minute=0, second=0)
    end_of_day = yesterday.replace(hour=23, minute=59, second=59)
    
    sessions = UserSession.objects.filter(
        session_start__range=(start_of_day, end_of_day)
    )
    
    feedback = Feedback.objects.filter(
        submitted_at__range=(start_of_day, end_of_day)
    )
    
    report = {
        'date': yesterday.date(),
        'total_sessions': sessions.count(),
        'unique_users': sessions.values('user').distinct().count(),
        'avg_duration': sessions.aggregate(avg=Avg('duration_minutes'))['avg'] or 0,
        'total_feedback': feedback.count(),
        'avg_rating': feedback.aggregate(avg=Avg('rating'))['avg'] or 0,
    }
    
    logger.info(f"Daily report generated: {report}")
    return report
