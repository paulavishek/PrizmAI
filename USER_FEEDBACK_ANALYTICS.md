# 📈 User Feedback & Behavior Tracking System

PrizmAI includes a **comprehensive user feedback and behavior tracking system** that helps you understand how users interact with your application and continuously improve the platform.

---

## 🎯 Overview

The user feedback system captures three key dimensions:

1. **User Feedback** - Direct feedback from users with sentiment analysis
2. **Session Tracking** - User behavior and engagement metrics
3. **Event Analytics** - Detailed tracking of user actions and feature usage

This system provides:
- 📊 Real-time feedback collection with sentiment analysis
- 🔄 User session monitoring and engagement scoring
- 📈 Behavioral analytics to understand feature adoption
- 🎯 Integration with Google Analytics and HubSpot
- 🔒 GDPR-compliant data tracking

---

## 📋 User Feedback Features

### Submitting Feedback

Users can provide feedback through the feedback form with:
- **Rating** - Quick 1-5 star rating
- **Comment** - Optional detailed feedback
- **Category** - Feedback type (bug, feature request, improvement, other)
- **Feature Tags** - Which features the feedback relates to

### Automatic Sentiment Analysis

Every piece of feedback is automatically analyzed for sentiment using:

#### **Rating-Based Sentiment**
- ⭐ 1-2 stars = **Negative**
- ⭐ 3 stars = **Neutral**
- ⭐ 4-5 stars = **Positive**

#### **Text-Based Sentiment (VADER)**
The system uses **VADER Sentiment Analysis** for text-based feedback:
- Analyzes the tone and sentiment of written comments
- Compound score: **≥ 0.05 = Positive**, **< 0.05 = Negative**
- Identifies emotional intensity and context
- Gracefully falls back if VADER is unavailable

**Example Analysis:**
```
User Feedback: "Love this feature! Works great!"
├─ Rating Sentiment: Positive (5 stars)
├─ Text Sentiment: Positive (VADER score: 0.89)
└─ Final: Positive ✅
```

### Feedback Categories

Track different types of feedback:
- 🐛 **Bug** - Problems or defects
- ✨ **Feature Request** - New capabilities
- 📈 **Improvement** - Enhancement suggestions
- 💭 **Other** - General comments

### HubSpot Integration

Feedback is automatically synced to HubSpot for:
- CRM customer insights
- Marketing analysis
- Customer support integration
- Historical feedback tracking

**Status:**
- ✅ Asynchronous sync using Celery (non-blocking)
- ✅ Automatic retry logic (3 retries, 60-second delays)
- ✅ Error handling and logging

---

## 🔄 User Session Tracking

### Session Lifecycle

Each user session is tracked from login to logout with detailed metrics.

#### **Session Creation**
When a user logs in, a `UserSession` record captures:
```python
# Session Information
├─ user: The authenticated user
├─ session_start: Timestamp of login
├─ ip_address: User's IP address
├─ user_agent: Browser/device information
└─ is_anonymous: True for anonymous visitors
```

#### **Session Activity**
During the session, the system tracks:
```python
# Activity Metrics
├─ page_views: Number of pages visited
├─ actions_performed: Count of user actions
├─ duration_minutes: Total session time
├─ last_activity: Last action timestamp
└─ device_type: Mobile, tablet, desktop
```

#### **Session Termination**
When session ends, recorded information includes:
```python
# Termination Details
├─ session_end: Logout timestamp
├─ exit_page: Last page viewed
├─ exit_reason: How session ended
│  ├─ "logout" - User logged out
│  ├─ "timeout" - Session timeout
│  └─ "navigation" - User navigated away
└─ engagement_score: Calculated engagement level
```

### Engagement Scoring

Users receive an engagement score (0-100) based on:
- **Session Duration** - How long they spent in the app
- **Activity Level** - Number of actions performed
- **Feature Exploration** - How many different features used
- **Return Visits** - Frequency of returning

**Calculation Logic:**
```
Engagement Score = 
    (Duration Factor × 30) +
    (Activity Factor × 30) +
    (Feature Factor × 25) +
    (Return Factor × 15)
```

