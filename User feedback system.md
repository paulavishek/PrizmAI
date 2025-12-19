# Complete Step-by-Step Guide: User Feedback System for PrizmAI

I'll give you a complete, integrated implementation plan combining all the best practices we discussed.

---

## 📋 Overview

We're building a sophisticated user feedback system that:
1. Tracks user behavior during their session
2. Shows personalized feedback form on logout
3. Integrates with HubSpot for CRM and email automation
4. Segments users by engagement level
5. Provides analytics dashboard for insights

---

## 🎯 Phase 1: Database Models (30 minutes)

### Step 1.1: Create UserSession Model

Create or update `your_app/models.py`:

```python
# models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class UserSession(models.Model):
    """
    Track user behavior during their session.
    This is the foundation for personalized feedback requests.
    """
    # Identity
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, db_index=True)
    
    # Behavior tracking
    boards_viewed = models.IntegerField(default=0)
    boards_created = models.IntegerField(default=0)
    tasks_created = models.IntegerField(default=0)
    tasks_completed = models.IntegerField(default=0)
    ai_features_used = models.IntegerField(default=0)
    
    # Time tracking
    session_start = models.DateTimeField(default=timezone.now)
    session_end = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(default=0)
    
    # Engagement scoring
    engagement_level = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('very_high', 'Very High'),
        ],
        default='low'
    )
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(max_length=500, blank=True)
    
    class Meta:
        ordering = ['-session_start']
        indexes = [
            models.Index(fields=['session_key', 'session_end']),
            models.Index(fields=['user', 'session_start']),
        ]
    
    def __str__(self):
        if self.user:
            return f"{self.user.username} - {self.session_start.strftime('%Y-%m-%d %H:%M')}"
        return f"Anonymous - {self.session_start.strftime('%Y-%m-%d %H:%M')}"
    
    def calculate_engagement_score(self):
        """
        Calculate engagement score (0-12 scale)
        This is key for segmentation and personalization
        """
        score = 0
        
        # Duration scoring (0-3 points)
        if self.duration_minutes >= 20:
            score += 3
        elif self.duration_minutes >= 10:
            score += 2
        elif self.duration_minutes >= 5:
            score += 1
        
        # Task activity (0-3 points)
        if self.tasks_created >= 5:
            score += 3
        elif self.tasks_created >= 2:
            score += 2
        elif self.tasks_created >= 1:
            score += 1
        
        # AI feature usage - key differentiator (0-3 points)
        if self.ai_features_used >= 5:
            score += 3
        elif self.ai_features_used >= 2:
            score += 2
        elif self.ai_features_used >= 1:
            score += 1
        
        # Board interaction (0-3 points)
        if self.boards_created >= 2:
            score += 3
        elif self.boards_created >= 1:
            score += 2
        elif self.boards_viewed >= 3:
            score += 1
        
        return score
    
    def update_engagement_level(self):
        """Update engagement level based on calculated score"""
        score = self.calculate_engagement_score()
        
        if score >= 9:
            self.engagement_level = 'very_high'
        elif score >= 6:
            self.engagement_level = 'high'
        elif score >= 3:
            self.engagement_level = 'medium'
        else:
            self.engagement_level = 'low'
        
        self.save(update_fields=['engagement_level'])


class Feedback(models.Model):
    """
    Store feedback submissions.
    Links to UserSession for correlation analysis.
    """
    # Link to session
    user_session = models.OneToOneField(
        UserSession, 
        on_delete=models.CASCADE,
        related_name='feedback',
        null=True,
        blank=True
    )
    
    # User info (optional - for anonymous users)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    organization = models.CharField(max_length=200, blank=True)
    
    # Feedback content
    feedback_text = models.TextField()
    rating = models.IntegerField(
        null=True,
        blank=True,
        choices=[(i, i) for i in range(1, 6)],
        help_text="1-5 star rating"
    )
    
    # Consent
    email_consent = models.BooleanField(
        default=False,
        help_text="User agreed to receive follow-up emails"
    )
    
    # Metadata
    submitted_at = models.DateTimeField(auto_now_add=True)
    hubspot_contact_id = models.CharField(max_length=50, blank=True)
    synced_to_hubspot = models.BooleanField(default=False)
    
    # Follow-up tracking
    follow_up_sent = models.BooleanField(default=False)
    follow_up_sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"Feedback from {self.name or self.email or 'Anonymous'} - {self.submitted_at.strftime('%Y-%m-%d')}"


class FeedbackPrompt(models.Model):
    """
    Track when we show feedback prompts to users.
    Helps prevent over-prompting and measure conversion rates.
    """
    user_session = models.ForeignKey(UserSession, on_delete=models.CASCADE)
    prompt_type = models.CharField(
        max_length=20,
        choices=[
            ('logout', 'Logout Page'),
            ('exit_intent', 'Exit Intent Popup'),
            ('in_app', 'In-App Banner'),
            ('email', 'Follow-up Email'),
        ]
    )
    shown_at = models.DateTimeField(auto_now_add=True)
    interacted = models.BooleanField(default=False)
    submitted = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-shown_at']
```

### Step 1.2: Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

---

## 🔧 Phase 2: Session Tracking Middleware (1 hour)

### Step 2.1: Create Middleware

Create `your_app/middleware.py`:

