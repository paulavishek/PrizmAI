

**Q: How is the demo currently implemented? Is there a separate demo user/organization created per session?**

**A:** Yes, the current implementation uses **demo organizations**:
- There are **3 official demo boards** in dedicated demo organizations
- Demo data is populated via `python manage.py populate_test_data` command
- The system creates **1000+ sample tasks** across Software Project, Bug Tracking, and Marketing Campaign boards
- Demo sessions are **session-based** with 48-hour expiry
- Each demo user gets access to pre-populated boards (not separate orgs per session in current state)

**Current Entry Point:**
- URL: Likely `/demo/` or similar Django route
- Users click "Demo" link → see dashboard with 3 pre-populated boards
- Currently **no demo mode selection screen** (this is what we're adding)

---

### **1. Existing Demo Data:**

**Q: Do you already have the 3 pre-populated demo boards mentioned?**

**A:** **YES**, confirmed in README:
- ✅ **Software Project** board
- ✅ **Bug Tracking** board  
- ✅ **Marketing Campaign** board
- ✅ 1000+ tasks with dynamic dates (relative to current date)
- ✅ Complete features: risk management, resource forecasting, budget tracking, milestones, dependencies

BUT THE DEMO MODE HAS BEEN CLEANED UP, SO CURRENTLY THERE IS NO DEMO DATA. iT'S A CLEAN SLATE NOW.

**Q: Are there existing demo users/personas?**

**A:** **PARTIALLY** - The improvement guide mentions creating personas:
- 🎯 **Alex Chen** - Project Manager (Admin)
- 👤 **Sam Rivera** - Team Member
- 👁️ **Jordan Taylor** - Stakeholder (Viewer)

**These personas need to be CREATED as part of implementation** (not currently in system based on documents).

---

### **2. Analytics Setup:**

**Q: Do you currently have Google Analytics (GA4) integrated?**

**A:** Yes. But please check the files to be sure

**Q: Is there an existing analytics model/table in Django?**

**A:** We have both Django and Google Analytics.

**Required Django Models (from implementation guide):**
```python
# These need to be CREATED:
class DemoAnalytics(models.Model):
    session_id = models.CharField(max_length=255)
    event_type = models.CharField(max_length=100)
    event_data = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)
    device_type = models.CharField(max_length=50)
    
class DemoSession(models.Model):
    session_id = models.CharField(max_length=255, unique=True)
    demo_mode = models.CharField(max_length=20)  # 'solo' or 'team'
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    features_explored = models.IntegerField(default=0)
    converted_to_signup = models.BooleanField(default=False)

class DemoConversion(models.Model):
    session_id = models.CharField(max_length=255)
    time_in_demo = models.IntegerField()  # seconds
    features_explored = models.IntegerField()
    aha_moments = models.IntegerField()
    conversion_source = models.CharField(max_length=50)
    timestamp = models.DateTimeField(auto_now_add=True)
```

---

### **3. Frontend Framework:**

**Q: What frontend framework are you using (vanilla JS, React, Vue, etc.)?**

**A:** Based on README Technology Stack section:

**Frontend:**
- ✅ **HTML5, CSS3, JavaScript** (vanilla)
- ✅ **Bootstrap 5** for styling
- ✅ **Progressive Web App (PWA)** support
- ✅ **WebSocket** support via Django Channels
- ❌ **NO React/Vue/Angular** mentioned

**Q: Are you using Django templates or a separate frontend?**

**A:** **Django Templates** (confirmed by "Django 5.2.3" in tech stack + no mention of SPA architecture)

**This means:**
- All UI changes implemented in **Django template files** (.html)
- JavaScript added via `<script>` tags or separate .js files
- Bootstrap components for modals, toasts, etc.
- AJAX/Fetch API for server communication

---

### **4. Mobile Considerations:**

**Q: Is the site currently mobile-responsive?**

**A:** **YES** - Multiple indicators:

From README:
- ✅ **Mobile PWA Support** section confirms mobile-first design
- ✅ **Progressive Web App** with offline capabilities
- ✅ Installable on home screen (iOS/Android)
- ✅ Dedicated mobile PWA repository: `github.com/paulavishek/PrizmAI_mobile_PWA`

**Current Mobile Features:**
- Responsive design (likely Bootstrap-based)
- Touch-friendly navigation
- PWA installability
- Bearer token authentication for mobile API

**Q: Any existing mobile-specific views?**

**A:** **YES** - Separate mobile PWA exists:
- Desktop: Main PrizmAI Django app
- Mobile: Dedicated PWA repository (separate frontend)
- Both use same Django backend via REST API

**Implication for Implementation:**
You'll need to update **BOTH**:
1. **Django templates** (desktop experience)
2. **Mobile PWA** (separate repo - mobile experience)

---

### **5. Priority Clarification:**

**Q: Would you like me to follow the phased approach (Week 1 → Week 2 → Week 3)?**

**My Recommendation:** **YES, follow phased approach** for these reasons:

**Why Phased is Better:**
1. ✅ **Incremental testing** - Catch bugs early before compounding
2. ✅ **Measurable progress** - See conversion improvements week-by-week
3. ✅ **Lower risk** - Can roll back if something breaks
4. ✅ **Team bandwidth** - Easier for friends to implement in chunks
5. ✅ **Data-driven** - Week 1 data informs Week 2 optimizations

**Suggested Phase Priority:**

**PHASE 1 (Week 1) - MUST HAVES:**
1. Demo mode selection screen (2 options + skip)
2. Persistent demo banner (desktop + mobile)
3. Basic reset functionality
4. Server-side analytics models (DemoAnalytics, DemoSession)
5. Aha moment detection (AI suggestion accepted)
6. Soft nudge (3 min OR 3 features)

**PHASE 2 (Week 2) - HIGH IMPACT:**
1. Role-switching for Team Demo
2. Medium + exit intent nudges
3. Session expiry warnings
4. Error handling (reset, role switch)
5. GA4 integration (hybrid tracking)

**PHASE 3 (Week 3+) - OPTIMIZATION:**
1. A/B testing framework
2. Analytics dashboards
3. Automated cleanup (Celery)
4. Continuous refinement based on data

---

## 🛠️ **Implementation Pre-Work Needed:**

Before start coding, these need to be set up:

### **Database Models (Django):**
```bash
# Create new Django app for demo analytics
python manage.py startapp demo_analytics

# Add models to demo_analytics/models.py:
# - DemoAnalytics
# - DemoSession  
# - DemoConversion

# Run migrations
python manage.py makemigrations
python manage.py migrate
```

### **Demo Personas (Database Seeding):**
```python
# Create management command: create_demo_personas.py
# Adds Alex Chen, Sam Rivera, Jordan Taylor to demo org
```

### **Google Analytics Setup:**
```html
<!-- Add to base.html template -->
<script async src="https://www.googletagmanager.com/gtag/js?id=GA_MEASUREMENT_ID"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'GA_MEASUREMENT_ID');
</script>
```

### **Mobile PWA Updates:**
Your friends will need access to:
- Main Django repo (backend + desktop frontend)
- Mobile PWA repo (mobile frontend)
- Coordination between both repos for consistent UX






## 📋 **Detailed Answers to Architecture Questions**

### **1. Demo Organization Names**

**Recommendation: Use "Demo -" prefix** ✅

**Names:**
- ✅ `"Demo - Software Development"` (instead of just "Dev Team")
- ✅ `"Demo - Marketing Campaign"`  
- ✅ `"Demo - Bug Tracking"`

**Why this approach:**

**Pros:**
- **Clear distinction** - Users immediately know it's demo data
- **Prevents confusion** - Won't accidentally think it's their real data
- **Easier cleanup** - Can filter by prefix: `Organization.objects.filter(name__startswith="Demo -")`
- **Audit trail** - Clear in database which orgs are demo vs. production

**Implementation:**
```python
# demo_analytics/management/commands/create_demo_organizations.py

DEMO_ORGANIZATIONS = [
    {
        'name': 'Demo - Software Development',
        'description': 'Sample software project with AI features',
        'is_demo': True
    },
    {
        'name': 'Demo - Marketing Campaign', 
        'description': 'Marketing workflow demonstration',
        'is_demo': True
    },
    {
        'name': 'Demo - Bug Tracking',
        'description': 'Bug triage and resolution workflow',
        'is_demo': True
    }
]
```

**Add database flag:**
```python
# models.py
class Organization(models.Model):
    name = models.CharField(max_length=255)
    is_demo = models.BooleanField(default=False)  # ADD THIS
    # ... other fields
```

This makes queries clean:
```python
# Get all demo orgs
demo_orgs = Organization.objects.filter(is_demo=True)

# Get all real orgs  
real_orgs = Organization.objects.filter(is_demo=False)

# Cleanup demo data
Organization.objects.filter(is_demo=True).delete()
```

---

### **2. Persona Email Domains**

**Recommendation: Use `@demo.prizmai.local`** ✅

**Email addresses:**
- ✅ `alex.chen@demo.prizmai.local` (Admin)
- ✅ `sam.rivera@demo.prizmai.local` (Member)
- ✅ `jordan.taylor@demo.prizmai.local` (Viewer)

**Why `.local` suffix:**

**Pros:**
- **Non-routable** - `.local` is reserved (RFC 6762), won't conflict with real domains
- **Professional appearance** - Looks branded vs. generic `@example.com`
- **No deliverability issues** - Email won't accidentally get sent to real addresses
- **Clear demo indicator** - `demo.prizmai` prefix makes it obvious

**Alternatives (ranked):**

| Option | Pros | Cons | Verdict |
|--------|------|------|---------|
| `@demo.prizmai.local` | Non-routable, branded, clear | Requires users understand `.local` | ✅ **Best** |
| `@demo.prizmai.com` | Looks real, branded | If you own `prizmai.com`, might receive emails | ⚠️ Only if you control domain |
| `@example.com` | Standard placeholder | Generic, unprofessional | ❌ Avoid |
| `@demo.example.com` | Non-routable, clear | Generic, not branded | 🆗 Acceptable fallback |

**Implementation:**
```python
# create_demo_personas.py

DEMO_PERSONAS = [
    {
        'email': 'alex.chen@demo.prizmai.local',
        'first_name': 'Alex',
        'last_name': 'Chen',
        'role': 'admin',
        'title': 'Project Manager'
    },
    {
        'email': 'sam.rivera@demo.prizmai.local',
        'first_name': 'Sam', 
        'last_name': 'Rivera',
        'role': 'member',
        'title': 'Team Member'
    },
    {
        'email': 'jordan.taylor@demo.prizmai.local',
        'first_name': 'Jordan',
        'last_name': 'Taylor', 
        'role': 'viewer',
        'title': 'Stakeholder'
    }
]
```

**Email validation bypass:**
```python
# Ensure demo emails don't trigger validation errors
def create_demo_user(email, **kwargs):
    user = User.objects.create(
        email=email,
        is_active=True,
        email_verified=True,  # Skip verification for demo
        **kwargs
    )
    return user
```

---

### **3. Demo Data Scope: How Many Tasks?**

**Recommendation: Start with 100-150 tasks total (MVP), scale to 1000+ later** ✅

**Phased Approach:**

**Phase 1 (MVP - Week 1):**
- ✅ **Software Development board:** 50 tasks
- ✅ **Marketing Campaign board:** 40 tasks  
- ✅ **Bug Tracking board:** 30 tasks
- **Total:** ~120 tasks

**Why 100-150 for MVP:**

**Pros:**
- **Faster seeding** - Won't slow down development/testing
- **Easier to verify** - Can manually check data quality
- **Sufficient for demo** - Enough to show features without overwhelming
- **Performance testing** - Identify issues before scaling to 1000+

**Phase 2 (Post-Launch - Week 3+):**
- Scale to **1000+ tasks** once system is stable
- Use for **performance testing** and **forecasting accuracy**

**Task Distribution (MVP - 120 tasks):**

**Software Development Board (50 tasks):**
- 15 "To Do" 
- 20 "In Progress"
- 10 "In Review"
- 5 "Done"

**Marketing Campaign Board (40 tasks):**
- 12 "Backlog"
- 15 "In Progress"  
- 8 "Review"
- 5 "Published"

**Bug Tracking Board (30 tasks):**
- 10 "New"
- 12 "In Progress"
- 5 "Testing"
- 3 "Closed"

**Implementation:**
```python
# populate_demo_data.py

def create_demo_tasks_mvp():
    """Create 120 high-quality demo tasks for MVP"""
    
    # Software Dev board - 50 tasks
    create_software_tasks(count=50)
    
    # Marketing board - 40 tasks  
    create_marketing_tasks(count=40)
    
    # Bug tracking board - 30 tasks
    create_bug_tasks(count=30)

def scale_to_1000_tasks():
    """Scale to 1000+ tasks for performance testing (Phase 2)"""
    # Run after MVP is stable
    pass
```

**Scaling trigger:** Once you hit **15%+ conversion rate** and system is stable, scale to 1000+ for realistic performance.

---

### **4. Reset Access Control**

**Recommendation: Session-based (anyone can reset their own demo session)** ✅

**Why this approach:**

**User Experience:**
- ✅ **Psychological safety** - Users can fearlessly experiment
- ✅ **No barriers** - Don't need admin privileges to reset
- ✅ **Self-service** - Matches user expectations from other SaaS demos

**Security:**
- ✅ **Isolated by session** - User can only reset THEIR demo data
- ✅ **Can't affect others** - No cross-session interference
- ✅ **Can't reset official boards** - Only user-created content deleted

**Implementation:**
```python
# views.py

@require_POST
def reset_demo_session(request):
    """Reset demo - available to all demo users (session-based)"""
    
    # Verify user is in demo mode
    if not request.session.get('is_demo_mode'):
        return JsonResponse({
            'status': 'error',
            'message': 'Not in demo mode'
        }, status=403)
    
    try:
        session_id = request.session.session_key
        
        # Delete ONLY this session's user-created content
        deleted = cleanup_user_created_demo_data(session_id)
        
        # Restore official demo boards (if modified)
        restore_official_demo_boards()
        
        # Track reset
        track_demo_event('demo_reset_success', {
            'session_id': session_id,
            'items_deleted': deleted
        })
        
        return JsonResponse({
            'status': 'success',
            'message': '✅ Demo reset successfully!'
        })
        
    except Exception as e:
        logger.error(f'Demo reset error: {str(e)}')
        return JsonResponse({
            'status': 'error',
            'message': 'Reset failed. Please try again.'
        }, status=500)

def cleanup_user_created_demo_data(session_id):
    """Delete only this session's created content"""
    
    # Get tasks created by this demo session
    tasks_deleted = Task.objects.filter(
        created_by_session=session_id,
        board__organization__is_demo=True
    ).delete()
    
    # Get boards created by this demo session  
    boards_deleted = Board.objects.filter(
        created_by_session=session_id,
        organization__is_demo=True,
        is_official_demo_board=False  # Don't delete official boards
    ).delete()
    
    return {
        'tasks': tasks_deleted[0],
        'boards': boards_deleted[0]
    }
```

**Access Control Matrix:**

| Action | Solo Demo User | Team Demo User | Superuser | Real User |
|--------|----------------|----------------|-----------|-----------|
| **Reset own session** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ N/A |
| **Reset other sessions** | ❌ No | ❌ No | ✅ Yes | ❌ N/A |
| **Delete official boards** | ❌ No | ❌ No | ❌ No | ❌ No |
| **Modify demo settings** | ❌ No | ❌ No | ✅ Yes | ❌ N/A |

**Database Schema Addition:**
```python
# models.py

class Task(models.Model):
    # ... existing fields
    created_by_session = models.CharField(
        max_length=255, 
        blank=True, 
        null=True,
        help_text="Session ID if created in demo mode"
    )
    
class Board(models.Model):
    # ... existing fields
    created_by_session = models.CharField(
        max_length=255, 
        blank=True, 
        null=True
    )
    is_official_demo_board = models.BooleanField(
        default=False,
        help_text="Official demo boards cannot be deleted"
    )
```

---

### **5. Mobile PWA Strategy**

**Recommendation: Desktop-first implementation, mobile documentation** ✅

**Approach:**

**Phase 1 (Now):**
- ✅ Implement **ALL features in Django/desktop** first
- ✅ Create comprehensive **mobile implementation guide** document
- ❌ **Don't** implement mobile PWA yet

**Phase 2 (After desktop is stable):**
- ✅ Port changes to mobile PWA repo
- ✅ Test mobile-specific UX adaptations
- ✅ Ensure feature parity

**Why desktop-first:**

**Pros:**
- **Faster iteration** - One codebase to debug
- **Easier coordination** - Friends working on same repo
- **Clear dependencies** - Mobile waits for stable desktop
- **Better testing** - Can validate desktop before mobile port

**Create Mobile Implementation Guide:**

```markdown
# MOBILE_PWA_IMPLEMENTATION.md

## Changes Needed in Mobile PWA Repo

### 1. Demo Mode Selection
**File:** `src/views/DemoSelection.vue` (or equivalent)
**Changes:**
- Add 2-option selection modal
- Implement skip link  
- Track selection in localStorage

### 2. Demo Banner
**File:** `src/components/DemoBanner.vue`
**Changes:**
- Collapsed by default on mobile
- Bottom sheet for actions menu
- Swipe-to-dismiss gesture

### 3. Role Switching  
**File:** `src/components/RoleSwitcher.vue`
**Changes:**
- Bottom sheet modal (not dropdown)
- 60px minimum touch targets
- Visual role badges

### 4. Aha Moments
**File:** `src/components/AhaCelebration.vue`  
**Changes:**
- Snackbar (not toast)
- Bottom-anchored
- 5s auto-dismiss (vs. 10s desktop)

### 5. Nudges
**File:** `src/components/ConversionNudge.vue`
**Changes:**
- No exit intent (desktop only)
- Show medium nudge at 7-8 min instead
- Full-screen interstitials for expiry warnings

### 6. API Endpoints (No Changes Needed)
- All API endpoints work as-is
- Mobile calls same Django backend
- Session-based auth already supported
```

**Coordination Strategy:**

**Week 1-2:**
- Friends implement desktop features
- You create mobile implementation guide
- Test desktop thoroughly

**Week 3:**
- Port to mobile PWA (if time permits)
- Otherwise, document for future sprint

**Week 4+:**
- Iterate on mobile based on desktop learnings

---

### **6. Existing Demo Views Strategy**

**Recommendation: Modify existing views, add new routes** ✅

**Approach:**

**Keep & Modify:**
- ✅ `demo_dashboard` → Add demo banner, track analytics
- ✅ `demo_board_detail` → Add role-based restrictions

**Add New:**
- ✅ `demo_mode_selection` → NEW view for Solo/Team choice
- ✅ `demo_reset` → NEW API endpoint
- ✅ `demo_switch_role` → NEW API endpoint (Team mode)

**Why hybrid approach:**

**Pros:**
- **Preserve working code** - Don't break existing demo
- **Incremental changes** - Safer refactoring
- **Backward compatible** - Old URLs still work
- **Clear separation** - New features in new files

**URL Structure:**

**Existing (Keep):**
```python
# urls.py (existing)
path('demo/', demo_dashboard, name='demo_dashboard'),
path('demo/board/<int:board_id>/', demo_board_detail, name='demo_board_detail'),
```

**New (Add):**
```python
# urls.py (additions)

# Demo entry & mode selection
path('demo/start/', demo_mode_selection, name='demo_start'),  # NEW

# Demo actions (API endpoints)
path('demo/reset/', reset_demo_session, name='demo_reset'),  # NEW
path('demo/switch-role/', switch_demo_role, name='demo_switch_role'),  # NEW

# Demo tracking (server-side)
path('demo/track-feature/', track_feature_explored, name='demo_track_feature'),  # NEW
path('demo/track-aha/', track_aha_moment, name='demo_track_aha'),  # NEW
```

**View Modifications:**

**Existing View (Modify):**
```python
# views.py

def demo_dashboard(request):
    """Modified to include demo banner & analytics"""
    
    # EXISTING CODE (keep)
    demo_boards = Board.objects.filter(organization__is_demo=True)
    
    # NEW CODE (add)
    # Check if demo mode selected
    if not request.session.get('demo_mode_selected'):
        return redirect('demo_start')  # Force selection first
    
    demo_mode = request.session.get('demo_mode', 'solo')
    current_role = request.session.get('demo_role', 'admin')
    
    # Track pageview (server-side)
    track_demo_event('demo_dashboard_viewed', {
        'session_id': request.session.session_key,
        'mode': demo_mode,
        'role': current_role
    })
    
    context = {
        'boards': demo_boards,
        'demo_mode': demo_mode,  # NEW
        'current_role': current_role,  # NEW
        'demo_expires_at': request.session.get('demo_expires_at'),  # NEW
    }
    
    return render(request, 'demo/dashboard.html', context)
```

**New View (Create):**
```python
# views.py

def demo_mode_selection(request):
    """NEW: Demo mode selection screen"""
    
    if request.method == 'POST':
        mode = request.POST.get('mode')  # 'solo' or 'team'
        selection_method = request.POST.get('method', 'selected')  # 'selected' or 'skipped'
        
        # Store in session
        request.session['demo_mode'] = mode
        request.session['demo_mode_selected'] = True
        request.session['demo_role'] = 'admin' if mode == 'solo' else 'admin'
        request.session['demo_expires_at'] = (
            timezone.now() + timedelta(hours=48)
        ).isoformat()
        request.session['is_demo_mode'] = True
        
        # Track selection (server-side)
        track_demo_event('demo_mode_selected', {
            'session_id': request.session.session_key,
            'mode': mode,
            'selection_method': selection_method
        })
        
        return redirect('demo_dashboard')
    
    return render(request, 'demo/mode_selection.html')
```

**Template Modifications:**

**Existing Template (Modify):**
```django
{# templates/demo/dashboard.html #}

{% extends "base.html" %}

{% block content %}

{# NEW: Demo banner #}
{% include "demo/partials/demo_banner.html" %}

{# EXISTING: Board list (keep) #}
<div class="boards-container">
  {% for board in boards %}
    <div class="board-card">
      <h3>{{ board.name }}</h3>
      <a href="{% url 'demo_board_detail' board.id %}">View Board</a>
    </div>
  {% endfor %}
</div>

{% endblock %}
```

**New Template (Create):**
```django
{# templates/demo/mode_selection.html #}

{% extends "base.html" %}

{% block content %}
<div class="demo-selection-modal">
  <h2>How do you want to explore PrizmAI?</h2>
  
  <form method="POST" id="demo-selection-form">
    {% csrf_token %}
    
    <div class="mode-option">
      <h3>🚀 Explore Solo (5 min)</h3>
      <p>Full access to all features</p>
      <button type="submit" name="mode" value="solo">
        Start Solo Exploration →
      </button>
    </div>
    
    <div class="mode-option">
      <h3>👥 Try as Team (10 min)</h3>
      <p>Experience real team workflows</p>
      <button type="submit" name="mode" value="team">
        Try Team Mode →
      </button>
    </div>
    
    <a href="#" id="skip-selection">
      Already know what you want? Skip selection →
    </a>
  </form>
</div>

<script>
// Handle skip selection
document.getElementById('skip-selection').addEventListener('click', function(e) {
  e.preventDefault();
  
  // Submit form with 'solo' mode and 'skipped' method
  const form = document.getElementById('demo-selection-form');
  const hiddenInput = document.createElement('input');
  hiddenInput.type = 'hidden';
  hiddenInput.name = 'method';
  hiddenInput.value = 'skipped';
  form.appendChild(hiddenInput);
  
  // Auto-select solo mode
  const modeInput = document.createElement('input');
  modeInput.type = 'hidden';
  modeInput.name = 'mode';
  modeInput.value = 'solo';
  form.appendChild(modeInput);
  
  form.submit();
});
</script>
{% endblock %}
```

---

## ✅ **Quick Decision Summary**

| Decision Point | Recommendation | Why |
|----------------|---------------|-----|
| **Org Names** | `"Demo - [Name]"` prefix | Clear distinction, easier cleanup |
| **Email Domain** | `@demo.prizmai.local` | Non-routable, branded, professional |
| **Task Count** | Start 120, scale to 1000+ | Faster MVP, scale after validation |
| **Reset Access** | Session-based (all demo users) | UX best practice, secure isolation |
| **Mobile Strategy** | Desktop-first, document mobile | Faster iteration, clear dependencies |
| **View Strategy** | Modify existing + add new | Preserve working code, safe refactoring |

---

## 🚀 **Implementation Checklist for Friends**

**Step 1: Database Setup**
```bash
# Add to models.py
- Organization.is_demo (BooleanField)
- Board.is_official_demo_board (BooleanField)  
- Task.created_by_session (CharField)
- Board.created_by_session (CharField)

# Create new models
- DemoAnalytics
- DemoSession
- DemoConversion

# Run migrations
python manage.py makemigrations
python manage.py migrate
```

**Step 2: Create Demo Data**
```bash
# Create management commands:
- create_demo_organizations.py  # 3 demo orgs with "Demo -" prefix
- create_demo_personas.py  # Alex, Sam, Jordan
- populate_demo_data.py  # 120 tasks (MVP)

# Run commands
python manage.py create_demo_organizations
python manage.py create_demo_personas  
python manage.py populate_demo_data --mvp
```

**Step 3: Create New Views & URLs**
```python
# Add to views.py:
- demo_mode_selection() 
- reset_demo_session()
- switch_demo_role()
- track_feature_explored()
- track_aha_moment()

# Add to urls.py:
- path('demo/start/', ...)
- path('demo/reset/', ...)
- path('demo/switch-role/', ...)
```

**Step 4: Modify Existing Views**
```python
# Update demo_dashboard():
- Check demo_mode_selected
- Add demo_mode, current_role to context
- Track pageview server-side

# Update demo_board_detail():  
- Add role-based permission checks
- Track feature interactions
```

**Step 5: Create Templates**
```django
# Create new:
- templates/demo/mode_selection.html
- templates/demo/partials/demo_banner.html

# Modify existing:
- templates/demo/dashboard.html (include banner)
```

**Step 6: Create Mobile Guide**
```markdown
# Create: MOBILE_PWA_IMPLEMENTATION.md
- Document all mobile adaptations
- List file changes needed
- Include mobile-specific UX patterns
```
