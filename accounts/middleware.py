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

                # ── Consistency guard ──────────────────────────────────
                # Detect and auto-repair state corruption where
                # is_viewing_demo is True but active_workspace is None
                # or belongs to the wrong workspace type.
                self._heal_workspace_state(profile)

                ws = profile.active_workspace  # re-read after potential heal
                if ws and ws.is_active:
                    request.workspace = ws
                elif profile.organization and not profile.is_viewing_demo:
                    # User has an org but no active workspace — lazily create one.
                    # This catches the "manual setup" and import-first paths.
                    from kanban.workspace_utils import get_or_create_real_workspace
                    ws = get_or_create_real_workspace(request.user)
                    if ws:
                        request.workspace = ws
            except Exception:
                pass

        response = self.get_response(request)
        return response

    @staticmethod
    def _heal_workspace_state(profile):
        """Detect and auto-repair demo/workspace state inconsistencies.

        Known corruption patterns:
          1. is_viewing_demo=True but active_workspace is None
          2. is_viewing_demo=True but active_workspace.is_demo is False
          3. is_viewing_demo=False but org is the demo org
          4. is_viewing_demo=True but org is NOT the demo org (and no demo ws)
        """
        import logging
        _log = logging.getLogger('accounts.middleware')

        try:
            is_demo = profile.is_viewing_demo
            ws = profile.active_workspace
            org = profile.organization

            if is_demo and (ws is None or (ws and not ws.is_demo)):
                # Pattern 1 & 2: in demo but workspace is wrong/missing
                from kanban.utils.demo_protection import get_demo_workspace
                demo_ws = get_demo_workspace()
                if demo_ws:
                    profile.active_workspace = demo_ws
                    profile.save(update_fields=['active_workspace'])
                    _log.warning(
                        "Healed workspace state for user %s: set active_workspace to demo",
                        profile.user_id,
                    )
                else:
                    # No demo workspace exists — exit demo mode
                    profile.is_viewing_demo = False
                    profile.save(update_fields=['is_viewing_demo'])
                    _log.warning(
                        "Healed workspace state for user %s: exited demo (no demo ws)",
                        profile.user_id,
                    )

            elif not is_demo and org and getattr(org, 'is_demo', False):
                # Pattern 3: not in demo but org is still demo org
                from kanban.models import Workspace
                from accounts.models import Organization
                real_ws = Workspace.objects.filter(
                    created_by=profile.user, is_demo=False, is_active=True,
                ).order_by('-created_at').first()
                real_org = (
                    real_ws.organization if real_ws and real_ws.organization
                    else Organization.objects.filter(
                        created_by=profile.user, is_demo=False,
                    ).order_by('-id').first()
                )
                fields = []
                if real_org:
                    profile.organization = real_org
                    fields.append('organization')
                if real_ws:
                    profile.active_workspace = real_ws
                    fields.append('active_workspace')
                if fields:
                    profile.save(update_fields=fields)
                    _log.warning(
                        "Healed workspace state for user %s: restored real org/ws",
                        profile.user_id,
                    )
        except Exception:
            pass  # Never break requests
