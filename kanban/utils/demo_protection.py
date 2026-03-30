"""
Demo Data Utilities — identification helpers for demo objects.

The pre_save/pre_delete signal-based immutability layer has been removed
as part of the single-tier personal demo refactor.  Each user now gets
their own private copy of demo data (sandbox), so server-side write
blocking is no longer needed.

Retained:
  - ``is_demo_object()`` — Used by various views to identify template data.
  - ``allow_demo_writes()`` — Context manager still used by sandbox
    provisioning code that creates copies of demo templates.
"""

import threading
import logging
from contextlib import contextmanager

from django.db.models import Q

logger = logging.getLogger(__name__)

# ── Thread-local state (kept for allow_demo_writes) ──────────────────────────

_local = threading.local()


def _bypass_active():
    return getattr(_local, 'demo_bypass', False)


@contextmanager
def allow_demo_writes():
    """Temporarily mark that we are performing a legitimate demo-data operation."""
    prev = getattr(_local, 'demo_bypass', False)
    _local.demo_bypass = True
    try:
        yield
    finally:
        _local.demo_bypass = prev


# ── Centralised board queryset for demo / real workspace ─────────────────────

def get_user_boards(user):
    """Return a Board queryset scoped to the user's current workspace mode.

    * **Demo mode** (``profile.is_viewing_demo == True``):
      returns the user's personal sandbox copies; falls back to official
      demo boards if no sandbox exists yet.
    * **Real mode**: returns only the user's own boards (created or member),
      explicitly excluding demo boards, sandbox copies, and Spectra-generated
      demo boards.

    Every view that aggregates data across boards (dashboard, calendar,
    messaging hub, conflicts, knowledge graph, etc.) should call this helper
    instead of building its own queryset — this is the single source of truth
    for demo-vs-real separation.
    """
    from kanban.models import Board  # late import to avoid circular deps

    profile = getattr(user, 'profile', None)
    is_demo = getattr(profile, 'is_viewing_demo', False)

    if is_demo:
        sandbox_boards = Board.objects.filter(
            owner=user,
            is_sandbox_copy=True,
        ).distinct()
        if sandbox_boards.exists():
            return sandbox_boards
        # Fallback: official demo boards (read-only)
        return Board.objects.filter(is_official_demo_board=True).distinct()

    # Real workspace — exclude every flavour of demo data
    return Board.objects.filter(
        Q(created_by=user) | Q(memberships__user=user),
        is_official_demo_board=False,
        is_sandbox_copy=False,
    ).exclude(
        created_by_session__startswith='spectra_demo_'
    ).distinct()


# ── Demo-object detection ────────────────────────────────────────────────────

def _safe_fk(instance, attr_name):
    """Safely dereference a FK attribute — returns None on any failure."""
    try:
        val = getattr(instance, attr_name, None)
        return val
    except Exception:
        return None


def _board_is_demo(board):
    """Return True if a Board instance is flagged as demo data."""
    return (
        getattr(board, 'is_seed_demo_data', False)
        or getattr(board, 'is_official_demo_board', False)
    )


def is_demo_object(instance):
    """
    Return True if *instance* is demo data (an official template object).

    Checks direct flags first, then walks up FK chains for child models
    that inherit demo status from their parent Board / Task / Org.
    """
    # ── 1. Direct flags ──────────────────────────────────────────────────
    if getattr(instance, 'is_seed_demo_data', None) is True:
        return True
    if getattr(instance, 'is_official_demo_board', None) is True:
        return True
    if getattr(instance, 'is_demo', None) is True:
        return True

    # ── 2. Parent Board (Column, TaskLabel, CalendarEvent, ChatRoom …) ───
    board = _safe_fk(instance, 'board')
    if board is not None and _board_is_demo(board):
        return True

    # ── 3. Parent Column → Board (Task) ─────────────────────────────────
    column = _safe_fk(instance, 'column')
    if column is not None:
        board = _safe_fk(column, 'board')
        if board is not None and _board_is_demo(board):
            return True

    # ── 4. Parent Task (Comment, TaskActivity, TaskFile) ────────────────
    task = _safe_fk(instance, 'task')
    if task is not None:
        if getattr(task, 'is_seed_demo_data', False):
            return True
        col = _safe_fk(task, 'column')
        if col is not None:
            board = _safe_fk(col, 'board')
            if board is not None and _board_is_demo(board):
                return True

    # ── 5. Parent ChatRoom → Board (ChatMessage) ────────────────────────
    chat_room = _safe_fk(instance, 'chat_room')
    if chat_room is not None:
        board = _safe_fk(chat_room, 'board')
        if board is not None and _board_is_demo(board):
            return True

    # ── 6. Parent Organization (WikiPage, WikiCategory) ─────────────────
    org = _safe_fk(instance, 'organization')
    if org is not None and getattr(org, 'is_demo', False):
        return True

    # ── 7. Upward strategic chain ────────────────────────────────────────
    mission = _safe_fk(instance, 'mission')
    if mission is not None:
        if getattr(mission, 'is_demo', False) or getattr(mission, 'is_seed_demo_data', False):
            return True

    org_goal = _safe_fk(instance, 'organization_goal')
    if org_goal is not None:
        if getattr(org_goal, 'is_demo', False) or getattr(org_goal, 'is_seed_demo_data', False):
            return True

    strategy = _safe_fk(instance, 'strategy')
    if strategy is not None and getattr(strategy, 'is_seed_demo_data', False):
        return True

    # ── 8. Exit-protocol chain: HospiceSession → Board ──────────────────
    hospice = _safe_fk(instance, 'hospice_session')
    if hospice is not None:
        board = _safe_fk(hospice, 'board')
        if board is not None and _board_is_demo(board):
            return True

    source_board = _safe_fk(instance, 'source_board')
    if source_board is not None and _board_is_demo(source_board):
        return True

    return False
