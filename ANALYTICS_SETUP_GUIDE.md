# 🎯 Analytics & Feedback System - Setup Guide

This guide will help you integrate the complete analytics and feedback system into your PrizmAI project.

## 📋 What's Been Implemented

You now have a **three-layered analytics strategy**:

### 1. **Django Custom Tracking** (Server-side)
- User session tracking with engagement scoring
- Feature usage analytics (boards, tasks, AI features)
- Personalized feedback collection based on engagement
- Integration with HubSpot CRM

### 2. **Google Analytics 4** (Client-side)
- Traffic source tracking
- Page view analytics
- Real-time user monitoring
- Device and browser analytics

### 3. **HubSpot CRM** (Contact Management)
- Automatic contact creation
- Feedback syncing
- Email automation capabilities
- Lead management

---

## 🚀 Quick Start

### Step 1: Run Migrations

Create the database tables for analytics:

```powershell
python manage.py makemigrations analytics
python manage.py migrate
```

### Step 2: Configure Environment Variables

Add these to your `.env` file:

```env
# Google Analytics 4
GA4_MEASUREMENT_ID=G-XXXXXXXXXX  # Get this from Google Analytics

# HubSpot CRM (Optional - for feedback management)
HUBSPOT_API_KEY=your-hubspot-api-key
HUBSPOT_PORTAL_ID=your-portal-id
HUBSPOT_FEEDBACK_FORM_ID=your-form-id
```

### Step 3: Set Up Google Analytics 4

1. **Create GA4 Property:**
   - Go to https://analytics.google.com/
   - Create new account → Create property
   - Property name: "PrizmAI"
   - Choose "Web" platform
   - Copy your **Measurement ID** (format: `G-XXXXXXXXXX`)

2. **Add to .env:**
   ```env
   GA4_MEASUREMENT_ID=G-XXXXXXXXXX
   ```

3. **Test It:**
   - Start your server: `python manage.py runserver`
   - Visit your site
   - Check GA4 Real-time report - you should see yourself!

### Step 4: Set Up HubSpot (Optional)

1. **Create Free HubSpot Account:**
   - Go to https://www.hubspot.com/
   - Sign up for free account

2. **Get API Key:**
   - Go to Settings → Integrations → API Key
   - Generate and copy your API key

3. **Create Feedback Form:**
   - Go to Marketing → Forms
   - Create new embedded form
   - Add fields: Name, Email, Feedback, Rating
   - Copy Form ID and Portal ID

4. **Add to .env:**
   ```env
   HUBSPOT_API_KEY=your-api-key-here
   HUBSPOT_PORTAL_ID=12345678
   HUBSPOT_FEEDBACK_FORM_ID=form-id-here
   ```

---

## 📊 How It Works

### User Session Tracking

The `SessionTrackingMiddleware` automatically tracks:

- **Duration**: How long users spend in your app
- **Activity**: Boards created, tasks completed, AI features used
- **Engagement Score**: 0-12 scale based on activity
- **Device Info**: Desktop/mobile/tablet detection

### Logout Experience

When users log out, they see:

1. **Session Summary** - Visual stats of their activity
2. **Personalized Feedback Form** - Only if they spent enough time
3. **Star Rating** - Quick 1-5 star rating
4. **Optional Details** - Text feedback and contact info

### Data Flow

```
User Activity → SessionTrackingMiddleware → UserSession Model
                                                    ↓
                                            Engagement Scoring
                                                    ↓
User Logout → CustomLogoutView → Feedback Form → Feedback Model
                                                    ↓
                                              HubSpot Sync
```

---

## 🎨 Features

### Engagement Levels

Users are automatically categorized:

- **Very High** (9-12 points): Power users, explored many features
- **High** (6-8 points): Active users, good engagement
- **Medium** (3-5 points): Casual users, moderate engagement
- **Low** (0-2 points): Brief visitors, minimal engagement

### Automatic Tracking

These actions are tracked automatically:

