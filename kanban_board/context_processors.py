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
    """Add user AI preferences and display mode to template context"""
    if request.user.is_authenticated:
        try:
            from ai_assistant.models import UserPreference
            user_pref = UserPreference.objects.get(user=request.user)
            ai_prefs = user_pref
        except UserPreference.DoesNotExist:
            ai_prefs = None

        try:
            display_mode = request.user.profile.display_mode or 'light'
        except Exception:
            display_mode = 'light'

        nav_ai_provider_key = ''
        nav_ai_provider_name = ''
        try:
            from ai_assistant.utils.ai_router import AIRouter
            _provider, _, _ = AIRouter()._resolve_provider(request.user)
            nav_ai_provider_key = _provider  # 'gemini', 'openai', 'anthropic'
            _short_names = {'gemini': 'Gemini', 'openai': 'OpenAI', 'anthropic': 'Claude'}
            nav_ai_provider_name = _short_names.get(_provider, _provider.title())
        except Exception:
            pass

        return {
            'user_ai_preferences': ai_prefs,
            'user_display_mode': display_mode,
            'nav_ai_provider_key': nav_ai_provider_key,
            'nav_ai_provider_name': nav_ai_provider_name,
        }
    return {
        'user_ai_preferences': None,
        'user_display_mode': 'light',
        'nav_ai_provider_key': '',
        'nav_ai_provider_name': '',
    }


def user_timezone(request):
    """Add user timezone to template context for the timezone selector."""
    if request.user.is_authenticated:
        tz = request.session.get('user_timezone')
        if not tz:
            try:
                tz = request.user.profile.timezone
            except Exception:
                tz = 'Asia/Kolkata'
        return {'user_timezone': tz}
    return {'user_timezone': 'Asia/Kolkata'}

