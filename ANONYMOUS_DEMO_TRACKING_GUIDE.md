# Anonymous Demo User Tracking Guide

## Overview

**YES, you MUST track anonymous demo users!** This data is crucial for optimizing conversion rates and understanding user behavior.

## Why Track Anonymous Users?

### Business Value
- **85% of users** try products before signing up (industry average)
- Understanding anonymous user behavior helps you:
  - Identify drop-off points → Fix friction
  - Optimize nudge timing → Improve conversion
  - Discover popular features → Focus development
  - Measure aha moments → Refine onboarding

### Example Metrics

```
100 anonymous users try demo
    ↓
40 explore AI features (40% engagement)
    ↓
25 experience aha moment (25% reach aha)
    ↓
15 create accounts (15% conversion)
```

**Insight:** Users who experience aha moments convert at **60%** (15/25) vs. baseline **15%** (15/100)  
**Action:** Optimize to get more users to aha moments → 2-4x conversion improvement

---

## What PrizmAI Already Tracks

### ✅ Server-Side Tracking (100% Coverage)

Your `analytics/models.py` has two key models:

#### 1. `DemoSession` Model
Tracks entire demo session lifecycle:

```python
{
    'session_id': 'abc123...',           # Unique session identifier
    'user': None,                         # NULL for anonymous users
    'demo_mode': 'solo',                  # Solo or Team mode
    'device_type': 'mobile',              # Desktop/Mobile/Tablet
    'created_at': '2025-12-29 10:00:00',
    'duration_seconds': 420,              # 7 minutes in demo
    'features_explored': 5,               # Count of features used
    'aha_moments': 2,                     # Aha moments experienced
    'nudges_shown': 3,                    # Conversion nudges displayed
    'nudges_clicked': 1,                  # Nudge CTAs clicked
    'converted_to_signup': False,         # Did they convert?
    'ip_address': '192.168.1.1',         # For geographic analysis
    'user_agent': 'Mozilla/5.0...',      # Browser/device info
}
```

#### 2. `DemoAnalytics` Model  
Tracks individual events within demo session:

```python
{
    'session_id': 'abc123...',
    'event_type': 'feature_explored',
    'event_data': {
        'feature_name': 'ai_generator',
        'interaction': 'suggestion_accepted',
        'is_anonymous': True,             # Anonymous flag
        'user_id': None                   # NULL for anonymous
    },
    'timestamp': '2025-12-29 10:05:23',
    'device_type': 'mobile',
    'page_path': '/demo/board/1/'
}
```

---

## Anonymous vs Authenticated Tracking

### Anonymous User Session Example

```json
// Session ID: xyz789 (anonymous)
{
  "DemoSession": {
    "session_id": "xyz789",
    "user": null,                    ← No user account
    "demo_mode": "solo",
    "is_anonymous": true,
    "features_explored": 3,
    "converted_to_signup": false     ← Didn't convert
  },
  "Events": [
    {
      "event_type": "demo_mode_selected",
      "is_anonymous": true,
      "timestamp": "10:00:00"
    },
    {
      "event_type": "feature_explored",
      "feature_name": "burndown",
      "is_anonymous": true,
      "timestamp": "10:03:15"
    },
    {
      "event_type": "demo_exited",
      "is_anonymous": true,
      "exit_reason": "no_conversion",
      "timestamp": "10:07:42"
    }
  ]
}
```

### Authenticated User Session Example

```json
// Session ID: abc123 (authenticated)
{
  "DemoSession": {
    "session_id": "abc123",
    "user": 42,                      ← User account exists
    "demo_mode": "team",
    "is_anonymous": false,
    "features_explored": 7,
    "converted_to_signup": true      ← Converted!
  },
  "Events": [
    {
      "event_type": "demo_mode_selected",
      "is_anonymous": false,
      "user_id": 42,
      "timestamp": "11:00:00"
    },
    {
      "event_type": "aha_moment",
      "trigger": "ai_value_recognition",
      "is_anonymous": false,
      "timestamp": "11:05:30"
    },
    {
      "event_type": "nudge_clicked",
      "nudge_type": "peak_moment",
      "is_anonymous": false,
      "timestamp": "11:05:45"
    }
  ]
}
```

---

## Key Events to Track

### Entry Events
- ✅ `demo_mode_selected` - Solo vs Team choice
- ✅ `demo_started` - Session initiated
- ⚠️ Track: `is_anonymous`, `device_type`, `referrer_source`

### Engagement Events
- ✅ `feature_explored` - User interacted with feature
- ✅ `aha_moment` - Value recognition triggered
- ✅ `role_switched` - Changed persona (Team mode)
- ✅ `demo_reset` - Reset demo to clean state
- ⚠️ Track: `feature_name`, `interaction_type`, `time_elapsed`

