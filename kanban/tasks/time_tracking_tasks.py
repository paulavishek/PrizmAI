"""
Celery tasks for time tracking reminders and alerts.
"""
from celery import shared_task
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Sum
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task(name='kanban.send_time_tracking_reminders')
def send_time_tracking_reminders():
    """
    Periodic task to send time tracking reminders to users.
    Runs at end of workday (e.g., 5 PM) on weekdays.
    Sends reminders to users who haven't logged time today.
    """
    from kanban.budget_models import TimeEntry
    from messaging.models import Notification
    
    logger.info("Starting time tracking reminder task...")
    
    today = timezone.now().date()
    now = timezone.now()
    
    # Skip weekends
    if today.weekday() >= 5:
        logger.info("Weekend - skipping time tracking reminders")
        return {'status': 'skipped', 'reason': 'weekend'}
    
    # Get all active users
    active_users = User.objects.filter(is_active=True)
    
    reminders_sent = 0
    users_with_time = 0
    
    for user in active_users:
        # Check if user has logged any time today
        today_hours = TimeEntry.objects.filter(
            user=user,
            work_date=today
        ).aggregate(total=Sum('hours_spent'))['total']
        
        if today_hours is None or today_hours == 0:
            # User hasn't logged time today - send reminder
            try:
                # Create in-app notification
                Notification.objects.create(
                    user=user,
                    notification_type='time_tracking',
                    title='Time Tracking Reminder',
                    message="You haven't logged any time today. Remember to track your work!",
                    action_url='/time-tracking/',
                    is_read=False
                )
                reminders_sent += 1
                logger.debug(f"Sent time tracking reminder to {user.username}")
            except Exception as e:
                logger.error(f"Failed to send reminder to {user.username}: {e}")
        else:
            users_with_time += 1
    
    result = {
        'status': 'completed',
        'reminders_sent': reminders_sent,
        'users_with_time': users_with_time,
        'total_users': active_users.count()
    }
    
    logger.info(f"Time tracking reminders completed: {result}")
    return result


@shared_task(name='kanban.detect_time_anomalies')
def detect_time_anomalies():
    """
    Periodic task to detect unusual time entry patterns.
    Runs daily to identify potential issues like excessive hours.
    """
    from kanban.budget_models import TimeEntry
    from kanban.time_tracking_ai import TimeTrackingAIService
    from messaging.models import Notification
    
    logger.info("Starting time anomaly detection task...")
    
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    
    # Get all users who logged time yesterday
    users_with_entries = User.objects.filter(
        time_entries__work_date=yesterday
    ).distinct()
    
    alerts_created = 0
    
    for user in users_with_entries:
        ai_service = TimeTrackingAIService(user)
        anomalies = ai_service.detect_anomalies(days_back=1)
        
        # Filter for critical/warning anomalies only
        serious_anomalies = [a for a in anomalies if a['severity'] in ['critical', 'warning']]
        
        for anomaly in serious_anomalies:
            try:
                # Create notification for the user
                Notification.objects.create(
                    user=user,
                    notification_type='time_tracking_alert',
                    title='Time Tracking Alert',
                    message=anomaly['message'],
                    action_url='/time-tracking/',
                    is_read=False
                )
                alerts_created += 1
            except Exception as e:
                logger.error(f"Failed to create anomaly notification for {user.username}: {e}")
    
    result = {
        'status': 'completed',
        'users_checked': users_with_entries.count(),
        'alerts_created': alerts_created
    }
    
    logger.info(f"Time anomaly detection completed: {result}")
    return result


@shared_task(name='kanban.weekly_time_summary')
def send_weekly_time_summary():
    """
    Periodic task to send weekly time summary to users.
    Runs every Monday morning to summarize last week's time entries.
    """
    from kanban.budget_models import TimeEntry
    from kanban.time_tracking_ai import TimeTrackingAIService
    from messaging.models import Notification
    
    logger.info("Starting weekly time summary task...")
    
    today = timezone.now().date()
    
    # Only run on Mondays
    if today.weekday() != 0:
        logger.info("Not Monday - skipping weekly summary")
        return {'status': 'skipped', 'reason': 'not_monday'}
    
    # Calculate last week's date range
    last_week_end = today - timedelta(days=1)  # Sunday
    last_week_start = last_week_end - timedelta(days=6)  # Monday
    
    # Get users with time entries last week
    users_with_entries = User.objects.filter(
        time_entries__work_date__gte=last_week_start,
        time_entries__work_date__lte=last_week_end
    ).distinct()
    
    summaries_sent = 0
    
    for user in users_with_entries:
        # Calculate week's total
        week_total = TimeEntry.objects.filter(
            user=user,
            work_date__gte=last_week_start,
            work_date__lte=last_week_end
        ).aggregate(total=Sum('hours_spent'))['total'] or 0
        
        # Get insights
        ai_service = TimeTrackingAIService(user)
        insights = ai_service.get_time_insights()
        
        trend = insights.get('trend_direction', 'stable')
        trend_emoji = '📈' if trend == 'up' else '📉' if trend == 'down' else '➡️'
        
        message = (
            f"Last week you logged {round(week_total, 1)} hours. "
            f"{trend_emoji} {abs(insights.get('trend_percent', 0))}% {'more' if trend == 'up' else 'less' if trend == 'down' else 'same as'} than the previous week."
        )
        
        try:
            Notification.objects.create(
                user=user,
                notification_type='time_tracking_summary',
                title='Weekly Time Summary',
                message=message,
                action_url='/time-tracking/',
                is_read=False
            )
            summaries_sent += 1
        except Exception as e:
            logger.error(f"Failed to send summary to {user.username}: {e}")
    
    result = {
        'status': 'completed',
        'summaries_sent': summaries_sent,
        'week_range': f"{last_week_start} to {last_week_end}"
    }
    
    logger.info(f"Weekly time summary completed: {result}")
    return result
