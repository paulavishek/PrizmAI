"""
Spectra RBAC Utilities — centralised permission checks for the AI assistant.

Every Spectra action (create task, send message, log time, etc.) and every
context-retrieval path (board data, tasks, team info) routes through one of
these helpers so that the RBAC rules in ``kanban.simple_access`` are enforced
consistently, and viewers / non-members cannot trick Spectra into bypassing
access controls.
"""
import logging
from django.db.models import Q

logger = logging.getLogger(__name__)


# ── Core permission helpers ──────────────────────────────────────────────────

def get_user_board_role(user, board):
    """
    Return the user's effective role on *board*.

    Returns one of:
        ``'owner'``   – board creator, board.owner field, owner membership, OrgAdmin, superuser
        ``'member'``  – regular member (full CRUD on tasks)
        ``'viewer'``  – read-only access
        ``None``      – no access at all
    """
    if not user or not user.is_authenticated or not board:
        return None

    # Superuser / OrgAdmin → always owner-level
    from kanban.permissions import is_user_org_admin
    if user.is_superuser or is_user_org_admin(user):
        return 'owner'

    # Board creator or explicit owner field
    if board.created_by_id == user.id:
        return 'owner'
    if getattr(board, 'owner_id', None) and board.owner_id == user.id:
        return 'owner'

    # Official demo board — treat as member (can read, but write is gated by demo_write_guard)
    if getattr(board, 'is_official_demo_board', False):
        return 'member'

    # Explicit BoardMembership
    from kanban.models import BoardMembership
    membership = BoardMembership.objects.filter(board=board, user=user).first()
    if membership:
        return membership.role  # 'owner', 'member', or 'viewer'

    # Same-org fallback (matches simple_access.can_access_board logic)
    try:
        if (
            board.organization_id
            and hasattr(user, 'profile')
            and user.profile.organization_id == board.organization_id
        ):
            return 'member'
    except Exception:
        pass

    return None


def can_spectra_read_board(user, board):
    """Can the user see this board's data through Spectra?"""
    return get_user_board_role(user, board) is not None


def can_spectra_write_board(user, board):
    """
    Can the user create/edit/delete tasks and other content via Spectra?

    Viewers are read-only → False.  Members and owners → True.
    """
    role = get_user_board_role(user, board)
    return role in ('owner', 'member')


def can_spectra_manage_board(user, board):
    """
    Can the user manage board settings, members, automations via Spectra?

    Only ``'owner'`` role (includes superuser / OrgAdmin / board creator).
    """
    return get_user_board_role(user, board) == 'owner'


# ── Action-level permission map ──────────────────────────────────────────────
# Maps each Spectra pending_action → required permission level.

ACTION_PERMISSION_MAP = {
    # Write-level actions (member or owner)
    'create_task':                  'write',
    'update_task':                  'write',
    'send_message':                 'write',
    'log_time':                     'write',
    'schedule_event':               'write',
    'create_retrospective':         'write',
    'place_commitment_bet':         'write',

    # Management-level actions (owner only)
    'activate_automation':          'manage',
    'create_custom_automation':     'manage',
    'create_scheduled_automation':  'manage',

    # Read-only actions (any member, including viewer)
    'get_commitment_status':        'read',
    'list_at_risk_commitments':     'read',

    # Board creation has no board yet — handled separately
    'create_board':                 None,
}


def check_spectra_action_permission(user, board, action):
    """
    Check if *user* has the required permission level on *board* for *action*.

    Returns ``(allowed: bool, denial_message: str | None)``.

    When *allowed* is ``False``, *denial_message* is a user-friendly Spectra
    message explaining the restriction.
    """
    required = ACTION_PERMISSION_MAP.get(action)

    # Actions with no board requirement (e.g. create_board) are always allowed
    if required is None:
        return True, None

    if board is None:
        return False, (
            "I need a board to perform this action. "
            "Please select one from the dropdown above."
        )

    role = get_user_board_role(user, board)

    if role is None:
        return False, (
            f"You don't have access to the **{board.name}** board. "
            "I can't perform actions on boards you're not a member of. "
            "Would you like me to send an access request to the board owner?"
        )

    if required == 'read':
        # Any role (viewer, member, owner) can read
        return True, None

    if required == 'write':
        if role == 'viewer':
            return False, (
                f"You have **viewer** access on **{board.name}**, which is read-only. "
                "I can answer questions about this board, but I can't create, edit, or "
                "delete content on your behalf. Please ask a board owner to upgrade your role."
            )
        return True, None

    if required == 'manage':
        if role == 'owner':
            return True, None
        if role == 'viewer':
            return False, (
                f"You have **viewer** access on **{board.name}**. "
                "Automations can only be managed by board owners. "
                "Please ask the board owner for assistance."
            )
        # member
        return False, (
            f"Managing automations on **{board.name}** requires **owner** access. "
            "You're currently a **member**, which allows creating and editing tasks, "
            "but automation management is reserved for board owners."
        )

    # Unknown action — deny by default (fail-closed)
    logger.warning('Unknown Spectra action in permission check: %s', action)
    return False, "I'm unable to perform that action due to a permissions check."


# ── Board filtering for context retrieval ────────────────────────────────────

