"""
Base Context Provider — RBAC-enforced, sandbox-aware foundation.

Every Spectra context provider inherits from ``BaseContextProvider``.
Security is baked in at this layer so individual providers never need
to worry about access control: if the user can't read the board, the
provider silently returns empty strings.

Architecture
~~~~~~~~~~~~
::

    BaseContextProvider
      ├── get_summary(board, user)  → 2-5 lines, ALWAYS included
      ├── get_detail(board, user, query) → full context, loaded on demand
      └── RBAC + sandbox checks in _check_access()

    ContextProviderRegistry
      ├── auto-discovers all providers
      ├── get_all_summaries(board, user)       → compact always-on context
      └── get_relevant_details(board, user, q) → detailed context for matched providers

Created: April 16, 2026 — Spectra Context Provider Overhaul
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseContextProvider(ABC):
    """
    Abstract base for all Spectra feature context providers.

    RBAC and sandbox enforcement is centralised here — subclasses only
    implement ``_get_summary_impl`` and ``_get_detail_impl``.

    Class attributes that subclasses MUST define:
        PROVIDER_NAME  (str):  Human-readable name, e.g. "Board Tasks"
        FEATURE_TAGS   (list): Keywords that signal relevance, e.g. ['task', 'assigned', 'column']
    """

    PROVIDER_NAME: str = ''
    FEATURE_TAGS: list = []

    # ── Public API (callers use these) ──────────────────────────────────

    def get_summary(self, board, user, is_demo_mode=False):
        """
        Return a compact 2-5 line summary of this feature's state.

        Always called for every query to provide baseline awareness.
        Returns empty string if user lacks access.
        """
        if not self._check_access(board, user, is_demo_mode):
            return ''
        try:
            return self._get_summary_impl(board, user, is_demo_mode) or ''
        except Exception as e:
            logger.warning(
                'Context provider %s summary failed: %s',
                self.PROVIDER_NAME, e,
            )
            return f'⚠️ {self.PROVIDER_NAME} data temporarily unavailable.\n'

    def get_detail(self, board, user, query='', is_demo_mode=False):
        """
        Return detailed context for this feature (only when relevant).

        Called by the router when the query matches this provider's tags.
        Returns empty string if user lacks access.
        """
        if not self._check_access(board, user, is_demo_mode):
            return ''
        try:
            return self._get_detail_impl(board, user, query, is_demo_mode) or ''
        except Exception as e:
            logger.warning(
                'Context provider %s detail failed: %s',
                self.PROVIDER_NAME, e,
            )
            return f'⚠️ {self.PROVIDER_NAME} detailed data temporarily unavailable.\n'

    # ── Security layer (RBAC + sandbox) ─────────────────────────────────

    def _check_access(self, board, user, is_demo_mode=False):
        """
        Centralised access gate.  Returns True only when user may see data.

        - No user → deny
        - Board provided → RBAC read check + sandbox isolation
        - No board → allow (cross-board providers handle their own filtering)
        """
        if not user or not user.is_authenticated:
            return False

        if board is None:
            # Cross-board / dashboard context — providers filter internally
            return True

        # ── Sandbox isolation ───────────────────────────────────────────
        if is_demo_mode:
            if getattr(board, 'is_official_demo_board', False):
                return True
            if (
                getattr(board, 'is_sandbox_copy', False)
                and board.owner_id == user.id
            ):
                return True
            if (
                getattr(board, 'created_by_session', '')
                == f'spectra_demo_{user.id}'
            ):
                return True
            # Demo mode but board doesn't belong to this user's sandbox
            return False

        # ── Standard RBAC read check ────────────────────────────────────
        from ai_assistant.utils.rbac_utils import can_spectra_read_board
        return can_spectra_read_board(user, board)

    # ── Helpers available to all subclasses ──────────────────────────────

    def _get_user_role(self, board, user):
        """Return the user's role on the board (owner/member/viewer/None)."""
        if not board or not user:
            return None
        from ai_assistant.utils.rbac_utils import get_user_board_role
        return get_user_board_role(user, board)

    def _get_accessible_boards(self, user, is_demo_mode=False):
        """Return queryset of boards the user can access (workspace-aware)."""
        from ai_assistant.utils.rbac_utils import get_accessible_boards_for_spectra
        org = None
        try:
            if hasattr(user, 'profile') and user.profile.organization_id:
                org = user.profile.organization
        except Exception:
            pass
        return get_accessible_boards_for_spectra(
            user, is_demo_mode=is_demo_mode, organization=org,
        )

    def _get_user_org(self, user):
        """Return the user's organization, or None."""
        try:
            if hasattr(user, 'profile') and user.profile.organization_id:
                return user.profile.organization
        except Exception:
            pass
        return None

    # ── Abstract methods (subclasses implement these) ───────────────────

    @abstractmethod
    def _get_summary_impl(self, board, user, is_demo_mode=False):
        """Return compact summary string. Board may be None for cross-board."""
        ...

    @abstractmethod
    def _get_detail_impl(self, board, user, query='', is_demo_mode=False):
        """Return detailed context string. Board may be None for cross-board."""
        ...