| Action | Tracking |
|--------|----------|
| View board | `boards_viewed++` |
| Create board | `boards_created++` |
| Create task | `tasks_created++` |
| Complete task | `tasks_completed++` |
| Use AI feature | `ai_features_used++` |
| Page navigation | `pages_visited++` |

### Google Analytics Events

Custom events sent to GA4:

- `sign_up` - User registration
- `board_created` - New board
- `task_created` - New task
- `ai_feature_used` - AI feature usage
- `feedback_submitted` - Feedback submission

---

## 🛠️ Admin Interface

Access the analytics admin at `/admin/analytics/`:

### UserSession Admin
- View all user sessions
- Filter by engagement level, device type
- See detailed activity metrics
- Export session data

### Feedback Admin
- View all feedback submissions
- Filter by rating, sentiment, status
- Sync to HubSpot with one click
- Add internal notes
- Track follow-up status

### Actions Available
- **Sync to HubSpot** - Bulk sync feedback
- **Mark as Reviewed** - Mark feedback as reviewed
- **Mark as Resolved** - Mark feedback as resolved

---

## 📈 Analytics Dashboard

Access at: `/analytics/dashboard/`

**Requires:** Staff member status

### Dashboard Sections

1. **Overview Metrics**
   - Total sessions
   - Total users
   - Feedback count
   - Return visitor rate

2. **Engagement Breakdown**
   - Sessions by engagement level
   - Average metrics per level
   - Feature adoption rates

3. **Daily Trends**
   - Session count by day
   - User growth
   - Average duration trends

4. **Feedback Analysis**
   - Average rating
   - Sentiment distribution
   - Recent feedback

5. **Conversion Funnel**
   - Visitors → Task creators → AI adopters → Feedback givers
   - Conversion rates at each stage

---

## 🔍 Usage Examples

### Track Custom Events

In your views:

```python
from analytics.models import AnalyticsEvent

def my_view(request):
    if hasattr(request, 'user_session'):
        AnalyticsEvent.objects.create(
            user_session=request.user_session,
            event_name='custom_action',
            event_category='features',
            event_label='feature_name',
            event_value=1
        )
```

### Get User Analytics

```python
from analytics.models import UserSession

# Get user's total activity
user_sessions = UserSession.objects.filter(user=request.user)
total_time = user_sessions.aggregate(Sum('duration_minutes'))
total_tasks = user_sessions.aggregate(Sum('tasks_created'))

# Get engagement breakdown
engagement = UserSession.objects.filter(
    user=request.user
).values('engagement_level').annotate(count=Count('id'))
```

### Manual HubSpot Sync

```python
from analytics.utils import HubSpotIntegration

hubspot = HubSpotIntegration()
if hubspot.is_configured():
    contact_id, engagement_id = hubspot.sync_feedback_to_hubspot(feedback)
```

---

## 🎯 Customization

### Change Engagement Scoring

Edit `analytics/models.py` in the `UserSession.calculate_engagement_score()` method:

```python
def calculate_engagement_score(self):
    score = 0
    
    # Customize point allocation
    if self.duration_minutes >= 30:  # Increase threshold
        score += 3
    
    # Add new criteria
    if self.boards_created >= 3:
        score += 2
    
    return score
```

### Customize Feedback Form

Edit `analytics/templates/analytics/logout_success.html` to:

- Add/remove form fields
- Change styling
- Modify messaging based on engagement

### Change Session Timeout

In `settings.py`:

```python
ANALYTICS_SESSION_TIMEOUT = 60  # 60 minutes instead of 30
```

---

## 📱 Google Analytics Custom Events

Add custom tracking to your templates:

```html
<!-- Track button click -->
<button onclick="trackFeatureUsage('board_export')">
  Export Board
</button>

<script>
function trackFeatureUsage(featureName) {
  if (typeof gtag !== 'undefined') {
    gtag('event', 'feature_used', {
      'feature_name': featureName,
      'user_type': '{{ user.is_authenticated|yesno:"registered,anonymous" }}'
    });
  }
}
</script>
```

---

