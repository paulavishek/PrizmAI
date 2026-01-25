"""
Context processors for conflict detection and demo mode

SIMPLIFIED MODE (January 2026):
- No demo limitations for authenticated users
- All users have same access level
- No role switching or permission errors
"""
from kanban.conflict_models import ConflictDetection
from django.utils import timezone


def demo_context(request):
    """
    Add demo session information to template context
    Makes demo variables available globally without repeating in every view
    
    SIMPLIFIED MODE (January 2026):
    - Authenticated users have full access (no demo limitations)
    - Demo mode session variables are simplified
    - No VPN penalties or complex abuse prevention
    
    LEGACY MODE:
    - Distinguishes between anonymous demo users and authenticated users
    - Applies demo limitations to anonymous users
    """
    # Import simplified mode setting
    from kanban.utils.demo_settings import SIMPLIFIED_MODE
    
    context = {
        'simplified_mode': SIMPLIFIED_MODE,
    }
    
    # SIMPLIFIED MODE: Much simpler logic
    if SIMPLIFIED_MODE:
        context['is_demo_mode'] = False  # No special demo mode in simplified
        context['show_demo_limitations'] = False  # No limitations for authenticated users
        context['is_authenticated_exploring_demo'] = False
        
        # User gets their standard quotas (not demo quotas)
        if request.user.is_authenticated:
            try:
                from api.ai_usage_models import AIUsageQuota
                quota = AIUsageQuota.objects.filter(user=request.user).first()
                if quota:
                    context['user_ai_remaining'] = quota.monthly_quota - quota.requests_used
                    context['user_ai_quota'] = quota.monthly_quota
                else:
                    context['user_ai_remaining'] = 50  # Default
                    context['user_ai_quota'] = 50
            except Exception:
                context['user_ai_remaining'] = 50
                context['user_ai_quota'] = 50
        
        return context
    
    # LEGACY MODE: Original complex demo tracking
    # Determine if user is authenticated with a real account
    # Exclude demo admin accounts and virtual demo users
    is_authenticated_user = False
    if request.user.is_authenticated:
        # Check if this is NOT an anonymous demo session
        if not request.session.get('is_anonymous_demo', False):
            # Check if user has a real email (not a demo placeholder)
            if hasattr(request.user, 'email') and request.user.email:
                email = request.user.email.lower()
                # Exclude virtual demo admin emails
                if not ('demo_admin' in email or email.startswith('virtual_demo')):
                    is_authenticated_user = True
    
    # Check if this authenticated user is just exploring demo content
    # They should NOT see demo limitations - they have their own quota
    context['is_authenticated_exploring_demo'] = (
        is_authenticated_user and 
        request.session.get('is_demo_mode', False)
    )
    
    # Demo limitations only apply to non-authenticated demo users
    context['show_demo_limitations'] = (
        request.session.get('is_demo_mode', False) and 
        not is_authenticated_user
    )
    
    # Check if user is in demo mode
    if request.session.get('is_demo_mode'):
        # Basic demo info
        context['is_demo_mode'] = True
        context['demo_mode'] = request.session.get('demo_mode', 'solo')
        context['demo_mode_type'] = request.session.get('demo_mode', 'solo').title()
        context['current_demo_role'] = request.session.get('demo_role', 'admin')
        
        # Demo limitations - import utility
        try:
            from kanban.utils.demo_limits import get_demo_status, DEMO_LIMITS
            demo_status = get_demo_status(request)
            
            # Add limit info to context
            context['demo_projects_created'] = demo_status['projects']['current']
            context['demo_projects_max'] = demo_status['projects']['max']
            context['demo_projects_remaining'] = demo_status['projects']['max'] - demo_status['projects']['current']
            context['demo_can_create_project'] = demo_status['projects']['can_create']
            
            context['demo_ai_uses'] = demo_status['ai']['current']
            context['demo_ai_max'] = demo_status['ai']['max']
            context['demo_can_use_ai'] = demo_status['ai']['can_generate']
            
            context['demo_export_allowed'] = demo_status['export']['allowed']
            context['demo_limitations_hit'] = demo_status.get('limitations_hit', [])
            context['demo_data_reset_hours'] = DEMO_LIMITS['data_reset_hours']
        except Exception as e:
            # Fallback defaults if utility fails
            context['demo_projects_created'] = 0
            context['demo_projects_max'] = 2
            context['demo_projects_remaining'] = 2
            context['demo_can_create_project'] = True
            context['demo_export_allowed'] = False
            context['demo_data_reset_hours'] = 48
        
        # Expiry information - ensure demo_expires_at is always set
        expires_at_str = request.session.get('demo_expires_at')
        
        # If no expiry is set, initialize it now (48 hours from now)
        if not expires_at_str:
            from datetime import timedelta
            expires_at = timezone.now() + timedelta(hours=48)
            request.session['demo_expires_at'] = expires_at.isoformat()
            expires_at_str = request.session['demo_expires_at']
            request.session.modified = True
        
        try:
            from dateutil import parser
            expires_at = parser.parse(expires_at_str)
            
            # Ensure timezone awareness
            if expires_at.tzinfo is None:
                from django.utils.timezone import make_aware
                expires_at = make_aware(expires_at)
            
            context['demo_expires_at'] = expires_at
            context['demo_expires_at_iso'] = expires_at.isoformat()
            
            # Calculate time remaining
            time_remaining = expires_at - timezone.now()
            total_seconds = time_remaining.total_seconds()
            
            # Handle negative time (expired)
            if total_seconds < 0:
                context['demo_time_remaining'] = None
                context['demo_hours_remaining'] = 0
                context['demo_hours_component'] = 0
                context['demo_minutes_component'] = 0
                context['demo_seconds_component'] = 0
                context['demo_time_formatted'] = '00:00:00'
                context['demo_expired'] = True
            else:
                context['demo_time_remaining'] = time_remaining
                context['demo_hours_remaining'] = round(total_seconds / 3600, 1)
                
                # Add formatted time components for HH:MM:SS display
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                seconds = int(total_seconds % 60)
                context['demo_hours_component'] = hours
                context['demo_minutes_component'] = minutes
                context['demo_seconds_component'] = seconds
                context['demo_time_formatted'] = f'{hours:02d}:{minutes:02d}:{seconds:02d}'
                
                context['demo_expired'] = False
            
            # Check if warning should be shown
            hours_remaining = max(0, total_seconds / 3600)
            if hours_remaining <= 0.25:  # 15 minutes
                context['show_expiry_warning'] = True
                context['expiry_warning_level'] = 'critical'
                minutes_left = max(1, int(total_seconds / 60))
                context['expiry_warning_message'] = f'Demo session expires in {minutes_left} minutes! Data will be reset.'
            elif hours_remaining <= 1:  # 1 hour
                context['show_expiry_warning'] = True
                context['expiry_warning_level'] = 'warning'
                minutes_left = max(1, int(total_seconds / 60))
                context['expiry_warning_message'] = f'Demo session expires in {minutes_left} minutes. Create an account to save your work!'
            elif hours_remaining <= 4:  # 4 hours
                context['show_expiry_warning'] = True
                context['expiry_warning_level'] = 'info'
                # Show hours and minutes for accurate display
                hours = int(hours_remaining)
                minutes = int((hours_remaining - hours) * 60)
                if hours > 0 and minutes > 0:
                    time_str = f'{hours} hour{"s" if hours != 1 else ""} {minutes} minutes'
                elif hours > 0:
                    time_str = f'{hours} hour{"s" if hours != 1 else ""}'
                else:
                    time_str = f'{minutes} minutes'
                context['expiry_warning_message'] = f'Demo session expires in {time_str}.'
        except Exception as e:
            # Fallback: set reasonable defaults
            import logging
            logging.getLogger(__name__).warning(f"Error parsing demo_expires_at: {e}")
            context['demo_hours_remaining'] = 48
            context['demo_expired'] = False
        
        # Track explored features
        features_explored = request.session.get('features_explored', [])
        context['features_explored'] = features_explored
        context['features_explored_count'] = len(features_explored)
        
        # Track aha moments
        aha_moments = request.session.get('aha_moments', [])
        context['aha_moments'] = aha_moments
        context['aha_moments_count'] = len(aha_moments)
        
        # Nudge information
        nudges_shown = request.session.get('nudges_shown', [])
        context['nudges_shown'] = nudges_shown
        context['nudges_shown_count'] = len(nudges_shown)
        
        # Extension limits information
        try:
            from analytics.models import DemoSession
            session_id = request.session.session_key
            if session_id:
                demo_session = DemoSession.objects.filter(session_id=session_id).first()
                if demo_session:
                    # Import constants from demo_views
                    from kanban.demo_views import MAX_DEMO_EXTENSIONS, EXTENSION_DURATION_HOURS
                    context['demo_extensions_used'] = demo_session.extensions_count
                    context['demo_extensions_max'] = MAX_DEMO_EXTENSIONS
                    context['demo_extensions_remaining'] = MAX_DEMO_EXTENSIONS - demo_session.extensions_count
                    context['demo_extension_duration'] = EXTENSION_DURATION_HOURS
                else:
                    context['demo_extensions_used'] = 0
                    context['demo_extensions_max'] = 3
                    context['demo_extensions_remaining'] = 3
                    context['demo_extension_duration'] = 1
            else:
                context['demo_extensions_used'] = 0
                context['demo_extensions_max'] = 3
                context['demo_extensions_remaining'] = 3
                context['demo_extension_duration'] = 1
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Error loading extension info: {e}")
            context['demo_extensions_used'] = 0
            context['demo_extensions_max'] = 3
            context['demo_extensions_remaining'] = 3
            context['demo_extension_duration'] = 1
        
        # Role display names
        role_names = {
            'admin': 'Demo Admin (Solo)',
            'member': 'Sam Rivera (Member)',
            'viewer': 'Jordan Taylor (Viewer)'
        }
        context['demo_role_display'] = role_names.get(
            context['current_demo_role'], 
            context['current_demo_role'].title()
        )
        
        # Team mode availability
        context['is_team_mode'] = context['demo_mode'] == 'team'
        context['can_switch_roles'] = context['is_team_mode']
        
    else:
        # Not in demo mode
        context['is_demo_mode'] = False
    
    return context


def conflict_count(request):
    """
    Add active conflict count to template context for all pages.
    """
    if not request.user.is_authenticated:
        return {'active_conflict_count': 0}
    
    try:
        from kanban.models import Board
        from django.db.models import Q
        
        # Get user's accessible boards
        profile = request.user.profile
        organization = profile.organization
        
        boards = Board.objects.filter(
            Q(organization=organization) &
            (Q(created_by=request.user) | Q(members=request.user))
        ).distinct()
        
        # Count active conflicts
        count = ConflictDetection.objects.filter(
            board__in=boards,
            status='active'
        ).count()
        
        return {'active_conflict_count': count}
    except:
        return {'active_conflict_count': 0}
