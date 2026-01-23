# Demo Mode Security & Abuse Prevention

## Overview

PrizmAI implements a multi-layered security system to prevent abuse of the demo mode while maintaining a smooth user experience for legitimate users. This document details the security architecture, implementation decisions, and trade-offs.

---

## The Challenge

Demo mode allows users to try AI-powered features without creating an account. However, AI features incur API costs (Google Cloud). Without proper guardrails, malicious users could:

1. **Create infinite demo sessions** by clearing cookies or using incognito mode
2. **Exhaust AI quotas** by repeatedly using AI features across sessions
3. **Use VPNs** to appear as different users
4. **Rapid-fire abuse** - consuming resources faster than intended

---

## Security Architecture

### Multi-Layer Protection Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    LAYER 1: Rate Limiting                        │
│         Max 5 AI calls per 10 minutes (sliding window)          │
│         VPN users: Max 3 AI calls per 10 minutes                │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                  LAYER 2: Global Limits                          │
│        Max 30 AI generations per IP+fingerprint                 │
│        VPN users: Max 15 AI generations                          │
│        Max 5 projects across all sessions                        │
│        Max 20 total demo sessions                                │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                 LAYER 3: Per-Session Limits                      │
│              Max 20 AI generations per session                   │
│              Max 2 projects per session                          │
│              48-hour session duration                            │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LAYER 4: Admin Controls                        │
│              Manual IP blocking/flagging                         │
│              Abuse dashboard for monitoring                      │
│              Automatic flagging after 10+ sessions               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Details

### 1. User Identification & Tracking

**Files:** 
- `kanban/utils/demo_abuse_prevention.py`
- `analytics/models.py` (DemoAbusePrevention, DemoSession)

**Dual Fingerprinting Strategy:**

| Method | Generation | Robustness | Persistence |
|--------|-----------|------------|-------------|
| Server-side fingerprint | User-Agent + Accept-Language + Accept-Encoding | Basic - can be spoofed | Stored in session & database |
| Client-side fingerprint | Canvas + WebGL + Audio + Fonts + Hardware | Strong - hard to spoof | Stored via `/demo/fingerprint/` endpoint |

**Server-side fingerprint generation:**
```python
def generate_browser_fingerprint(request):
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
    fingerprint_data = f"{user_agent}|{accept_language}|{accept_encoding}"
    return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:64]
```

**Client-side fingerprint (fingerprint.js):**
- Canvas fingerprinting (GPU rendering patterns)
- WebGL fingerprinting (graphics driver info)
- Audio context fingerprinting (audio processing patterns)
- Font detection (installed font enumeration)
- Hardware info (screen size, color depth, cores, memory)

**Cross-session tracking:**
When a user clears cookies and returns, the system can still identify them via:
1. Client-side fingerprint stored in the database
2. IP address correlation
3. Combined IP + server fingerprint matching

---

### 2. Rate Limiting

**File:** `kanban/utils/demo_abuse_prevention.py`

**Sliding Window Algorithm:**
```python
def check_ai_rate_limit(request):
    MAX_CALLS_PER_WINDOW = 5  # or 3 for VPN users
    WINDOW_MINUTES = 10
    
    # Get recent timestamps from database
    recent_timestamps = [ts for ts in timestamps 
                         if within_window(ts, WINDOW_MINUTES)]
    
    if len(recent_timestamps) >= MAX_CALLS_PER_WINDOW:
        # Calculate wait time
        wait_seconds = calculate_wait_time(oldest_timestamp)
        return {'allowed': False, 'wait_seconds': wait_seconds}
    
    return {'allowed': True}
```

**Why sliding window?**
- More fair than fixed windows (no "reset at midnight" abuse)
- Provides smooth user experience
- Prevents burst attacks

---

### 3. VPN/Proxy Detection

**File:** `kanban/utils/vpn_detection.py`

**Detection Method:** IP range matching against known datacenter networks

**Covered providers:**
- AWS, Google Cloud, Azure
- DigitalOcean, Linode, Vultr
- Hetzner, OVH
- Common VPN providers (NordVPN, ExpressVPN, etc.)