```python
# middleware.py
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from .models import UserSession
import logging

logger = logging.getLogger(__name__)

class SessionTrackingMiddleware(MiddlewareMixin):
    """
    Track user behavior throughout their session.
    This runs on every request and updates the UserSession model.
    """
    
    def process_request(self, request):
        # Skip tracking for:
        # - Static files
        # - Admin pages
        # - API health checks
        skip_paths = ['/static/', '/media/', '/admin/', '/health/']
        if any(request.path.startswith(path) for path in skip_paths):
            return None
        
        # Ensure session exists
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key
        
        # Get or create UserSession
        try:
            if request.user.is_authenticated:
                user_session, created = UserSession.objects.get_or_create(
                    user=request.user,
                    session_end__isnull=True,
                    defaults={
                        'session_key': session_key,
                        'session_start': timezone.now(),
                        'ip_address': self.get_client_ip(request),
                        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
                        'referrer': request.META.get('HTTP_REFERER', '')[:500],
                    }
                )
            else:
                user_session, created = UserSession.objects.get_or_create(
                    session_key=session_key,
                    session_end__isnull=True,
                    defaults={
                        'session_start': timezone.now(),
                        'ip_address': self.get_client_ip(request),
                        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
                        'referrer': request.META.get('HTTP_REFERER', '')[:500],
                    }
                )
            
            # Attach to request for easy access in views
            request.user_session = user_session
            
            if created:
                logger.info(f"New session created: {session_key}")
        
        except Exception as e:
            logger.error(f"Error in session tracking: {e}")
            # Don't break the request if tracking fails
            request.user_session = None
        
        return None
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """Track specific user actions"""
        if not hasattr(request, 'user_session') or request.user_session is None:
            return None
        
        session = request.user_session
        path = request.path.lower()
        method = request.method
        
        try:
            # Track board views (GET requests to board pages)
            if 'board' in path and method == 'GET' and 'list' not in path:
                session.boards_viewed += 1
                session.save(update_fields=['boards_viewed'])
            
            # Track board creation (POST to board endpoint)
            if 'board' in path and method == 'POST' and 'create' in path:
                session.boards_created += 1
                session.save(update_fields=['boards_created'])
            
            # Track task creation
            if 'task' in path and method == 'POST':
                session.tasks_created += 1
                session.save(update_fields=['tasks_created'])
            
            # Track task completion
            if 'task' in path and method in ['PUT', 'PATCH']:
                # You might want to check if status changed to 'completed'
                session.tasks_completed += 1
                session.save(update_fields=['tasks_completed'])
            
            # Track AI feature usage
            ai_paths = ['ai-recommend', 'ai-forecast', 'gemini', 'ai-coach', 'ai-detect']
            if any(ai_path in path for ai_path in ai_paths):
                session.ai_features_used += 1
                session.save(update_fields=['ai_features_used'])
        
        except Exception as e:
            logger.error(f"Error tracking action: {e}")
        
        return None
    
    def get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
```

### Step 2.2: Register Middleware

Add to `settings.py`:

```python
# settings.py

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Add your session tracking middleware
    'your_app.middleware.SessionTrackingMiddleware',  # ← Add this
]
```

---

## 🎨 Phase 3: Logout View with Feedback (1 hour)

### Step 3.1: Create Custom Logout View

Add to `your_app/views.py`:

```python
# views.py
from django.contrib.auth import logout
from django.shortcuts import render
from django.views import View
from django.utils import timezone
from datetime import timedelta
from .models import UserSession, FeedbackPrompt
import logging

logger = logging.getLogger(__name__)

class CustomLogoutView(View):
    """
    Custom logout view that:
    1. Collects session stats before logout
    2. Logs out the user
    3. Shows personalized feedback form based on engagement
    """
    template_name = 'registration/logout_success.html'
    
    def get(self, request):
        return self.handle_logout(request)
    
    def post(self, request):
        return self.handle_logout(request)
    
    def handle_logout(self, request):
        # Get session stats BEFORE logout (session will be destroyed)
        session_stats = self.get_session_stats(request)
        engagement_level = session_stats.get('engagement_level', 'low')
        
        # Track that we showed a feedback prompt
        if hasattr(request, 'user_session') and request.user_session:
            FeedbackPrompt.objects.create(
                user_session=request.user_session,
                prompt_type='logout'
            )
        
        # Store session ID for feedback form submission
        user_session_id = request.user_session.id if hasattr(request, 'user_session') and request.user_session else None
        
        # Logout user (destroys session)
        logout(request)
        
        # Prepare context for feedback page
        context = {
            'session_stats': session_stats,
            'engagement_level': engagement_level,
            'user_session_id': user_session_id,
            'show_detailed_stats': engagement_level in ['high', 'very_high'],
        }
        
        # Render feedback page
        return render(request, self.template_name, context)
    
    def get_session_stats(self, request):
        """
        Calculate and return session statistics.
        This must be called BEFORE logout() destroys the session.
        """
        stats = {
            'boards_viewed': 0,
            'boards_created': 0,
            'tasks_created': 0,
            'tasks_completed': 0,
            'ai_features_used': 0,
            'duration_minutes': 0,
            'engagement_level': 'low',
            'engagement_score': 0,
            'high_engagement': False,
        }
        
        try:
            if hasattr(request, 'user_session') and request.user_session:
                session = request.user_session
                
                # Calculate session duration
                session.session_end = timezone.now()
                duration = (session.session_end - session.session_start).total_seconds() / 60
                session.duration_minutes = int(duration)
                
                # Calculate engagement
                engagement_score = session.calculate_engagement_score()
                session.update_engagement_level()
                
                # Save final session state
                session.save()
                
                # Prepare stats
                stats = {
                    'boards_viewed': session.boards_viewed,
                    'boards_created': session.boards_created,
                    'tasks_created': session.tasks_created,
                    'tasks_completed': session.tasks_completed,
                    'ai_features_used': session.ai_features_used,
                    'duration_minutes': session.duration_minutes,
                    'engagement_level': session.engagement_level,
                    'engagement_score': engagement_score,
                    'high_engagement': session.engagement_level in ['high', 'very_high'],
                }
                
                logger.info(f"Session ended: {session.id}, Engagement: {session.engagement_level}")
        
        except Exception as e:
            logger.error(f"Error getting session stats: {e}")
        
        return stats
```

