"""
Audit Logging Middleware
Automatically logs important system events
"""
import time
from django.utils import timezone
from kanban.audit_utils import log_authentication_event, log_audit, get_client_ip


class AuditLoggingMiddleware:
    """
    Middleware to automatically log authentication events and track requests
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Store request start time
        request.audit_start_time = time.time()
        
        # Get response
        response = self.get_response(request)
        
        # Log after response (so we have user info)
        self.log_request(request, response)
        
        return response
    
    def log_request(self, request, response):
        """Log request if it's a significant action"""
        
        # Skip static files and media
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            return
        
        # Skip API status checks
        if request.path == '/api/v1/status/':
            return
        
        user = request.user if request.user.is_authenticated else None
        
        # Calculate request duration
        duration_ms = int((time.time() - request.audit_start_time) * 1000)
        
        # Log slow requests (> 3 seconds)
        if duration_ms > 3000:
            from kanban.audit_models import SystemAuditLog
            SystemAuditLog.log(
                action_type='system.warning',
                user=user,
                severity='medium',
                object_type='request',
                object_repr=f'{request.method} {request.path}',
                message=f'Slow request: {duration_ms}ms',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
                request_method=request.method,
                request_path=request.path,
                additional_data={
                    'duration_ms': duration_ms,
                    'status_code': response.status_code
                }
            )
    
    def process_exception(self, request, exception):
        """Log exceptions that occur during request processing"""
        from kanban.audit_models import SystemAuditLog
        
        user = request.user if request.user.is_authenticated else None
        
        SystemAuditLog.log(
            action_type='system.error',
            user=user,
            severity='high',
            object_type='error',
            object_repr=str(exception),
            message=f'Unhandled exception: {exception.__class__.__name__}',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
            request_method=request.method,
            request_path=request.path,
            additional_data={
                'exception_type': exception.__class__.__name__,
                'exception_message': str(exception)
            }
        )


class APIRequestLoggingMiddleware:
    """
    Middleware to log all API requests for analytics and security
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only log API requests
        if not request.path.startswith('/api/'):
            return self.get_response(request)
        
        start_time = time.time()
        
        # Get response
        response = self.get_response(request)
        
        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Log the API request
        self.log_api_request(request, response, response_time_ms)
        
        return response
    
    def log_api_request(self, request, response, response_time_ms):
        """Log API request to APIRequestLog"""
        from api.models import APIRequestLog
        
        # Get API token if present
        token = getattr(request, 'api_token', None)
        
        # Extract error message if present
        error_message = ''
        if response.status_code >= 400:
            try:
                error_data = response.data if hasattr(response, 'data') else {}
                error_message = str(error_data.get('detail', error_data.get('error', '')))
            except:
                pass
        
        # Log the request
        APIRequestLog.objects.create(
            token=token,
            endpoint=request.path,
            method=request.method,
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
            error_message=error_message[:500] if error_message else ''
        )


class SecurityMonitoringMiddleware:
    """
    Middleware to detect and respond to security threats
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Monitor for suspicious activity
        if request.user.is_authenticated:
            self.check_for_anomalies(request, response)
        
        return response
    
    def check_for_anomalies(self, request, response):
        """Check for suspicious patterns in user behavior"""
        from kanban.audit_models import SystemAuditLog
        from django.utils import timezone
        from datetime import timedelta
        
        user = request.user
        ip_address = get_client_ip(request)
        
        # Check for rapid-fire requests (possible bot/script)
        last_minute = timezone.now() - timedelta(minutes=1)
        recent_requests = SystemAuditLog.objects.filter(
            user=user,
            timestamp__gte=last_minute
        ).count()
        
        if recent_requests > 100:  # More than 100 requests per minute
            from kanban.audit_utils import log_security_event
            log_security_event(
                event_type='unusual_api_usage',
                description=f'User {user.username} made {recent_requests} requests in 1 minute',
                user=user,
                ip_address=ip_address,
                risk_score=60
            )
        
        # Check for IP address changes (possible account compromise)
        last_hour = timezone.now() - timedelta(hours=1)
        unique_ips = SystemAuditLog.objects.filter(
            user=user,
            timestamp__gte=last_hour
        ).values_list('ip_address', flat=True).distinct()
        
        if len(list(unique_ips)) > 3:  # More than 3 different IPs in 1 hour
            from kanban.audit_utils import log_security_event
            log_security_event(
                event_type='suspicious_login',
                description=f'User {user.username} accessed from {len(unique_ips)} different IPs in 1 hour',
                user=user,
                ip_address=ip_address,
                risk_score=65
            )