**Policy for VPN Users:**
- **NOT blocked** - legitimate users may use VPNs
- **Reduced limits by 50%:**
  - 15 AI generations instead of 30
  - 3 AI calls per 10 minutes instead of 5
  - 10 total sessions instead of 20

**Rationale:** Balance between security and user experience. Blocking VPN users entirely would hurt legitimate privacy-conscious users.

---

### 4. Limit Configuration

**File:** `kanban/utils/demo_abuse_prevention.py`

#### Production Limits
```python
GLOBAL_DEMO_LIMITS = {
    'max_ai_generations_global': 30,      # Cost control
    'max_projects_global': 5,
    'max_sessions_per_hour': 3,
    'max_sessions_per_24h': 5,
    'max_sessions_total': 20,
    'cooldown_after_abuse_hours': 24,
}
```

#### Development Limits
```python
GLOBAL_DEMO_LIMITS = {
    'max_ai_generations_global': 500,     # High for testing
    'max_projects_global': 50,
    'max_sessions_per_hour': 100,
    'max_sessions_per_24h': 500,
    'max_sessions_total': 1000,
}
```

#### Per-Session Limits
```python
DEMO_LIMITS = {
    'max_projects': 2,
    'max_ai_generations': 20,
    'export_enabled': False,
    'data_reset_hours': 48,
}
```

---

### 5. Production Safeguard

**Problem:** Accidentally deploying with `DEBUG=True` would use development limits (500 AI instead of 30).

**Solution:** Runtime detection and logging

```python
if settings.DEBUG:
    # Development limits applied
    if os.environ.get('PRODUCTION_SERVER') == 'true' or \
       os.environ.get('RAILWAY_ENVIRONMENT'):
        logger.critical(
            "⚠️ SECURITY WARNING: DEBUG=True in production! "
            "Demo limits are set to development values."
        )
```

---

### 6. Admin Abuse Dashboard

**File:** `analytics/abuse_views.py`

**Features:**
- Real-time overview of flagged/blocked visitors
- High-risk visitor identification
- Session analytics by hour
- Limitation hit statistics
- Manual IP blocking/unblocking

**Auto-flagging triggers:**
- Creating more than 10 demo sessions
- Unusual request patterns (future enhancement)

---

## Database Schema

### DemoAbusePrevention Model

```python
class DemoAbusePrevention(models.Model):
    # Identification
    ip_address = GenericIPAddressField(db_index=True)
    browser_fingerprint = CharField(max_length=64, db_index=True)
    client_fingerprint = CharField(max_length=64, db_index=True)  # JS-generated
    
    # Aggregated limits
    total_ai_generations = IntegerField(default=0)
    total_projects_created = IntegerField(default=0)
    total_sessions_created = IntegerField(default=1)
    
    # VPN tracking
    is_vpn_user = BooleanField(default=False)
    
    # Rate limiting
    ai_generation_timestamps = JSONField(default=list)
    sessions_last_hour = IntegerField(default=0)
    sessions_last_24h = IntegerField(default=0)
    
    # Abuse flags
    is_flagged = BooleanField(default=False)
    is_blocked = BooleanField(default=False)
    flag_reason = TextField(blank=True)
    
    class Meta:
        unique_together = [['ip_address', 'browser_fingerprint']]
```

### DemoSession Model

```python
class DemoSession(models.Model):
    session_id = CharField(unique=True, db_index=True)
    browser_fingerprint = CharField(max_length=64, db_index=True)
    client_fingerprint = CharField(max_length=64, db_index=True)
    is_vpn_detected = BooleanField(default=False)
    
    # Limits tracking
    projects_created_in_demo = IntegerField(default=0)
    ai_generations_used = IntegerField(default=0)
    export_attempts = IntegerField(default=0)
    limitations_hit = JSONField(default=list)
    
    # Timing
    first_demo_start = DateTimeField()
    expires_at = DateTimeField()
    extensions_count = IntegerField(default=0)
```

---

## Cost Analysis

### Scenario: Worst-case abuse without guardrails

