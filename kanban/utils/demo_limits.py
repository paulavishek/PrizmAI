"""
Demo Limitations Utility
Handles checking and enforcing demo mode restrictions for conversion optimization.

Demo Limits:
- Max 2 projects (boards) can be created
- Export functionality is blocked
- AI generations limited to 20

These limits create conversion incentives while still demonstrating product value.
"""
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# Demo limitation constants
DEMO_LIMITS = {
    'max_projects': 2,
    'max_ai_generations': 20,
    'export_enabled': False,
    'data_reset_hours': 48,
}


def is_demo_mode(request):
    """Check if the current session is in demo mode"""
    return request.session.get('is_demo_mode', False)


def get_demo_session(request):
    """Get the DemoSession object for the current session"""
    if not is_demo_mode(request):
        return None
    
    try:
        from analytics.models import DemoSession
        session_id = request.session.session_key
        if not session_id:
            return None
        return DemoSession.objects.filter(session_id=session_id).first()
    except Exception as e:
        logger.error(f"Error getting demo session: {e}")
        return None


def check_project_limit(request):
    """
    Check if user can create more projects in demo mode.
    Returns dict with:
    - can_create: bool
    - current_count: int
    - max_allowed: int
    - message: str
    """
    if not is_demo_mode(request):
        return {
            'can_create': True,
            'current_count': 0,
            'max_allowed': float('inf'),
            'message': None,
            'is_demo': False
        }
    
    demo_session = get_demo_session(request)
    if not demo_session:
        # If no demo session, allow creation but with limit
        return {
            'can_create': True,
            'current_count': 0,
            'max_allowed': DEMO_LIMITS['max_projects'],
            'message': None,
            'is_demo': True
        }
    
    current_count = demo_session.projects_created_in_demo
    max_allowed = DEMO_LIMITS['max_projects']
    can_create = current_count < max_allowed
    
    if not can_create:
        message = f"Demo limit reached! You've created {current_count}/{max_allowed} projects. Create a free account to create unlimited projects."
    else:
        remaining = max_allowed - current_count
        message = f"You can create {remaining} more project(s) in demo mode."
    
    return {
        'can_create': can_create,
        'current_count': current_count,
        'max_allowed': max_allowed,
        'message': message,
        'is_demo': True
    }


def increment_project_count(request):
    """Increment the project count after successfully creating a project in demo mode"""
    if not is_demo_mode(request):
        return
    
    demo_session = get_demo_session(request)
    if demo_session:
        demo_session.projects_created_in_demo += 1
        demo_session.save(update_fields=['projects_created_in_demo'])
        logger.info(f"Demo project count incremented to {demo_session.projects_created_in_demo}")


def check_export_allowed(request):
    """
    Check if export is allowed in current session.
    Returns dict with:
    - allowed: bool
    - message: str
    """
    if not is_demo_mode(request):
        return {
            'allowed': True,
            'message': None,
            'is_demo': False
        }
    
    return {
        'allowed': DEMO_LIMITS['export_enabled'],
        'message': "Export is not available in demo mode. Create a free account to export your boards to JSON or CSV.",
        'is_demo': True
    }


def record_export_attempt(request):
    """Record an export attempt for analytics"""
    if not is_demo_mode(request):
        return
    
    demo_session = get_demo_session(request)
    if demo_session:
        demo_session.export_attempts += 1
        if 'export_blocked' not in demo_session.limitations_hit:
            demo_session.limitations_hit = demo_session.limitations_hit + ['export_blocked']
        demo_session.save(update_fields=['export_attempts', 'limitations_hit'])
        logger.info(f"Demo export attempt recorded (total: {demo_session.export_attempts})")