**Example:**
```
User Session Analysis:
├─ Duration: 45 minutes → Score: 28/30
├─ Actions: 156 actions → Score: 28/30
├─ Features: Used 8 features → Score: 22/25
├─ Return Visits: 12th session → Score: 15/15
└─ Total Engagement: 93/100 ⭐
```

### Return Visitor Tracking

System automatically identifies:
- ✅ New users on their first session
- ✅ Returning users (2+ sessions)
- ✅ Active users (sessions in last 30 days)
- ✅ Inactive users (no sessions in 30+ days)

**Metrics:**
```python
# Tracking Example
new_users = User.objects.annotate(
    session_count=Count('usersession')
).filter(session_count=1).count()

returning_users = User.objects.annotate(
    session_count=Count('usersession')
).filter(session_count__gt=1).count()

registration_rate = (new_users / total_sessions) * 100
```

---

## 📊 Event Analytics

### Tracked Events

The system tracks user actions across the platform:

```python
# Event Categories
├─ Page Views
│  └─ User navigated to a page
├─ Feature Interactions
│  ├─ Kanban board drag-drop
│  ├─ AI recommendation clicked
│  ├─ Filter applied
│  └─ Task created/updated
├─ Form Submissions
│  ├─ User registration
│  ├─ Feedback submission
│  └─ Task creation
└─ System Events
   ├─ API calls made
   ├─ Errors encountered
   └─ Session timeouts
```

### Event Data Captured

Each event includes:
```python
class AnalyticsEvent(models.Model):
    user              # Who performed the action
    event_type        # What action was performed
    event_category    # Category of action
    page_url          # Which page
    timestamp         # When it happened
    duration_ms       # How long it took
    data              # Additional context (JSON)
```

### Bulk Event Processing

Events are efficiently batched to prevent database overload:
- Events collected during request processing
- Bulk created at end of request (not per-event)
- Significantly reduces database writes
- Improves performance on high-traffic operations

---

## 🔍 Analytics Dashboard

### Key Metrics Tracked

#### **User Acquisition**
```python
# Total User Analysis
total_registered_users      # Users with accounts
total_anonymous_visitors    # Anonymous sessions
total_unique_visitors       # Combined unique users
registration_rate           # New users per period
```

#### **Engagement Metrics**
```python
# Activity Analysis
average_session_duration    # Avg time spent per session
sessions_per_user          # How often users return
actions_per_session        # Activity intensity
page_views_per_session     # Navigation behavior
feature_adoption_rate      # % using each feature
```

#### **Retention Analysis**
```python
# User Retention
day_1_retention            # % active after 1 day
week_1_retention           # % active after 1 week
month_1_retention          # % active after 1 month
returning_user_rate        # % of users who return
```

#### **Sentiment Analysis**
```python
# Feedback Analysis
positive_feedback_rate     # % positive ratings
negative_feedback_rate     # % negative ratings
average_rating             # Mean rating (1-5)
feedback_volume            # Feedback submissions
sentiment_trends           # Sentiment over time
```

### Querying Analytics Data

#### **Daily Active Users**
```python
from django.db.models.functions import TruncDate
from django.db.models import Count, Avg

daily_metrics = UserSession.objects.annotate(
    date=TruncDate('session_start')
).values('date').annotate(
    unique_users=Count('user', distinct=True),
    total_sessions=Count('id'),
    avg_duration=Avg('duration_minutes'),
    avg_engagement=Avg('engagement_score')
).order_by('date')
```

#### **Feature Adoption**
```python
feature_usage = AnalyticsEvent.objects.filter(
    event_type__in=['kanban_view', 'burndown_view', 'ai_recommend']
).values('event_type').annotate(
    count=Count('id'),
    unique_users=Count('user', distinct=True)
)
```

#### **Sentiment Trends**
```python
from django.db.models import Q

positive = Feedback.objects.filter(
    Q(rating__gte=4) | Q(sentiment='positive')
).count()

negative = Feedback.objects.filter(
    Q(rating__lte=2) | Q(sentiment='negative')
).count()

sentiment_ratio = (positive / (positive + negative)) * 100
```

