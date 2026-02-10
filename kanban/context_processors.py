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
    
    # Check if user is a demo account (sam, jordan, alex) - they cannot use AI features
    # Demo accounts have @demo.prizmai.local email domain
    is_demo_account = False
    if request.user.is_authenticated and hasattr(request.user, 'email') and request.user.email:
        if '@demo.prizmai.local' in request.user.email.lower():
            is_demo_account = True
    context['is_demo_account'] = is_demo_account
    
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
        except Exception as e:
            # Fallback defaults if utility fails
            context['demo_projects_created'] = 0
            context['demo_projects_max'] = 2
            context['demo_projects_remaining'] = 2
            context['demo_can_create_project'] = True
            context['demo_export_allowed'] = False
        
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
    MVP Mode: Works without organization requirement.
    """
    if not request.user.is_authenticated:
        return {'active_conflict_count': 0}
    
    try:
        from kanban.models import Board
        from accounts.models import UserProfile
        from django.db.models import Q
        
        # Ensure user has a profile
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            return {'active_conflict_count': 0}
        
        # MVP Mode: Get all boards the user has access to
        demo_boards = Board.objects.filter(is_official_demo_board=True)
        user_boards = Board.objects.filter(
            Q(created_by=request.user) | Q(members=request.user)
        )
        boards = (demo_boards | user_boards).distinct()
        
        # Count active conflicts
        count = ConflictDetection.objects.filter(
            board__in=boards,
            status='active'
        ).count()
        
        return {'active_conflict_count': count}
    except:
        return {'active_conflict_count': 0}
