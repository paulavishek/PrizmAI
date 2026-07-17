"""Shared workspace-scoping helpers for the wiki app.

Workspace is the tenant boundary now (org is retired from access scoping).
Both the page views (``wiki/views.py``) and the AI-analysis API
(``wiki/api_views.py``) gate wiki content through ``wiki_scope_q`` so the two
surfaces can never disagree.
"""
from django.db.models import Q


def wiki_scope_q(request):
    """Q filter scoping wiki objects to the request user's active WORKSPACE.

    This is the single source of truth for wiki visibility - the page views
    (``wiki/views.py``), the category listings, and the AI-analysis API
    (``wiki/api_views.py``) all gate through it so the surfaces can never
    disagree.

    Real mode scopes strictly to the active workspace (fails closed when there
    is none).

    Demo mode is the single shared demo workspace, so scoping by workspace alone
    would let every demo user see (and edit) every other demo user's wiki
    content. Isolation instead comes from cloning the demo wiki per user
    (``sandbox_owner=user``) - the same model Discovery uses - so demo reads are
    scoped to the current user's own clones and never touch the shared templates
    (``sandbox_owner IS NULL``) or another user's copies. See
    project_demo_sandbox_isolation_model. The clone is (re)built on
    provision/reset by ``_clone_wiki_for_user``; the Knowledge Hub self-heals an
    empty clone set on first visit.
    """
    profile = getattr(request.user, 'profile', None)
    ws = getattr(profile, 'active_workspace', None)
    is_demo = getattr(profile, 'is_viewing_demo', False)
    if is_demo:
        # Per-user sandbox isolation: only the current user's cloned wiki rows.
        return Q(sandbox_owner=request.user)
    if ws is not None:
        # Real content never carries a sandbox_owner; the extra clause keeps any
        # stray demo clone (shared demo workspace) out of a real workspace view.
        return Q(workspace=ws, sandbox_owner__isnull=True)
    return Q(pk__in=[])
