"""
Comprehensive Audit Logging Models for PrizmAI
Tracks all system operations for security, compliance, and forensics
"""
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class SystemAuditLog(models.Model):
    """
    Comprehensive audit log for all system operations
    Immutable record of who did what, when, and what changed
    """
    
    # Action Categories and Types
    ACTION_TYPES = [
        # Authentication & Session
        ('user.login', 'User Login'),
        ('user.logout', 'User Logout'),
        ('user.login_failed', 'Login Failed'),
        ('user.password_changed', 'Password Changed'),
        ('user.session_expired', 'Session Expired'),
        
        # User Management
        ('user.created', 'User Created'),
        ('user.updated', 'User Updated'),
        ('user.deleted', 'User Deleted'),
        ('user.profile_updated', 'Profile Updated'),
        
        # Organization
        ('organization.created', 'Organization Created'),
        ('organization.updated', 'Organization Updated'),
        ('organization.member_added', 'Member Added to Organization'),
        ('organization.member_removed', 'Member Removed from Organization'),
        
        # Board Operations
        ('board.created', 'Board Created'),
        ('board.updated', 'Board Updated'),
        ('board.deleted', 'Board Deleted'),
        ('board.member_added', 'Board Member Added'),
        ('board.member_removed', 'Board Member Removed'),
        ('board.viewed', 'Board Viewed'),
        
        # Column Operations
        ('column.created', 'Column Created'),
        ('column.updated', 'Column Updated'),
        ('column.deleted', 'Column Deleted'),
        ('column.reordered', 'Column Reordered'),
        
        # Task Operations
        ('task.created', 'Task Created'),
        ('task.updated', 'Task Updated'),
        ('task.deleted', 'Task Deleted'),
        ('task.field_changed', 'Task Field Changed'),
        ('task.assigned', 'Task Assigned'),
        ('task.moved', 'Task Moved Between Columns'),
        ('task.viewed', 'Task Viewed'),
        
        # Comment Operations
        ('comment.created', 'Comment Created'),
        ('comment.updated', 'Comment Updated'),
        ('comment.deleted', 'Comment Deleted'),
        
        # Label Operations
        ('label.created', 'Label Created'),
        ('label.updated', 'Label Updated'),
        ('label.deleted', 'Label Deleted'),
        ('label.added_to_task', 'Label Added to Task'),
        ('label.removed_from_task', 'Label Removed from Task'),
        
        # File Operations
        ('file.uploaded', 'File Uploaded'),
        ('file.downloaded', 'File Downloaded'),
        ('file.deleted', 'File Deleted'),
        
        # Permission & Security
        ('permission.granted', 'Permission Granted'),
        ('permission.revoked', 'Permission Revoked'),
        ('role.assigned', 'Role Assigned'),
        ('role.removed', 'Role Removed'),
        ('access.denied', 'Access Denied'),
        
        # API & Integration
        ('token.created', 'API Token Created'),
        ('token.revoked', 'API Token Revoked'),
        ('token.used', 'API Token Used'),
        ('webhook.created', 'Webhook Created'),
        ('webhook.updated', 'Webhook Updated'),
        ('webhook.deleted', 'Webhook Deleted'),
        ('webhook.triggered', 'Webhook Triggered'),
        
        # Data Operations
        ('data.exported', 'Data Exported'),
        ('data.imported', 'Data Imported'),
        ('data.bulk_operation', 'Bulk Operation Performed'),
        
        # System Events
        ('system.error', 'System Error'),
        ('system.warning', 'System Warning'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    # Core Fields
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True, editable=False)
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES, db_index=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='medium', db_index=True)
    
    # User Information
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='audit_logs',
        help_text="User who performed the action"
    )
    user_email = models.EmailField(blank=True, help_text="Email at time of action (preserved even if user deleted)")
    user_username = models.CharField(max_length=150, blank=True, help_text="Username at time of action")
    
    # Object Tracking (using GenericForeignKey for flexibility)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Backup object representation (in case object is deleted)
    object_type = models.CharField(max_length=50, help_text="Type of object (board, task, user, etc.)")
    object_id_backup = models.IntegerField(help_text="ID of the affected object")
    object_repr = models.CharField(max_length=255, help_text="Human-readable representation")
    
    # Change Tracking (JSON format for flexibility)
    changes = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Dictionary of field changes: {'field_name': {'old': 'value', 'new': 'value'}}"
    )
    
    # Request Context
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="Client IP address")
    user_agent = models.CharField(max_length=255, blank=True, help_text="Browser/client user agent")
    session_key = models.CharField(max_length=40, blank=True, help_text="Session identifier")
    request_method = models.CharField(max_length=10, blank=True, help_text="HTTP method (GET, POST, etc.)")
    request_path = models.CharField(max_length=500, blank=True, help_text="Request URL path")
    
    # Additional Context
    additional_data = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Any additional context data specific to the action"
    )
    
    # Message & Description
    message = models.TextField(blank=True, help_text="Human-readable description of the action")
    
    # Organization Context (for filtering)
    organization_id = models.IntegerField(null=True, blank=True, db_index=True, help_text="Organization ID (denormalized for performance)")
    board_id = models.IntegerField(null=True, blank=True, db_index=True, help_text="Board ID (denormalized for performance)")
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action_type', '-timestamp']),
            models.Index(fields=['object_type', 'object_id_backup']),
            models.Index(fields=['organization_id', '-timestamp']),
            models.Index(fields=['board_id', '-timestamp']),
            models.Index(fields=['severity', '-timestamp']),
        ]
        # Permissions
        permissions = [
            ('view_audit_log', 'Can view audit logs'),
            ('export_audit_log', 'Can export audit logs'),
        ]
    
    def __str__(self):
        user_str = self.user_username or 'System'
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {user_str} - {self.get_action_type_display()}"
    
    def save(self, *args, **kwargs):
        # Populate backup fields from user if available
        if self.user and not self.user_email:
            self.user_email = self.user.email
            self.user_username = self.user.username
        
        # Make this record immutable after creation
        if self.pk is not None:
            raise ValueError("Audit logs are immutable and cannot be modified after creation")
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """Prevent deletion of audit logs"""
        raise ValueError("Audit logs cannot be deleted")
    
    @classmethod
    def log(cls, action_type, user=None, object_type=None, object_id=None, object_repr=None,
            changes=None, message=None, ip_address=None, user_agent=None, session_key=None,
            request_method=None, request_path=None, additional_data=None, severity='medium',
            organization_id=None, board_id=None, content_object=None):
        """
        Convenience method to create audit log entries
        
        Usage:
            SystemAuditLog.log(
                action_type='task.created',
                user=request.user,
                object_type='task',
                object_id=task.id,
                object_repr=task.title,
                message=f'Created task: {task.title}',
                ip_address=request.META.get('REMOTE_ADDR'),
                board_id=task.column.board.id
            )
        """
        return cls.objects.create(
            action_type=action_type,
            severity=severity,
            user=user,
            content_object=content_object,
            object_type=object_type or '',
            object_id_backup=object_id or 0,
            object_repr=object_repr or '',
            changes=changes or {},
            message=message or '',
            ip_address=ip_address,
            user_agent=user_agent or '',
            session_key=session_key or '',
            request_method=request_method or '',
            request_path=request_path or '',
            additional_data=additional_data or {},
            organization_id=organization_id,
            board_id=board_id
        )