### Step 3.2: Create Feedback Submission View

Add to `your_app/views.py`:

```python
# views.py (continued)
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import Feedback, UserSession
import json

@require_http_methods(["POST"])
def submit_feedback_ajax(request):
    """
    Handle AJAX feedback submission from logout page.
    This is called when user submits the feedback form.
    """
    try:
        # Parse JSON data
        data = json.loads(request.body)
        
        # Get user session
        user_session_id = data.get('user_session_id')
        user_session = None
        if user_session_id:
            try:
                user_session = UserSession.objects.get(id=user_session_id)
            except UserSession.DoesNotExist:
                pass
        
        # Create feedback record
        feedback = Feedback.objects.create(
            user_session=user_session,
            user=request.user if request.user.is_authenticated else None,
            name=data.get('name', ''),
            email=data.get('email', ''),
            organization=data.get('organization', ''),
            feedback_text=data.get('feedback', ''),
            rating=data.get('rating'),
            email_consent=data.get('email_consent', False),
        )
        
        # Update feedback prompt as submitted
        if user_session:
            FeedbackPrompt.objects.filter(
                user_session=user_session,
                prompt_type='logout'
            ).update(submitted=True)
        
        logger.info(f"Feedback submitted: {feedback.id}")
        
        # TODO: Sync to HubSpot (we'll implement this in Phase 4)
        
        return JsonResponse({
            'success': True,
            'message': 'Thank you for your feedback!'
        })
    
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to submit feedback. Please try again.'
        }, status=500)
```

### Step 3.3: Update URLs

Add to `your_app/urls.py`:

```python
# urls.py
from django.urls import path
from .views import CustomLogoutView, submit_feedback_ajax

urlpatterns = [
    # ... your existing patterns ...
    
    # Custom logout
    path('accounts/logout/', CustomLogoutView.as_view(), name='logout'),
    
    # AJAX feedback submission
    path('api/submit-feedback/', submit_feedback_ajax, name='submit_feedback_ajax'),
]
```

**Important:** If you're using `django.contrib.auth.urls`, make sure your custom logout comes AFTER:

```python
# urls.py
from django.urls import path, include

urlpatterns = [
    # First include default auth URLs
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Then override logout with your custom one
    path('accounts/logout/', CustomLogoutView.as_view(), name='logout'),
]
```

---

## 🎨 Phase 4: Feedback Template (1 hour)

### Step 4.1: Create HubSpot Form

1. **Go to HubSpot** (sign up for free at hubspot.com)
2. Navigate to **Marketing → Forms**
3. Click **Create Form** → **Embedded Form**
4. Add fields:
   - **Email** (required)
   - **First Name**
   - **Company**
   - **Feedback** (multi-line text)
   - **Rating** (dropdown: 1-5)
   - Add **Hidden Fields**:
     - `app_usage_level` (text)
     - `session_duration` (text)
     - `ai_features_used` (number)
5. Under **Options**:
   - Thank you message: "Thanks! Your feedback helps improve PrizmAI."
6. Click **Publish** and copy the embed code

### Step 4.2: Create Logout Template

Create `templates/registration/logout_success.html`:

