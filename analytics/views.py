"""
Analytics views for logout, feedback submission, and dashboard.
"""
from django.contrib.auth import logout
from django.shortcuts import render, redirect
from django.views import View
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Avg, Sum, Q
from django.db.models.functions import TruncDate, TruncWeek
from datetime import timedelta
import json
import logging

from .models import UserSession, Feedback, FeedbackPrompt, AnalyticsEvent
from .utils import HubSpotIntegration

logger = logging.getLogger(__name__)


class CustomLogoutView(View):
    """
    Custom logout view that:
    1. Collects session stats before logout
    2. Logs out the user
    3. Shows personalized feedback form based on engagement
    """
    template_name = 'analytics/logout_success.html'
    
    def get(self, request):
        return self.handle_logout(request)
    
    def post(self, request):
        return self.handle_logout(request)
    
    def handle_logout(self, request):
        """Handle logout and show feedback form"""
        # Get session stats before logout
        session_stats = None
        engagement_level = 'low'
        show_feedback_form = False
        
        if hasattr(request, 'user_session') and request.user_session:
            session = request.user_session
            
            # End the session
            session.end_session(
                reason='logout',
                exit_page=request.META.get('HTTP_REFERER', '')
            )
            
            # Get session stats for template
            session_stats = {
                'duration_minutes': session.duration_minutes,
                'boards_viewed': session.boards_viewed,
                'boards_created': session.boards_created,
                'tasks_created': session.tasks_created,
                'tasks_completed': session.tasks_completed,
                'ai_features_used': session.ai_features_used,
                'pages_visited': session.pages_visited,
            }
            
            engagement_level = session.engagement_level
            
            # Show feedback form based on engagement
            # Don't show to very low engagement users (quick bounces)
            show_feedback_form = session.duration_minutes >= 2
            
            # Create feedback prompt record
            if show_feedback_form:
                try:
                    FeedbackPrompt.objects.create(
                        user_session=session,
                        prompt_type='logout'
                    )
                except Exception as e:
                    logger.error(f"Error creating feedback prompt: {e}")
        
        # Get user info for pre-filling form
        user_info = {}
        if request.user.is_authenticated:
            user_info = {
                'name': request.user.get_full_name() or request.user.username,
                'email': request.user.email,
            }
        
        # Logout the user
        logout(request)
        
        context = {
            'session_stats': session_stats,
            'engagement_level': engagement_level,
            'show_feedback_form': show_feedback_form,
            'user_info': user_info,
            'hubspot_portal_id': getattr(settings, 'HUBSPOT_PORTAL_ID', ''),
            'hubspot_form_id': getattr(settings, 'HUBSPOT_FEEDBACK_FORM_ID', ''),
        }
        
        return render(request, self.template_name, context)


@require_http_methods(["POST"])
def submit_feedback_ajax(request):
    """
    AJAX endpoint for feedback submission.
    Syncs to HubSpot if configured.
    """
    try:
        data = json.loads(request.body)
        
        # Get session if available
        user_session = None
        if hasattr(request, 'user_session'):
            user_session = request.user_session
        
        # Create feedback
        feedback = Feedback.objects.create(
            user_session=user_session,
            user=request.user if request.user.is_authenticated else None,
            name=data.get('name', ''),
            email=data.get('email', ''),
            organization=data.get('organization', ''),
            feedback_text=data.get('feedback', ''),
            rating=data.get('rating'),
            feedback_type=data.get('feedback_type', 'other'),
            email_consent=data.get('email_consent', False),
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        
        # Analyze sentiment
        feedback.analyze_sentiment()
        
        # Update prompt as submitted
        if user_session:
            FeedbackPrompt.objects.filter(
                user_session=user_session,
                prompt_type='logout'
            ).update(submitted=True, interacted=True)
        
        # Sync to HubSpot (async would be better in production)
        hubspot = HubSpotIntegration()
        if hubspot.is_configured() and feedback.email:
            try:
                contact_id, engagement_id = hubspot.sync_feedback_to_hubspot(feedback)
                if contact_id:
                    logger.info(f"Feedback synced to HubSpot: {contact_id}")
            except Exception as e:
                logger.error(f"Error syncing to HubSpot: {e}")
        
        return JsonResponse({
            'success': True,
            'message': 'Thank you for your feedback!',
            'feedback_id': feedback.id
        })
    
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': 'An error occurred. Please try again.'
        }, status=500)