class SecurityEvent(models.Model):
    """
    High-priority security events requiring attention
    Subset of audit logs focused on security incidents
    """
    
    EVENT_TYPES = [
        ('suspicious_login', 'Suspicious Login Attempt'),
        ('brute_force', 'Possible Brute Force Attack'),
        ('unauthorized_access', 'Unauthorized Access Attempt'),
        ('permission_escalation', 'Permission Escalation Attempt'),
        ('unusual_api_usage', 'Unusual API Usage Pattern'),
        ('data_exfiltration', 'Possible Data Exfiltration'),
        ('token_compromised', 'Possibly Compromised Token'),
        ('multiple_failures', 'Multiple Failed Attempts'),
    ]
    
    STATUS_CHOICES = [
        ('new', 'New'),
        ('investigating', 'Under Investigation'),
        ('resolved', 'Resolved'),
        ('false_positive', 'False Positive'),
    ]
    
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', db_index=True)
    
    # Related User/IP
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=255, blank=True)
    
    # Event Details
    description = models.TextField()
    risk_score = models.IntegerField(default=50, help_text="Risk score 0-100")
    
    # Related Audit Logs
    audit_logs = models.ManyToManyField(SystemAuditLog, related_name='security_events', blank=True)
    
    # Investigation
    investigated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='investigated_security_events'
    )
    investigated_at = models.DateTimeField(null=True, blank=True)
    investigation_notes = models.TextField(blank=True)
    
    # Actions Taken
    actions_taken = models.JSONField(default=list, blank=True)
    
    # Notification
    notification_sent = models.BooleanField(default=False)
    notification_sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['status', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['ip_address', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {self.get_event_type_display()} - {self.ip_address}"


class DataAccessLog(models.Model):
    """
    Track access to sensitive data for compliance (HIPAA, GDPR, etc.)
    Separate from general audit logs for performance and retention
    """
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # Data Access Details
    data_type = models.CharField(
        max_length=50, 
        db_index=True,
        help_text="Type of sensitive data accessed (task, user_profile, etc.)"
    )
    record_id = models.IntegerField(help_text="ID of accessed record")
    access_type = models.CharField(
        max_length=20, 
        choices=[
            ('read', 'Read'),
            ('create', 'Create'),
            ('update', 'Update'),
            ('delete', 'Delete'),
            ('export', 'Export'),
        ]
    )
    
    # Context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    purpose = models.TextField(blank=True, help_text="Business reason for access (if required)")
    
    # Denormalized for retention
    user_email = models.EmailField(blank=True)
    organization_id = models.IntegerField(null=True, db_index=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['data_type', 'record_id']),
            models.Index(fields=['organization_id', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user_email} - {self.access_type} - {self.data_type}:{self.record_id}"
