"""
Webhook Models for Event-Driven Integrations
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import URLValidator
from django.utils import timezone
from kanban.models import Board


class Webhook(models.Model):
    """
    Webhook subscription for board events
    Allows external services to receive real-time notifications
    """
    EVENT_CHOICES = [
        ('task.created', 'Task Created'),
        ('task.updated', 'Task Updated'),
        ('task.deleted', 'Task Deleted'),
        ('task.completed', 'Task Completed'),
        ('task.assigned', 'Task Assigned'),
        ('task.moved', 'Task Moved to Different Column'),
        ('comment.added', 'Comment Added'),
        ('board.updated', 'Board Updated'),
        ('board.member_added', 'Board Member Added'),
        ('board.member_removed', 'Board Member Removed'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('failed', 'Failed'),
        ('disabled', 'Disabled'),
    ]
    
    # Basic Info
    name = models.CharField(
        max_length=100,
        help_text="Friendly name for this webhook (e.g., 'Slack Notifications')"
    )
    url = models.URLField(
        max_length=500,
        validators=[URLValidator()],
        help_text="URL to send webhook POST requests to"
    )
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name='webhooks',
        help_text="Board to monitor for events"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_webhooks'
    )
    
    # Event Configuration
    events = models.JSONField(
        default=list,
        help_text="List of event types to trigger this webhook (e.g., ['task.created', 'task.updated'])"
    )
    
    # Status & Control
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this webhook is currently active"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_triggered = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this webhook was triggered"
    )
    
    # Delivery Settings
    timeout_seconds = models.IntegerField(
        default=10,
        help_text="HTTP request timeout in seconds"
    )
    max_retries = models.IntegerField(
        default=3,
        help_text="Maximum number of retry attempts on failure"
    )
    retry_delay_seconds = models.IntegerField(
        default=60,
        help_text="Delay between retry attempts in seconds"
    )
    
    # Statistics
    total_deliveries = models.IntegerField(
        default=0,
        help_text="Total number of delivery attempts"
    )
    successful_deliveries = models.IntegerField(
        default=0,
        help_text="Number of successful deliveries"
    )
    failed_deliveries = models.IntegerField(
        default=0,
        help_text="Number of failed deliveries"
    )
    consecutive_failures = models.IntegerField(
        default=0,
        help_text="Number of consecutive failures (resets on success)"
    )
    
    # Security
    secret = models.CharField(
        max_length=64,
        blank=True,
        help_text="Optional secret key for HMAC signature verification"
    )
    
    # Custom Headers
    custom_headers = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom HTTP headers to include in webhook requests"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['board', 'is_active']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.board.name})"
    
    def increment_delivery_stats(self, success=True):
        """Update delivery statistics"""
        self.total_deliveries += 1
        if success:
            self.successful_deliveries += 1
            self.consecutive_failures = 0
            if self.status == 'failed':
                self.status = 'active'
        else:
            self.failed_deliveries += 1
            self.consecutive_failures += 1
            # Disable webhook after 10 consecutive failures
            if self.consecutive_failures >= 10:
                self.status = 'failed'
                self.is_active = False
        
        self.last_triggered = timezone.now()
        self.save(update_fields=[
            'total_deliveries', 'successful_deliveries', 'failed_deliveries',
            'consecutive_failures', 'last_triggered', 'status', 'is_active'
        ])
    
    @property
    def success_rate(self):
        """Calculate success rate percentage"""
        if self.total_deliveries == 0:
            return 0
        return round((self.successful_deliveries / self.total_deliveries) * 100, 2)


class WebhookDelivery(models.Model):
    """
    Log of webhook delivery attempts
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('retrying', 'Retrying'),
    ]
    
    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name='deliveries'
    )
    event_type = models.CharField(max_length=50)
    payload = models.JSONField(help_text="Event data sent to webhook")
    
    # Delivery Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    
    # Response Info
    response_status_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)
    response_time_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Response time in milliseconds"
    )
    
    # Error Handling
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['webhook', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['next_retry_at']),
        ]
    
    def __str__(self):
        return f"{self.webhook.name} - {self.event_type} - {self.status}"
    
    def is_retriable(self):
        """Check if this delivery can be retried"""
        return (
            self.status in ['failed', 'retrying'] and
            self.retry_count < self.webhook.max_retries
        )


class WebhookEvent(models.Model):
    """
    Event log for all webhook-triggering events
    Used for debugging and analytics
    """
    event_type = models.CharField(max_length=50, db_index=True)
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name='webhook_events'
    )
    object_id = models.IntegerField(
        help_text="ID of the object that triggered the event (task, comment, etc.)"
    )
    data = models.JSONField(help_text="Event data snapshot")
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='triggered_webhook_events'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # How many webhooks were triggered by this event
    webhooks_triggered = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['board', '-created_at']),
            models.Index(fields=['event_type', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - Board: {self.board.name}"