---

## 🔐 Privacy & Security

### GDPR Compliance

The system is designed with privacy-first principles:

#### **Data Minimization**
- Only essential data is collected
- No personally identifiable information in events
- User IDs hashed for Google Analytics

#### **Data Retention**
```python
# Configurable Retention Policy
SESSION_RETENTION_DAYS = 90      # Delete sessions after 90 days
EVENT_RETENTION_DAYS = 180       # Keep events for 6 months
FEEDBACK_RETENTION_DAYS = 365    # Archive feedback after 1 year
```

#### **User Consent**
- Users are informed about tracking
- Opt-out available in privacy settings
- Cookie consent banners displayed
- Clear privacy policy linked

#### **Data Security**
- ✅ Encrypted in transit (HTTPS)
- ✅ Encrypted at rest (database-level)
- ✅ Rate limiting on feedback submissions (5-minute cooldown per IP)
- ✅ Secure HubSpot API integration with retry logic
- ✅ Audit logging of data access

---

## 🚀 Rate Limiting & Security

### Feedback Submission Rate Limiting

Protects against spam and abuse:

```python
# Rate Limiting Configuration
FEEDBACK_RATE_LIMIT = 5              # Max 1 submission
FEEDBACK_COOLDOWN_MINUTES = 5        # Per IP per 5 minutes

# Returns HTTP 429 if exceeded:
{
    "status": "error",
    "message": "Too many feedback submissions. Try again in 4 minutes."
}
```

### Protection Features
- ✅ Per-IP rate limiting
- ✅ Cache-based tracking
- ✅ Automatic cooldown periods
- ✅ Friendly error messages
- ✅ Prevents database overload

---

## 🔧 Configuration

### Settings

The analytics system is configured in `kanban_board/settings.py`:

```python
# Middleware Configuration
MIDDLEWARE = [
    # ... other middleware ...
    'analytics.middleware.SessionTrackingMiddleware',
    'analytics.middleware.SessionTimeoutMiddleware',
]

# Celery Configuration (for async HubSpot sync)
CELERY_BROKER_URL = 'redis://localhost:6379'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

# Analytics Settings
ANALYTICS_ENABLED = True
HUBSPOT_INTEGRATION_ENABLED = True
GOOGLE_ANALYTICS_ID = 'G-XXXXX'

# Event tracking
TRACK_PAGE_VIEWS = True
TRACK_FEATURE_USAGE = True
BULK_EVENT_CREATION = True  # Batch events instead of individual writes
```

### Customization

#### **Add Custom Events**
```python
from analytics.models import AnalyticsEvent

# Track custom event
AnalyticsEvent.objects.create(
    user=request.user,
    event_type='custom_feature_used',
    event_category='features',
    page_url=request.path,
    data={
        'feature_name': 'smart_scheduling',
        'duration_seconds': 45
    }
)
```

#### **Custom Engagement Calculation**
```python
# Override engagement scoring
def calculate_custom_engagement(session):
    duration_score = min(session.duration_minutes / 120 * 30, 30)
    activity_score = min(session.actions_performed / 200 * 30, 30)
    
    return duration_score + activity_score
```

---

## 📊 Analytics Endpoints

### API Reference

Get feedback and analytics data via REST API:

```bash
# Get user's feedback
GET /api/feedback/?user=<user_id>

# Get session analytics
GET /api/analytics/sessions/?date_from=2025-01-01

# Get engagement metrics
GET /api/analytics/engagement/?user=<user_id>

# Get event analytics
GET /api/analytics/events/?event_type=feature_used
```

See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for complete API reference.

---

## 🔗 Integration with External Services

### Google Analytics Integration

User IDs are hashed and sent to Google Analytics:
```javascript
// Hashed user ID sent to GA4
gtag('config', 'G-XXXXX', {
    'user_id': hashedUserId
});

// Track custom events
gtag('event', 'board_created', {
    'value': 1
});
```

### HubSpot Integration

Feedback automatically syncs to HubSpot:
- ✅ Feedback records stored in HubSpot
- ✅ Customer profiles enriched with feedback data
- ✅ Sentiment analysis available in CRM
- ✅ Support team can access customer feedback

