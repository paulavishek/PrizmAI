"""
Session tracking middleware for analytics.
Tracks user behavior throughout their session automatically.
"""
from datetime import timedelta

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
    
    # AI feature paths → named feature key (used for FeatureAdoptionEvent + deduplication)
    AI_PATH_FEATURES = {
        '/assistant/':        ('spectra_query',    'ai'),
        '/coach/':            ('ai_coach',         'ai'),
        '/forecast/':         ('burndown_chart',   'core'),
        '/what-if/':          ('what_if',          'enterprise_ai'),
        '/retro':             ('ai_retrospective', 'ai'),
        '/skill-gap':         ('skill_gap',        'ai'),
        '/recommendations/':  ('ai_bubble_up',     'ai'),
        '/ai-analyze':        ('requirements_ai',  'ai'),
        '/ai-create-tasks':   ('requirements_ai',  'ai'),
        '/spectra':           ('spectra_query',    'ai'),
        '/gap-analysis':      ('skill_gap',        'ai'),
    }

    # Keep a flat path list for quick "any match" checks (backwards compat)
    @property
    def AI_PATHS(self):
        return list(self.AI_PATH_FEATURES.keys())
    
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
                # Close any stale open sessions (inactive for > 4 hours) to prevent
                # inflated duration_minutes on the logout page
                stale_cutoff = timezone.now() - timedelta(hours=4)
                UserSession.objects.filter(
                    user=request.user,
                    session_end__isnull=True,
                    last_activity__lt=stale_cutoff,
                ).update(session_end=stale_cutoff, exit_reason='stale')

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
                        **self._workspace_context(request.user),
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
            # Deduplicate: only count each unique board ID once per session
            if method == 'GET':
                board_match = re.search(r'/boards?/(\d+)(?:/|$)', path)
                if board_match:
                    board_id = board_match.group(1)
                    visited_boards = request.session.get('_visited_board_ids', [])
                    if board_id not in visited_boards:
                        session.boards_viewed += 1
                        visited_boards.append(board_id)
                        request.session['_visited_board_ids'] = visited_boards
                        request.session.modified = True
            
            # Track board creation (POST to board create endpoint)
            if 'board' in path and method == 'POST' and ('create' in path or path.endswith('/boards/')):
                session.boards_created += 1
                request._pending_events.append({
                    'user_session': session,
                    'event_name': 'board_created',
                    'event_category': 'boards',
                    'timestamp': timezone.now()
                })
            
            # Track task creation — only match explicit create-task endpoints,
            # not every POST that happens to contain 'task' in the URL
            _TASK_CREATE_PATTERNS = [
                r'/create-task/',
                r'/boards/\d+/tasks/$',
                r'/api/wizard/create-task/',
                r'/calendar/create-task/',
            ]
            if method == 'POST' and any(re.search(p, path) for p in _TASK_CREATE_PATTERNS):
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
            
            # Track AI feature usage — only count GET requests to AI feature pages
            # (not every sub-API call within the same feature)
            if method == 'GET' and any(ai_path in path for ai_path in self.AI_PATH_FEATURES):
                # Determine feature name and category
                matched_path = next((p for p in self.AI_PATH_FEATURES if p in path), None)
                feature_name, feature_cat = self.AI_PATH_FEATURES.get(matched_path, ('unknown', 'ai'))
                used_ai = request.session.get('_used_ai_features', [])
                if matched_path not in used_ai:
                    session.ai_features_used += 1
                    used_ai.append(matched_path)
                    request.session['_used_ai_features'] = used_ai
                    request.session.modified = True
                    request._pending_events.append({
                        'user_session': session,
                        'event_name': 'ai_feature_used',
                        'event_category': 'ai_features',
                        'event_label': feature_name,
                        'timestamp': timezone.now()
                    })
                    # Record FeatureAdoptionEvent for authenticated users
                    if request.user.is_authenticated and feature_name != 'unknown':
                        try:
                            from analytics.signals import _record_feature
                            _record_feature(
                                request.user, feature_name, feature_cat,
                                session=session
                            )
                        except Exception:
                            pass
            
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

    @staticmethod
    def _workspace_context(user):
        """
        Return a dict with workspace_preset, byok_active, ai_provider_used
        for the given authenticated user.  Never raises — returns empty defaults.
        """
        ctx = {'workspace_preset': '', 'byok_active': False, 'ai_provider_used': ''}
        try:
            # Workspace preset from the user's active workspace (the tenant boundary)
            ws = getattr(getattr(user, 'profile', None), 'active_workspace', None)
            preset_obj = getattr(ws, 'workspace_preset', None) if ws else None
            if preset_obj:
                ctx['workspace_preset'] = preset_obj.global_preset
        except Exception:
            pass
        try:
            from ai_assistant.models import UserAISettings
            settings_obj = UserAISettings.objects.filter(user=user).first()
            if settings_obj and settings_obj.encrypted_api_key:
                ctx['byok_active'] = True
                ctx['ai_provider_used'] = getattr(settings_obj, 'byok_provider', '') or ''
            elif settings_obj:
                ctx['ai_provider_used'] = getattr(settings_obj, 'provider_override', '') or ''
        except Exception:
            pass
        return ctx


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
