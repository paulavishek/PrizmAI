"""
Demo Abuse Prevention Utility

Prevents users from bypassing demo limitations by:
- Creating new accounts
- Clearing cookies/using incognito
- Using multiple browsers

Tracks usage at the IP + fingerprint level, not just session level.
"""
import hashlib
import logging
import os
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

logger = logging.getLogger(__name__)

# Global limits (across all sessions from same IP/fingerprint)
# In DEBUG mode, limits are much higher for development
if settings.DEBUG:
    GLOBAL_DEMO_LIMITS = {
        'max_ai_generations_global': 500,     # High for development
        'max_projects_global': 50,            # High for development
        'max_sessions_per_hour': 100,         # Effectively unlimited
        'max_sessions_per_24h': 500,          # Effectively unlimited
        'max_sessions_total': 1000,           # Effectively unlimited
        'cooldown_after_abuse_hours': 24,
    }
    # PRODUCTION SAFEGUARD: Log a critical warning if DEBUG=True in production
    # This helps catch accidental deployment with relaxed limits
    if os.environ.get('PRODUCTION_SERVER') == 'true' or os.environ.get('RAILWAY_ENVIRONMENT'):
        logger.critical(
            "⚠️ SECURITY WARNING: DEBUG=True detected in what appears to be a production environment! "
            "Demo abuse prevention limits are set to development values (500 AI generations instead of 30). "
            "This is a security risk. Set DEBUG=False in production settings."
        )
else:
    GLOBAL_DEMO_LIMITS = {
        'max_ai_generations_global': 30,      # Across all sessions (lowered for cost control)
        'max_projects_global': 5,              # Across all sessions
        'max_sessions_per_hour': 3,            # Rate limit
        'max_sessions_per_24h': 5,             # Daily limit
        'max_sessions_total': 20,              # Before blocking
        'cooldown_after_abuse_hours': 24,      # Cooldown period
    }
    logger.info(f"Demo abuse prevention initialized with production limits: {GLOBAL_DEMO_LIMITS['max_ai_generations_global']} global AI generations")


def get_client_ip(request):
    """Extract real client IP, handling proxies and load balancers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Take the first IP in the chain (original client)
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


def generate_browser_fingerprint(request):
    """
    Generate a browser fingerprint from available request data.
    
    This is a basic fingerprint. For production, consider:
    - Adding canvas fingerprinting (client-side)
    - WebGL fingerprinting
    - Audio context fingerprinting
    - Font enumeration
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
    
    # Combine multiple headers for better uniqueness
    fingerprint_data = f"{user_agent}|{accept_language}|{accept_encoding}"
    
    return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:64]


def get_or_create_abuse_record(request):
    """
    Get or create an abuse prevention record for this visitor.
    Uses IP + fingerprint combination for identification.
    """
    try:
        from analytics.models import DemoAbusePrevention
        
        ip_address = get_client_ip(request)
        fingerprint = generate_browser_fingerprint(request)
        
        if not ip_address:
            logger.warning("Could not determine client IP address")
            return None
        
        record, created = DemoAbusePrevention.objects.get_or_create(
            ip_address=ip_address,
            browser_fingerprint=fingerprint,
            defaults={
                'last_seen': timezone.now(),
            }
        )
        
        if not created:
            record.last_seen = timezone.now()
            record.save(update_fields=['last_seen'])
        
        return record
        
    except Exception as e:
        logger.error(f"Error getting abuse prevention record: {e}")
        return None


def check_abuse_status(request):
    """
    Check if this visitor can use demo features.
    
    Returns:
        dict with:
        - allowed: bool
        - reason: str (if not allowed)
        - record: DemoAbusePrevention object
        - warnings: list of warning messages
    """
    record = get_or_create_abuse_record(request)
    
    if not record:
        # If we can't track, allow but log
        logger.warning("Could not create abuse prevention record - allowing access")
        return {
            'allowed': True,
            'reason': None,
            'record': None,
            'warnings': [],
        }
    
    warnings = []
    
    # Check if blocked
    if record.is_blocked:
        return {
            'allowed': False,
            'reason': 'Your access to demo mode has been restricted. Please create a free account to continue.',
            'record': record,
            'warnings': [],
        }
    
    # Check rate limiting
    can_create, rate_message = record.check_rate_limit()
    if not can_create:
        return {
            'allowed': False,
            'reason': rate_message,
            'record': record,
            'warnings': [],
        }
    
    # Check global AI limit
    can_use_ai, ai_message = record.check_ai_limit()
    if not can_use_ai:
        warnings.append(ai_message)
    
    # Check if flagged (still allowed but logged)
    if record.is_flagged:
        logger.info(f"Flagged visitor accessing demo: IP={record.ip_address}, reason={record.flag_reason}")
    
    # Add warnings for approaching limits
    ai_remaining = GLOBAL_DEMO_LIMITS['max_ai_generations_global'] - record.total_ai_generations
    if ai_remaining <= 10 and ai_remaining > 0:
        warnings.append(f"You have {ai_remaining} AI uses remaining across all demo sessions.")
    
    sessions_remaining = GLOBAL_DEMO_LIMITS['max_sessions_total'] - record.total_sessions_created
    if sessions_remaining <= 3 and sessions_remaining > 0:
        warnings.append(f"You can create {sessions_remaining} more demo sessions before needing to sign up.")
    
    return {
        'allowed': True,
        'reason': None,
        'record': record,
        'warnings': warnings,
    }


