"""
Analytics models for tracking user sessions, feedback, and engagement.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q, Avg, Count, Sum


class UserSession(models.Model):
    """
    Track user behavior during their session.
    Foundation for personalized feedback requests and engagement scoring.
    """
    # Identity
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        help_text="Authenticated user (null for anonymous)"
    )
    session_key = models.CharField(max_length=40, db_index=True)
    
    # Behavior tracking
    boards_viewed = models.IntegerField(default=0)
    boards_created = models.IntegerField(default=0)
    tasks_created = models.IntegerField(default=0)
    tasks_completed = models.IntegerField(default=0)
    ai_features_used = models.IntegerField(default=0)
    pages_visited = models.IntegerField(default=0)
    
    # Time tracking
    session_start = models.DateTimeField(default=timezone.now)
    session_end = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(default=timezone.now)
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
    engagement_score = models.IntegerField(default=0, help_text="Calculated score 0-12")
    
    # Engagement update tracking
    last_engagement_update = models.IntegerField(default=0, help_text="Duration minutes when engagement was last updated")
    
    # Registration tracking
    registered_during_session = models.BooleanField(default=False)
    is_return_visit = models.BooleanField(default=False)
    previous_session_count = models.IntegerField(default=0)
    
    # Feature discovery
    features_discovered = models.JSONField(
        default=list, 
        blank=True,
        help_text="List of features user discovered: ['kanban', 'ai_recommend', etc.]"
    )
    
    # Exit tracking
    exit_page = models.CharField(max_length=200, blank=True)
    exit_reason = models.CharField(
        max_length=20,
        choices=[
            ('logout', 'User Logged Out'),
            ('timeout', 'Session Timeout'),
            ('navigation', 'Navigation Away'),
        ],
        blank=True
    )
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(max_length=500, blank=True)
    device_type = models.CharField(
        max_length=20,
        choices=[
            ('desktop', 'Desktop'),
            ('mobile', 'Mobile'),
            ('tablet', 'Tablet'),
            ('unknown', 'Unknown'),
        ],
        default='unknown'
    )
    
    class Meta:
        ordering = ['-session_start']
        indexes = [
            models.Index(fields=['session_key', 'session_end']),
            models.Index(fields=['user', 'session_start']),
            models.Index(fields=['engagement_level']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(session_end__isnull=True),
                name='one_active_session_per_user'
            )
        ]
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'
    
    def __str__(self):
        if self.user:
            return f"{self.user.username} - {self.session_start.strftime('%Y-%m-%d %H:%M')}"
        return f"Anonymous - {self.session_start.strftime('%Y-%m-%d %H:%M')}"
    
    def calculate_engagement_score(self):
        """
        Calculate engagement score (0-12 scale).
        Used for user segmentation and personalization.
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
        
        self.engagement_score = score
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
        
        self.save(update_fields=['engagement_level', 'engagement_score'])
    
    def update_duration(self):
        """Calculate and update session duration"""
        if self.session_end:
            delta = self.session_end - self.session_start
        else:
            delta = self.last_activity - self.session_start
        
        self.duration_minutes = int(delta.total_seconds() / 60)
        self.save(update_fields=['duration_minutes'])
    
    def end_session(self, reason='logout', exit_page=''):
        """End the session and calculate final metrics"""
        self.session_end = timezone.now()
        self.exit_reason = reason
        self.exit_page = exit_page
        self.update_duration()
        self.update_engagement_level()
        self.save()
    
    def save(self, *args, **kwargs):
        # Auto-detect return visits
        if self.user and not self.pk:  # Only on creation
            previous_sessions = UserSession.objects.filter(
                user=self.user,
                session_end__isnull=False
            )
            
            if previous_sessions.exists():
                self.is_return_visit = True
                self.previous_session_count = previous_sessions.count()
        
        super().save(*args, **kwargs)


