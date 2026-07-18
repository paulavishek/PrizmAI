"""Demo per-user scoping for CustomFieldDefinition.

CustomFieldDefinition is workspace-scoped, but the demo workspace is shared by
every demo user, so scoping by ``workspace`` alone lets each demo user see (and
edit/delete) every other demo user's fields. Isolation instead comes from
cloning the demo field set per user (``sandbox_owner=user``) - the same model
Discovery and the Wiki use (see ``wiki/scoping.py`` and
project_demo_sandbox_isolation_model). The clone is (re)built on provision/reset
by ``kanban.sandbox_views._clone_custom_fields_for_user``.

Two scoping surfaces funnel through here so they can never disagree:

* **Management UI** (``custom_field_views.py``) - request/user-driven, exactly
  like the wiki: scope to the requesting user's own clones in demo.
* **Task -> field resolution** (``custom_field_serializers.py``,
  ``custom_field_filters.py``, coach/AI contexts) - board-driven: the fields a
  task shows must belong to the SANDBOX BOARD OWNER, not the viewer, so a demo
  persona browsing a teammate's sandbox board sees that owner's fields (matching
  how every other board-scoped feature is owner-scoped).

Real workspaces always have ``sandbox_owner IS NULL``; the null clause keeps any
stray demo clone (shared demo workspace) out of a real-workspace view.
"""
from django.db.models import Q


def _demo_owner_for_board(board):
    """Return the user whose custom-field clones a sandbox board should show.

    A sandbox copy is owned by exactly one demo user; the board's tasks must
    resolve that owner's cloned fields. Non-sandbox (real or official-template)
    boards return None -> caller uses the ``sandbox_owner IS NULL`` templates.
    """
    if board is None:
        return None
    if getattr(board, 'is_sandbox_copy', False):
        return getattr(board, 'owner', None)
    return None


def custom_field_scope_q_for_user(user):
    """Q filter for the management UI: the user's own clones in demo, else
    real-workspace templates (``sandbox_owner IS NULL``).

    Only the demo/real discriminator matters here; the caller still ANDs in the
    ``workspace=`` filter (the management UI is always workspace-addressed).
    """
    from kanban.utils.demo_protection import user_is_demo
    if user_is_demo(user):
        return Q(sandbox_owner=user)
    return Q(sandbox_owner__isnull=True)


def custom_field_scope_q_for_board(board):
    """Q filter for the task->field resolution path, driven by the board owner.

    On a sandbox board, show the board owner's cloned fields
    (``sandbox_owner=owner``); everywhere else show the shared/real templates
    (``sandbox_owner IS NULL``). This makes a demo persona viewing a teammate's
    sandbox board see that teammate's fields, matching board-data ownership.
    """
    owner = _demo_owner_for_board(board)
    if owner is not None:
        return Q(sandbox_owner=owner)
    return Q(sandbox_owner__isnull=True)