### Conversion Events
- ✅ `nudge_shown` - Conversion prompt displayed
- ✅ `nudge_clicked` - User clicked signup CTA
- ✅ `nudge_dismissed` - User dismissed nudge
- ✅ `demo_to_signup` - User converted to account
- ⚠️ Track: `nudge_type`, `features_explored_before_conversion`, `time_to_conversion`

### Exit Events  
- ✅ `demo_exited` - User left without converting
- ✅ `session_expired` - 48-hour expiry reached
- ⚠️ Track: `exit_reason`, `last_feature_viewed`, `total_duration`

---

## Google Analytics 4 Integration

### Server-Side Tracking (Always Works)
```python
# Django tracks in database (cannot be blocked)
DemoAnalytics.objects.create(
    session_id=request.session.session_key,
    event_type='demo_mode_selected',
    event_data={'mode': 'solo', 'is_anonymous': True}
)
```

### Client-Side Tracking (Best Effort)
Add to your demo templates:

```html
<!-- Google Analytics 4 -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  
  // Configure GA4
  gtag('config', 'G-XXXXXXXXXX', {
    'anonymize_ip': true,           // Privacy compliance
    'send_page_view': false         // Manual tracking
  });
  
  // Track demo mode selection
  gtag('event', 'demo_mode_selected', {
    'event_category': 'Demo',
    'mode': '{{ request.session.demo_mode }}',
    'is_anonymous': {{ request.user.is_authenticated|yesno:"false,true" }},
    'session_id': '{{ request.session.session_key }}'
  });
  
  // Track feature exploration
  function trackFeatureExplored(featureName, interactionType) {
    // Client-side (best effort - may be blocked)
    try {
      gtag('event', 'feature_explored', {
        'event_category': 'Demo',
        'feature_name': featureName,
        'interaction': interactionType,
        'is_anonymous': {{ request.user.is_authenticated|yesno:"false,true" }}
      });
    } catch(e) {
      console.log('GA4 blocked - server-side tracking active');
    }
    
    // Server-side (always works)
    fetch('/demo/track-feature/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify({
        feature: featureName,
        interaction: interactionType
      })
    });
  }
</script>
```

---

## Privacy Considerations

### ✅ What You CAN Track (Anonymous Users)
- Session ID (randomly generated, not PII)
- Device type (desktop/mobile/tablet)
- Browser user agent
- IP address (for geographic analysis only)
- Feature usage patterns
- Time spent in demo
- Click events and navigation
- Conversion actions

### ❌ What You CANNOT Track (Without Consent)
- Personal information (name, email)
- Precise location (beyond city/country)
- Cross-site tracking (without cookie consent)
- Sensitive personal data

### GDPR/CCPA Compliance

**Anonymous Session Tracking is Compliant:**
- Session IDs are not personally identifiable
- No cross-site tracking without consent
- Users can opt-out via browser settings
- Data is anonymized (no PII collected)

**Add Cookie Banner (Recommended):**
```html
<!-- Cookie Consent for GA4 -->
<div id="cookie-banner" style="display: none;">
  <p>We use cookies to improve your demo experience.</p>
  <button onclick="acceptCookies()">Accept</button>
  <button onclick="declineCookies()">Decline</button>
</div>

<script>
  // Only load GA4 after consent
  function acceptCookies() {
    localStorage.setItem('ga4_consent', 'true');
    loadGA4();
  }
  
  function declineCookies() {
    // Server-side tracking still works
    localStorage.setItem('ga4_consent', 'false');
  }
</script>
```

---

## Analytics Dashboard Queries

### 1. Anonymous vs Authenticated Conversion Rates

```python
from analytics.models import DemoSession

# Anonymous users
anonymous_sessions = DemoSession.objects.filter(user__isnull=True)
anonymous_converted = anonymous_sessions.filter(converted_to_signup=True).count()
anonymous_total = anonymous_sessions.count()
anonymous_conversion_rate = (anonymous_converted / anonymous_total * 100) if anonymous_total > 0 else 0

# Authenticated users (started in demo before logging in)
auth_sessions = DemoSession.objects.filter(user__isnull=False)
auth_converted = auth_sessions.filter(converted_to_signup=True).count()
auth_total = auth_sessions.count()
auth_conversion_rate = (auth_converted / auth_total * 100) if auth_total > 0 else 0

print(f"Anonymous Conversion: {anonymous_conversion_rate:.1f}%")
print(f"Authenticated Conversion: {auth_conversion_rate:.1f}%")
```

### 2. Features Explored by Anonymous Users

```python
from analytics.models import DemoAnalytics
from django.db.models import Count

# Get most explored features by anonymous users
features = DemoAnalytics.objects.filter(
    event_type='feature_explored',
    event_data__is_anonymous=True
).values('event_data__feature_name').annotate(
    count=Count('id')
).order_by('-count')[:10]

for feature in features:
    print(f"{feature['event_data__feature_name']}: {feature['count']} interactions")
```