Assuming $0.01 per AI generation (Google Cloud API cost):

| Scenario | AI Calls | Cost |
|----------|----------|------|
| Single abuser, unlimited | 1000+ | $10+ |
| 100 coordinated abusers | 100,000 | $1,000 |

### With guardrails in place

| User Type | Max AI Calls | Cost Cap |
|-----------|-------------|----------|
| Regular demo user | 30 | $0.30 |
| VPN user | 15 | $0.15 |
| Per session | 20 | $0.20 |

**Effective cost cap per unique visitor:** $0.30 max

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/demo/start/` | POST | Create demo session (abuse check performed) |
| `/demo/fingerprint/` | POST | Receive client-side JS fingerprint |
| `/demo/status/` | GET | Get current demo limits status |
| `/demo/extend/` | POST | Extend session (limited extensions) |

---

## Security Trade-offs

### Design Decisions

| Decision | Pro | Con |
|----------|-----|-----|
| Allow VPN users with reduced limits | Doesn't alienate privacy-conscious users | Slightly higher abuse potential |
| 30 global AI limit | Strong cost control | May feel restrictive for power users |
| Client-side fingerprinting | More robust tracking | Requires JavaScript enabled |
| Sliding window rate limiting | Smooth UX | More complex implementation |
| No email verification for demo | Frictionless experience | Can't verify user identity |

### Remaining Risks

1. **Sophisticated attackers** with unique IPs and spoofed fingerprints can still abuse (mitigated by low per-session limits)
2. **Bot networks** could coordinate attacks (mitigated by rate limiting)
3. **JavaScript disabled** users only get server-side fingerprinting (acceptable fallback)

---

## Monitoring & Alerts

### Key Metrics to Monitor

1. **Daily AI generations** - Alert if unusually high
2. **New demo sessions per hour** - Detect coordinated attacks
3. **Flagged visitors count** - Review suspicious activity
4. **VPN user ratio** - Understand user base

### Recommended Alerts

```python
# Example alert conditions
if daily_ai_generations > 1000:
    alert("High AI usage detected")
    
if new_sessions_last_hour > 50:
    alert("Possible coordinated attack")
    
if flagged_visitors_today > 10:
    alert("Multiple suspicious visitors")
```

---

## Future Enhancements

1. **Behavioral analysis** - Detect patterns like identical request timing
2. **IP reputation scoring** - Use external APIs for risk assessment
3. **CAPTCHA integration** - For suspicious users only
4. **Daily global budget cap** - Hard limit across all demo users
5. **Email domain validation** - Block disposable email addresses

---

## Quick Reference

### Limits Summary Table

| Limit Type | Regular User | VPN User |
|------------|-------------|----------|
| AI per session | 20 | 20 |
| AI global (all sessions) | 30 | 15 |
| AI per 10 minutes | 5 | 3 |
| Projects per session | 2 | 2 |
| Projects global | 5 | 5 |
| Session duration | 48 hours | 48 hours |
| Max sessions total | 20 | 10 |
| Sessions per hour | 3 | 3 |
| Sessions per 24h | 5 | 5 |

### Key Files

| Purpose | File |
|---------|------|
| Global limits & abuse prevention | `kanban/utils/demo_abuse_prevention.py` |
| Per-session limits | `kanban/utils/demo_limits.py` |
| VPN detection | `kanban/utils/vpn_detection.py` |
| Demo views & fingerprint endpoint | `kanban/demo_views.py` |
| Models | `analytics/models.py` |
| Client fingerprinting | `static/js/fingerprint.js` |
| Abuse admin dashboard | `analytics/abuse_views.py` |

---

## Interview Talking Points

1. **Multi-layered defense** - No single point of failure
2. **Cost consciousness** - Every limit was set with API costs in mind
3. **User experience balance** - VPN users get access, just with reduced limits
4. **Production safeguards** - Runtime detection of misconfigurations
5. **Scalable architecture** - Database-backed tracking, not just session-based
6. **Extensible design** - Easy to add new detection methods or adjust limits

---

*Last updated: January 2026*
