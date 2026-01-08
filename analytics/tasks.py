"""
Celery tasks for analytics operations.
Background jobs for analytics processing and demo user engagement.
"""
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# DEMO USER EMAIL REMINDERS
# ============================================================================

@shared_task(name='analytics.send_demo_reminder_emails')
def send_demo_reminder_emails():
    """
    Send reminder emails to demo users at 24h and 12h before expiration.
    
    This task:
    1. Finds demo sessions expiring in ~24 hours (not yet notified)
    2. Finds demo sessions expiring in ~12 hours (not yet notified)
    3. Sends appropriate reminder emails
    4. Marks sessions as notified to prevent duplicate emails
    
    Runs every 30 minutes via Celery Beat.
    """
    from .models import DemoSession, DemoAnalytics
    
    now = timezone.now()
    emails_sent = {'24h': 0, '12h': 0, 'errors': 0}
    
    # === 24-HOUR REMINDERS ===
    # Find sessions expiring between 23-25 hours from now (catches window)
    expiry_24h_start = now + timedelta(hours=23)
    expiry_24h_end = now + timedelta(hours=25)
    
    sessions_24h = DemoSession.objects.filter(
        expires_at__gte=expiry_24h_start,
        expires_at__lte=expiry_24h_end,
        reminder_24h_sent=False,
        converted_to_signup=False,
    ).exclude(
        demo_user_email__isnull=True
    ).exclude(
        demo_user_email=''
    )
    
    for session in sessions_24h:
        try:
            _send_demo_reminder_email(session, '24h')
            session.reminder_24h_sent = True
            session.reminder_24h_sent_at = now
            session.save(update_fields=['reminder_24h_sent', 'reminder_24h_sent_at'])
            emails_sent['24h'] += 1
            
            # Log analytics event
            DemoAnalytics.objects.create(
                session_id=session.session_id,
                demo_session=session,
                event_type='reminder_email_sent',
                event_data={'reminder_type': '24h', 'email': session.demo_user_email}
            )
        except Exception as e:
            logger.error(f"Failed to send 24h reminder for session {session.session_id}: {e}")
            emails_sent['errors'] += 1
    
    # === 12-HOUR REMINDERS ===
    # Find sessions expiring between 11-13 hours from now
    expiry_12h_start = now + timedelta(hours=11)
    expiry_12h_end = now + timedelta(hours=13)
    
    sessions_12h = DemoSession.objects.filter(
        expires_at__gte=expiry_12h_start,
        expires_at__lte=expiry_12h_end,
        reminder_12h_sent=False,
        converted_to_signup=False,
    ).exclude(
        demo_user_email__isnull=True
    ).exclude(
        demo_user_email=''
    )
    
    for session in sessions_12h:
        try:
            _send_demo_reminder_email(session, '12h')
            session.reminder_12h_sent = True
            session.reminder_12h_sent_at = now
            session.save(update_fields=['reminder_12h_sent', 'reminder_12h_sent_at'])
            emails_sent['12h'] += 1
            
            # Log analytics event
            DemoAnalytics.objects.create(
                session_id=session.session_id,
                demo_session=session,
                event_type='reminder_email_sent',
                event_data={'reminder_type': '12h', 'email': session.demo_user_email}
            )
        except Exception as e:
            logger.error(f"Failed to send 12h reminder for session {session.session_id}: {e}")
            emails_sent['errors'] += 1
    
    logger.info(f"Demo reminder emails sent: 24h={emails_sent['24h']}, 12h={emails_sent['12h']}, errors={emails_sent['errors']}")
    return emails_sent


def _send_demo_reminder_email(session, reminder_type):
    """
    Send a demo expiry reminder email.
    
    Args:
        session: DemoSession instance
        reminder_type: '24h' or '12h'
    """
    hours_remaining = 24 if reminder_type == '24h' else 12
    
    # Calculate features explored for personalization
    features_explored = session.features_list or []
    aha_moments = session.aha_moments_list or []
    
    # Get unexplored high-value features to suggest
    high_value_features = [
        {'key': 'ai_generator', 'name': 'AI Task Generator', 'emoji': '🤖'},
        {'key': 'burndown', 'name': 'Burndown Charts', 'emoji': '📊'},
        {'key': 'gantt', 'name': 'Gantt Timeline', 'emoji': '📅'},
        {'key': 'budget', 'name': 'Budget Forecasting', 'emoji': '💰'},
        {'key': 'retrospective', 'name': 'Sprint Retrospectives', 'emoji': '🔄'},
    ]
    suggested_features = [f for f in high_value_features if f['key'] not in features_explored][:3]
    
    context = {
        'hours_remaining': hours_remaining,
        'session': session,
        'features_explored_count': len(features_explored),
        'aha_moments_count': len(aha_moments),
        'suggested_features': suggested_features,
        'demo_url': f"{getattr(settings, 'SITE_URL', 'https://prizmAI.com')}/demo/",
        'signup_url': f"{getattr(settings, 'SITE_URL', 'https://prizmAI.com')}/accounts/signup/",
        'reminder_type': reminder_type,
    }
    
    if reminder_type == '24h':
        subject = "⏰ 24 hours left in your PrizmAI demo - don't miss out!"
    else:
        subject = "⚡ Only 12 hours left! Complete your PrizmAI exploration"
    
    # Render email templates
    html_message = render_to_string('analytics/emails/demo_reminder.html', context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[session.demo_user_email],
        html_message=html_message,
        fail_silently=False,
    )
    
    logger.info(f"Sent {reminder_type} reminder to {session.demo_user_email}")


