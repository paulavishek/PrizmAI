"""
PrizmAI RBAC — reusable decorators.

demo_write_guard: blocks any state-changing request (POST/PUT/PATCH/DELETE)
from demo login accounts (is_demo_account=True on UserProfile).  These
accounts are read-only showcases — they have zero create/edit/delete
access and zero AI access.
"""
import functools
from django.http import JsonResponse, HttpResponseForbidden


_DEMO_BLOCK_MESSAGE = (
    "Demo accounts are read-only. "
    "Sign up for a free account to create and edit content."
)

_WRITE_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})


def demo_write_guard(view_func):
    """
    Block write requests (POST/PUT/PATCH/DELETE) from demo login accounts.

    If the user's UserProfile.is_demo_account is True and the request
    method is a mutating one, return:
    - A JSON 403 response for AJAX / API requests
    - An HTML 403 Forbidden response for regular page requests

    Read requests (GET/HEAD/OPTIONS) pass through unaffected so that demo
    accounts can still view all content they have access to.

    Usage::

        @login_required
        @demo_write_guard
        def my_write_view(request, ...):
            ...
    """
    @functools.wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.method in _WRITE_METHODS:
            try:
                if request.user.is_authenticated and request.user.profile.is_demo_account:
                    if (
                        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                        or request.content_type == 'application/json'
                        or request.path.startswith('/api/')
                    ):
                        return JsonResponse({'error': _DEMO_BLOCK_MESSAGE, 'demo_blocked': True}, status=403)
                    return HttpResponseForbidden(_DEMO_BLOCK_MESSAGE)
            except AttributeError:
                pass  # No profile attached — let the view handle it normally
        return view_func(request, *args, **kwargs)
    return _wrapped
