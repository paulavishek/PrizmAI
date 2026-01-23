"""
AI Usage Tracking Models

Tracks AI feature consumption per user for quota management.
This is different from API rate limiting - it tracks internal AI usage
(AI Coach, AI Assistant, etc.) to manage costs and enforce usage limits.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal


class AIUsageQuota(models.Model):
    """
    Track AI feature usage per user with monthly quotas.
    Resets every 30 days.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='ai_usage_quota',
        help_text="User whose AI usage is being tracked"
    )
    
    # Usage tracking
    requests_used = models.IntegerField(
        default=0,
        help_text="Number of AI requests made in current period"
    )
    monthly_quota = models.IntegerField(
        default=50,
        help_text="Maximum AI requests allowed per month (50 for free users)"
    )
    
    # Daily limit tracking (cost control)
    daily_requests_used = models.IntegerField(
        default=0,
        help_text="Number of AI requests made today"
    )
    daily_limit = models.IntegerField(
        default=10,
        help_text="Maximum AI requests allowed per day (10 for free users)"
    )
    last_daily_reset = models.DateField(
        null=True,
        blank=True,
        help_text="Date of last daily counter reset"
    )
    
    # Period tracking
    period_start = models.DateTimeField(
        default=timezone.now,
        help_text="When the current usage period started"
    )
    period_end = models.DateTimeField(
        help_text="When the current usage period ends"
    )
    
    # Metadata
    last_request_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time user made an AI request"
    )
    total_requests_all_time = models.IntegerField(
        default=0,
        help_text="Total AI requests made since account creation"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "AI Usage Quota"
        verbose_name_plural = "AI Usage Quotas"
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.requests_used}/{self.monthly_quota}"
    
    def save(self, *args, **kwargs):
        # Set period_end if not set (30 days from start)
        if not self.period_end:
            self.period_end = self.period_start + timedelta(days=30)
        super().save(*args, **kwargs)
    
    def check_and_reset_if_needed(self):
        """Check if period has ended and reset if needed"""
        now = timezone.now()
        today = now.date()
        fields_to_update = []
        
        # Check monthly reset
        if now >= self.period_end:
            # Reset for new period
            self.requests_used = 0
            self.period_start = now
            self.period_end = now + timedelta(days=30)
            fields_to_update.extend(['requests_used', 'period_start', 'period_end'])
        
        # Check daily reset
        if self.last_daily_reset is None or self.last_daily_reset < today:
            self.daily_requests_used = 0
            self.last_daily_reset = today
            fields_to_update.extend(['daily_requests_used', 'last_daily_reset'])
        
        if fields_to_update:
            fields_to_update.append('updated_at')
            self.save(update_fields=fields_to_update)
            return True
        return False
    
    def has_quota_remaining(self):
        """Check if user has remaining quota (both monthly and daily)"""
        self.check_and_reset_if_needed()
        return self.requests_used < self.monthly_quota and self.daily_requests_used < self.daily_limit
    
    def has_daily_quota_remaining(self):
        """Check if user has remaining daily quota"""
        self.check_and_reset_if_needed()
        return self.daily_requests_used < self.daily_limit
    
    def get_remaining_daily_requests(self):
        """Get number of remaining requests for today"""
        self.check_and_reset_if_needed()
        return max(0, self.daily_limit - self.daily_requests_used)
    
    def get_remaining_requests(self):
        """Get number of remaining requests"""
        self.check_and_reset_if_needed()
        return max(0, self.monthly_quota - self.requests_used)
    
    def get_usage_percent(self):
        """Get usage percentage"""
        if self.monthly_quota == 0:
            return 100.0
        return round((self.requests_used / self.monthly_quota) * 100, 1)
    
    def get_days_until_reset(self):
        """Get days remaining until quota resets"""
        now = timezone.now()
        if now >= self.period_end:
            return 0
        delta = self.period_end - now
        return delta.days
    
    def increment_usage(self):
        """Increment usage counter (both monthly and daily)"""
        self.check_and_reset_if_needed()
        self.requests_used += 1
        self.daily_requests_used += 1
        self.total_requests_all_time += 1
        self.last_request_at = timezone.now()
        self.save(update_fields=['requests_used', 'daily_requests_used', 'total_requests_all_time', 'last_request_at', 'updated_at'])


class AIRequestLog(models.Model):
    """
    Detailed log of AI requests for analytics and debugging
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='ai_request_logs',
        help_text="User who made the AI request"
    )
    
    # Request details
    feature = models.CharField(
        max_length=50,
        help_text="Which AI feature was used (ai_coach, ai_assistant, etc.)",
        db_index=True
    )
    request_type = models.CharField(
        max_length=50,
        help_text="Type of request (question, suggestion, analysis, etc.)",
        blank=True
    )
    
    # Model info
    ai_model = models.CharField(
        max_length=50,
        default="gemini",
        help_text="AI model used (gemini, gpt, etc.)"
    )
    tokens_used = models.IntegerField(
        default=0,
        help_text="Approximate tokens used (if available)"
    )
    
    # Response info
    success = models.BooleanField(
        default=True,
        help_text="Whether the request was successful"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error message if request failed"
    )
    response_time_ms = models.IntegerField(
        default=0,
        help_text="Response time in milliseconds"
    )
    
    # Context
    board_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Board ID if request was board-specific"
    )
    
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        verbose_name = "AI Request Log"
        verbose_name_plural = "AI Request Logs"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['feature', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.feature} - {self.timestamp}"