# ============================================================================
# INACTIVITY RE-ENGAGEMENT
# ============================================================================

@shared_task(name='analytics.send_inactivity_reengagement_emails')
def send_inactivity_reengagement_emails():
    """
    Send re-engagement emails to demo users who have been inactive for 12+ hours.
    
    This task:
    1. Finds demo sessions inactive for 12+ hours but not expired
    2. Excludes already converted users
    3. Excludes users who already received inactivity email
    4. Sends personalized "don't forget" email
    
    Runs every hour via Celery Beat.
    """
    from .models import DemoSession, DemoAnalytics
    
    now = timezone.now()
    inactivity_threshold = now - timedelta(hours=12)
    
    inactive_sessions = DemoSession.objects.filter(
        last_activity__lte=inactivity_threshold,
        expires_at__gt=now,  # Not expired yet
        inactivity_email_sent=False,
        converted_to_signup=False,
    ).exclude(
        demo_user_email__isnull=True
    ).exclude(
        demo_user_email=''
    )
    
    emails_sent = 0
    errors = 0
    
    for session in inactive_sessions:
        try:
            _send_inactivity_email(session)
            session.inactivity_email_sent = True
            session.inactivity_email_sent_at = now
            session.save(update_fields=['inactivity_email_sent', 'inactivity_email_sent_at'])
            emails_sent += 1
            
            # Log analytics event
            DemoAnalytics.objects.create(
                session_id=session.session_id,
                demo_session=session,
                event_type='inactivity_email_sent',
                event_data={
                    'inactive_hours': (now - session.last_activity).total_seconds() / 3600,
                    'email': session.demo_user_email
                }
            )
        except Exception as e:
            logger.error(f"Failed to send inactivity email for session {session.session_id}: {e}")
            errors += 1
    
    logger.info(f"Inactivity re-engagement emails sent: {emails_sent}, errors: {errors}")
    return {'emails_sent': emails_sent, 'errors': errors}


def _send_inactivity_email(session):
    """
    Send an inactivity re-engagement email.
    """
    # Calculate time remaining
    hours_remaining = (session.expires_at - timezone.now()).total_seconds() / 3600
    
    # Get session stats for personalization
    features_explored = session.features_list or []
    
    # Determine personalization based on what they did explore
    if 'ai_generator' in features_explored:
        hook_message = "You tried our AI features - there's so much more to explore!"
        hook_feature = {'name': 'Advanced AI Analytics', 'emoji': '🧠'}
    elif 'burndown' in features_explored:
        hook_message = "You checked out the analytics - wait until you see the forecasting!"
        hook_feature = {'name': 'Smart Forecasting', 'emoji': '📈'}
    elif features_explored:
        hook_message = f"You explored {len(features_explored)} features - but have you seen the AI magic?"
        hook_feature = {'name': 'AI Task Generator', 'emoji': '🤖'}
    else:
        hook_message = "You haven't had a chance to explore yet - let's change that!"
        hook_feature = {'name': 'Guided Demo Tour', 'emoji': '🎯'}
    
    context = {
        'session': session,
        'hours_remaining': int(hours_remaining),
        'hook_message': hook_message,
        'hook_feature': hook_feature,
        'features_explored_count': len(features_explored),
        'demo_url': f"{getattr(settings, 'SITE_URL', 'https://prizmAI.com')}/demo/",
        'signup_url': f"{getattr(settings, 'SITE_URL', 'https://prizmAI.com')}/accounts/signup/",
    }
    
    subject = "👋 Don't forget - your PrizmAI demo is waiting!"
    
    html_message = render_to_string('analytics/emails/inactivity_reminder.html', context)
    plain_message = strip_tags(html_message)
    
    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[session.demo_user_email],
        html_message=html_message,
        fail_silently=False,
    )
    
    logger.info(f"Sent inactivity re-engagement email to {session.demo_user_email}")


# ============================================================================
# EXISTING TASKS
# ============================================================================

@shared_task
def cleanup_old_sessions():
    """
    Clean up old user sessions from the database.
    Run this periodically to keep database size manageable.
    """
    from .models import UserSession
    
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
    from .models import UserSession, Feedback, AhaMomentEvent
    from django.db.models import Avg, Count
    
    yesterday = timezone.now() - timedelta(days=1)
    start_of_day = yesterday.replace(hour=0, minute=0, second=0)
    end_of_day = yesterday.replace(hour=23, minute=59, second=59)
    
    sessions = UserSession.objects.filter(
        session_start__range=(start_of_day, end_of_day)
    )
    
    feedback = Feedback.objects.filter(
        submitted_at__range=(start_of_day, end_of_day)
    )
    
    aha_moments = AhaMomentEvent.objects.filter(
        timestamp__range=(start_of_day, end_of_day)
    )
    
    report = {
        'date': yesterday.date(),
        'total_sessions': sessions.count(),
        'unique_users': sessions.values('user').distinct().count(),
        'avg_duration': sessions.aggregate(avg=Avg('duration_minutes'))['avg'] or 0,
        'total_feedback': feedback.count(),
        'avg_rating': feedback.aggregate(avg=Avg('rating'))['avg'] or 0,
        'aha_moments': aha_moments.count(),
        'aha_by_type': dict(aha_moments.values('moment_type').annotate(count=Count('id')).values_list('moment_type', 'count')),
    }
    
    logger.info(f"Daily report generated: {report}")
    return report
