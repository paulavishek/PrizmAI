"""
Analytics views for logout, feedback submission, and dashboard.
Simple Django + Google Analytics approach - no HubSpot required.
"""
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.views import View
from django.views.decorators.http import require_http_methods
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Avg, Sum, Q
from django.db.models.functions import TruncDate, TruncWeek
from django.core.cache import cache
from datetime import timedelta
import json
import logging

from .models import UserSession, Feedback, FeedbackPrompt, AnalyticsEvent

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
            min_engagement = getattr(settings, 'ANALYTICS_MIN_ENGAGEMENT_FOR_FEEDBACK', 2)
            show_feedback_form = session.duration_minutes >= min_engagement
            
            logger.info(f"Logout - User: {session.user}, Duration: {session.duration_minutes}min, "
                       f"Min Required: {min_engagement}min, Show Form: {show_feedback_form}")
            
            # Create feedback prompt record
            if show_feedback_form:
                try:
                    FeedbackPrompt.objects.create(
                        user_session=session,
                        prompt_type='logout'
                    )
                except Exception as e:
                    logger.error(f"Error creating feedback prompt: {e}")
        else:
            logger.warning(f"Logout - No user_session found on request! "
                          f"User: {request.user}, Session Key: {request.session.session_key}")
        
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
        }
        
        logger.info(f"Logout - Rendering template with show_feedback_form={show_feedback_form}")
        
        return render(request, self.template_name, context)


@require_http_methods(["POST"])
def submit_feedback_ajax(request):
    """
    Simple AJAX endpoint for feedback submission.
    Stores in Django, analyzes sentiment, sends data to Google Analytics.
    """
    try:
        # Rate limiting - prevent feedback spam
        ip = request.META.get('REMOTE_ADDR')
        cache_key = f'feedback_submit_{ip}'
        
        if cache.get(cache_key):
            return JsonResponse({
                'success': False,
                'message': 'Please wait a few minutes before submitting more feedback.'
            }, status=429)
        
        # Set 5-minute cooldown
        cache.set(cache_key, True, 300)
        
        data = json.loads(request.body)
        
        # Get session if available
        user_session = None
        if hasattr(request, 'user_session'):
            user_session = request.user_session
        
        # Create feedback (convert rating to int)
        rating = data.get('rating')
        if rating:
            rating = int(rating)
        
        feedback = Feedback.objects.create(
            user_session=user_session,
            user=request.user if request.user.is_authenticated else None,
            name=data.get('name', ''),
            email=data.get('email', ''),
            feedback_text=data.get('feedback', ''),
            rating=rating,
            email_consent=data.get('email_consent', False),
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        
        # Analyze sentiment automatically
        feedback.analyze_sentiment()
        
        # Update prompt as submitted
        if user_session:
            FeedbackPrompt.objects.filter(
                user_session=user_session,
                prompt_type='logout'
            ).update(submitted=True, interacted=True)
        
        logger.info(f"Feedback submitted: ID={feedback.id}, Rating={feedback.rating}, "
                   f"Sentiment={feedback.sentiment}, Email={feedback.email}")
        
        return JsonResponse({
            'success': True,
            'message': 'Thank you for your feedback!',
            'feedback_id': feedback.id,
            'sentiment': feedback.sentiment,
            'rating': feedback.rating,
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
    feedback, engagement metrics, and abuse prevention stats.
    """
    # Date range for analysis
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)
    
    # Import abuse prevention models
    from analytics.models import DemoAbusePrevention, DemoSession
    
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
    
    # Calculate percentages
    if total_sessions > 0:
        feature_usage['board_creators_pct'] = round((feature_usage['board_creators'] / total_sessions) * 100, 1)
        feature_usage['task_creators_pct'] = round((feature_usage['task_creators'] / total_sessions) * 100, 1)
        feature_usage['ai_users_pct'] = round((feature_usage['ai_users'] / total_sessions) * 100, 1)
    else:
        feature_usage['board_creators_pct'] = 0
        feature_usage['task_creators_pct'] = 0
        feature_usage['ai_users_pct'] = 0
    
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
    
    # Calculate sentiment percentages
    sentiment_list = list(sentiment_breakdown)
    for item in sentiment_list:
        if total_feedback > 0:
            item['percentage'] = round((item['count'] / total_feedback) * 100, 1)
        else:
            item['percentage'] = 0
    
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
    
    # === ABUSE PREVENTION STATS ===
    abuse_stats = {
        'total_records': DemoAbusePrevention.objects.count(),
        'flagged_count': DemoAbusePrevention.objects.filter(is_flagged=True).count(),
        'blocked_count': DemoAbusePrevention.objects.filter(is_blocked=True).count(),
        'recent_flagged': DemoAbusePrevention.objects.filter(
            is_flagged=True,
            last_seen__gte=start_date
        ).count(),
    }
    
    # Demo session stats
    demo_stats = {
        'total_demo_sessions': DemoSession.objects.filter(created_at__gte=start_date).count(),
        'solo_sessions': DemoSession.objects.filter(created_at__gte=start_date, demo_mode='solo').count(),
        'team_sessions': DemoSession.objects.filter(created_at__gte=start_date, demo_mode='team').count(),
        'demo_conversions': DemoSession.objects.filter(created_at__gte=start_date, converted_to_signup=True).count(),
        'ai_limit_hit': DemoSession.objects.filter(created_at__gte=start_date, ai_generations_used__gte=20).count(),
        'project_limit_hit': DemoSession.objects.filter(created_at__gte=start_date, projects_created_in_demo__gte=2).count(),
    }
    
    # High risk visitors (potential abusers)
    high_risk_visitors = DemoAbusePrevention.objects.filter(
        Q(is_flagged=True) | Q(total_sessions_created__gte=5) | Q(total_ai_generations__gte=30)
    ).order_by('-last_seen')[:5]
    
    # Calculate demo conversion rate
    if demo_stats['total_demo_sessions'] > 0:
        demo_stats['conversion_rate'] = round(
            (demo_stats['demo_conversions'] / demo_stats['total_demo_sessions']) * 100, 1
        )
    else:
        demo_stats['conversion_rate'] = 0
    
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
        'sentiment_breakdown': sentiment_list,
        'rating_distribution': rating_distribution,
        
        # Funnel
        'funnel': funnel,
        
        # Recent activity
        'recent_feedback': recent_feedback,
        'high_engagement_users': high_engagement_users,
        
        # Abuse prevention (NEW)
        'abuse_stats': abuse_stats,
        'demo_stats': demo_stats,
        'high_risk_visitors': high_risk_visitors,
    }
    
    return render(request, 'analytics/dashboard.html', context)
