"""
Demo Data Protection — Model-level immutability for all demo artifacts.

Uses Django pre_save / pre_delete signals to block any web-initiated
modification of demo data.  Management commands and Celery tasks are NOT
affected because the protection only activates inside HTTP request
context (tracked via thread-local flag set by DemoProtectionMiddleware).

Hierarchy checked (in order):
    1. Direct flags:  is_seed_demo_data · is_official_demo_board · is_demo
    2. Parent Board:  Column / TaskLabel → board FK
    3. Parent Task:   Comment / TaskActivity / TaskFile → task FK
    4. Parent Chain:  ChatMessage → chat_room → board
    5. Parent Org:    WikiPage / WikiCategory → organization FK
    6. Parent Strategy / Mission / Goal (upward strategic chain)

Web flows that *legitimately* must modify demo data (e.g. assigning a
few demo tasks to the real user on toggle_demo_mode) use the bypass:

    from kanban.utils.demo_protection import allow_demo_writes
    with allow_demo_writes():
        task.save(update_fields=['assigned_to'])

Setup — call once from KanbanConfig.ready():

    from kanban.utils.demo_protection import connect_demo_protection_signals
    connect_demo_protection_signals()
"""

import threading
import logging
from contextlib import contextmanager

from django.db.models.signals import pre_save, pre_delete

logger = logging.getLogger(__name__)

# ── Thread-local state ────────────────────────────────────────────────────────

_local = threading.local()


def _in_web_request():
    return getattr(_local, 'in_web_request', False)


def _bypass_active():
    return getattr(_local, 'demo_bypass', False)


def mark_web_request():
    """Set by DemoProtectionMiddleware at the start of every request."""
    _local.in_web_request = True


def unmark_web_request():
    """Cleared by DemoProtectionMiddleware in its finally-block."""
    _local.in_web_request = False


@contextmanager
def allow_demo_writes():
    """Temporarily bypass demo protection (for legitimate demo flows)."""
    prev = getattr(_local, 'demo_bypass', False)
    _local.demo_bypass = True
    try:
        yield
    finally:
        _local.demo_bypass = prev


# ── Exception ────────────────────────────────────────────────────────────────

class DemoProtectionError(Exception):
    """Raised when a write operation targets a demo-protected object."""
    pass


_DEMO_BLOCK_MSG = (
    "This is demo data and cannot be modified. "
    "Create your own boards and tasks to get started!"
)

# ── Model exemptions ─────────────────────────────────────────────────────────
# These models are NEVER blocked even if they reference demo-flagged parents.
# Rationale: they are user-interaction or system bookkeeping records, not
# structural components of the demo dataset.

_EXEMPT_MODEL_NAMES = frozenset({
    # User joins / leaves demo boards
    'BoardMembership',
    'StrategicMembership',
    'BoardInvitation',
    # Demo-mode lifecycle records
    'DemoSession',
    'DemoAnalytics',
    'DemoSandbox',
    'DemoAbusePrevention',
    # System / analytics
    'Notification',
    'SessionTracking',
    'AuditLog',
    'UserProfile',
    'User',
    # Decision center items are per-user ephemeral nudges
    'DecisionItem',
    'DecisionCenterBriefing',
    # Coaching / forecasting are generated insights
    'CoachingSuggestion',
    'CoachingFeedback',
    'CoachingInsight',
    'PMMetrics',
    'ForecastSnapshot',
    'ForecastAlert',
    # Commitment / conflict are per-user interactions
    'CommitmentProtocol',
    'ConfidenceSignal',
    'CommitmentBet',
    'NegotiationSession',
    'UserCredibilityScore',
    'ConflictNotification',
    # Resource leveling
    'UserPerformanceProfile',
    'TaskAssignmentHistory',
    'ResourceLevelingSuggestion',
    # Automation audit records
    'AutomationLog',
    # Knowledge graph (user-created memories)
    'MemoryNode',
    'MemoryConnection',
    # Burndown/velocity snapshots (auto-generated)
    'BurndownSnapshot',
    'VelocitySnapshot',
    # Onboarding records
    'OnboardingWorkspacePreview',
})

# ── Model-check cache ────────────────────────────────────────────────────────
# Pre-computed per model class: do we need to run is_demo_object() at all?

_model_needs_check_cache: dict = {}

# Fields on a model that would cause us to run is_demo_object()
_DEMO_INDICATOR_FIELDS = frozenset({
    'is_seed_demo_data', 'is_official_demo_board', 'is_demo',
    'board', 'column', 'task',
    'organization', 'mission', 'organization_goal', 'strategy',
    'chat_room', 'source_board', 'hospice_session',
})


def _model_should_be_checked(sender):
    """Return True if *sender* has any demo-relevant fields worth inspecting."""
    if sender not in _model_needs_check_cache:
        # Exempt models are never checked
        if sender.__name__ in _EXEMPT_MODEL_NAMES:
            _model_needs_check_cache[sender] = False
        else:
            field_names = {f.name for f in sender._meta.get_fields()}
            _model_needs_check_cache[sender] = bool(
                field_names & _DEMO_INDICATOR_FIELDS
            )
    return _model_needs_check_cache[sender]


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
    Return True if *instance* is demo data that must be immutable.

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
        # Continue up: task → column → board
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


# ── Signal handlers ──────────────────────────────────────────────────────────

def _pre_save_demo_guard(sender, instance, **kwargs):
    """Block save() on demo objects during web requests."""
    if not _in_web_request() or _bypass_active():
        return
    if not _model_should_be_checked(sender):
        return
    if is_demo_object(instance):
        logger.warning(
            "Blocked demo-data save: %s pk=%s",
            sender.__name__, instance.pk,
        )
        raise DemoProtectionError(_DEMO_BLOCK_MSG)


def _pre_delete_demo_guard(sender, instance, **kwargs):
    """Block delete() on demo objects during web requests."""
    if not _in_web_request() or _bypass_active():
        return
    if not _model_should_be_checked(sender):
        return
    if is_demo_object(instance):
        logger.warning(
            "Blocked demo-data delete: %s pk=%s",
            sender.__name__, instance.pk,
        )
        raise DemoProtectionError(_DEMO_BLOCK_MSG)


def connect_demo_protection_signals():
    """Connect the pre_save / pre_delete guards. Call from AppConfig.ready()."""
    pre_save.connect(
        _pre_save_demo_guard,
        dispatch_uid='demo_protection_pre_save',
    )
    pre_delete.connect(
        _pre_delete_demo_guard,
        dispatch_uid='demo_protection_pre_delete',
    )
    logger.info("Demo protection signals connected")
