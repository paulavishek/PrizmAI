"""
Demo Mode Configuration Settings
Centralized location for all demo mode limits and settings

Update these values to change demo behavior across the application.

SIMPLIFIED MODE (January 2026):
- Single authenticated environment (no demo/real distinction)
- All users get same limits
- No VPN penalties
- No Solo/Team mode selection
- Pre-populated demo data for new users
"""

# ============================================================================
# SIMPLIFIED MODE FLAG
# When True, uses simplified single-environment access control
# When False, uses legacy demo mode with Solo/Team selection
# ============================================================================
SIMPLIFIED_MODE = True


# ============================================================================
# PROJECT & AI LIMITS (Same for all users in simplified mode)
# ============================================================================

# Maximum projects a user can create (simplified: no limit)
DEMO_PROJECT_LIMIT = 999 if SIMPLIFIED_MODE else 2

# Maximum AI generations allowed per month
DEMO_AI_GENERATION_LIMIT = 50 if SIMPLIFIED_MODE else 20

# Daily AI limit
DAILY_AI_LIMIT = 10

# Whether exports are allowed (simplified: yes)
DEMO_ALLOW_EXPORTS = True if SIMPLIFIED_MODE else False

# Rate limiting: max AI requests per 10 minutes
AI_RATE_LIMIT_REQUESTS = 5
AI_RATE_LIMIT_WINDOW_MINUTES = 10


# ============================================================================
# VPN DETECTION SETTINGS (Simplified: detect but don't penalize)
# ============================================================================

# Whether to apply VPN penalties (reduced limits)
# In simplified mode, we detect VPNs for analytics only, no penalties
APPLY_VPN_PENALTIES = False if SIMPLIFIED_MODE else True

# VPN penalty multiplier (0.5 = 50% of normal limits)
VPN_PENALTY_MULTIPLIER = 1.0 if SIMPLIFIED_MODE else 0.5


# ============================================================================
# ANTI-ABUSE SETTINGS
# ============================================================================

# Maximum number of demo sessions from same IP/browser fingerprint
MAX_SESSIONS_PER_FINGERPRINT = 5

# How long before allowing new demo session from same fingerprint (hours)
FINGERPRINT_COOLDOWN_HOURS = 24

# Maximum number of demo resets per session
MAX_DEMO_RESETS = 3


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_limit_settings():
    """Return all demo limit settings as a dictionary."""
    return {
        'project_limit': DEMO_PROJECT_LIMIT,
        'ai_generation_limit': DEMO_AI_GENERATION_LIMIT,
        'allow_exports': DEMO_ALLOW_EXPORTS,
    }


def get_all_settings():
    """Return all demo settings as a dictionary."""
    return {
        'limits': get_limit_settings(),
        'max_sessions_per_fingerprint': MAX_SESSIONS_PER_FINGERPRINT,
        'fingerprint_cooldown_hours': FINGERPRINT_COOLDOWN_HOURS,
        'max_demo_resets': MAX_DEMO_RESETS,
    }
