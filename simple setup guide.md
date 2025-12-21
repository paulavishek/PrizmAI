# SIMPLE DJANGO + GOOGLE ANALYTICS FEEDBACK SYSTEM

## Overview
This is a clean, simple approach that:
- ✅ Uses Django forms (no HubSpot complexity)
- ✅ Stores feedback in SQLite database
- ✅ Sends rich analytics data to Google Analytics
- ✅ Works without Celery or external dependencies
- ✅ Perfect for portfolio/demo purposes

## What You Get

### 1. User Journey Tracking
When users log out, they see:
- **Session Summary** with personalized stats
- **Engagement badge** (Low, Medium, High, Very High)
- **Simple feedback form** (rating + text + optional contact info)

### 2. Data Storage (SQLite)
All feedback stored in Django with:
- Rating (1-5 stars)
- Feedback text
- Sentiment (auto-analyzed: positive/neutral/negative)
- User info (name, email - optional)
- Linked to user session (engagement level, duration, activity)

### 3. Google Analytics Events
Three types of events sent to GA4:

**Event 1: Feedback Submitted**
```javascript
gtag('event', 'feedback_submitted', {
  'event_category': 'engagement',
  'event_label': 'logout_feedback',
  'value': 5  // rating
});
```

**Event 2: Rating Given**
```javascript
gtag('event', 'rating_given', {
  'event_category': 'satisfaction',
  'event_label': '5_stars',
  'value': 5
});
```

**Event 3: Session Completed**
```javascript
gtag('event', 'session_completed', {
  'event_category': 'user_journey',
  'engagement_level': 'high',
  'session_duration': 15,
  'tasks_created': 3,
  'ai_features_used': 2,
  'boards_viewed': 1
});
```

## Setup Instructions

### Step 1: Replace Template File

```bash
# Backup your current file
cp analytics/templates/analytics/logout_success.html analytics/templates/analytics/logout_success.html.backup

# Copy the new simple version
cp /path/to/logout_success_simple.html analytics/templates/analytics/logout_success.html
```

### Step 2: Update Views (Optional)

The current views.py should work fine, but if you want the simplified version without HubSpot:

```bash
cp /path/to/views_simple.py analytics/views.py
```

### Step 3: Verify Google Analytics is Configured

Check your `base.html` template has Google Analytics:

```html
<!-- Google Analytics 4 -->
{% if GA4_MEASUREMENT_ID %}
<script async src="https://www.googletagmanager.com/gtag/js?id={{ GA4_MEASUREMENT_ID }}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', '{{ GA4_MEASUREMENT_ID }}');
</script>
{% endif %}
```

And in your `.env` file:

```bash
GA4_MEASUREMENT_ID=G-S5W3EY5FLY  # Your GA4 ID
```

### Step 4: Test the Flow

1. **Login to your app**
2. **Do some activity:**
   - Create 2-3 tasks
   - View a board
   - Use an AI feature
   - Spend at least 2 minutes
3. **Logout**
4. **You should see:**
   - Session summary with your stats
   - Feedback form
5. **Submit feedback**
6. **Check results:**
   - Django admin: `/admin/analytics/feedback/`
   - Google Analytics: Real-time events

### Step 5: Adjust Feedback Form Threshold (Optional)

By default, feedback form shows to users who spent 2+ minutes. To change:

In `settings.py`:
```python
# Show feedback to all users (even quick visits)
ANALYTICS_MIN_ENGAGEMENT_FOR_FEEDBACK = 0

# Or show only to engaged users (5+ minutes)
ANALYTICS_MIN_ENGAGEMENT_FOR_FEEDBACK = 5
```

## Viewing Analytics

### In Django Admin

Go to `/admin/analytics/feedback/` to see:
- All feedback submissions
- Ratings and sentiment analysis
- Linked session data (engagement level, duration, etc.)
- Filter by rating, sentiment, date
- Search by name/email

### In Google Analytics

1. Go to your GA4 property
2. **Real-time View** → See events as they happen
3. **Reports** → Events → See all custom events:
   - `feedback_submitted`
   - `rating_given`
   - `session_completed`

4. **Create Custom Reports:**
   - Average rating over time
   - Feedback rate by engagement level
   - Session duration vs rating correlation