## 🔒 Privacy & GDPR Compliance

Built-in privacy features:

✅ **IP Anonymization** - Google Analytics anonymizes IPs  
✅ **User ID Hashing** - User IDs are MD5 hashed before sending to GA  
✅ **Email Consent** - Users opt-in for follow-up emails  
✅ **Secure Cookies** - SameSite=None;Secure flags  

### Data Retention

Configure in GA4:
- Go to Admin → Data Settings → Data Retention
- Set appropriate retention period (2, 14, 26, 38, 50 months)

---

## 🐛 Troubleshooting

### Sessions Not Being Created

**Check:**
1. Middleware is in INSTALLED_APPS
2. Middleware order (should be after SessionMiddleware)
3. Paths aren't in SKIP_PATHS list

**Debug:**
```python
# In views.py
if hasattr(request, 'user_session'):
    print(f"Session ID: {request.user_session.id}")
else:
    print("No user session attached")
```

### Google Analytics Not Tracking

**Check:**
1. `GA4_MEASUREMENT_ID` is set in .env
2. `DEBUG = False` (GA only loads in production mode)
3. Browser isn't blocking GA (check browser console)

**Test in Dev:**
Remove the `{% if not debug %}` check in base.html temporarily

### HubSpot Sync Failing

**Check:**
1. API key is valid
2. Portal ID is correct
3. Email field exists in HubSpot contacts
4. Check logs: `python manage.py shell`
   ```python
   from analytics.utils import HubSpotIntegration
   hs = HubSpotIntegration()
   print(hs.is_configured())
   ```

---

## 📊 Monitoring Performance

### Database Queries

Analytics middleware runs on every request. Monitor with Django Debug Toolbar:

```python
# In development
pip install django-debug-toolbar

# settings.py
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
```

### Async Processing (Recommended for Production)

For high-traffic sites, process analytics async with Celery:

```python
# tasks.py
from celery import shared_task

@shared_task
def sync_feedback_to_hubspot(feedback_id):
    feedback = Feedback.objects.get(id=feedback_id)
    hubspot = HubSpotIntegration()
    hubspot.sync_feedback_to_hubspot(feedback)

# In views.py
sync_feedback_to_hubspot.delay(feedback.id)  # Async
```

---

## 🎓 Interview Talking Points

When discussing this with recruiters/interviewers:

1. **Multi-layered Analytics**
   - "I implemented a comprehensive analytics system with three layers: Django for deep product metrics, Google Analytics for traffic analysis, and HubSpot for CRM integration."

2. **User Segmentation**
   - "I built an engagement scoring system that automatically segments users into four tiers based on their activity, enabling personalized feedback requests."

3. **Privacy First**
   - "The system is GDPR-compliant with IP anonymization, user ID hashing, and explicit email consent."

4. **Data-Driven Product Development**
   - "By tracking feature adoption and correlating it with feedback, we can identify which features drive user engagement and which need improvement."

---

## 📚 Next Steps

### Immediate
- [ ] Run migrations
- [ ] Set up Google Analytics
- [ ] Test logout flow
- [ ] Check admin interface

### Optional Enhancements
- [ ] Set up HubSpot integration
- [ ] Create custom dashboard templates
- [ ] Add Celery for async processing
- [ ] Implement email automation
- [ ] Create cohort analysis
- [ ] Add A/B testing framework

---

## 🤝 Support

Need help? Check:

1. **Documentation**: Your comprehensive docs in this project
2. **Django Admin**: `/admin/analytics/` for data inspection
3. **Logs**: Check console output for errors
4. **GA4 Real-time**: Verify events are being tracked

---

## 🎉 You're Ready!

Your analytics system is now fully integrated! Users will automatically have their sessions tracked, and you'll get valuable feedback to iterate on your product.

**Test it:**
1. Start server: `python manage.py runserver`
2. Create some boards/tasks
3. Log out
4. See your session stats and feedback form!
5. Check `/admin/analytics/` to see your data
6. Check GA4 Real-time report

Happy tracking! 🚀