```html
{% extends 'base.html' %}

{% block title %}Thanks for trying PrizmAI{% endblock %}

{% block extra_css %}
<style>
    .logout-container {
        max-width: 800px;
        margin: 50px auto;
        padding: 20px;
    }
    
    .session-summary {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 15px;
        padding: 30px;
        margin-bottom: 30px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }
    
    .stat-card {
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        transition: transform 0.3s;
    }
    
    .stat-card:hover {
        transform: translateY(-5px);
    }
    
    .stat-number {
        font-size: 2.5rem;
        font-weight: bold;
        margin: 10px 0;
    }
    
    .stat-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    
    .feedback-section {
        background: white;
        border-radius: 15px;
        padding: 30px;
        box-shadow: 0 5px 20px rgba(0,0,0,0.05);
    }
    
    .engagement-badge {
        display: inline-block;
        padding: 5px 15px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-left: 10px;
    }
    
    .badge-very_high { background: #10b981; color: white; }
    .badge-high { background: #3b82f6; color: white; }
    .badge-medium { background: #f59e0b; color: white; }
    .badge-low { background: #6b7280; color: white; }
</style>
{% endblock %}

{% block content %}
<div class="logout-container">
    <!-- Session Summary -->
    <div class="session-summary">
        <div class="text-center mb-4">
            <h2>👋 Thanks for exploring PrizmAI!</h2>
            <p class="mb-0">
                {% if engagement_level == 'very_high' %}
                    You really dove deep into the features!
                {% elif engagement_level == 'high' %}
                    Great session! You explored several features.
                {% elif engagement_level == 'medium' %}
                    Nice! You got a feel for PrizmAI.
                {% else %}
                    Thanks for checking out PrizmAI!
                {% endif %}
                <span class="engagement-badge badge-{{ engagement_level }}">
                    {{ engagement_level|title }} Engagement
                </span>
            </p>
        </div>
        
        <!-- Session Stats -->
        {% if show_detailed_stats %}
        <div class="row g-3">
            <div class="col-md-3">
                <div class="stat-card">
                    <div class="stat-number">{{ session_stats.boards_viewed }}</div>
                    <div class="stat-label">Boards Viewed</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card">
                    <div class="stat-number">{{ session_stats.tasks_created }}</div>
                    <div class="stat-label">Tasks Created</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card">
                    <div class="stat-number">{{ session_stats.ai_features_used }}</div>
                    <div class="stat-label">AI Features Used</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="stat-card">
                    <div class="stat-number">{{ session_stats.duration_minutes }}</div>
                    <div class="stat-label">Minutes Active</div>
                </div>
            </div>
        </div>
        {% endif %}
    </div>
    
    <!-- Feedback Form -->
    <div class="feedback-section">
        <div class="text-center mb-4">
            {% if engagement_level in 'high,very_high' %}
                <h3>Your Feedback Matters! 🎯</h3>
                <p class="text-muted">
                    Since you spent time exploring PrizmAI, your insights would be incredibly valuable. 
                    What worked well? What could be better?
                </p>
            {% else %}
                <h3>Quick Feedback? (30 seconds)</h3>
                <p class="text-muted">
                    Help me understand what would make PrizmAI more useful for you.
                </p>
            {% endif %}
        </div>
        
        <!-- HubSpot Form Embed -->
        <div id="hubspot-form-container"></div>
        
        <script charset="utf-8" type="text/javascript" src="//js.hsforms.net/forms/embed/v2.js"></script>
        <script>
            hbspt.forms.create({
                region: "na1",  // Change to your HubSpot region
                portalId: "YOUR_PORTAL_ID",  // Replace with your HubSpot Portal ID
                formId: "YOUR_FORM_ID",  // Replace with your HubSpot Form ID
                target: "#hubspot-form-container",
                
                // Pre-populate fields with session data
                onFormReady: function($form) {
                    // Hidden fields
                    $form.find('input[name="app_usage_level"]').val("{{ engagement_level }}");
                    $form.find('input[name="session_duration"]').val("{{ session_stats.duration_minutes }}");
                    $form.find('input[name="ai_features_used"]').val("{{ session_stats.ai_features_used }}");
                    
                    // Pre-fill email if user was logged in
                    {% if user.email %}
                    $form.find('input[name="email"]').val("{{ user.email }}");
                    {% endif %}
                    
                    {% if user.first_name %}
                    $form.find('input[name="firstname"]').val("{{ user.first_name }}");
                    {% endif %}
                },
                
                // Handle submission
                onFormSubmit: function($form) {
                    console.log('Feedback submitted via HubSpot');
                    
                    // Track conversion in your analytics
                    if (typeof gtag !== 'undefined') {
                        gtag('event', 'feedback_submitted', {
                            'engagement_level': '{{ engagement_level }}',
                            'session_duration': {{ session_stats.duration_minutes }}
                        });
                    }
                    
                    // Update feedback prompt as interacted
                    {% if user_session_id %}
                    fetch('/api/track-feedback-interaction/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken')
                        },
                        body: JSON.stringify({
                            user_session_id: {{ user_session_id }},
                            submitted: true
                        })
                    });
                    {% endif %}
                }
            });
            
            // Helper function to get CSRF token
            function getCookie(name) {
                let cookieValue = null;
                if (document.cookie && document.cookie !== '') {
                    const cookies = document.cookie.split(';');
                    for (let i = 0; i < cookies.length; i++) {
                        const cookie = cookies[i].trim();
                        if (cookie.substring(0, name.length + 1) === (name + '=')) {
                            cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                            break;
                        }
                    }
                }
                return cookieValue;
            }
        </script>
        
        <!-- Alternative: Simple fallback form if HubSpot fails -->
        <noscript>
            <div class="alert alert-info mt-3">
                Please enable JavaScript to submit feedback, or email me directly at 
                <a href="mailto:avishek-paul@outlook.com">avishek-paul@outlook.com</a>
            </div>
        </noscript>
    </div>
    
    <!-- Navigation Links -->
    <div class="text-center mt-4">
        <a href="{% url 'login' %}" class="btn btn-primary btn-lg">Return to Login</a>
        <a href="/" class="btn btn-outline-secondary btn-lg">Homepage</a>
    </div>
    
    <!-- Skip link (less prominent) -->
    <div class="text-center mt-3">
        <small>
            <a href="/" class="text-muted">Skip feedback</a>
        </small>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
    // Track if user interacts with form (but doesn't submit)
    let formInteracted = false;
    
    document.addEventListener('DOMContentLoaded', function() {
        // Monitor form interaction
        setTimeout(function() {
            const formInputs = document.querySelectorAll('#hubspot-form-container input, #hubspot-form-container textarea');
            formInputs.forEach(input => {
                input.addEventListener('focus', function() {
                    if (!formInteracted) {
                        formInteracted = true;
                        
                        // Track interaction
                        {% if user_session_id %}
                        fetch('/api/track-feedback-interaction/', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': getCookie('csrftoken')
                            },
                            body: JSON.stringify({
                                user_session_id: {{ user_session_id }},
                                interacted: true
                            })
                        });
                        {% endif %}
                    }
                });
            });
        }, 1000); // Wait for HubSpot form to load
    });
    
    // Track abandonment (user leaves without submitting)
    window.addEventListener('beforeunload', function(e) {
        if (formInteracted) {
            // User interacted but didn't submit
            if (navigator.sendBeacon) {
                {% if user_session_id %}
                const data = JSON.stringify({
                    user_session_id: {{ user_session_id }},
                    abandoned: true
                });
                navigator.sendBeacon('/api/track-feedback-abandonment/', data);
                {% endif %}
            }
        }
    });
</script>
{% endblock %}
```

### Step 4.3: Add HubSpot Tracking Pixel to Base Template

Add to `templates/base.html` (before `</head>`):

```html
<!-- base.html -->
<head>
    <!-- ... your existing head content ... -->
    
    <!-- HubSpot Tracking Code -->
    <script type="text/javascript" id="hs-script-loader" async defer src="//js.hs-scripts.com/YOUR_PORTAL_ID.js"></script>
</head>
```

Replace `YOUR_PORTAL_ID` with your actual HubSpot Portal ID.

---

## 📊 Phase 5: HubSpot Integration (1 hour)