**Async Processing:**
```python
# Non-blocking, retries automatically
from analytics.tasks import sync_feedback_to_hubspot_task

sync_feedback_to_hubspot_task.delay(feedback_id=123)
```

---

## 📈 Usage Examples

### Track User Registration

```python
class UserRegistrationView(CreateView):
    def form_valid(self, form):
        user = form.save()
        
        # Link session to user if exists
        if hasattr(self.request, 'user_session'):
            session = self.request.user_session
            session.user = user
            session.registered_during_session = True
            session.save()
        
        return redirect('home')
```

### Analyze Feature Adoption

```python
from django.db.models import Count

# Which features are most used?
top_features = AnalyticsEvent.objects.filter(
    event_category='features'
).values('event_type').annotate(
    usage_count=Count('id'),
    unique_users=Count('user', distinct=True)
).order_by('-usage_count')[:10]

for feature in top_features:
    print(f"{feature['event_type']}: {feature['unique_users']} users")
```

### Get User Engagement Report

```python
from django.db.models import Avg, Count

user = User.objects.get(pk=user_id)
sessions = UserSession.objects.filter(user=user)

report = {
    'total_sessions': sessions.count(),
    'avg_engagement': sessions.aggregate(Avg('engagement_score'))['engagement_score__avg'],
    'total_time_minutes': sessions.aggregate(Sum('duration_minutes'))['duration_minutes__sum'],
    'last_active': sessions.latest('session_end').session_end,
}
```

---

## 🐛 Troubleshooting

### Analytics Not Recording

**Problem:** Events not appearing in database

**Solutions:**
1. Check middleware is enabled in `MIDDLEWARE` setting
2. Verify `ANALYTICS_ENABLED = True` in settings
3. Check database migrations: `python manage.py migrate analytics`
4. Review middleware order: SessionTrackingMiddleware before SessionTimeoutMiddleware

### Engagement Score Not Updating

**Problem:** Engagement score stuck on old value

**Solutions:**
1. Check `last_engagement_update` field is being set
2. Verify 5-minute cooldown logic in middleware
3. Manually trigger: `session.save(force_update=True)`

### HubSpot Sync Failing

**Problem:** Feedback not syncing to HubSpot

**Solutions:**
1. Check HubSpot API key is valid: `HUBSPOT_API_KEY`
2. Verify Celery is running: `celery -A kanban_board worker -l info`
3. Check Redis is accessible: `redis-cli ping`
4. Review task logs for errors

### High Database Load

**Problem:** Too many event records creating performance issues

**Solutions:**
1. Enable `BULK_EVENT_CREATION = True`
2. Implement event archival script
3. Add database index on `event_type` and `timestamp`
4. Consider event sampling for high-traffic features

---

## 📚 Related Documentation

- **[ANALYTICS_SETUP_GUIDE.md](ANALYTICS_SETUP_GUIDE.md)** - Setup and configuration
- **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)** - Analytics API endpoints
- **[SECURITY_OVERVIEW.md](SECURITY_OVERVIEW.md)** - Security & compliance
- **[FEATURES.md](FEATURES.md)** - All platform features
- **[README.md](README.md)** - Project overview

---

## 🎓 Best Practices

### For Product Teams
1. **Monitor Engagement Scores** - Track overall user engagement trends
2. **Analyze Sentiment** - Understand customer satisfaction
3. **Track Feature Adoption** - See which features are most valuable
4. **Identify Drop-off Points** - See where users lose interest

### For Development Teams
1. **Use Event Tracking** - Understand how features are actually used
2. **Monitor Error Events** - Catch bugs through analytics
3. **Optimize High-Usage Features** - Focus on features users love
4. **A/B Test with Analytics** - Measure impact of changes

### For Operations
1. **Monitor Session Health** - Detect authentication issues
2. **Track Performance Metrics** - Session duration, page loads
3. **Identify Bot Traffic** - Anomalous usage patterns
4. **Plan Capacity** - Understanding peak usage times

---

**Last Updated:** December 2025  
**Status:** Production Ready ✅
