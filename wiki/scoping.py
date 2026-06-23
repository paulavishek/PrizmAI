"""Shared workspace-scoping helpers for the wiki app.

Workspace is the tenant boundary now (org is retired from access scoping).
Both the page views (``wiki/views.py``) and the AI-analysis API
(``wiki/api_views.py``) gate wiki content through ``wiki_scope_q`` so the two
surfaces can never disagree.
"""
from django.db.models import Q


def wiki_scope_q(request):
    """Q filter scoping wiki objects to the request user's active WORKSPACE.

    Real mode scopes strictly to the active workspace (fails closed when there
    is none); demo mode additionally surfaces legacy null-workspace seed rows.
    """
    profile = getattr(request.user, 'profile', None)
    ws = getattr(profile, 'active_workspace', None)
    is_demo = getattr(profile, 'is_viewing_demo', False)
    if ws is not None:
        if is_demo:
            return Q(workspace=ws) | Q(workspace__isnull=True)
        return Q(workspace=ws)
    return Q(pk__in=[])
