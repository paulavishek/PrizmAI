import pytz
from django.utils import timezone


class TimezoneMiddleware:
    """
    Activate the user's preferred timezone for each request.

    Once activated, all Django template date/time filters and
    ``timezone.localtime()`` calls automatically convert UTC datetimes
    to the user's timezone for the duration of the request.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tzname = None

        if request.user.is_authenticated:
            # Try session cache first to avoid a DB hit on every request
            tzname = request.session.get('user_timezone')
            if not tzname:
                try:
                    tzname = request.user.profile.timezone
                except Exception:
                    tzname = None
                if tzname:
                    request.session['user_timezone'] = tzname

        if tzname:
            try:
                timezone.activate(pytz.timezone(tzname))
            except pytz.UnknownTimeZoneError:
                timezone.deactivate()
        else:
            timezone.deactivate()

        response = self.get_response(request)
        return response


class WorkspaceMiddleware:
    """
    Resolve ``request.workspace`` from the authenticated user's
    ``profile.active_workspace``.

    This gives every view access to ``request.workspace`` (a Workspace
    instance or None).  Views that support workspace-scoping can filter
    their querysets by ``workspace=request.workspace``.

    The middleware is intentionally lightweight — it does NOT enforce
    that a workspace must be set, and it does NOT redirect users.  Views
    decide how to interpret a None workspace.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.workspace = None

        if request.user.is_authenticated:
            try:
                profile = request.user.profile
                ws = profile.active_workspace
                if ws and ws.is_active:
                    request.workspace = ws
            except Exception:
                pass

        response = self.get_response(request)
        return response