@staff_member_required
def analytics_dashboard(request):
    """
    Comprehensive analytics dashboard combining session data,
    feedback, and engagement metrics.
    """
    # Date range for analysis
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    # === USER ACQUISITION & RETENTION ===
    total_sessions = UserSession.objects.filter(session_start__gte=start_date).count()
    total_users = User.objects.filter(date_joined__gte=start_date).count()
    total_feedback = Feedback.objects.filter(submitted_at__gte=start_date).count()
    
    # Registrations during sessions
    registrations = UserSession.objects.filter(
        session_start__gte=start_date,
        registered_during_session=True
    ).count()
    
    # Return visitors
    return_visitors = UserSession.objects.filter(
        session_start__gte=start_date,
        is_return_visit=True
    ).count()
    
    # === ENGAGEMENT METRICS ===
    engagement_breakdown = UserSession.objects.filter(
        session_start__gte=start_date
    ).values('engagement_level').annotate(
        count=Count('id'),
        avg_duration=Avg('duration_minutes'),
        avg_tasks=Avg('tasks_created'),
        avg_ai_usage=Avg('ai_features_used')
    ).order_by('engagement_level')
    
    # Average session metrics
    avg_metrics = UserSession.objects.filter(
        session_start__gte=start_date
    ).aggregate(
        avg_duration=Avg('duration_minutes'),
        avg_tasks=Avg('tasks_created'),
        avg_boards=Avg('boards_created'),
        avg_ai_features=Avg('ai_features_used'),
        avg_pages=Avg('pages_visited')
    )
    
    # === FEATURE ADOPTION ===
    feature_usage = {
        'board_creators': UserSession.objects.filter(
            session_start__gte=start_date,
            boards_created__gt=0
        ).count(),
        'task_creators': UserSession.objects.filter(
            session_start__gte=start_date,
            tasks_created__gt=0
        ).count(),
        'ai_users': UserSession.objects.filter(
            session_start__gte=start_date,
            ai_features_used__gt=0
        ).count(),
    }
    
    # AI feature breakdown
    ai_events = AnalyticsEvent.objects.filter(
        timestamp__gte=start_date,
        event_category='ai_features'
    ).values('event_label').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # === DAILY TRENDS ===
    daily_sessions = UserSession.objects.filter(
        session_start__gte=start_date
    ).annotate(
        date=TruncDate('session_start')
    ).values('date').annotate(
        sessions=Count('id'),
        unique_users=Count('user', distinct=True),
        avg_duration=Avg('duration_minutes')
    ).order_by('date')
    
    # === FEEDBACK ANALYSIS ===
    feedback_stats = {
        'total': total_feedback,
        'avg_rating': Feedback.objects.filter(
            submitted_at__gte=start_date,
            rating__isnull=False
        ).aggregate(Avg('rating'))['rating__avg'] or 0,
    }
    
    # Sentiment breakdown
    sentiment_breakdown = Feedback.objects.filter(
        submitted_at__gte=start_date
    ).values('sentiment').annotate(
        count=Count('id')
    ).order_by('sentiment')
    
    # Rating distribution
    rating_distribution = Feedback.objects.filter(
        submitted_at__gte=start_date,
        rating__isnull=False
    ).values('rating').annotate(
        count=Count('id')
    ).order_by('rating')
    
    # === CONVERSION FUNNEL ===
    funnel = {
        'visitors': total_sessions,
        'task_creators': UserSession.objects.filter(
            session_start__gte=start_date,
            tasks_created__gt=0
        ).count(),
        'ai_adopters': UserSession.objects.filter(
            session_start__gte=start_date,
            ai_features_used__gt=0
        ).count(),
        'feedback_givers': total_feedback,
    }
    
    # Calculate conversion rates
    if funnel['visitors'] > 0:
        funnel['task_conversion'] = (funnel['task_creators'] / funnel['visitors']) * 100
        funnel['ai_conversion'] = (funnel['ai_adopters'] / funnel['visitors']) * 100
        funnel['feedback_conversion'] = (funnel['feedback_givers'] / funnel['visitors']) * 100
    
    # === TOP INSIGHTS ===
    recent_feedback = Feedback.objects.filter(
        submitted_at__gte=start_date
    ).select_related('user_session').order_by('-submitted_at')[:10]
    
    high_engagement_users = UserSession.objects.filter(
        session_start__gte=start_date,
        engagement_level='very_high'
    ).select_related('user').order_by('-engagement_score')[:10]
    
    context = {
        'days': days,
        'start_date': start_date,
        
        # Summary stats
        'total_sessions': total_sessions,
        'total_users': total_users,
        'total_feedback': total_feedback,
        'registrations': registrations,
        'return_visitors': return_visitors,
        
        # Engagement
        'engagement_breakdown': engagement_breakdown,
        'avg_metrics': avg_metrics,
        
        # Features
        'feature_usage': feature_usage,
        'ai_events': ai_events,
        
        # Trends
        'daily_sessions': list(daily_sessions),
        
        # Feedback
        'feedback_stats': feedback_stats,
        'sentiment_breakdown': sentiment_breakdown,
        'rating_distribution': rating_distribution,
        
        # Funnel
        'funnel': funnel,
        
        # Recent activity
        'recent_feedback': recent_feedback,
        'high_engagement_users': high_engagement_users,
    }
    
    return render(request, 'analytics/dashboard.html', context)


from django.conf import settings
from django.contrib.auth.models import User