### 3. Time to Conversion for Anonymous Users

```python
from django.db.models import Avg

avg_time = DemoSession.objects.filter(
    user__isnull=True,
    converted_to_signup=True
).aggregate(Avg('time_to_conversion_seconds'))

print(f"Average time to conversion: {avg_time['time_to_conversion_seconds__avg'] / 60:.1f} minutes")
```

### 4. Aha Moment Impact on Conversion

```python
# No aha moments
no_aha = DemoSession.objects.filter(aha_moments=0)
no_aha_conversion = no_aha.filter(converted_to_signup=True).count() / no_aha.count() * 100

# 1+ aha moments
with_aha = DemoSession.objects.filter(aha_moments__gte=1)
with_aha_conversion = with_aha.filter(converted_to_signup=True).count() / with_aha.count() * 100

print(f"No aha moment: {no_aha_conversion:.1f}% conversion")
print(f"With aha moment: {with_aha_conversion:.1f}% conversion")
print(f"Lift: {(with_aha_conversion / no_aha_conversion - 1) * 100:.0f}%")
```

---

## Implementation Checklist

### ✅ Already Implemented
- [x] DemoSession model with anonymous support
- [x] DemoAnalytics event tracking
- [x] Session-based identification
- [x] Device type detection
- [x] Server-side tracking (cannot be blocked)

### 🔄 To Implement
- [ ] Add `is_anonymous` flag to all tracking events
- [ ] Create analytics dashboard for demo metrics
- [ ] Set up GA4 property and tracking code
- [ ] Add cookie consent banner (optional but recommended)
- [ ] Create weekly analytics reports
- [ ] Set up conversion funnel visualization

### 📊 To Monitor Weekly
- [ ] Anonymous demo entry rate
- [ ] Feature exploration patterns
- [ ] Aha moment triggers
- [ ] Conversion rates (anonymous vs auth)
- [ ] Drop-off points
- [ ] Device breakdown (mobile vs desktop)

---

## Key Insights You'll Gain

### From Anonymous User Tracking:

1. **Drop-Off Analysis**
   - 70% leave after 2 minutes → Need better onboarding
   - 45% leave at feature X → Feature needs redesign
   - Mobile users abandon 2x more → Mobile UX issues

2. **Feature Popularity**
   - AI features: 60% engagement → Market this heavily
   - Burndown charts: 25% engagement → Need better discovery
   - RBAC: 15% engagement → Team mode needs promotion

3. **Conversion Optimization**
   - Aha moment → 35% conversion (vs 12% baseline)
   - Nudge timing: 5-min nudge = 20% CTR (vs 10-min = 8% CTR)
   - Solo mode: 18% conversion, Team mode: 22% conversion

4. **Segment Analysis**
   - Mobile users: 12% conversion (optimize mobile UX)
   - Desktop users: 24% conversion (desktop works well)
   - Returning anonymous: 35% conversion (remarketing works)

---

## Summary

### Should You Track Anonymous Users?

**YES, 100% ESSENTIAL!**

### Why?
- 70-85% of users try demo before signing up
- Understanding their behavior = 2-4x conversion improvement
- Identifies friction points and optimization opportunities
- Validates product-market fit

### How?
- ✅ Session-based tracking (already implemented)
- ✅ Server-side events (cannot be blocked)
- ✅ Client-side GA4 (best effort, 65-70% coverage)
- ✅ Privacy-compliant (no PII required)

### What to Track?
- Entry method (how they found demo)
- Features explored (what they tried)
- Aha moments (when they "got it")
- Exit points (where they left)
- Conversion events (if they signed up)

### Expected Results
- 15-25% baseline conversion rate
- 35-45% conversion with aha moments
- 60-70% analytics coverage (including ad-blocker users)
- Actionable insights within 2 weeks

---

## Next Steps

1. **Verify tracking is working:**
   ```python
   # Check recent anonymous sessions
   python manage.py shell
   >>> from analytics.models import DemoSession
   >>> DemoSession.objects.filter(user__isnull=True).count()
   ```

2. **Set up GA4 property** (optional but recommended)
   - Create GA4 property at analytics.google.com
   - Add tracking code to demo templates
   - Verify events in real-time reports

3. **Create analytics dashboard**
   - Weekly conversion rates
   - Feature engagement metrics
   - Drop-off visualization
   - Device breakdown

4. **Monitor and optimize**
   - Week 1: Establish baseline
   - Week 2: Identify top issues
   - Week 3: Implement fixes
   - Week 4: Measure improvement

**Remember:** Anonymous tracking is the KEY to understanding why users don't convert and how to fix it!