def check_global_ai_limit(request):
    """
    Check if this visitor can use AI features (global check across all sessions).
    
    VPN users get reduced limits (50%) to minimize abuse potential.
    
    Returns:
        dict with:
        - can_generate: bool
        - current_count: int (global count)
        - max_allowed: int
        - message: str
        - is_vpn_user: bool
    """
    record = get_or_create_abuse_record(request)
    
    if not record:
        # If we can't track, allow but with per-session limits
        return {
            'can_generate': True,
            'current_count': 0,
            'max_allowed': GLOBAL_DEMO_LIMITS['max_ai_generations_global'],
            'message': None,
            'is_global_check': True,
            'is_vpn_user': False,
        }
    
    # Apply reduced limits for VPN users (50% of normal)
    max_allowed = GLOBAL_DEMO_LIMITS['max_ai_generations_global']
    if record.is_vpn_user:
        max_allowed = max_allowed // 2  # 15 instead of 30
    
    current_count = record.total_ai_generations
    can_generate = current_count < max_allowed
    
    if not can_generate:
        message = (
            f"You've used {current_count} AI generations across all demo sessions. "
            f"Create a free account for unlimited AI features!"
        )
    else:
        remaining = max_allowed - current_count
        if remaining <= 10:
            message = f"You have {remaining} AI uses remaining across all demo sessions."
        else:
            message = None
    
    return {
        'can_generate': can_generate,
        'current_count': current_count,
        'max_allowed': max_allowed,
        'message': message,
        'is_global_check': True,
        'is_vpn_user': record.is_vpn_user if record else False,
    }


def check_ai_rate_limit(request):
    """
    Check if this visitor is generating AI content too quickly.
    Implements a sliding window rate limit: max 5 AI calls per 10 minutes.
    
    This prevents rapid abuse even within the global limit.
    
    Returns:
        dict with:
        - allowed: bool
        - wait_seconds: int (seconds to wait if not allowed)
        - message: str
    """
    record = get_or_create_abuse_record(request)
    
    if not record:
        return {'allowed': True, 'wait_seconds': 0, 'message': None}
    
    # Sliding window: max 5 AI calls per 10 minutes
    MAX_CALLS_PER_WINDOW = 5
    WINDOW_MINUTES = 10
    
    # For VPN users, be more restrictive: 3 calls per 10 minutes
    if record.is_vpn_user:
        MAX_CALLS_PER_WINDOW = 3
    
    now = timezone.now()
    window_start = now - timedelta(minutes=WINDOW_MINUTES)
    
    # Get timestamps from the record
    timestamps = record.ai_generation_timestamps or []
    
    # Filter to only recent timestamps within the window
    recent_timestamps = [
        ts for ts in timestamps 
        if isinstance(ts, str) and timezone.datetime.fromisoformat(ts) > window_start
    ]
    
    if len(recent_timestamps) >= MAX_CALLS_PER_WINDOW:
        # Calculate when the oldest call in the window will expire
        oldest_ts = min(recent_timestamps)
        oldest_dt = timezone.datetime.fromisoformat(oldest_ts)
        wait_until = oldest_dt + timedelta(minutes=WINDOW_MINUTES)
        wait_seconds = max(0, int((wait_until - now).total_seconds()))
        
        return {
            'allowed': False,
            'wait_seconds': wait_seconds,
            'message': f"You're using AI features too quickly. Please wait {wait_seconds // 60} minutes and try again."
        }
    
    return {'allowed': True, 'wait_seconds': 0, 'message': None}


def increment_global_ai_count(request, count=1):
    """Increment global AI generation count and record timestamp for rate limiting."""
    record = get_or_create_abuse_record(request)
    if record:
        record.increment_ai_count(count)
        
        # Also record timestamp for rate limiting
        now = timezone.now()
        timestamps = record.ai_generation_timestamps or []
        timestamps.append(now.isoformat())
        
        # Keep only last 20 timestamps to prevent unbounded growth
        if len(timestamps) > 20:
            timestamps = timestamps[-20:]
        
        record.ai_generation_timestamps = timestamps
        record.save(update_fields=['ai_generation_timestamps'])
        
        logger.debug(f"Incremented global AI count: IP={record.ip_address}, total={record.total_ai_generations}")


def increment_global_project_count(request, count=1):
    """Increment global project count for abuse prevention."""
    record = get_or_create_abuse_record(request)
    if record:
        record.increment_project_count(count)
        logger.debug(f"Incremented global project count: IP={record.ip_address}, total={record.total_projects_created}")


def register_new_session(request, session_id):
    """
    Register a new demo session for abuse tracking.
    Call this when a new demo session is created.
    """
    record = get_or_create_abuse_record(request)
    if record:
        # Add session ID to list
        if session_id not in record.session_ids:
            record.session_ids = record.session_ids + [session_id]
        
        record.increment_session_count()
        
        logger.info(
            f"New demo session registered: IP={record.ip_address}, "
            f"session={session_id[:8]}..., total_sessions={record.total_sessions_created}"
        )
        
        return True
    return False