def get_accessible_boards_for_spectra(user, is_demo_mode=False, organization=None):
    """
    Return a queryset of boards the user can see through Spectra.

    Mirrors the logic in ``chatbot_service._get_user_boards`` but uses the
    canonical ``can_access_board`` semantics so RBAC stays consistent.

    Workspace scoping guarantees:
    - Demo mode → only the current user's sandbox copies (``is_sandbox_copy=True``
      AND ``owner=user``) within a demo workspace.  Other users' sandboxes are
      never included.
    - Personal mode → only non-demo boards in the user's active workspace /
      organisation.  Sandbox copies and official demo boards are excluded.
    - Organisation filter prevents cross-org data leakage when multiple orgs
      share the same database.
    """
    from kanban.models import Board

    base = Board.objects.filter(is_archived=False)

    if is_demo_mode:
        # Demo workspace — only this user's personal sandbox copies.
        # The ``workspace__is_demo=True`` guard ensures we never pull boards
        # from the user's real workspace even if ``is_sandbox_copy`` is True.
        sandbox_qs = base.filter(
            Q(owner=user, is_sandbox_copy=True)
            | Q(created_by_session=f'spectra_demo_{user.id}')
        ).filter(
            Q(workspace__is_demo=True) | Q(workspace__isnull=True)
        )
        if organization:
            sandbox_qs = sandbox_qs.filter(organization=organization)
        sandbox_qs = sandbox_qs.distinct()
        if sandbox_qs.exists():
            return sandbox_qs
        # Fallback to templates if sandbox not provisioned yet
        fallback = base.filter(is_official_demo_board=True)
        if organization:
            fallback = fallback.filter(organization=organization)
        return fallback.distinct()

    # Personal workspace — only non-demo boards the user has explicit access to.
    qs = base.filter(
        Q(created_by=user)
        | Q(owner=user)
        | Q(memberships__user=user)
    )

    if organization:
        qs = qs.filter(organization=organization)
    else:
        try:
            if hasattr(user, 'profile') and user.profile.organization_id:
                qs = qs.filter(organization_id=user.profile.organization_id)
        except Exception:
            pass

    # Exclude demo artefacts from the personal workspace
    return qs.filter(
        Q(workspace__is_demo=False) | Q(workspace__isnull=True)
    ).exclude(
        created_by_session__startswith='spectra_demo_'
    ).exclude(
        is_official_demo_board=True
    ).exclude(
        is_sandbox_copy=True
    ).distinct()


def filter_boards_by_read_access(user, boards_qs):
    """
    Given a Board queryset, return only boards the user can read.

    This is useful for aggregate / cross-board queries where we start
    with a wide queryset and need to narrow it.
    """
    from kanban.simple_access import can_access_board

    # For efficiency, if the queryset is already filtered by membership we
    # can trust it.  But for safety with org-level fallbacks, double-check.
    accessible_ids = [b.id for b in boards_qs if can_access_board(user, b)]
    return boards_qs.filter(id__in=accessible_ids)


# ── RBAC-aware context description for system prompts ────────────────────────

def build_rbac_context_for_prompt(user, board):
    """
    Build a compact RBAC context block to inject into Spectra's system prompt
    so the AI model itself is aware of the user's permissions and can refuse
    in-prompt requests that would violate RBAC.

    Returns a string block or empty string if no board.
    """
    if not board:
        return ""

    role = get_user_board_role(user, board)
    if role is None:
        return (
            f"\n**ACCESS CONTROL:** User does NOT have access to board "
            f"\"{board.name}\". Do NOT reveal any data about this board. "
            f"Politely inform the user they need access."
        )

    parts = [f"\n**ACCESS CONTROL — User Role on \"{board.name}\": {role.upper()}**"]

    if role == 'viewer':
        parts.append(
            "- The user has READ-ONLY access. They can view tasks, data, and analytics."
        )
        parts.append(
            "- REFUSE any request to create, edit, delete, move, or assign tasks. "
            "REFUSE requests to log time, send messages, create automations, or "
            "schedule events. Politely explain they need member or owner access."
        )
        parts.append(
            "- If the user asks you to perform a write action, say: "
            "\"You have viewer access on this board, which is read-only. "
            "Please ask a board owner to upgrade your role to member.\""
        )
    elif role == 'member':
        parts.append(
            "- The user can: view data, create/edit/delete tasks, log time, "
            "send messages, schedule events, and update tasks."
        )
        parts.append(
            "- The user CANNOT: manage automations, delete the board, or "
            "manage board members. These require owner access."
        )
        parts.append(
            "- If the user asks to set up automations, say: "
            "\"Automation management requires owner access on this board. "
            "You're currently a member.\""
        )
    else:
        # owner — full access
        parts.append("- The user has FULL access (owner). All actions are permitted.")

    return '\n'.join(parts)


def build_rbac_context_for_fc_prompt(user, board):
    """
    Compact RBAC context for the Function-Calling (FC) system prompt.
    Shorter than the full prompt version to save tokens.
    """
    if not board:
        return ""

    role = get_user_board_role(user, board)
    if role is None:
        return "ACCESS: NONE. Deny all actions."

    if role == 'viewer':
        return (
            f"ACCESS: VIEWER (read-only on \"{board.name}\"). "
            "REFUSE write actions (create/edit/delete tasks, log time, send messages, automations). "
            "Only answer data queries."
        )
    if role == 'member':
        return (
            f"ACCESS: MEMBER on \"{board.name}\". "
            "OK: create/edit tasks, log time, send messages, schedule events. "
            "REFUSE: automation management (owner-only)."
        )
    return f"ACCESS: OWNER on \"{board.name}\". All actions permitted."
