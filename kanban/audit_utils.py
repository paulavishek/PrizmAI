"""
Audit Logging Utilities and Helpers
Convenience functions for creating audit log entries
"""
from django.contrib.auth.models import User
from kanban.audit_models import SystemAuditLog, SecurityEvent, DataAccessLog


def get_client_ip(request):
    """Extract client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_request_context(request):
    """Extract common request context for audit logging"""
    return {
        'ip_address': get_client_ip(request),
        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:255],
        'session_key': request.session.session_key if hasattr(request, 'session') else '',
        'request_method': request.method,
        'request_path': request.path,
    }


def log_audit(action_type, user=None, request=None, **kwargs):
    """
    Simplified audit logging function
    
    Args:
        action_type: Action type from SystemAuditLog.ACTION_TYPES
        user: User performing the action
        request: Django request object (optional, will extract context)
        **kwargs: Additional fields for SystemAuditLog
    
    Usage:
        log_audit('task.created', user=request.user, request=request,
                  object_type='task', object_id=task.id, object_repr=task.title)
    """
    context = get_request_context(request) if request else {}
    
    return SystemAuditLog.log(
        action_type=action_type,
        user=user,
        **context,
        **kwargs
    )


def log_model_change(action_type, instance, user, request=None, changes=None):
    """
    Log a model change with automatic object detection
    
    Args:
        action_type: Action type (e.g., 'task.updated')
        instance: Model instance being changed
        user: User making the change
        request: Django request (optional)
        changes: Dict of changes (optional)
    """
    from django.contrib.contenttypes.models import ContentType
    
    content_type = ContentType.objects.get_for_model(instance)
    object_type = content_type.model
    
    context = get_request_context(request) if request else {}
    
    # Try to get organization and board context
    organization_id = None
    board_id = None
    
    if hasattr(instance, 'organization_id'):
        organization_id = instance.organization_id
    elif hasattr(instance, 'organization'):
        organization_id = instance.organization.id if instance.organization else None
    
    if hasattr(instance, 'board_id'):
        board_id = instance.board_id
    elif hasattr(instance, 'board'):
        board_id = instance.board.id if instance.board else None
    elif hasattr(instance, 'column') and hasattr(instance.column, 'board'):
        board_id = instance.column.board.id
    
    return SystemAuditLog.log(
        action_type=action_type,
        user=user,
        content_object=instance,
        object_type=object_type,
        object_id=instance.pk,
        object_repr=str(instance),
        changes=changes or {},
        organization_id=organization_id,
        board_id=board_id,
        **context
    )


def log_authentication_event(action_type, user=None, request=None, success=True, reason=''):
    """
    Log authentication-related events
    
    Args:
        action_type: 'user.login', 'user.logout', or 'user.login_failed'
        user: User object (can be None for failed attempts)
        request: Django request
        success: Whether authentication succeeded
        reason: Failure reason if applicable
    """
    context = get_request_context(request) if request else {}
    
    severity = 'low' if success else 'high'
    
    log = SystemAuditLog.log(
        action_type=action_type,
        user=user,
        severity=severity,
        object_type='authentication',
        object_id=user.id if user else 0,
        object_repr=user.username if user else 'Unknown',
        message=reason,
        **context
    )
    
    # Check for suspicious patterns (multiple failures)
    if not success:
        check_for_brute_force(context.get('ip_address'), user)
    
    return log


def log_access_denied(user, request, resource_type, resource_id, permission_required):
    """
    Log when access is denied due to insufficient permissions
    
    Args:
        user: User who was denied access
        request: Django request
        resource_type: Type of resource (board, task, etc.)
        resource_id: ID of the resource
        permission_required: Permission that was missing
    """
    context = get_request_context(request)
    
    log = SystemAuditLog.log(
        action_type='access.denied',
        user=user,
        severity='medium',
        object_type=resource_type,
        object_id=resource_id,
        message=f'Access denied - required permission: {permission_required}',
        additional_data={'permission_required': permission_required},
        **context
    )
    
    # Check for permission escalation attempts
    check_for_escalation_attempt(user, context.get('ip_address'))
    
    return log


def log_data_export(user, request, export_type, record_count, board_id=None):
    """
    Log data export operations
    
    Args:
        user: User performing export
        request: Django request
        export_type: Type of export (csv, json, etc.)
        record_count: Number of records exported
        board_id: Board ID if applicable
    """
    context = get_request_context(request)
    
    return SystemAuditLog.log(
        action_type='data.exported',
        user=user,
        severity='medium',
        object_type='export',
        board_id=board_id,
        message=f'Exported {record_count} records as {export_type}',
        additional_data={
            'export_type': export_type,
            'record_count': record_count
        },
        **context
    )


def log_security_event(event_type, description, user=None, ip_address=None, 
                       user_agent='', risk_score=50, audit_logs=None):
    """
    Create a high-priority security event
    
    Args:
        event_type: Type of security event
        description: Description of the event
        user: User involved (if known)
        ip_address: IP address
        user_agent: User agent string
        risk_score: Risk score 0-100
        audit_logs: Related audit log entries
    """
    event = SecurityEvent.objects.create(
        event_type=event_type,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        description=description,
        risk_score=risk_score
    )
    
    if audit_logs:
        event.audit_logs.set(audit_logs)
    
    # TODO: Send notification to admins if risk_score > 70
    if risk_score > 70:
        # notify_security_admins(event)
        pass
    
    return event


def check_for_brute_force(ip_address, user=None):
    """
    Check for possible brute force attacks
    Looks for multiple failed login attempts from same IP
    """
    from django.utils import timezone
    from datetime import timedelta
    
    # Count failed attempts in last 15 minutes
    since = timezone.now() - timedelta(minutes=15)
    
    failed_attempts = SystemAuditLog.objects.filter(
        action_type='user.login_failed',
        ip_address=ip_address,
        timestamp__gte=since
    ).count()
    
    if failed_attempts >= 5:
        # Possible brute force attack
        recent_logs = list(SystemAuditLog.objects.filter(
            action_type='user.login_failed',
            ip_address=ip_address,
            timestamp__gte=since
        )[:10])
        
        log_security_event(
            event_type='brute_force',
            description=f'Possible brute force attack detected from IP {ip_address}. {failed_attempts} failed login attempts in 15 minutes.',
            user=user,
            ip_address=ip_address,
            risk_score=80,
            audit_logs=recent_logs
        )


def check_for_escalation_attempt(user, ip_address):
    """
    Check for permission escalation attempts
    Looks for multiple access denied events
    """
    from django.utils import timezone
    from datetime import timedelta
    
    # Count access denied in last hour
    since = timezone.now() - timedelta(hours=1)
    
    denied_count = SystemAuditLog.objects.filter(
        action_type='access.denied',
        user=user,
        timestamp__gte=since
    ).count()
    
    if denied_count >= 10:
        # Possible escalation attempt
        recent_logs = list(SystemAuditLog.objects.filter(
            action_type='access.denied',
            user=user,
            timestamp__gte=since
        )[:15])
        
        log_security_event(
            event_type='permission_escalation',
            description=f'Possible permission escalation attempt by user {user.username}. {denied_count} access denied events in 1 hour.',
            user=user,
            ip_address=ip_address,
            risk_score=70,
            audit_logs=recent_logs
        )


def log_sensitive_data_access(user, data_type, record_id, access_type, request=None, purpose=''):
    """
    Log access to sensitive data for compliance
    
    Args:
        user: User accessing the data
        data_type: Type of data (task, user_profile, etc.)
        record_id: ID of the record
        access_type: read, create, update, delete, export
        request: Django request (optional)
        purpose: Business reason for access
    """
    context = get_request_context(request) if request else {}
    
    organization_id = None
    if hasattr(user, 'profile') and user.profile:
        organization_id = user.profile.organization_id
    
    return DataAccessLog.objects.create(
        user=user,
        user_email=user.email,
        data_type=data_type,
        record_id=record_id,
        access_type=access_type,
        ip_address=context.get('ip_address'),
        purpose=purpose,
        organization_id=organization_id
    )


# Context manager for tracking changes
class AuditLogContext:
    """
    Context manager for tracking model changes
    
    Usage:
        with AuditLogContext(task, user, request) as ctx:
            task.title = "New Title"
            task.priority = "high"
            task.save()
        # Automatically logs changes
    """
    def __init__(self, instance, user, request=None, action_type=None):
        self.instance = instance
        self.user = user
        self.request = request
        self.action_type = action_type
        self.original_values = {}
        self.changes = {}
    
    def __enter__(self):
        # Capture original values
        if self.instance.pk:
            model_class = type(self.instance)
            try:
                original = model_class.objects.get(pk=self.instance.pk)
                for field in self.instance._meta.fields:
                    if not field.primary_key:
                        self.original_values[field.name] = getattr(original, field.name)
            except model_class.DoesNotExist:
                pass
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Log changes if no exception
        if exc_type is None and self.original_values:
            # Compare with current values
            for field_name, old_value in self.original_values.items():
                new_value = getattr(self.instance, field_name)
                if old_value != new_value:
                    self.changes[field_name] = {
                        'old': str(old_value),
                        'new': str(new_value)
                    }
            
            # Log if there were changes
            if self.changes:
                action_type = self.action_type or f'{self.instance._meta.model_name}.updated'
                log_model_change(
                    action_type=action_type,
                    instance=self.instance,
                    user=self.user,
                    request=self.request,
                    changes=self.changes
                )
