"""
Defense-in-depth board / task access enforcement.

Many board-scoped views correctly gate access with the canonical rules
predicate::

    is_demo_context(request, board) OR request.user.has_perm('prizmai.view_board', board)

…but a number of secondary dashboards/APIs (scope, burndown, forecasting,
retrospective, resource-leveling, premortem, scope-autopsy, coach, …) historically
fetched the board straight from the URL ``board_id`` and rendered its data with
**no** access check — a cross-tenant read/write exposure (e.g. an attacker
enumerating ``/boards/<id>/scope/``).

Rather than retrofit ~70 individual views (and miss future ones), this middleware
enforces the *same* canonical gate at a single chokepoint, in ``process_view`` —
so it sees the resolved URL kwargs. It is a backstop:

  * Views that already check are unaffected (identical predicate → identical result).
  * Views that forgot to check are now covered.

It deliberately mirrors ``kanban.views.board_detail`` exactly, so a user who can
open a board's main page can open all of its sub-views, and one who cannot, cannot.

Scope: only ``board_id`` / ``task_id`` / ``column_id`` URL kwargs are enforced.
``pk`` is intentionally NOT treated as a board id — it is overloaded across the app
(missions, goals, strategies, …) and treating it as a board would misfire.
"""

import logging

logger = logging.getLogger(__name__)

# Views that legitimately operate on a board the requesting user may NOT yet be
# able to view, and therefore must NOT be gated by view_board:
#   * join_board — runs its own workspace-scoped, fail-closed join logic.
# (Access-request submission reads board_id from the POST body, not a URL kwarg,
#  so it never reaches the resolver here.)
WHITELIST_VIEW_NAMES = frozenset({
    'join_board',
})


class BoardAccessEnforcementMiddleware:
    """Enforce ``view_board`` on every board/task/column-scoped view."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = getattr(request, 'user', None)
        # Anonymous users are handled by each view's own @login_required (HTML)
        # or DRF authentication (which runs in the view, after this middleware),
        # so we never see an authenticated DRF token user here — skip them.
        if user is None or not user.is_authenticated:
            return None

        if getattr(view_func, '__name__', '') in WHITELIST_VIEW_NAMES:
            return None

        board = self._resolve_board(view_kwargs)
        if board is None:
            return None  # not a board-scoped view (or id doesn't resolve) → let the view 404

        # Mirror board_detail exactly: demo context bypasses RBAC; otherwise the
        # canonical view_board predicate decides.
        try:
            from kanban.permissions import is_demo_context
            if is_demo_context(request, board=board):
                return None
            if request.user.has_perm('prizmai.view_board', board):
                return None
        except Exception:
            # Never let an enforcement bug 500 the whole site; fall through to deny
            # only if we positively resolved a board the user couldn't be cleared for.
            logger.exception("Board access enforcement check errored for board %s", getattr(board, 'id', '?'))
            # Be conservative: if we cannot evaluate access, deny (fail closed).

        from kanban.simple_access import _spectra_denial_response
        return _spectra_denial_response(request, board, trigger='board_view')

    @staticmethod
    def _resolve_board(kwargs):
        """Resolve the kanban Board a request is scoped to, or None.

        Returns None (skip enforcement) when the id does not resolve to a Board —
        this keeps the middleware inert for unrelated views that happen to share a
        kwarg name but whose id is not a kanban board.
        """
        from kanban.models import Board, Task, Column
        try:
            if 'board_id' in kwargs:
                return (Board.objects
                        .filter(id=kwargs['board_id'])
                        .select_related('workspace')
                        .first())
            if 'task_id' in kwargs:
                task = (Task.objects
                        .filter(id=kwargs['task_id'])
                        .select_related('column__board__workspace')
                        .first())
                return task.column.board if task and task.column_id else None
            if 'column_id' in kwargs:
                col = (Column.objects
                       .filter(id=kwargs['column_id'])
                       .select_related('board__workspace')
                       .first())
                return col.board if col else None
        except Exception:
            return None
        return None
