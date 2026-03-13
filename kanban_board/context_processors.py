from django.conf import settings

def static_version(request):
    """Add STATIC_VERSION to template context for cache busting"""
    return {
        'STATIC_VERSION': getattr(settings, 'STATIC_VERSION', '1'),
        'GA4_MEASUREMENT_ID': getattr(settings, 'GA4_MEASUREMENT_ID', ''),
    }


def force_auth_layout(request):
    """Force unauthenticated layout on social-auth pages so the sidebar
    never appears during OAuth flows, even if the user has an active session."""
    auth_paths = ('/accounts/google/', '/accounts/social/')
    return {
        'force_auth_layout': request.path.startswith(auth_paths),
    }


def user_preferences(request):
    """Add user AI preferences to template context"""
    if request.user.is_authenticated:
        try:
            from ai_assistant.models import UserPreference
            user_pref = UserPreference.objects.get(user=request.user)
            return {
                'user_ai_preferences': user_pref
            }
        except UserPreference.DoesNotExist:
            pass
    return {
        'user_ai_preferences': None
    }

