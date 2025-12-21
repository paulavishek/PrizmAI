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
