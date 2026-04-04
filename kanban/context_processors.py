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

        # Single-tier personal sandbox (profile-based, not session-based)
        if request.user.is_authenticated:
            try:
                profile = request.user.profile
                context['is_viewing_demo'] = getattr(profile, 'is_viewing_demo', False)
                # Workspace context for the workspace switcher dropdown
                active_ws = getattr(profile, 'active_workspace', None)
                context['active_workspace'] = active_ws
                if profile.organization:
                    from kanban.models import Workspace
                    all_ws = list(
                        Workspace.objects.filter(
                            organization=profile.organization,
                            is_active=True,
                        ).order_by('is_demo', '-created_at')
                    )
                    context['user_workspaces'] = all_ws
                    # Split real vs demo for templates
                    context['real_workspaces'] = [w for w in all_ws if not w.is_demo]
                    context['demo_workspace'] = next((w for w in all_ws if w.is_demo), None)
                    # Only org creator can create new workspaces
                    context['can_setup_workspace'] = (
                        profile.organization.created_by_id == request.user.id
                    )
                else:
                    context['user_workspaces'] = []
                    context['real_workspaces'] = []
                    context['demo_workspace'] = None
                    context['can_setup_workspace'] = True  # No org yet — can set up
            except Exception:
                context['is_viewing_demo'] = False
                context['active_workspace'] = None
                context['user_workspaces'] = []
                context['real_workspaces'] = []
                context['demo_workspace'] = None
                context['can_setup_workspace'] = False
        else:
            context['is_viewing_demo'] = False
            context['active_workspace'] = None
            context['user_workspaces'] = []
            context['real_workspaces'] = []
            context['demo_workspace'] = None
            context['can_setup_workspace'] = False
        
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
        
        # Get boards scoped to the user's current workspace (demo vs real)
        demo_mode = getattr(profile, 'is_viewing_demo', False)

        if demo_mode:
            boards = Board.objects.filter(
                owner=request.user,
                is_sandbox_copy=True,
            ).distinct()
        else:
            boards = Board.objects.filter(
                Q(created_by=request.user) | Q(memberships__user=request.user),
                is_official_demo_board=False,
                is_sandbox_copy=False,
            ).exclude(
                created_by_session__startswith='spectra_demo_'
            ).distinct()
        
        # Count active conflicts
        count = ConflictDetection.objects.filter(
            board__in=boards,
            status='active'
        ).count()
        
        return {'active_conflict_count': count}
    except:
        return {'active_conflict_count': 0}


def user_favorites(request):
    """
    Add user's favorites to template context for sidebar rendering.
    Uses select_related on content_type and cached display_name to avoid N+1.
    """
    if not request.user.is_authenticated:
        return {'user_favorites': []}

    try:
        from kanban.models import UserFavorite
        favorites = (
            UserFavorite.objects
            .filter(user=request.user)
            .select_related('content_type')
            .order_by('position', '-created_at')[:20]
        )
        return {'user_favorites': favorites}
    except Exception:
        return {'user_favorites': []}


def preset_features(request):
    """
    Inject feature-visibility flags into every template based on the
    effective workspace preset (lean / professional / enterprise).

    Priority order:
      1. Demo accounts (persona accounts or is_viewing_demo) → always enterprise
      2. Board-specific preset (from URL board_id kwarg) → BoardPreset.effective_preset()
      3. Org-level global preset → WorkspacePreset.global_preset
      4. Fallback → lean (safest default for unknown state)
    """
    from kanban.preset_models import build_feature_flags

    if not request.user.is_authenticated:
        return {'features': build_feature_flags('lean')}

    # Demo accounts always see everything
    is_demo = False
    try:
        profile = request.user.profile
        is_demo = getattr(profile, 'is_demo_account', False) or \
                  getattr(profile, 'is_viewing_demo', False)
    except Exception:
        pass

    if is_demo:
        return {'features': build_feature_flags('enterprise')}

    # Try to resolve from a board-specific context
    preset = None
    board_id = None
    if getattr(request, 'resolver_match', None) and request.resolver_match.kwargs:
        board_id = request.resolver_match.kwargs.get('board_id') or \
                   request.resolver_match.kwargs.get('pk')

    if board_id:
        try:
            from kanban.preset_models import BoardPreset
            bp = BoardPreset.objects.select_related(
                'board__organization__workspace_preset'
            ).get(board_id=board_id)
            preset = bp.effective_preset()
        except Exception:
            pass

    # Fall back to org-level global preset
    if preset is None:
        try:
            org = request.user.profile.organization
            if org is not None:
                preset = org.workspace_preset.global_preset
        except Exception:
            pass

    return {'features': build_feature_flags(preset or 'lean')}
