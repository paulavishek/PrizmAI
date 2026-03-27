"""
PrizmAI RBAC — reusable decorators.

demo_write_guard: blocks any state-changing request (POST/PUT/PATCH/DELETE)
from demo login accounts (is_demo_account=True on UserProfile) AND from
real users viewing the read-only demo workspace (is_viewing_demo=True).

demo_ai_guard: blocks AI generation API calls for users viewing the
read-only demo workspace (is_viewing_demo=True).  Returns a 403 with
sandbox upsell messaging.
"""
import functools
from django.http import JsonResponse, HttpResponseForbidden


_DEMO_BLOCK_MESSAGE = (
    "Demo accounts are read-only. "
    "Sign up for a free account to create and edit content."
)

_DEMO_VIEWER_BLOCK_MESSAGE = (
    "Demo data is read-only. "
    "Launch your private Sandbox to create or edit content."
)

_DEMO_AI_BLOCK_MESSAGE = (
    "Want to see Spectra AI in action? "
    "Launch your private Sandbox to unlock AI capabilities and interact with this data."
)

_WRITE_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})


def _is_ajax_or_api(request):
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.content_type == 'application/json'
        or request.path.startswith('/api/')
    )


def demo_write_guard(view_func):
    """
    Block write requests (POST/PUT/PATCH/DELETE) from:
    1. Demo login accounts (is_demo_account=True)
    2. Real users viewing read-only demo (is_viewing_demo=True)

    Read requests (GET/HEAD/OPTIONS) pass through unaffected.

    Usage::

        @login_required
        @demo_write_guard
        def my_write_view(request, ...):
            ...
    """
    @functools.wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.method in _WRITE_METHODS and request.user.is_authenticated:
            try:
                profile = request.user.profile

                # Block 1: demo login accounts (virtual showcases)
                if getattr(profile, 'is_demo_account', False):
                    if _is_ajax_or_api(request):
                        return JsonResponse({'error': _DEMO_BLOCK_MESSAGE, 'demo_blocked': True}, status=403)
                    return HttpResponseForbidden(_DEMO_BLOCK_MESSAGE)

                # Block 2: real users in Tier-1 read-only demo view
                if getattr(profile, 'is_viewing_demo', False) and not request.session.get('in_sandbox', False):
                    if _is_ajax_or_api(request):
                        return JsonResponse({
                            'error': _DEMO_VIEWER_BLOCK_MESSAGE,
                            'demo_readonly': True,
                            'show_sandbox_cta': True,
                        }, status=403)
                    return HttpResponseForbidden(_DEMO_VIEWER_BLOCK_MESSAGE)
            except AttributeError:
                pass  # No profile attached — let the view handle it normally
        return view_func(request, *args, **kwargs)
    return _wrapped


def demo_ai_guard(view_func):
    """
    Block AI generation API calls for users in Tier-1 read-only demo.

    Returns a 403 JSON response with sandbox upsell messaging so the
    frontend can display the "Launch Sandbox" prompt.

    Usage::

        @login_required
        @demo_ai_guard
        def my_ai_endpoint(request, ...):
            ...
    """
    @functools.wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.is_authenticated:
            try:
                profile = request.user.profile
                if getattr(profile, 'is_viewing_demo', False) and not request.session.get('in_sandbox', False):
                    return JsonResponse({
                        'error': _DEMO_AI_BLOCK_MESSAGE,
                        'demo_readonly': True,
                        'ai_blocked': True,
                        'show_sandbox_cta': True,
                    }, status=403)
            except AttributeError:
                pass
        return view_func(request, *args, **kwargs)
    return _wrapped
