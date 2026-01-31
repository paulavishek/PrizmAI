"""
Demo Session Management Middleware
Tracks demo sessions, updates activity.
Automatically refreshes demo data dates to keep demo content fresh.
"""
from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse
from datetime import timedelta
import json
import logging

logger = logging.getLogger(__name__)


class DemoSessionMiddleware:
    """
    Middleware to manage demo sessions:
    - Track last activity
    - Update DemoSession records
    - Automatically refresh demo data dates (once per day)
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Process request
        if request.session.get('is_demo_mode'):
            # Refresh demo data dates if needed (once per day)
            self.refresh_demo_dates_if_needed()
            
            self.update_demo_session(request)
        
        # Get response
        response = self.get_response(request)
        
        return response
    
    def refresh_demo_dates_if_needed(self):
        """
        Check if demo data dates need to be refreshed and refresh them.
        This runs once per day to keep demo data timelines dynamic.
        """
        try:
            from kanban.utils.demo_date_refresh import (
                should_refresh_demo_dates,
                refresh_all_demo_dates
            )
            
            if should_refresh_demo_dates():
                logger.info("Refreshing demo data dates (daily automatic refresh)")
                stats = refresh_all_demo_dates()
                logger.info(f"Demo dates refreshed successfully: {stats}")
        except Exception as e:
            # Don't break the request if refresh fails
            logger.warning(f"Error during automatic demo date refresh: {e}")
    
    def update_demo_session(self, request):
        """Update demo session activity and metadata"""
        try:
            from analytics.models import DemoSession
            
            session_id = request.session.session_key
            if not session_id:
                return
            
            # Get or create demo session
            demo_session, created = DemoSession.objects.get_or_create(
                session_id=session_id,
                defaults={
                    'demo_mode': request.session.get('demo_mode', 'solo'),
                    'current_role': request.session.get('demo_role', 'admin'),
                }
            )
            
            # Update last activity
            demo_session.last_activity = timezone.now()
            
            # Calculate time in demo (seconds)
            if demo_session.started_at:
                time_in_demo = (timezone.now() - demo_session.started_at).total_seconds()
                demo_session.time_in_demo = int(time_in_demo)
            
            # Update current page
            demo_session.current_page = request.path
            
            demo_session.save(update_fields=['last_activity', 'time_in_demo', 'current_page'])
            
        except Exception as e:
            # Analytics models may not exist - that's OK
            pass


class DemoAnalyticsMiddleware:
    """
    Middleware to track demo page views and user interactions
    Provides server-side analytics that work even with ad blockers
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Track pageview for demo users
        if request.session.get('is_demo_mode') and request.method == 'GET':
            self.track_pageview(request)
        
        response = self.get_response(request)
        return response
    
    def track_pageview(self, request):
        """Track demo page views server-side"""
        try:
            from analytics.models import DemoAnalytics
            
            # Only track actual page views (not AJAX, not static files)
            if self.should_track_page(request):
                DemoAnalytics.objects.create(
                    session_id=request.session.session_key,
                    event_type='pageview',
                    event_data={
                        'path': request.path,
                        'method': request.method,
                        'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
                        'referer': request.META.get('HTTP_REFERER', '')[:200],
                    }
                )
        except Exception as e:
            # Fail silently - don't break the app
            pass
    
    def should_track_page(self, request):
        """Determine if this request should be tracked"""
        # Don't track static files, media, admin, API calls
        path = request.path
        
        skip_prefixes = [
            '/static/', '/media/', '/admin/', '/api/',
            '/__debug__/', '/favicon.ico'
        ]
        
        for prefix in skip_prefixes:
            if path.startswith(prefix):
                return False
        
        # Only track demo-related pages
        return path.startswith('/demo/') or path.startswith('/kanban/demo/')
    
    def get_device_type(self, user_agent):
        """Detect device type from user agent"""
        user_agent = user_agent.lower()
        
        if 'mobile' in user_agent or 'android' in user_agent:
            return 'mobile'
        elif 'tablet' in user_agent or 'ipad' in user_agent:
            return 'tablet'
        else:
            return 'desktop'
