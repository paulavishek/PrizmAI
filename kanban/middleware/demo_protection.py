"""
DemoProtectionMiddleware — activates model-level demo guards for web requests.

1. Sets a thread-local flag so pre_save / pre_delete signals know we are
   inside an HTTP request (management commands & Celery remain unaffected).
2. Catches ``DemoProtectionError`` and returns a user-friendly 403.
"""
import logging

from django.http import JsonResponse, HttpResponseForbidden

from kanban.utils.demo_protection import (
    mark_web_request,
    unmark_web_request,
    DemoProtectionError,
)

logger = logging.getLogger(__name__)

_DEMO_BLOCK_HTML = (
    '<div style="text-align:center;padding:60px 20px;font-family:system-ui,sans-serif">'
    '<h2 style="color:#e74c3c">Demo Data Is Read-Only</h2>'
    '<p>This is demo data and cannot be modified.</p>'
    '<p>Create your own boards and tasks to get started!</p>'
    '</div>'
)


class DemoProtectionMiddleware:
    """
    Activates demo-data immutability for every HTTP request.

    Must be placed **after** AuthenticationMiddleware in MIDDLEWARE so that
    ``request.user`` is available (not used here, but downstream signals
    may inspect it).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        mark_web_request()
        try:
            response = self.get_response(request)
        except DemoProtectionError as exc:
            return self._forbidden_response(request, str(exc))
        finally:
            unmark_web_request()
        return response

    # Django calls process_exception for errors raised inside the view;
    # __call__ catches errors raised in other middleware layers.
    def process_exception(self, request, exception):
        if isinstance(exception, DemoProtectionError):
            return self._forbidden_response(request, str(exception))
        return None

    @staticmethod
    def _forbidden_response(request, message):
        is_ajax = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or getattr(request, 'content_type', '') == 'application/json'
            or request.path.startswith('/api/')
        )
        if is_ajax:
            return JsonResponse(
                {'error': message, 'demo_blocked': True},
                status=403,
            )
        return HttpResponseForbidden(_DEMO_BLOCK_HTML)