## What Gets Tracked

### In SQLite Database
```
Feedback Table:
- id
- user_id (if authenticated)
- user_session_id (links to session data)
- name (optional)
- email (optional)
- feedback_text
- rating (1-5)
- sentiment (positive/neutral/negative - auto-analyzed)
- submitted_at
- ip_address

UserSession Table (automatically tracked):
- engagement_level (low/medium/high/very_high)
- duration_minutes
- boards_viewed
- boards_created
- tasks_created
- tasks_completed
- ai_features_used
- pages_visited
```

### In Google Analytics
```
Events sent:
1. feedback_submitted
2. rating_given  
3. session_completed (with all engagement metrics)

User properties:
- engagement_level
- session_duration
- feature_usage
```

## Portfolio Benefits

This simple approach lets you demonstrate:

### 1. Product Analytics Instrumentation
- Custom event tracking
- User journey mapping
- Engagement scoring
- Conversion funnel analysis

### 2. Data-Driven Decision Making
"Based on feedback analysis, I discovered that users with 'high' engagement 
levels rated the product 4.2/5 on average, compared to 3.1/5 for 'low' 
engagement users. This insight led us to focus on improving onboarding 
to get users to the 'aha moment' faster."

### 3. User Research at Scale
- Automated sentiment analysis
- Quantitative (ratings) + qualitative (text) feedback
- Segmentation by engagement level
- Feedback conversion rate tracking

### 4. Technical Product Skills
- Django backend development
- JavaScript analytics integration
- Database design
- Sentiment analysis implementation

## Interview Talking Points

**For PM Interviews:**

"I built a comprehensive feedback and analytics system that tracks user 
engagement throughout their session and captures structured feedback on 
logout. The system automatically analyzes sentiment, segments users by 
engagement level, and sends detailed events to Google Analytics for 
deeper analysis.

This enabled data-driven decisions like [example: discovering that users 
who tried AI features were 3x more likely to give positive feedback, 
leading to better feature discoverability in onboarding]."

**For Technical Discussions:**

"The system uses Django middleware to passively track user behavior, 
calculates an engagement score based on multiple factors (duration, 
feature usage, content creation), and presents personalized feedback 
prompts. Sentiment analysis uses VADER for text analysis with rating-based 
fallback. All data is stored in SQLite and simultaneously sent to GA4 for 
cross-platform analysis."

## Troubleshooting

### Feedback not appearing in Django admin?
- Check `/admin/analytics/feedback/`
- Look for errors in browser console (F12)
- Check Django logs for errors
- Verify CSRF token is present in form

### Google Analytics events not showing?
- Check GA4_MEASUREMENT_ID is set in settings
- Open browser console and verify `gtag` is defined
- Go to GA4 Real-time view while testing
- Events can take 24-48 hours to appear in standard reports

### Session stats not showing on logout?
- Ensure SessionTrackingMiddleware is in MIDDLEWARE
- Check that middleware is BEFORE SessionTimeoutMiddleware
- Verify you spent enough time (check MIN_ENGAGEMENT_FOR_FEEDBACK)
- Check Django logs for middleware errors

## Next Steps

Once working, you can enhance with:

1. **Email follow-ups** to feedback providers
2. **Feedback categorization** (bug/feature/praise)
3. **A/B testing** different feedback prompts
4. **NPS calculation** from ratings
5. **Feedback trends** dashboard
6. **Automated alerts** for negative feedback

But the current simple version is perfect for demonstrating PM skills in 
interviews while being easy to maintain and explain!

## Files Changed

- `analytics/templates/analytics/logout_success.html` - Main feedback form
- `analytics/views.py` - Simplified views (optional)
- No other changes needed!
- No Celery required
- No HubSpot complexity
- No external dependencies

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
                       f"Engagement: {engagement_level}, Show Form: {show_feedback_form}")
            
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
            logger.warning(f"Logout - No user_session found! User: {request.user}")
        
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
        
        # Create feedback
        feedback = Feedback.objects.create(
            user_session=user_session,
            user=request.user if request.user.is_authenticated else None,
            name=data.get('name', ''),
            email=data.get('email', ''),
            feedback_text=data.get('feedback', ''),
            rating=data.get('rating'),
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