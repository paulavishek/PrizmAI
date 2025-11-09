from django.conf import settings

def static_version(request):
    """Add STATIC_VERSION to template context for cache busting"""
    return {
        'STATIC_VERSION': getattr(settings, 'STATIC_VERSION', '1')
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
