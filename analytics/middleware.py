"""
Session tracking middleware for analytics.
Tracks user behavior throughout their session automatically.
"""
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
from .models import UserSession, AnalyticsEvent
import logging
import re

logger = logging.getLogger(__name__)


class SessionTrackingMiddleware(MiddlewareMixin):
    """
    Track user behavior throughout their session.
    Runs on every request and updates the UserSession model.
    """
    
    # Paths to skip tracking
    SKIP_PATHS = [
        '/static/', 
        '/media/', 
        '/admin/',
        '/health/',
        '/__debug__/',
        '/favicon.ico',
    ]
    
    # AI feature paths to track
    AI_PATHS = [
        'ai-recommend',
        'ai-forecast', 
        'gemini',
        'ai-coach',
        'ai-detect',
        'ai-suggest',
        'ai_assistant',
    ]
    
    def process_request(self, request):
        """Initialize or retrieve user session"""
        # Skip tracking for certain paths
        if any(request.path.startswith(path) for path in self.SKIP_PATHS):
            return None
        
        # Ensure session exists
        if not request.session.session_key:
            request.session.create()
        
        session_key = request.session.session_key
        
        # Get or create UserSession
        try:
            if request.user.is_authenticated:
                # For authenticated users, get or create active session
                user_session, created = UserSession.objects.get_or_create(
                    user=request.user,
                    session_end__isnull=True,  # Only get active sessions
                    defaults={
                        'session_key': session_key,
                        'session_start': timezone.now(),
                        'ip_address': self.get_client_ip(request),
                        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
                        'referrer': request.META.get('HTTP_REFERER', '')[:500],
                        'device_type': self.detect_device_type(request),
                    }
                )
            else:
                # For anonymous users, use session key
                user_session, created = UserSession.objects.get_or_create(
                    session_key=session_key,
                    session_end__isnull=True,
                    defaults={
                        'session_start': timezone.now(),
                        'ip_address': self.get_client_ip(request),
                        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
                        'referrer': request.META.get('HTTP_REFERER', '')[:500],
                        'device_type': self.detect_device_type(request),
                    }
                )
            
            # Update last activity
            if not created:
                user_session.last_activity = timezone.now()
                user_session.save(update_fields=['last_activity'])
            
            # Attach to request for easy access in views
            request.user_session = user_session
            
            if created:
                logger.info(f"New session created: {session_key}")
        
        except Exception as e:
            logger.error(f"Error in session tracking: {e}", exc_info=True)
            # Don't break the request if tracking fails
            request.user_session = None
        
        return None
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """Track specific user actions based on the view being accessed"""
        if not hasattr(request, 'user_session') or request.user_session is None:
            return None
        
        session = request.user_session
        path = request.path.lower()
        method = request.method
        
        # Initialize pending events list for bulk creation
        if not hasattr(request, '_pending_events'):
            request._pending_events = []
        
        try:
            # Increment pages visited (for GET requests only)
            if method == 'GET':
                session.pages_visited += 1
            
            # Track board views (GET requests to board detail pages)
            if 'board' in path and method == 'GET':
                # Check if it's a detail view (has ID in path)
                if re.search(r'/board[s]?/\d+', path):
                    session.boards_viewed += 1
            
            # Track board creation (POST to board create endpoint)
            if 'board' in path and method == 'POST' and ('create' in path or path.endswith('/boards/')):
                session.boards_created += 1
                request._pending_events.append({
                    'user_session': session,
                    'event_name': 'board_created',
                    'event_category': 'boards',
                    'timestamp': timezone.now()
                })
            
            # Track task creation
            if 'task' in path and method == 'POST':
                session.tasks_created += 1
                request._pending_events.append({
                    'user_session': session,
                    'event_name': 'task_created',
                    'event_category': 'tasks',
                    'timestamp': timezone.now()
                })
            
            # Track task completion (look for status updates)
            if 'task' in path and method in ['PUT', 'PATCH', 'POST']:
                # Check if this is a status update to 'done'
                # You might want to check request.POST or request.body
                if 'complete' in path or 'done' in path:
                    session.tasks_completed += 1
                    request._pending_events.append({
                        'user_session': session,
                        'event_name': 'task_completed',
                        'event_category': 'tasks',
                        'timestamp': timezone.now()
                    })
            
            # Track AI feature usage
            if any(ai_path in path for ai_path in self.AI_PATHS):
                session.ai_features_used += 1
                # Extract which AI feature
                feature_name = next((ai for ai in self.AI_PATHS if ai in path), 'unknown')
                request._pending_events.append({
                    'user_session': session,
                    'event_name': 'ai_feature_used',
                    'event_category': 'ai_features',
                    'event_label': feature_name,
                    'timestamp': timezone.now()
                })
            
            # Save updates (batch save for performance)
            session.save(update_fields=[
                'boards_viewed', 
                'boards_created', 
                'tasks_created', 
                'tasks_completed',
                'ai_features_used',
                'pages_visited'
            ])
        
        except Exception as e:
            logger.error(f"Error tracking action: {e}", exc_info=True)
        
        return None
    
    def process_response(self, request, response):
        """Update session duration and engagement on response, and bulk create events"""
        # Bulk create pending events
        if hasattr(request, '_pending_events') and request._pending_events:
            try:
                AnalyticsEvent.objects.bulk_create([
                    AnalyticsEvent(**event_data) 
                    for event_data in request._pending_events
                ])
            except Exception as e:
                logger.error(f"Error bulk creating analytics events: {e}", exc_info=True)
        
        if hasattr(request, 'user_session') and request.user_session:
            try:
                session = request.user_session
                session.update_duration()
                
                # Update engagement level periodically (not on every request)
                # Only update if duration changed significantly (every 5 minutes)
                if session.duration_minutes - session.last_engagement_update >= 5:
                    session.update_engagement_level()
                    session.last_engagement_update = session.duration_minutes
                    session.save(update_fields=['last_engagement_update'])
            except Exception as e:
                logger.error(f"Error updating session metrics: {e}", exc_info=True)
        
        return response
    
    def get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def detect_device_type(self, request):
        """Detect device type from user agent"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
            return 'mobile'
        elif 'tablet' in user_agent or 'ipad' in user_agent:
            return 'tablet'
        elif 'mozilla' in user_agent or 'chrome' in user_agent or 'safari' in user_agent:
            return 'desktop'
        else:
            return 'unknown'


class SessionTimeoutMiddleware(MiddlewareMixin):
    """
    Automatically end sessions that have been inactive for too long.
    Configurable timeout period.
    """
    
    # Session timeout in minutes
    SESSION_TIMEOUT = 30
    
    def process_request(self, request):
        """Check for session timeout"""
        if hasattr(request, 'user_session') and request.user_session:
            session = request.user_session
            
            # Check if session has timed out
            if session.last_activity:
                inactive_minutes = (timezone.now() - session.last_activity).total_seconds() / 60
                
                if inactive_minutes > self.SESSION_TIMEOUT:
                    # End the session
                    session.end_session(reason='timeout')
                    logger.info(f"Session {session.session_key} timed out after {inactive_minutes} minutes")
                    
                    # Clear request session reference
                    request.user_session = None
        
        return None