def check_ai_generation_limit(request):
    """
    Check if user can use more AI generations in demo mode.
    
    Checks BOTH:
    1. Per-session limit (20 AI generations per session)
    2. Global limit across all sessions (prevents abuse via new accounts)
    
    Returns dict with:
    - can_generate: bool
    - current_count: int
    - max_allowed: int
    - message: str
    """
    if not is_demo_mode(request):
        return {
            'can_generate': True,
            'current_count': 0,
            'max_allowed': float('inf'),
            'message': None,
            'is_demo': False
        }
    
    # Check global limit first (prevents abuse)
    try:
        from kanban.utils.demo_abuse_prevention import check_global_ai_limit
        global_status = check_global_ai_limit(request)
        if not global_status['can_generate']:
            return {
                'can_generate': False,
                'current_count': global_status['current_count'],
                'max_allowed': global_status['max_allowed'],
                'message': global_status['message'],
                'is_demo': True,
                'is_global_limit': True
            }
    except Exception as e:
        logger.warning(f"Could not check global AI limit: {e}")
    
    # Check per-session limit
    demo_session = get_demo_session(request)
    if not demo_session:
        return {
            'can_generate': True,
            'current_count': 0,
            'max_allowed': DEMO_LIMITS['max_ai_generations'],
            'message': None,
            'is_demo': True
        }
    
    current_count = demo_session.ai_generations_used
    max_allowed = DEMO_LIMITS['max_ai_generations']
    can_generate = current_count < max_allowed
    
    if not can_generate:
        message = f"Demo AI limit reached! You've used {current_count}/{max_allowed} AI generations. Create a free account for unlimited AI features."
    else:
        remaining = max_allowed - current_count
        message = f"You have {remaining} AI generation(s) remaining in demo mode."
    
    return {
        'can_generate': can_generate,
        'current_count': current_count,
        'max_allowed': max_allowed,
        'message': message,
        'is_demo': True
    }


def increment_ai_generation_count(request):
    """
    Increment the AI generation count after using AI in demo mode.
    Updates BOTH session-level and global (IP-based) counters.
    """
    if not is_demo_mode(request):
        return
    
    # Update session counter
    demo_session = get_demo_session(request)
    if demo_session:
        demo_session.ai_generations_used += 1
        demo_session.save(update_fields=['ai_generations_used'])
    
    # Update global counter (abuse prevention)
    try:
        from kanban.utils.demo_abuse_prevention import increment_global_ai_count
        increment_global_ai_count(request)
    except Exception as e:
        logger.warning(f"Could not update global AI count: {e}")


def record_limitation_hit(request, limitation_type):
    """
    Record when a user hits a limitation.
    limitation_type: 'project_limit', 'export_blocked', 'ai_limit', 'time_expired'
    """
    if not is_demo_mode(request):
        return
    
    demo_session = get_demo_session(request)
    if demo_session:
        if limitation_type not in demo_session.limitations_hit:
            demo_session.limitations_hit = demo_session.limitations_hit + [limitation_type]
            demo_session.save(update_fields=['limitations_hit'])
            logger.info(f"Demo limitation recorded: {limitation_type}")


def get_demo_status(request):
    """
    Get comprehensive demo status for templates/JavaScript.
    Returns dict with all relevant demo information.
    """
    if not is_demo_mode(request):
        return {
            'is_demo': False,
        }
    
    demo_session = get_demo_session(request)
    
    # Calculate time remaining
    expires_at = request.session.get('demo_expires_at')
    time_remaining_hours = 48  # default
    if expires_at:
        try:
            from datetime import datetime
            if isinstance(expires_at, str):
                expires_dt = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
            else:
                expires_dt = expires_at
            
            # Make timezone aware if needed
            if expires_dt.tzinfo is None:
                from django.utils import timezone as tz
                expires_dt = tz.make_aware(expires_dt)
            
            time_remaining = expires_dt - timezone.now()
            time_remaining_hours = max(0, time_remaining.total_seconds() / 3600)
        except Exception as e:
            logger.error(f"Error calculating time remaining: {e}")
    
    project_status = check_project_limit(request)
    ai_status = check_ai_generation_limit(request)
    export_status = check_export_allowed(request)
    
    return {
        'is_demo': True,
        'demo_mode': request.session.get('demo_mode', 'solo'),
        'demo_role': request.session.get('demo_role', 'admin'),
        'time_remaining_hours': round(time_remaining_hours, 1),
        'data_reset_hours': DEMO_LIMITS['data_reset_hours'],
        'projects': {
            'can_create': project_status['can_create'],
            'current': project_status['current_count'],
            'max': project_status['max_allowed'],
        },
        'ai': {
            'can_generate': ai_status['can_generate'],
            'current': ai_status['current_count'],
            'max': ai_status['max_allowed'],
        },
        'export': {
            'allowed': export_status['allowed'],
        },
        'limitations_hit': demo_session.limitations_hit if demo_session else [],
    }
