# 🎯 Analytics System - Quick Reference

## 📁 File Structure

```
analytics/
├── models.py              # UserSession, Feedback, AnalyticsEvent
├── middleware.py          # SessionTrackingMiddleware
├── views.py               # CustomLogoutView, analytics_dashboard
├── admin.py               # Admin interface
├── utils.py               # HubSpot & GA helpers
├── urls.py                # URL routing
└── templates/
    └── analytics/
        ├── logout_success.html    # Feedback form
        └── dashboard.html         # Analytics dashboard (TODO)
```

## 🔗 Important URLs

| URL | Purpose | Access |
|-----|---------|--------|
| `/analytics/logout/` | Custom logout with feedback | All users |
| `/analytics/dashboard/` | Analytics dashboard | Staff only |
| `/analytics/api/submit-feedback/` | AJAX feedback endpoint | All users |
| `/admin/analytics/` | Django admin | Superuser |

## 🎯 Key Models

### UserSession
Tracks user activity during their session.

**Key Fields:**
- `user` - Authenticated user (null for anonymous)
- `duration_minutes` - Session length
- `engagement_level` - low/medium/high/very_high
- `tasks_created`, `boards_created`, `ai_features_used` - Activity counters

**Key Methods:**
- `calculate_engagement_score()` - Returns 0-12 score
- `update_engagement_level()` - Updates based on score
- `end_session(reason, exit_page)` - Closes session

### Feedback
Stores user feedback submissions.

**Key Fields:**
- `user_session` - Link to UserSession
- `feedback_text` - Feedback content
- `rating` - 1-5 star rating
- `sentiment` - positive/neutral/negative
- `hubspot_contact_id` - Synced contact ID

**Key Methods:**
- `analyze_sentiment()` - Auto-detect sentiment

## 📊 Engagement Scoring

| Level | Score | Criteria |
|-------|-------|----------|
| **Very High** | 9-12 | 20+ min, 5+ tasks, 5+ AI features |
| **High** | 6-8 | 10+ min, 2+ tasks, 2+ AI features |
| **Medium** | 3-5 | 5+ min, 1+ task, 1+ AI feature |
| **Low** | 0-2 | Quick visit, minimal activity |

## 🔧 Configuration

### settings.py

```python
INSTALLED_APPS = [
    # ...
    'analytics',
]

MIDDLEWARE = [
    # ...
    'analytics.middleware.SessionTrackingMiddleware',
]

# Analytics settings
GA4_MEASUREMENT_ID = os.getenv('GA4_MEASUREMENT_ID', '')
HUBSPOT_API_KEY = os.getenv('HUBSPOT_API_KEY', '')
```

### .env

```env
GA4_MEASUREMENT_ID=G-XXXXXXXXXX
HUBSPOT_API_KEY=your-api-key
HUBSPOT_PORTAL_ID=12345678
```

## 🚀 Quick Commands

```powershell
# Create database tables
python manage.py makemigrations analytics
python manage.py migrate

# Create superuser (if needed)
python manage.py createsuperuser

# Run server
python manage.py runserver

# Access admin
# http://localhost:8000/admin/analytics/
```

## 📈 Google Analytics Events

### Automatically Tracked

- Page views (all pages)
- User type (registered/anonymous)
- Session duration
- Device type

### Custom Events (add manually)

```html
<script>
gtag('event', 'feature_used', {
  'feature_name': 'export_board',
  'engagement_level': '{{ engagement_level }}'
});
</script>
```

## 🎨 Customization Points

### 1. Change Engagement Thresholds

**File:** `analytics/models.py`
**Method:** `UserSession.calculate_engagement_score()`

```python
# Current: 20 min = 3 points
if self.duration_minutes >= 20:
    score += 3

# Change to: 30 min = 3 points
if self.duration_minutes >= 30:
    score += 3
```

### 2. Customize Feedback Form

**File:** `analytics/templates/analytics/logout_success.html`

- Add/remove fields
- Change styling
- Modify messaging

### 3. Add Custom Event Tracking

**In your views:**

```python
from analytics.models import AnalyticsEvent

if hasattr(request, 'user_session'):
    AnalyticsEvent.objects.create(
        user_session=request.user_session,
        event_name='custom_action',
        event_category='features',
        event_label='feature_name'
    )
```

## 🐛 Troubleshooting

### Sessions Not Creating

**Check:**
1. ✅ Middleware in settings.py?
2. ✅ Migrations run?
3. ✅ Path not in SKIP_PATHS?

**Debug:**
```python
# In view
print(f"Has session: {hasattr(request, 'user_session')}")
if hasattr(request, 'user_session'):
    print(f"Session ID: {request.user_session.id}")
```

### Google Analytics Not Working

**Check:**
1. ✅ GA4_MEASUREMENT_ID in .env?
2. ✅ Browser not blocking?
3. ✅ DEBUG = False? (GA only loads in production)

**Quick Test:**
Remove `{% if not debug %}` from base.html temporarily

### HubSpot Sync Failing

**Check:**
```python
from analytics.utils import HubSpotIntegration
hs = HubSpotIntegration()
print(f"Configured: {hs.is_configured()}")
print(f"API Key: {hs.api_key[:10]}..." if hs.api_key else "Not set")
```

## 📊 Admin Actions

### UserSession Admin
- View all sessions
- Filter by engagement/device
- Cannot add (auto-created)

### Feedback Admin
- View feedback
- **Sync to HubSpot** (bulk action)
- **Mark as Reviewed** (bulk action)
- **Mark as Resolved** (bulk action)
- Add internal notes

## 🎓 Key Features for Interviews

1. **Multi-layered Analytics**
   - Django (server-side product metrics)
   - Google Analytics (client-side traffic)
   - HubSpot (CRM & follow-up)

2. **Intelligent Engagement Scoring**
   - Automatic user segmentation
   - Personalized feedback requests
   - 0-12 point scoring system

3. **Privacy-First Design**
   - GDPR compliant
   - IP anonymization
   - User ID hashing
   - Explicit consent

4. **Production-Ready**
   - Middleware-based (efficient)
   - Admin interface
   - Async-ready (Celery)
   - Error handling

## 🔗 External Links

- **Google Analytics:** https://analytics.google.com/
- **HubSpot:** https://app.hubspot.com/
- **Django Docs:** https://docs.djangoproject.com/

## ⚡ Performance Tips

1. **Use Database Indexes** (already added)
   - session_key
   - user + session_start
   - engagement_level

2. **Batch Operations**
   - Middleware saves multiple fields at once
   - Use `update_fields` parameter

3. **Async Processing** (for production)
   ```python
   # Use Celery for HubSpot sync
   @shared_task
   def sync_to_hubspot(feedback_id):
       # ...
   ```

## 📝 Testing Checklist

- [ ] Sessions created on page visit
- [ ] Activity counters increment
- [ ] Engagement score calculated
- [ ] Logout shows session stats
- [ ] Feedback form appears (if engaged)
- [ ] Feedback submits successfully
- [ ] Admin interface works
- [ ] GA events tracked (in GA4 real-time)
- [ ] HubSpot sync works (if configured)

## 🎉 Done!

Your analytics system is ready to track user behavior and collect valuable feedback!

**Next:** Run migrations and start tracking! 🚀
