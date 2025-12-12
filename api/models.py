"""
API Models for External Integration
"""
import secrets
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class APIToken(models.Model):
    """
    API Token for external application authentication
    Allows third-party apps to access PrizmAI APIs programmatically
    """
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='api_tokens',
        help_text="User who owns this API token"
    )
    token = models.CharField(
        max_length=64, 
        unique=True, 
        db_index=True,
        help_text="Unique API token string"
    )
    name = models.CharField(
        max_length=100,
        help_text="Friendly name for this token (e.g., 'Slack Integration', 'Mobile App')"
    )
    scopes = models.JSONField(
        default=list,
        help_text="API scopes/permissions (e.g., ['boards.read', 'tasks.write', 'tasks.read'])"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this token is currently active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Last time this token was used"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this token expires (null = never expires)"
    )
    
    # Rate limiting
    rate_limit_per_hour = models.IntegerField(
        default=1000,
        help_text="Maximum API requests allowed per hour"
    )
    request_count_current_hour = models.IntegerField(
        default=0,
        help_text="Number of requests made in current hour"
    )
    rate_limit_reset_at = models.DateTimeField(
        default=timezone.now,
        help_text="When the rate limit counter resets"
    )
    
    # Metadata
    user_agent = models.CharField(
        max_length=255, 
        blank=True,
        help_text="User agent of application using this token"
    )
    ip_whitelist = models.JSONField(
        default=list,
        blank=True,
        help_text="List of allowed IP addresses (empty = allow all)"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "API Token"
        verbose_name_plural = "API Tokens"
    
    def __str__(self):
        return f"{self.name} ({self.user.username})"
    
    @classmethod
    def generate_token(cls):
        """Generate a secure random token"""
        return secrets.token_urlsafe(48)
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = self.generate_token()
        super().save(*args, **kwargs)
    
    def is_expired(self):
        """Check if token is expired"""
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at
    
    def is_valid(self):
        """Check if token is valid (active and not expired)"""
        return self.is_active and not self.is_expired()
    
    def has_scope(self, scope):
        """Check if token has a specific scope"""
        return scope in self.scopes or '*' in self.scopes
    
    def check_rate_limit(self):
        """Check if token has exceeded rate limit"""
        now = timezone.now()
        
        # Reset counter if hour has passed
        if now > self.rate_limit_reset_at:
            self.request_count_current_hour = 0
            self.rate_limit_reset_at = now + timezone.timedelta(hours=1)
            self.save(update_fields=['request_count_current_hour', 'rate_limit_reset_at'])
        
        return self.request_count_current_hour < self.rate_limit_per_hour
    
    def increment_request_count(self):
        """Increment request count and update last_used"""
        self.request_count_current_hour += 1
        self.last_used = timezone.now()
        self.save(update_fields=['request_count_current_hour', 'last_used'])


class APIRequestLog(models.Model):
    """
    Log of API requests for analytics and debugging
    """
    token = models.ForeignKey(
        APIToken,
        on_delete=models.CASCADE,
        related_name='request_logs',
        null=True,
        blank=True
    )
    endpoint = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    status_code = models.IntegerField()
    response_time_ms = models.IntegerField(help_text="Response time in milliseconds")
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "API Request Log"
        verbose_name_plural = "API Request Logs"
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['token', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.method} {self.endpoint} - {self.status_code}"