class Feedback(models.Model):
    """
    Store feedback submissions from users.
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
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True
    )
    name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    organization = models.CharField(max_length=200, blank=True)
    
    # Feedback content
    feedback_text = models.TextField()
    rating = models.IntegerField(
        null=True,
        blank=True,
        choices=[(i, f"{i} Star{'s' if i != 1 else ''}") for i in range(1, 6)],
        help_text="1-5 star rating"
    )
    
    # Sentiment analysis (can be auto-generated)
    sentiment = models.CharField(
        max_length=20,
        choices=[
            ('positive', 'Positive'),
            ('neutral', 'Neutral'),
            ('negative', 'Negative'),
        ],
        blank=True
    )
    
    # Categorization
    feedback_type = models.CharField(
        max_length=20,
        choices=[
            ('feature_request', 'Feature Request'),
            ('bug_report', 'Bug Report'),
            ('praise', 'Praise'),
            ('complaint', 'Complaint'),
            ('question', 'Question'),
            ('other', 'Other'),
        ],
        default='other'
    )
    
    # Consent
    email_consent = models.BooleanField(
        default=False,
        help_text="User agreed to receive follow-up emails"
    )
    
    # Metadata
    submitted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Follow-up tracking
    follow_up_sent = models.BooleanField(default=False)
    follow_up_sent_at = models.DateTimeField(null=True, blank=True)
    follow_up_response = models.TextField(blank=True)
    
    # Internal notes
    admin_notes = models.TextField(
        blank=True,
        help_text="Internal notes for team use only"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('new', 'New'),
            ('reviewed', 'Reviewed'),
            ('in_progress', 'In Progress'),
            ('resolved', 'Resolved'),
            ('archived', 'Archived'),
        ],
        default='new'
    )
    
    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'User Feedback'
        verbose_name_plural = 'User Feedback'
    
    def __str__(self):
        identifier = self.name or self.email or 'Anonymous'
        return f"Feedback from {identifier} - {self.submitted_at.strftime('%Y-%m-%d')}"
    
    def analyze_sentiment(self):
        """
        Enhanced sentiment analysis using VADER for text and rating-based fallback.
        """
        if self.rating:
            # Rating-based sentiment (quick and accurate for rated feedback)
            if self.rating >= 4:
                self.sentiment = 'positive'
            elif self.rating >= 3:
                self.sentiment = 'neutral'
            else:
                self.sentiment = 'negative'
        else:
            # Use VADER for text analysis if available
            try:
                from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
                analyzer = SentimentIntensityAnalyzer()
                scores = analyzer.polarity_scores(self.feedback_text)
                
                if scores['compound'] >= 0.05:
                    self.sentiment = 'positive'
                elif scores['compound'] <= -0.05:
                    self.sentiment = 'negative'
                else:
                    self.sentiment = 'neutral'
            except ImportError:
                # Fallback to keyword-based sentiment if VADER not installed
                text_lower = self.feedback_text.lower()
                positive_words = ['love', 'great', 'excellent', 'amazing', 'fantastic', 'helpful', 'awesome', 'perfect']
                negative_words = ['hate', 'terrible', 'awful', 'confusing', 'bug', 'broken', 'issue', 'poor', 'bad']
                
                pos_count = sum(1 for word in positive_words if word in text_lower)
                neg_count = sum(1 for word in negative_words if word in text_lower)
                
                if pos_count > neg_count:
                    self.sentiment = 'positive'
                elif neg_count > pos_count:
                    self.sentiment = 'negative'
                else:
                    self.sentiment = 'neutral'
        
        self.save(update_fields=['sentiment'])


class FeedbackPrompt(models.Model):
    """
    Track when we show feedback prompts to users.
    Helps prevent over-prompting and measure conversion rates.
    """
    user_session = models.ForeignKey(
        UserSession, 
        on_delete=models.CASCADE,
        related_name='feedback_prompts'
    )
    prompt_type = models.CharField(
        max_length=20,
        choices=[
            ('logout', 'Logout Page'),
            ('exit_intent', 'Exit Intent Popup'),
            ('in_app', 'In-App Banner'),
            ('email', 'Follow-up Email'),
            ('modal', 'Modal Dialog'),
        ]
    )
    shown_at = models.DateTimeField(auto_now_add=True)
    interacted = models.BooleanField(
        default=False,
        help_text="User clicked or engaged with prompt"
    )
    submitted = models.BooleanField(
        default=False,
        help_text="User submitted feedback"
    )
    dismissed = models.BooleanField(
        default=False,
        help_text="User dismissed/closed prompt"
    )
    
    class Meta:
        ordering = ['-shown_at']
        verbose_name = 'Feedback Prompt'
        verbose_name_plural = 'Feedback Prompts'
    
    def __str__(self):
        return f"{self.prompt_type} prompt - {self.shown_at.strftime('%Y-%m-%d %H:%M')}"


class AnalyticsEvent(models.Model):
    """
    Track custom events for detailed analytics.
    Complements GA4 with server-side event tracking.
    """
    user_session = models.ForeignKey(
        UserSession,
        on_delete=models.CASCADE,
        related_name='events'
    )
    event_name = models.CharField(max_length=100, db_index=True)
    event_category = models.CharField(max_length=50, blank=True)
    event_label = models.CharField(max_length=200, blank=True)
    event_value = models.IntegerField(null=True, blank=True)
    event_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional event metadata"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event_name', 'timestamp']),
            models.Index(fields=['user_session', 'event_name']),
        ]
        verbose_name = 'Analytics Event'
        verbose_name_plural = 'Analytics Events'
    
    def __str__(self):
        return f"{self.event_name} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


# ============================================================================
# DEMO MODE ANALYTICS MODELS
# ============================================================================

class DemoSession(models.Model):
    """
    Track demo sessions separately from regular user sessions.
    Supports hybrid analytics (server-side + client-side tracking).
    """
    # Session identification
    session_id = models.CharField(max_length=255, unique=True, db_index=True)
    browser_fingerprint = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="Browser fingerprint to track demo across sessions"
    )
    client_fingerprint = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="Client-side JS fingerprint (more robust than server-side)"
    )
    is_vpn_detected = models.BooleanField(
        default=False,
        help_text="Whether VPN/proxy was detected for this session"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='demo_sessions',
        help_text="User who started demo (null if demo led to signup)"
    )
    
    # Demo configuration
    demo_mode = models.CharField(
        max_length=20,
        choices=[
            ('solo', 'Solo Exploration'),
            ('team', 'Team Collaboration'),
        ],
        help_text="Demo mode selected by user"
    )
    selection_method = models.CharField(
        max_length=20,
        choices=[
            ('selected', 'Explicitly Selected'),
            ('skipped', 'Skipped Selection'),
        ],
        default='selected',
        help_text="How user entered demo mode"
    )
    current_role = models.CharField(
        max_length=20,
        choices=[
            ('admin', 'Administrator'),
            ('member', 'Team Member'),
            ('viewer', 'Viewer'),
        ],
        default='admin',
        help_text="Current persona role (for Team mode)"
    )
    
    # Session timing
    created_at = models.DateTimeField(auto_now_add=True)
    first_demo_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When user FIRST started demo (persists across logins)"
    )
    expires_at = models.DateTimeField(help_text="Session expiration (48 hours default)")
    last_activity = models.DateTimeField(auto_now=True)
    session_end = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0, help_text="Total time in demo")
    
    # Engagement metrics
    features_explored = models.IntegerField(default=0, help_text="Count of features with meaningful interaction")
    features_list = models.JSONField(
        default=list,
        blank=True,
        help_text="List of features explored: ['ai_generator', 'burndown', etc.]"
    )
    aha_moments = models.IntegerField(default=0, help_text="Count of aha moments experienced")
    aha_moments_list = models.JSONField(
        default=list,
        blank=True,
        help_text="List of aha moment triggers"
    )
    nudges_shown = models.IntegerField(default=0, help_text="Count of conversion nudges shown")
    nudges_clicked = models.IntegerField(default=0, help_text="Count of nudge CTAs clicked")
    nudges_dismissed = models.IntegerField(default=0, help_text="Count of nudges dismissed by user")
    
    # Demo Limitations Tracking
    projects_created_in_demo = models.IntegerField(default=0, help_text="Number of projects created in demo mode")
    ai_generations_used = models.IntegerField(default=0, help_text="Number of AI generations used in demo")
    export_attempts = models.IntegerField(default=0, help_text="Number of export attempts (blocked)")
    limitations_hit = models.JSONField(
        default=list,
        blank=True,
        help_text="List of limitations encountered: ['project_limit', 'export_blocked', etc.]"
    )
    
    # Conversion tracking
    converted_to_signup = models.BooleanField(default=False)
    conversion_timestamp = models.DateTimeField(null=True, blank=True)
    time_to_conversion_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time from demo start to signup"
    )
    
    # Demo actions
    reset_count = models.IntegerField(default=0, help_text="Number of times demo was reset")
    role_switches = models.IntegerField(default=0, help_text="Number of role switches (Team mode)")
    extensions_count = models.IntegerField(default=0, help_text="Number of times session was extended")
    
    # Device & metadata
    device_type = models.CharField(
        max_length=20,
        choices=[
            ('desktop', 'Desktop'),
            ('mobile', 'Mobile'),
            ('tablet', 'Tablet'),
            ('unknown', 'Unknown'),
        ],
        default='unknown'
    )
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Analytics tracking flags
    has_ga4_data = models.BooleanField(
        default=False,
        help_text="Whether GA4 successfully tracked this session"
    )
    
    # Email reminder tracking
    reminder_24h_sent = models.BooleanField(
        default=False,
        help_text="Whether 24-hour reminder email was sent"
    )
    reminder_24h_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When 24-hour reminder email was sent"
    )
    reminder_12h_sent = models.BooleanField(
        default=False,
        help_text="Whether 12-hour reminder email was sent"
    )
    reminder_12h_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When 12-hour reminder email was sent"
    )
    
    # Inactivity re-engagement tracking
    inactivity_email_sent = models.BooleanField(
        default=False,
        help_text="Whether inactivity re-engagement email was sent"
    )
    inactivity_email_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When inactivity email was sent"
    )
    
    # User email for demo (optional - collected during demo or linked to account)
    demo_user_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Email address for demo user (for sending reminders)"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session_id']),
            models.Index(fields=['created_at', 'expires_at']),
            models.Index(fields=['demo_mode']),
            models.Index(fields=['converted_to_signup']),
        ]
        verbose_name = 'Demo Session'
        verbose_name_plural = 'Demo Sessions'
    
    def __str__(self):
        return f"Demo Session {self.session_id[:8]} - {self.demo_mode}"
    
    def is_expired(self):
        """Check if session has expired"""
        return timezone.now() > self.expires_at
    
    def calculate_duration(self):
        """Calculate and update session duration"""
        if self.session_end:
            delta = self.session_end - self.created_at
        else:
            delta = self.last_activity - self.created_at
        
        self.duration_seconds = int(delta.total_seconds())
        self.save(update_fields=['duration_seconds'])
        return self.duration_seconds
    
    def record_conversion(self):
        """Record successful conversion to signup"""
        self.converted_to_signup = True
        self.conversion_timestamp = timezone.now()
        self.time_to_conversion_seconds = int(
            (self.conversion_timestamp - self.created_at).total_seconds()
        )
        self.save(update_fields=[
            'converted_to_signup',
            'conversion_timestamp',
            'time_to_conversion_seconds'
        ])


class DemoAnalytics(models.Model):
    """
    Server-side event tracking for demo mode.
    Provides 100% coverage (cannot be blocked by ad-blockers).
    """
    # Session reference
    session_id = models.CharField(max_length=255, db_index=True)
    demo_session = models.ForeignKey(
        DemoSession,
        on_delete=models.CASCADE,
        related_name='analytics_events',
        null=True,
        blank=True
    )
    
    # Event details
    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Event name: 'demo_mode_selected', 'feature_explored', 'aha_moment', etc."
    )
    event_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Event-specific data and metadata"
    )
    
    # Timing
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Context
    page_path = models.CharField(max_length=500, blank=True)
    device_type = models.CharField(
        max_length=20,
        choices=[
            ('desktop', 'Desktop'),
            ('mobile', 'Mobile'),
            ('tablet', 'Tablet'),
            ('unknown', 'Unknown'),
        ],
        default='unknown'
    )
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['session_id', 'event_type']),
            models.Index(fields=['event_type', 'timestamp']),
            models.Index(fields=['demo_session', 'event_type']),
        ]
        verbose_name = 'Demo Analytics Event'
        verbose_name_plural = 'Demo Analytics Events'
    
    def __str__(self):
        return f"{self.event_type} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


class AhaMomentEvent(models.Model):
    """
    Dedicated tracking for aha moments - key product value discoveries.
    Used for understanding when users realize the product's value and
    optimizing the path to conversion.
    """
    # Aha moment types
    AHA_MOMENT_TYPES = [
        ('ai_suggestion_accepted', 'AI Suggestion Accepted'),
        ('burndown_viewed', 'Burndown Chart Viewed'),
        ('rbac_workflow', 'RBAC/Permissions Used'),
        ('time_tracking_used', 'Time Tracking Used'),
        ('dependency_created', 'Task Dependency Created'),
        ('gantt_viewed', 'Gantt Chart Viewed'),
        ('skill_gap_viewed', 'Skill Gap Analysis Viewed'),
        ('conflict_detected', 'Conflict Detection Explored'),
        ('budget_forecasting', 'Budget Forecasting Used'),
        ('retrospective_completed', 'Retrospective Completed'),
        ('milestone_reached', 'Milestone Reached'),
        ('first_board_created', 'First Board Created'),
        ('first_task_completed', 'First Task Completed'),
        ('team_collaboration', 'Team Collaboration Feature'),
        ('wiki_explored', 'Wiki/Documentation Explored'),
        ('analytics_deep_dive', 'Analytics Deep Dive'),
        ('custom', 'Custom Aha Moment'),
    ]
    
    # Session references
    demo_session = models.ForeignKey(
        DemoSession,
        on_delete=models.CASCADE,
        related_name='aha_moment_events',
        null=True,
        blank=True,
        help_text="Demo session where aha moment occurred"
    )
    user_session = models.ForeignKey(
        UserSession,
        on_delete=models.CASCADE,
        related_name='aha_moment_events',
        null=True,
        blank=True,
        help_text="User session where aha moment occurred"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='aha_moment_events',
        null=True,
        blank=True,
        help_text="User who experienced the aha moment"
    )
    session_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Session identifier for tracking"
    )
    
    # Aha moment details
    moment_type = models.CharField(
        max_length=50,
        choices=AHA_MOMENT_TYPES,
        db_index=True,
        help_text="Type of aha moment triggered"
    )
    moment_subtype = models.CharField(
        max_length=100,
        blank=True,
        help_text="Specific subtype or variant of aha moment"
    )
    
    # Context when aha happened
    page_path = models.CharField(max_length=500, help_text="Page where aha moment occurred")
    feature_context = models.CharField(
        max_length=100,
        blank=True,
        help_text="Specific feature being used (e.g., 'task_generator', 'sprint_burndown')"
    )
    trigger_action = models.CharField(
        max_length=100,
        blank=True,
        help_text="Specific action that triggered the aha (e.g., 'accept_suggestion', 'view_chart')"
    )
    
    # Timing and journey
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    time_since_session_start = models.IntegerField(
        null=True,
        blank=True,
        help_text="Seconds since session started when aha occurred"
    )
    actions_before_aha = models.IntegerField(
        default=0,
        help_text="Number of user actions before this aha moment"
    )
    previous_aha_moments = models.IntegerField(
        default=0,
        help_text="Number of aha moments before this one in session"
    )
    
    # Impact tracking
    led_to_conversion = models.BooleanField(
        default=False,
        help_text="Whether this aha moment led to signup/conversion"
    )
    conversion_time_seconds = models.IntegerField(
        null=True,
        blank=True,
        help_text="Seconds between aha moment and conversion"
    )
    engagement_after_aha = models.CharField(
        max_length=20,
        choices=[
            ('increased', 'Increased Engagement'),
            ('maintained', 'Maintained Engagement'),
            ('decreased', 'Decreased Engagement'),
            ('unknown', 'Unknown'),
        ],
        default='unknown',
        help_text="User engagement level after aha moment"
    )
    
    # User feedback on aha (optional)
    user_acknowledged = models.BooleanField(
        default=False,
        help_text="Whether user interacted with aha celebration UI"
    )
    celebration_shown = models.BooleanField(
        default=True,
        help_text="Whether celebration UI was shown to user"
    )
    celebration_dismissed = models.BooleanField(
        default=False,
        help_text="Whether user dismissed celebration quickly"
    )
    cta_clicked = models.BooleanField(
        default=False,
        help_text="Whether user clicked the CTA in celebration UI"
    )
    
    # Additional metadata
    event_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context data about the aha moment"
    )
    device_type = models.CharField(
        max_length=20,
        choices=[
            ('desktop', 'Desktop'),
            ('mobile', 'Mobile'),
            ('tablet', 'Tablet'),
            ('unknown', 'Unknown'),
        ],
        default='unknown'
    )
    user_agent = models.TextField(blank=True)
    
    # Google Analytics sync
    ga_event_sent = models.BooleanField(
        default=False,
        help_text="Whether event was synced to Google Analytics"
    )
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['session_id', 'moment_type']),
            models.Index(fields=['moment_type', 'timestamp']),
            models.Index(fields=['demo_session', 'moment_type']),
            models.Index(fields=['led_to_conversion']),
            models.Index(fields=['user', 'timestamp']),
        ]
        verbose_name = 'Aha Moment Event'
        verbose_name_plural = 'Aha Moment Events'
    
    def __str__(self):
        user_str = self.user.username if self.user else f"Session {self.session_id[:8]}"
        return f"{user_str} - {self.get_moment_type_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    @classmethod
    def track_aha_moment(cls, session_id, moment_type, page_path, **kwargs):
        """
        Convenience method to track an aha moment with proper context.
        """
        from django.utils import timezone
        
        # Get demo session if exists
        demo_session = None
        user_session = None
        user = None
        
        try:
            demo_session = DemoSession.objects.get(session_id=session_id)
            if demo_session.user:
                user = demo_session.user
        except DemoSession.DoesNotExist:
            pass
        
        try:
            user_session = UserSession.objects.filter(session_key=session_id).first()
            if user_session and user_session.user:
                user = user_session.user
        except Exception:
            pass
        
        # Calculate time since session start
        time_since_start = None
        if demo_session:
            time_since_start = int((timezone.now() - demo_session.created_at).total_seconds())
        elif user_session:
            time_since_start = int((timezone.now() - user_session.session_start).total_seconds())
        
        # Count previous aha moments in this session
        previous_count = cls.objects.filter(session_id=session_id).count()
        
        # Create the aha moment event
        event = cls.objects.create(
            session_id=session_id,
            demo_session=demo_session,
            user_session=user_session,
            user=user,
            moment_type=moment_type,
            page_path=page_path,
            time_since_session_start=time_since_start,
            previous_aha_moments=previous_count,
            **kwargs
        )
        
        # Update demo session aha counter if applicable
        if demo_session:
            demo_session.aha_moments += 1
            if moment_type not in demo_session.aha_moments_list:
                demo_session.aha_moments_list.append(moment_type)
            demo_session.save(update_fields=['aha_moments', 'aha_moments_list'])
        
        return event
    
    @classmethod
    def get_aha_moment_stats(cls, days=30):
        """
        Get aggregated statistics about aha moments.
        """
        from datetime import timedelta
        
        cutoff = timezone.now() - timedelta(days=days)
        
        stats = {
            'total_aha_moments': cls.objects.filter(timestamp__gte=cutoff).count(),
            'unique_sessions': cls.objects.filter(timestamp__gte=cutoff).values('session_id').distinct().count(),
            'conversion_rate': 0,
            'by_type': {},
            'avg_time_to_aha': 0,
        }
        
        # Stats by type
        by_type = cls.objects.filter(timestamp__gte=cutoff).values('moment_type').annotate(
            count=Count('id'),
            conversions=Count('id', filter=Q(led_to_conversion=True)),
            avg_time=Avg('time_since_session_start')
        ).order_by('-count')
        
        for item in by_type:
            stats['by_type'][item['moment_type']] = {
                'count': item['count'],
                'conversions': item['conversions'],
                'avg_time_seconds': item['avg_time'] or 0
            }
        
        # Overall conversion rate from aha moments
        total_with_conversion = cls.objects.filter(
            timestamp__gte=cutoff,
            led_to_conversion=True
        ).values('session_id').distinct().count()
        
        if stats['unique_sessions'] > 0:
            stats['conversion_rate'] = round((total_with_conversion / stats['unique_sessions']) * 100, 2)
        
        # Average time to first aha
        avg_time = cls.objects.filter(
            timestamp__gte=cutoff,
            time_since_session_start__isnull=False,
            previous_aha_moments=0  # First aha in session
        ).aggregate(avg=Avg('time_since_session_start'))['avg']
        
        stats['avg_time_to_aha'] = round(avg_time or 0, 0)
        
        return stats


class DemoConversion(models.Model):
    """
    Detailed tracking of demo-to-signup conversions.
    Used for conversion optimization and attribution analysis.
    """
    # Session reference
    session_id = models.CharField(max_length=255, unique=True, db_index=True)
    demo_session = models.OneToOneField(
        DemoSession,
        on_delete=models.CASCADE,
        related_name='conversion_details'
    )
    
    # User who converted
    converted_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='demo_conversion'
    )
    
    # Conversion metrics
    time_in_demo_seconds = models.IntegerField(help_text="Total time spent in demo before signup")
    features_explored = models.IntegerField(default=0)
    features_list = models.JSONField(default=list, blank=True)
    aha_moments = models.IntegerField(default=0)
    aha_moments_list = models.JSONField(default=list, blank=True)
    
    # Attribution
    last_nudge_seen = models.CharField(max_length=50, blank=True)
    nudge_clicks = models.IntegerField(default=0)
    conversion_source = models.CharField(
        max_length=50,
        choices=[
            ('demo', 'Demo CTA'),
            ('nudge_soft', 'Soft Nudge'),
            ('nudge_medium', 'Medium Nudge'),
            ('nudge_peak', 'Peak Moment Nudge'),
            ('nudge_exit', 'Exit Intent Nudge'),
            ('banner', 'Demo Banner'),
            ('direct', 'Direct Signup'),
        ],
        default='demo'
    )
    
    # Demo activity
    reset_count = models.IntegerField(default=0)
    role_switches = models.IntegerField(default=0)
    demo_mode = models.CharField(max_length=20)
    
    # Timing
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Device
    device_type = models.CharField(max_length=20)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['converted_user']),
            models.Index(fields=['conversion_source']),
            models.Index(fields=['timestamp']),
        ]
        verbose_name = 'Demo Conversion'
        verbose_name_plural = 'Demo Conversions'
    
    def __str__(self):
        return f"Conversion: {self.converted_user.username} - {self.timestamp.strftime('%Y-%m-%d')}"

class DemoAbusePrevention(models.Model):
    """
    Track demo usage across sessions to prevent abuse.
    
    Users can bypass session-based limits by:
    - Clearing cookies (new session)
    - Using incognito mode
    - Creating new accounts
    
    This model tracks usage by IP address and browser fingerprint
    to enforce limits across sessions and accounts.
    """
    # Identification (at least one required)
    ip_address = models.GenericIPAddressField(db_index=True)
    browser_fingerprint = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="SHA256 hash of browser attributes"
    )
    client_fingerprint = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        db_index=True,
        help_text="Client-side JS fingerprint (canvas, webgl, audio)"
    )
    is_vpn_user = models.BooleanField(
        default=False,
        help_text="Whether this visitor uses VPN/proxy"
    )
    ai_generation_timestamps = models.JSONField(
        default=list,
        blank=True,
        help_text="Timestamps of recent AI generations for rate limiting"
    )
    
    # Aggregated limits across ALL sessions from this IP/fingerprint
    total_ai_generations = models.IntegerField(
        default=0,
        help_text="Total AI generations across all demo sessions"
    )
    total_projects_created = models.IntegerField(
        default=0,
        help_text="Total projects created across all demo sessions"
    )
    total_export_attempts = models.IntegerField(
        default=0,
        help_text="Total export attempts across all demo sessions"
    )
    total_sessions_created = models.IntegerField(
        default=1,
        help_text="Number of demo sessions created from this IP"
    )
    
    # Abuse detection flags
    is_flagged = models.BooleanField(
        default=False,
        help_text="Flagged for suspicious activity"
    )
    flag_reason = models.TextField(
        blank=True,
        help_text="Reason for flagging"
    )
    is_blocked = models.BooleanField(
        default=False,
        help_text="Blocked from demo access"
    )
    
    # Time tracking
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    last_session_created = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the last demo session was started"
    )
    
    # Rate limiting
    sessions_last_hour = models.IntegerField(
        default=0,
        help_text="Sessions created in the last hour (for rate limiting)"
    )
    sessions_last_24h = models.IntegerField(
        default=0,
        help_text="Sessions created in the last 24 hours"
    )
    last_rate_limit_reset = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When rate limit counters were last reset"
    )
    
    # Associated sessions for reference
    session_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of all session IDs from this IP/fingerprint"
    )
    
    class Meta:
        verbose_name = 'Demo Abuse Prevention'
        verbose_name_plural = 'Demo Abuse Prevention Records'
        indexes = [
            models.Index(fields=['ip_address', 'browser_fingerprint']),
            models.Index(fields=['is_flagged']),
            models.Index(fields=['is_blocked']),
            models.Index(fields=['last_seen']),
        ]
        # Allow same IP with different fingerprints (shared networks)
        unique_together = [['ip_address', 'browser_fingerprint']]
    
    def __str__(self):
        return f"Abuse Prevention: {self.ip_address} (AI: {self.total_ai_generations}, Sessions: {self.total_sessions_created})"
    
    def check_rate_limit(self):
        """Check if this IP/fingerprint is creating sessions too fast"""
        from datetime import timedelta
        
        # Reset hourly counter if needed
        if self.last_rate_limit_reset:
            if timezone.now() - self.last_rate_limit_reset > timedelta(hours=1):
                self.sessions_last_hour = 0
                self.last_rate_limit_reset = timezone.now()
        else:
            self.last_rate_limit_reset = timezone.now()
        
        # Rate limits (increased for development)
        MAX_SESSIONS_PER_HOUR = 50
        MAX_SESSIONS_PER_24H = 100
        
        if self.sessions_last_hour >= MAX_SESSIONS_PER_HOUR:
            return False, "Too many demo sessions. Please try again later."
        if self.sessions_last_24h >= MAX_SESSIONS_PER_24H:
            return False, "Daily demo session limit reached. Please create an account for unlimited access."
        
        return True, None
    
    def check_ai_limit(self):
        """Check if this IP/fingerprint has exceeded global AI limits"""
        # Global limit across ALL sessions (prevents account cycling)
        # Use centralized limit from demo_abuse_prevention
        from kanban.utils.demo_abuse_prevention import GLOBAL_DEMO_LIMITS
        GLOBAL_AI_LIMIT = GLOBAL_DEMO_LIMITS.get('max_ai_generations_global', 30)
        
        if self.total_ai_generations >= GLOBAL_AI_LIMIT:
            return False, f"You've used {self.total_ai_generations} AI generations across demo sessions. Create a free account for unlimited AI."
        
        return True, None
    
    def increment_session_count(self):
        """Call when a new demo session is created"""
        from datetime import timedelta
        
        self.total_sessions_created += 1
        self.sessions_last_hour += 1
        self.sessions_last_24h += 1
        self.last_session_created = timezone.now()
        
        # Flag suspicious behavior
        if self.total_sessions_created > 10:
            self.is_flagged = True
            self.flag_reason = f"Created {self.total_sessions_created} demo sessions (possible abuse)"
        
        self.save()
    
    def increment_ai_count(self, count=1):
        """Call when AI is used in any demo session"""
        self.total_ai_generations += count
        self.save(update_fields=['total_ai_generations', 'last_seen'])
    
    def increment_project_count(self, count=1):
        """Call when a project is created in any demo session"""
        self.total_projects_created += count
        self.save(update_fields=['total_projects_created', 'last_seen'])