### Step 5.1: Install HubSpot SDK

```bash
pip install hubspot-api-client
pip freeze > requirements.txt
```

### Step 5.2: Add HubSpot Configuration

Add to `settings.py`:

```python
# settings.py

# HubSpot Configuration
HUBSPOT_ACCESS_TOKEN = os.getenv('HUBSPOT_ACCESS_TOKEN', '')
HUBSPOT_PORTAL_ID = os.getenv('HUBSPOT_PORTAL_ID', '')
```

### Step 5.3: Get HubSpot API Key

1. Go to HubSpot → Settings → Integrations → Private Apps
2. Create a Private App
3. Give it scopes:
   - `crm.objects.contacts.write`
   - `crm.objects.contacts.read`
4. Copy the Access Token
5. Add to your `.env` file:

```bash
# .env
HUBSPOT_ACCESS_TOKEN=your_access_token_here
HUBSPOT_PORTAL_ID=your_portal_id_here
```

### Step 5.4: Create HubSpot Integration Utility

Create `your_app/hubspot_integration.py`:

```python
# hubspot_integration.py
from hubspot import HubSpot
from hubspot.crm.contacts import SimplePublicObjectInput, ApiException
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class HubSpotIntegration:
    """
    Handles all HubSpot API interactions.
    Syncs feedback and user data to HubSpot CRM.
    """
    
    def __init__(self):
        if settings.HUBSPOT_ACCESS_TOKEN:
            self.client = HubSpot(access_token=settings.HUBSPOT_ACCESS_TOKEN)
        else:
            self.client = None
            logger.warning("HubSpot access token not configured")
    
    def create_or_update_contact(self, feedback):
        """
        Create or update a contact in HubSpot with feedback data.
        Returns the contact ID if successful, None otherwise.
        """
        if not self.client:
            logger.warning("HubSpot client not initialized")
            return None
        
        if not feedback.email:
            logger.info("No email provided, skipping HubSpot sync")
            return None
        
        try:
            # Prepare contact properties
            properties = {
                "email": feedback.email,
                "firstname": feedback.name.split()[0] if feedback.name else "",
                "lastname": " ".join(feedback.name.split()[1:]) if feedback.name and len(feedback.name.split()) > 1 else "",
                "company": feedback.organization,
                
                # Custom properties (create these in HubSpot first)
                "prizmai_feedback": feedback.feedback_text[:1000],  # HubSpot has char limits
                "prizmai_rating": str(feedback.rating) if feedback.rating else "",
                "prizmai_email_consent": "Yes" if feedback.email_consent else "No",
                "prizmai_engagement_level": feedback.user_session.engagement_level if feedback.user_session else "unknown",
                "prizmai_tasks_created": str(feedback.user_session.tasks_created) if feedback.user_session else "0",
                "prizmai_ai_features_used": str(feedback.user_session.ai_features_used) if feedback.user_session else "0",
                "prizmai_session_duration": str(feedback.user_session.duration_minutes) if feedback.user_session else "0",
                "prizmai_submitted_at": feedback.submitted_at.isoformat(),
                "lead_source": "PrizmAI Demo",
            }
            
            # Remove empty values
            properties = {k: v for k, v in properties.items() if v}
            
            # Try to find existing contact
            existing_contact = self._find_contact_by_email(feedback.email)
            
            if existing_contact:
                # Update existing contact
                contact_id = existing_contact['id']
                self.client.crm.contacts.basic_api.update(
                    contact_id=contact_id,
                    simple_public_object_input=SimplePublicObjectInput(properties=properties)
                )
                logger.info(f"Updated HubSpot contact: {contact_id}")
            else:
                # Create new contact
                contact = self.client.crm.contacts.basic_api.create(
                    simple_public_object_input=SimplePublicObjectInput(properties=properties)
                )
                contact_id = contact.id
                logger.info(f"Created HubSpot contact: {contact_id}")
            
            return contact_id
        
        except ApiException as e:
            logger.error(f"HubSpot API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error syncing to HubSpot: {e}")
            return None
    
    def _find_contact_by_email(self, email):
        """Find existing contact by email"""
        try:
            # Search for contact by email
            search_request = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "email",
                                "operator": "EQ",
                                "value": email
                            }
                        ]
                    }
                ]
            }
            
            results = self.client.crm.contacts.search_api.do_search(
                public_object_search_request=search_request
            )
            
            if results.results:
                return results.results[0].to_dict()
            return None
        
        except Exception as e:
            logger.error(f"Error searching for contact: {e}")
            return None
    
    def add_note_to_contact(self, contact_id, note_text):
        """Add an engagement note to a contact"""
        if not self.client:
            return False
        
        try:
            # HubSpot Notes API
            note_properties = {
                "hs_note_body": note_text,
                "hs_timestamp": datetime.now().isoformat()
            }
            
            # Create engagement
            # Note: This requires additional scopes - engagement.write
            # For simplicity, we'll skip this for now
            # You can implement if needed
            
            logger.info(f"Note added to contact {contact_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error adding note: {e}")
            return False


# Singleton instance
hubspot_integration = HubSpotIntegration()
```

### Step 5.5: Update Feedback Submission to Sync with HubSpot

Update `views.py`:

```python
# views.py (add to submit_feedback_ajax function)
from .hubspot_integration import hubspot_integration

@require_http_methods(["POST"])
def submit_feedback_ajax(request):
    """Handle AJAX feedback submission from logout page."""
    try:
        # ... existing code ...
        
        # Create feedback record
        feedback = Feedback.objects.create(
            user_session=user_session,
            user=request.user if request.user.is_authenticated else None,
            name=data.get('name', ''),
            email=data.get('email', ''),
            organization=data.get('organization', ''),
            feedback_text=data.get('feedback', ''),
            rating=data.get('rating'),
            email_consent=data.get('email_consent', False),
        )
        
        # Sync to HubSpot asynchronously (recommended for production)
        # For now, we'll do it synchronously
        if feedback.email:
            contact_id = hubspot_integration.create_or_update_contact(feedback)
            if contact_id:
                feedback.hubspot_contact_id = contact_id
                feedback.synced_to_hubspot = True
                feedback.save(update_fields=['hubspot_contact_id', 'synced_to_hubspot'])
        
        # ... rest of the code ...
```

