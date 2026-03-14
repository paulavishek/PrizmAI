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