def can_create_demo_session(request):
    """
    Check if this visitor can create a new demo session.
    Use this before allowing demo mode entry.
    
    Also checks for VPN/proxy usage and adjusts limits accordingly.
    VPN users get reduced limits (50%) to minimize abuse potential
    while still allowing legitimate VPN users to try the demo.
    
    Returns:
        tuple: (allowed: bool, message: str or None)
    """
    status = check_abuse_status(request)
    
    if not status['allowed']:
        return False, status['reason']
    
    record = status['record']
    
    # Check for VPN/proxy usage
    is_vpn = False
    try:
        from kanban.utils.vpn_detection import is_datacenter_ip
        ip_address = get_client_ip(request)
        is_vpn = is_datacenter_ip(ip_address)
        
        if is_vpn and record:
            # Mark the record as VPN user
            if not record.is_vpn_user:
                record.is_vpn_user = True
                record.save(update_fields=['is_vpn_user'])
            logger.info(f"VPN/datacenter IP detected: {ip_address}")
    except Exception as e:
        logger.warning(f"Could not check VPN status: {e}")
    
    if record:
        # For VPN users, apply stricter session limits (50% reduction)
        max_sessions = GLOBAL_DEMO_LIMITS['max_sessions_total']
        if is_vpn or record.is_vpn_user:
            max_sessions = max_sessions // 2  # 10 instead of 20
        
        if record.total_sessions_created >= max_sessions:
            return False, (
                "You've used demo mode many times. "
                "Create a free account to get unlimited access!"
            )
    
    return True, None


def get_abuse_summary(request):
    """
    Get a summary of abuse prevention status for this visitor.
    Useful for debugging and admin views.
    """
    record = get_or_create_abuse_record(request)
    
    if not record:
        return {
            'tracked': False,
            'message': 'Could not establish tracking',
        }
    
    return {
        'tracked': True,
        'ip_address': record.ip_address,
        'fingerprint': record.browser_fingerprint[:8] + '...' if record.browser_fingerprint else None,
        'total_sessions': record.total_sessions_created,
        'total_ai_generations': record.total_ai_generations,
        'total_projects': record.total_projects_created,
        'is_flagged': record.is_flagged,
        'flag_reason': record.flag_reason,
        'is_blocked': record.is_blocked,
        'first_seen': record.first_seen,
        'last_seen': record.last_seen,
        'ai_remaining': GLOBAL_DEMO_LIMITS['max_ai_generations_global'] - record.total_ai_generations,
        'sessions_remaining': GLOBAL_DEMO_LIMITS['max_sessions_total'] - record.total_sessions_created,
    }


# Admin utilities

def flag_abuser(ip_address, reason):
    """Flag an IP address as suspicious."""
    try:
        from analytics.models import DemoAbusePrevention
        
        records = DemoAbusePrevention.objects.filter(ip_address=ip_address)
        count = records.update(is_flagged=True, flag_reason=reason)
        logger.warning(f"Flagged {count} records for IP {ip_address}: {reason}")
        return count
    except Exception as e:
        logger.error(f"Error flagging abuser: {e}")
        return 0


def block_abuser(ip_address, reason):
    """Block an IP address from demo access."""
    try:
        from analytics.models import DemoAbusePrevention
        
        records = DemoAbusePrevention.objects.filter(ip_address=ip_address)
        count = records.update(is_blocked=True, is_flagged=True, flag_reason=reason)
        logger.warning(f"Blocked {count} records for IP {ip_address}: {reason}")
        return count
    except Exception as e:
        logger.error(f"Error blocking abuser: {e}")
        return 0


def unblock_ip(ip_address):
    """Unblock an IP address."""
    try:
        from analytics.models import DemoAbusePrevention
        
        records = DemoAbusePrevention.objects.filter(ip_address=ip_address)
        count = records.update(is_blocked=False)
        logger.info(f"Unblocked {count} records for IP {ip_address}")
        return count
    except Exception as e:
        logger.error(f"Error unblocking IP: {e}")
        return 0


def get_abuse_stats():
    """Get statistics on demo abuse prevention."""
    try:
        from analytics.models import DemoAbusePrevention
        from django.db.models import Sum, Avg, Count, Q
        
        stats = DemoAbusePrevention.objects.aggregate(
            total_records=Count('id'),
            total_flagged=Count('id', filter=Q(is_flagged=True)),
            total_blocked=Count('id', filter=Q(is_blocked=True)),
            total_ai_used=Sum('total_ai_generations'),
            avg_sessions_per_visitor=Avg('total_sessions_created'),
        )
        
        # High-usage visitors (potential abusers)
        high_usage = DemoAbusePrevention.objects.filter(
            total_sessions_created__gte=5
        ).count()
        
        stats['high_usage_visitors'] = high_usage
        
        return stats
    except Exception as e:
        logger.error(f"Error getting abuse stats: {e}")
        return {}