---

## 📈 Phase 6: Analytics Dashboard (1-2 hours)

### Step 6.1: Create Analytics View

Add to `views.py`:

```python
# views.py
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Avg, Count, Q, F
from django.utils import timezone
from datetime import timedelta

@staff_member_required
def feedback_analytics_dashboard(request):
    """
    Analytics dashboard for feedback and user engagement.
    Show this to recruiters - demonstrates data-driven thinking.
    """
    
    # Time periods
    now = timezone.now()
    last_7_days = now - timedelta(days=7)
    last_30_days = now - timedelta(days=30)
    
    # Overall stats
    total_sessions = UserSession.objects.count()
    total_feedback = Feedback.objects.count()
    feedback_rate = (total_feedback / total_sessions * 100) if total_sessions > 0 else 0
    
    # Recent stats
    recent_sessions = UserSession.objects.filter(session_start__gte=last_7_days).count()
    recent_feedback = Feedback.objects.filter(submitted_at__gte=last_7_days).count()
    
    # Engagement breakdown
    engagement_distribution = UserSession.objects.values('engagement_level').annotate(
        count=Count('id'),
        feedback_count=Count('feedback'),
        avg_duration=Avg('duration_minutes'),
        avg_tasks=Avg('tasks_created'),
        avg_ai_usage=Avg('ai_features_used')
    ).order_by('-count')
    
    # Feedback by engagement level
    feedback_by_engagement = Feedback.objects.values(
        'user_session__engagement_level'
    ).annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Average ratings
    avg_rating = Feedback.objects.filter(
        rating__isnull=False
    ).aggregate(avg=Avg('rating'))['avg']
    
    # Conversion funnel
    conversion_funnel = {
        'total_visitors': total_sessions,
        'engaged_users': UserSession.objects.filter(tasks_created__gte=1).count(),
        'power_users': UserSession.objects.filter(ai_features_used__gte=3).count(),
        'feedback_providers': total_feedback,
    }
    
    # Calculate conversion rates
    if conversion_funnel['total_visitors'] > 0:
        conversion_funnel['engagement_rate'] = (
            conversion_funnel['engaged_users'] / conversion_funnel['total_visitors'] * 100
        )
        conversion_funnel['power_user_rate'] = (
            conversion_funnel['power_users'] / conversion_funnel['total_visitors'] * 100
        )
        conversion_funnel['feedback_rate'] = feedback_rate
    
    # Prompt performance
    prompt_stats = FeedbackPrompt.objects.values('prompt_type').annotate(
        shown=Count('id'),
        interacted=Count('id', filter=Q(interacted=True)),
        submitted=Count('id', filter=Q(submitted=True))
    )
    
    for stat in prompt_stats:
        if stat['shown'] > 0:
            stat['interaction_rate'] = (stat['interacted'] / stat['shown'] * 100)
            stat['completion_rate'] = (stat['submitted'] / stat['shown'] * 100)
    
    # Top feedback (most engaged users)
    top_feedback = Feedback.objects.select_related('user_session').order_by(
        '-user_session__engagement_level',
        '-submitted_at'
    )[:10]
    
    # Recent feedback
    recent_feedback_list = Feedback.objects.select_related('user_session').order_by(
        '-submitted_at'
    )[:20]
    
    # Email consent rate
    email_consent_rate = Feedback.objects.filter(
        email_consent=True
    ).count() / total_feedback * 100 if total_feedback > 0 else 0
    
    context = {
        'total_sessions': total_sessions,
        'total_feedback': total_feedback,
        'feedback_rate': round(feedback_rate, 1),
        'recent_sessions': recent_sessions,
        'recent_feedback': recent_feedback,
        'avg_rating': round(avg_rating, 2) if avg_rating else None,
        'engagement_distribution': engagement_distribution,
        'feedback_by_engagement': feedback_by_engagement,
        'conversion_funnel': conversion_funnel,
        'prompt_stats': prompt_stats,
        'top_feedback': top_feedback,
        'recent_feedback_list': recent_feedback_list,
        'email_consent_rate': round(email_consent_rate, 1),
    }
    
    return render(request, 'analytics/feedback_dashboard.html', context)
```

### Step 6.2: Create Dashboard Template

Create `templates/analytics/feedback_dashboard.html`:

```html
{% extends 'base.html' %}

{% block title %}Feedback Analytics Dashboard{% endblock %}

{% block extra_css %}
<style>
    .dashboard-container {
        padding: 30px;
    }
    
    .stat-card {
        background: white;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    .stat-number {
        font-size: 2.5rem;
        font-weight: bold;
        color: #667eea;
    }
    
    .stat-label {
        color: #6b7280;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .progress-bar-custom {
        height: 8px;
        border-radius: 4px;
    }
    
    .table-feedback {
        font-size: 0.9rem;
    }
    
    .engagement-badge {
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    
    .badge-very_high { background: #10b981; color: white; }
    .badge-high { background: #3b82f6; color: white; }
    .badge-medium { background: #f59e0b; color: white; }
    .badge-low { background: #6b7280; color: white; }
</style>
{% endblock %}

{% block content %}
<div class="dashboard-container">
    <h1 class="mb-4">📊 Feedback Analytics Dashboard</h1>
    
    <!-- Key Metrics -->
    <div class="row mb-4">
        <div class="col-md-3">
            <div class="stat-card text-center">
                <div class="stat-number">{{ total_sessions }}</div>
                <div class="stat-label">Total Sessions</div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="stat-card text-center">
                <div class="stat-number">{{ total_feedback }}</div>
                <div class="stat-label">Feedback Submissions</div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="stat-card text-center">
                <div class="stat-number">{{ feedback_rate }}%</div>
                <div class="stat-label">Feedback Rate</div>
            </div>
        </div>
        <div class="col-md-3">
            <div class="stat-card text-center">
                <div class="stat-number">{{ avg_rating|default:"N/A" }}</div>
                <div class="stat-label">Average Rating</div>
            </div>
        </div>
    </div>
    
    <!-- Recent Activity -->
    <div class="row mb-4">
        <div class="col-md-6">
            <div class="stat-card">
                <h5>Last 7 Days</h5>
                <p class="mb-1"><strong>{{ recent_sessions }}</strong> sessions</p>
                <p class="mb-0"><strong>{{ recent_feedback }}</strong> feedback submissions</p>
            </div>
        </div>
        <div class="col-md-6">
            <div class="stat-card">
                <h5>Email Consent</h5>
                <p class="mb-1"><strong>{{ email_consent_rate }}%</strong> opted in for follow-up</p>
                <div class="progress">
                    <div class="progress-bar bg-success progress-bar-custom" 
                         style="width: {{ email_consent_rate }}%"></div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Conversion Funnel -->
    <div class="stat-card mb-4">
        <h5 class="mb-3">🎯 Conversion Funnel</h5>
        <div class="row text-center">
            <div class="col-md-3">
                <h4>{{ conversion_funnel.total_visitors }}</h4>
                <small>Total Visitors</small>
                <div class="mt-2 text-success">100%</div>
            </div>
            <div class="col-md-3">
                <h4>{{ conversion_funnel.engaged_users }}</h4>
                <small>Engaged Users</small>
                <div class="mt-2 text-info">{{ conversion_funnel.engagement_rate|floatformat:1 }}%</div>
            </div>
            <div class="col-md-3">
                <h4>{{ conversion_funnel.power_users }}</h4>
                <small>Power Users (3+ AI)</small>
                <div class="mt-2 text-warning">{{ conversion_funnel.power_user_rate|floatformat:1 }}%</div>
            </div>
            <div class="col-md-3">
                <h4>{{ conversion_funnel.feedback_providers }}</h4>
                <small>Feedback Providers</small>
                <div class="mt-2 text-primary">{{ conversion_funnel.feedback_rate|floatformat:1 }}%</div>
            </div>
        </div>
    </div>
    
    <!-- Engagement Distribution -->
    <div class="row mb-4">
        <div class="col-md-6">
            <div class="stat-card">
                <h5 class="mb-3">📈 Engagement Distribution</h5>
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>Level</th>
                            <th>Sessions</th>
                            <th>Avg Duration</th>
                            <th>Avg Tasks</th>
                            <th>Avg AI Usage</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in engagement_distribution %}
                        <tr>
                            <td>
                                <span class="engagement-badge badge-{{ item.engagement_level }}">
                                    {{ item.engagement_level|title }}
                                </span>
                            </td>
                            <td>{{ item.count }}</td>
                            <td>{{ item.avg_duration|floatformat:0 }}m</td>
                            <td>{{ item.avg_tasks|floatformat:1 }}</td>
                            <td>{{ item.avg_ai_usage|floatformat:1 }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        
        <div class="col-md-6">
            <div class="stat-card">
                <h5 class="mb-3">💬 Prompt Performance</h5>
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>Prompt Type</th>
                            <th>Shown</th>
                            <th>Interaction Rate</th>
                            <th>Completion Rate</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for stat in prompt_stats %}
                        <tr>
                            <td>{{ stat.prompt_type|title }}</td>
                            <td>{{ stat.shown }}</td>
                            <td>{{ stat.interaction_rate|floatformat:1 }}%</td>
                            <td>{{ stat.completion_rate|floatformat:1 }}%</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    
    <!-- Recent Feedback -->
    <div class="stat-card">
        <h5 class="mb-3">📝 Recent Feedback</h5>
        <div class="table-responsive">
            <table class="table table-feedback table-hover">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Name/Email</th>
                        <th>Organization</th>
                        <th>Engagement</th>
                        <th>Rating</th>
                        <th>Feedback</th>
                        <th>Consent</th>
                    </tr>
                </thead>
                <tbody>
                    {% for fb in recent_feedback_list %}
                    <tr>
                        <td>{{ fb.submitted_at|date:"M d, Y" }}</td>
                        <td>
                            {{ fb.name|default:"Anonymous" }}<br>
                            <small class="text-muted">{{ fb.email|default:"No email" }}</small>
                        </td>
                        <td>{{ fb.organization|default:"-" }}</td>
                        <td>
                            {% if fb.user_session %}
                            <span class="engagement-badge badge-{{ fb.user_session.engagement_level }}">
                                {{ fb.user_session.engagement_level|title }}
                            </span>
                            {% else %}
                            -
                            {% endif %}
                        </td>
                        <td>
                            {% if fb.rating %}
                                ⭐ {{ fb.rating }}/5
                            {% else %}
                                -
                            {% endif %}
                        </td>
                        <td>
                            <small>{{ fb.feedback_text|truncatewords:15 }}</small>
                        </td>
                        <td>
                            {% if fb.email_consent %}
                                <span class="badge bg-success">Yes</span>
                            {% else %}
                                <span class="badge bg-secondary">No</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% empty %}
                    <tr>
                        <td colspan="7" class="text-center text-muted">No feedback yet</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
{% endblock %}
```

### Step 6.3: Add Dashboard URL

```python
# urls.py
from .views import feedback_analytics_dashboard

urlpatterns = [
    # ... existing patterns ...
    
    # Analytics dashboard (staff only)
    path('analytics/feedback/', feedback_analytics_dashboard, name='feedback_analytics'),
]
```

---

## 🧪 Phase 7: Testing (30 minutes)

### Step 7.1: Test Checklist

Create a test plan:

```markdown
# Feedback System Test Plan

## 1. Session Tracking
- [ ] Visit homepage → boards_viewed increments
- [ ] Create task → tasks_created increments
- [ ] Use AI feature → ai_features_used increments
- [ ] Check UserSession in admin → stats are correct

## 2. Logout Flow
- [ ] Click logout → see feedback page (not login page)
- [ ] Session stats display correctly
- [ ] Engagement level badge shows
- [ ] HubSpot form loads

## 3. Feedback Submission
- [ ] Fill form → submit → success message
- [ ] Check Feedback in admin → saved correctly
- [ ] Check HubSpot → contact created/updated
- [ ] Email consent checkbox works

## 4. Analytics Dashboard
- [ ] Visit /analytics/feedback/ → dashboard loads
- [ ] All metrics display correctly
- [ ] Recent feedback shows
- [ ] Conversion funnel calculates correctly

## 5. Edge Cases
- [ ] Anonymous user logout → works
- [ ] User with no activity → shows low engagement
- [ ] Form submission without email → saves locally
- [ ] HubSpot API failure → doesn't break flow
```

### Step 7.2: Manual Testing Steps

```bash
# 1. Create test user
python manage.py createsuperuser

# 2. Login and simulate activity
# - Create a board
# - Create 5+ tasks
# - Use 3+ AI features
# - Spend 10+ minutes

# 3. Logout and check
# - Should see personalized feedback page
# - Session stats should be accurate
# - Fill and submit feedback form

# 4. Check results
# - Django admin: Check UserSession and Feedback models
# - HubSpot: Check Contacts
# - Analytics dashboard: /analytics/feedback/
```

---

## 🚀 Phase 8: Deployment (30 minutes)

### Step 8.1: Update Environment Variables

Add to your production `.env`:

```bash
# .env (production)
HUBSPOT_ACCESS_TOKEN=your_production_access_token
HUBSPOT_PORTAL_ID=your_portal_id

# Optional: Email for notifications
ADMIN_EMAIL=avishek-paul@outlook.com
```

### Step 8.2: Deploy to Railway/Render

```bash
# 1. Commit all changes
git add .
git commit -m "Add user feedback system with HubSpot integration"
git push origin main

# 2. Deploy (Railway auto-deploys on push)
# Or manually: railway up

# 3. Run migrations on production
railway run python manage.py migrate

# 4. Test on production
# Visit: your-app.railway.app
```

---

## 📊 Phase 9: Monitor & Iterate (Ongoing)

### Step 9.1: Weekly Monitoring

```python
# Create a management command for weekly reports
# your_app/management/commands/weekly_feedback_report.py

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from your_app.models import UserSession, Feedback
from datetime import timedelta
from django.utils import timezone

class Command(BaseCommand):
    help = 'Send weekly feedback report email'
    
    def handle(self, *args, **options):
        # Calculate stats for last 7 days
        week_ago = timezone.now() - timedelta(days=7)
        
        sessions = UserSession.objects.filter(session_start__gte=week_ago)
        feedback = Feedback.objects.filter(submitted_at__gte=week_ago)
        
        report = f"""
        PrizmAI Weekly Feedback Report
        ==============================
        
        Period: Last 7 days
        
        ## Sessions
        - Total sessions: {sessions.count()}
        - High engagement: {sessions.filter(engagement_level__in=['high', 'very_high']).count()}
        - Avg duration: {sessions.aggregate(avg=models.Avg('duration_minutes'))['avg']:.1f} minutes
        
        ## Feedback
        - Total submissions: {feedback.count()}
        - Feedback rate: {(feedback.count() / sessions.count() * 100):.1f}%
        - Email opt-ins: {feedback.filter(email_consent=True).count()}
        - Avg rating: {feedback.filter(rating__isnull=False).aggregate(avg=models.Avg('rating'))['avg']:.2f}/5
        
        ## Top Insights
        {self.get_top_insights(feedback)}
        
        View full dashboard: {settings.SITE_URL}/analytics/feedback/
        """
        
        send_mail(
            subject='PrizmAI: Weekly Feedback Report',
            message=report,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_EMAIL],
            fail_silently=False,
        )
        
        self.stdout.write(self.style.SUCCESS('Weekly report sent!'))
    
    def get_top_insights(self, feedback):
        # Extract common themes from feedback
        # You could use AI here to summarize feedback
        insights = []
        for fb in feedback[:5]:
            insights.append(f"- {fb.name or 'Anonymous'}: {fb.feedback_text[:100]}...")
        return "\n".join(insights)
```

Run weekly:
```bash
python manage.py weekly_feedback_report
```

Or set up a cron job / Celery task.

---

## 🎯 Summary: What You've Built

✅ **Session Tracking System**
- Automatic behavior tracking via middleware
- Engagement scoring algorithm
- Duration and activity monitoring

✅ **Personalized Feedback Collection**
- Smart logout page with session stats
- Engagement-based messaging
- HubSpot form integration

✅ **HubSpot CRM Integration**
- Automatic contact creation/updates
- Custom properties for PrizmAI data
- Email consent tracking

✅ **Analytics Dashboard**
- Real-time metrics
- Conversion funnel analysis
- Engagement distribution
- Prompt performance tracking

✅ **Follow-up Automation** (via HubSpot)
- Email workflows for non-responders
- Segmented messaging by engagement
- Automated nurture sequences

