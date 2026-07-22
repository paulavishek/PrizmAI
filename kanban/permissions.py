"""
PrizmAI RBAC — django-rules predicates and permission rules.

4 roles: Org Admin, Owner, Member, Viewer.
Core rule: access flows DOWN automatically, never UP without an explicit invitation.

Created in Phase 1 of the RBAC rollout.
"""
import rules


# ── Unified Org Admin helper ─────────────────────────────────────────────────

def is_user_org_admin(user):
    """
    Canonical check for whether a user has Org Admin privileges.

    A user is an Org Admin if ANY of the following is true:
      1. They are in the 'OrgAdmin' Django Group
      2. They are the creator of their organization (org.created_by)
      3. They have been promoted to admin via the UI (profile.is_admin)

    This function should be used everywhere instead of inline
    ``user.groups.filter(name='OrgAdmin').exists()`` checks.
    """
    if not user or not user.is_authenticated:
        return False
    # 1. Django Group (canonical — set by migration, sync'd by toggle_admin)
    if user.groups.filter(name='OrgAdmin').exists():
        return True
    # 2. Organization creator
    profile = getattr(user, 'profile', None)
    if profile:
        org = getattr(profile, 'organization', None)
        if org and org.created_by_id == user.id:
            return True
        # 3. UI-promoted admin
        if getattr(profile, 'is_admin', False):
            return True
    return False


# ── Workspace ownership helpers ──────────────────────────────────────────────

def is_workspace_owner(user, workspace):
    """True if ``user`` owns ``workspace`` (its creator).

    Workspaces are personal-per-user; ``created_by`` is the ownership signal
    now that Workspace is the top-level tenant boundary (Organization is no
    longer read for user-facing scoping).
    """
    return bool(workspace) and getattr(workspace, 'created_by_id', None) == getattr(user, 'id', None)


def owns_active_workspace(user):
    """True if the user's current (non-demo) active workspace is their own."""
    ws = getattr(getattr(user, 'profile', None), 'active_workspace', None)
    return bool(ws) and not getattr(ws, 'is_demo', False) and ws.created_by_id == getattr(user, 'id', None)


# ── Demo context helper ──────────────────────────────────────────────────────

def is_demo_context(request, board=None, workspace=None):
    """
    Returns True if the current request is within a Demo workspace.
    In Demo mode, all RBAC checks should be bypassed.

    Usage:
        if is_demo_context(request, workspace=current_workspace):
            return allow_action()
    """
    # Check if a workspace was passed directly
    if workspace is not None:
        return getattr(workspace, 'is_demo', False)

    # Check if a board was passed — get its workspace
    if board is not None:
        board_ws = getattr(board, 'workspace', None)
        if board_ws is not None:
            return getattr(board_ws, 'is_demo', False)

    # Try to get workspace from the request (set by WorkspaceMiddleware)
    current_workspace = getattr(request, 'workspace', None)
    if current_workspace is not None:
        return getattr(current_workspace, 'is_demo', False)

    # Fallback: check user profile flag
    profile = getattr(request.user, 'profile', None)
    if profile is not None:
        return getattr(profile, 'is_viewing_demo', False)

    return False


def can_user_create_goals(user, request=None):
    """Check if a user can create Goals.
    Allowed: the owner of the active (non-demo) workspace.  Goals are
    workspace-scoped, so workspace ownership is the gate.
    If in demo context, always True.
    """
    if request and is_demo_context(request):
        return True
    return owns_active_workspace(user)


def can_user_create_missions(user, request=None, parent_goal=None):
    """Check if a user can create Missions.
    Allowed: the active-workspace owner, or the owner/creator of the parent
    Goal.  If in demo context, always True.
    """
    if request and is_demo_context(request):
        return True
    if owns_active_workspace(user):
        return True
    # Owner or creator of the parent goal
    if parent_goal:
        if getattr(parent_goal, 'owner', None) == user:
            return True
        if getattr(parent_goal, 'created_by', None) == user:
            return True
    return False


# ── Core predicates ──────────────────────────────────────────────────────────

@rules.predicate
def is_org_admin(user, obj=None):
    """DEPRECATED — intentionally NOT wired into any permission rule.

    This predicate granted access whenever the user was an org admin AND shared
    the object's organization. That was a cross-workspace leak: invite acceptance
    reassigns an invitee's ``profile.organization`` to the inviter's org (see
    ``kanban/workspace_member_views.py`` and ``accounts/views.py`` accept flows),
    so an org admin would gain view/edit/delete on a colleague's separate-
    workspace boards and strategic records — violating the Workspace-is-the-
    tenant-boundary model enforced everywhere else.

    It is left defined (not deleted) so this history is greppable and the term is
    never re-added to the rules below. Org-admin's legitimate reach is org-level
    SETTINGS only (Workspace Preset tier, AI/BYOK config), gated via the plain
    ``is_user_org_admin()`` helper — never via object permissions. Do NOT re-add
    ``is_org_admin`` to any ``rules.add_perm`` call.

    Original behavior (org admin AND same organization as the object):"""
    if not is_user_org_admin(user):
        return False
    if obj is None:
        return True  # No object to scope against (e.g., generic admin checks)

    # Resolve the object's organization
    obj_org_id = getattr(obj, 'organization_id', None)

    if obj_org_id is None:
        # Try traversal for objects without a direct organization FK
        try:
            # Strategy → mission → goal → organization
            if hasattr(obj, 'mission') and obj.mission:
                goal = getattr(obj.mission, 'organization_goal', None)
                if goal:
                    obj_org_id = getattr(goal, 'organization_id', None)
            # Mission → goal → organization
            elif hasattr(obj, 'organization_goal') and obj.organization_goal:
                obj_org_id = getattr(obj.organization_goal, 'organization_id', None)
        except Exception:
            pass

    if obj_org_id is None:
        # Cannot determine org — deny to be safe
        return False

    try:
        return user.profile.organization_id == obj_org_id
    except Exception:
        return False


@rules.predicate
def is_record_owner(user, obj):
    """Direct owner of this specific record (Board, Strategy, Mission, Goal)."""
    owner = getattr(obj, 'owner', None)
    if owner is None:
        # Fallback: check created_by (covers records created before owner field was populated)
        created_by = getattr(obj, 'created_by', None)
        if created_by is not None:
            return created_by == user
        # Truly orphaned record — only Org Admin can act
        return is_user_org_admin(user)
    return owner == user


@rules.predicate
def is_ancestor_owner(user, obj):
    """
    Implements the downward access flow rule:
    'Access flows DOWN automatically.'

    Traverses UP the hierarchy from the given object to check if the user
    owns any ancestor.  Uses select_related where possible to avoid N+1.

    Traversal paths:
      Board    → strategy → mission → organization_goal
      Task     → column → board   → (then Board path)
      Strategy → mission → organization_goal
      Mission  → organization_goal
    """
    from kanban.models import Board

    # Task → Board resolution
    try:
        from kanban.models import Task
        if isinstance(obj, Task):
            board = getattr(getattr(obj, 'column', None), 'board', None)
            if board is None:
                return False
            return _check_board_ancestors(user, board)
    except (AttributeError, ImportError):
        pass

    # Board → ancestors
    if isinstance(obj, Board):
        return _check_board_ancestors(user, obj)

    # Strategy → Mission → Goal
    if hasattr(obj, 'mission') and obj.mission:
        if obj.mission.owner == user:
            return True
        goal = getattr(obj.mission, 'organization_goal', None)
        if goal and goal.owner == user:
            return True

    # Mission → Goal
    if hasattr(obj, 'organization_goal') and obj.organization_goal:
        if obj.organization_goal.owner == user:
            return True

    return False


def _check_board_ancestors(user, board):
    """Walk board → strategy → mission → goal, checking ownership at each level."""
    try:
        strategy = getattr(board, 'strategy', None)
        if strategy:
            if strategy.owner == user:
                return True
            mission = getattr(strategy, 'mission', None)
            if mission:
                if mission.owner == user:
                    return True
                goal = getattr(mission, 'organization_goal', None)
                if goal and goal.owner == user:
                    return True
    except AttributeError:
        pass
    return False


@rules.predicate
def has_board_membership(user, board):
    """True if user has ANY membership on this board (any role)."""
    from kanban.models import BoardMembership
    return BoardMembership.objects.filter(board=board, user=user).exists()


@rules.predicate
def is_board_member_role(user, board):
    """True if user has specifically the Member role on this board."""
    from kanban.models import BoardMembership
    return BoardMembership.objects.filter(
        board=board, user=user, role='member'
    ).exists()


@rules.predicate
def is_board_owner_role(user, board):
    """True if user has the Owner role in BoardMembership for this board."""
    from kanban.models import BoardMembership
    return BoardMembership.objects.filter(
        board=board, user=user, role='owner'
    ).exists()


@rules.predicate
def has_strategic_membership(user, obj):
    """True if user has ANY StrategicMembership on this Goal/Mission/Strategy."""
    from django.contrib.contenttypes.models import ContentType
    from kanban.models import StrategicMembership
    ct = ContentType.objects.get_for_model(obj)
    return StrategicMembership.objects.filter(
        content_type=ct, object_id=obj.pk, user=user
    ).exists()


@rules.predicate
def is_descendant_board_member(user, obj):
    """True if user is a board member of ANY board that descends from this
    Goal/Mission/Strategy.  Provides read-only upward visibility."""
    from kanban.models import (
        Board, BoardMembership, Strategy, Mission, OrganizationGoal,
    )

    if isinstance(obj, Strategy):
        return BoardMembership.objects.filter(
            user=user, board__strategy=obj
        ).exists()

    if isinstance(obj, Mission):
        return BoardMembership.objects.filter(
            user=user, board__strategy__mission=obj
        ).exists()

    if isinstance(obj, OrganizationGoal):
        return BoardMembership.objects.filter(
            user=user, board__strategy__mission__organization_goal=obj
        ).exists()

    return False


@rules.predicate
def is_demo_board(user, board):
    """True if the board is an official demo board — universally accessible."""
    return getattr(board, 'is_official_demo_board', False)


@rules.predicate
def is_demo_strategic_object(user, obj):
    """True if the Goal/Mission/Strategy is part of the demo dataset.
    Mirrors ``is_demo_board`` so sandbox users can view the hierarchy
    that the dashboard already surfaces for them."""
    return getattr(obj, 'is_demo', False) or getattr(obj, 'is_seed_demo_data', False)


# ── Permission rules ─────────────────────────────────────────────────────────

# TENANT BOUNDARY = WORKSPACE. Org-admin status does NOT grant access to any
# board or strategic record. `is_org_admin` is deliberately absent from every
# rule below: a user reassigned into another user's Organization (which happens
# on workspace/org invite acceptance) must NOT thereby gain view/edit/delete on
# that colleague's separate-workspace boards or strategic records. Access flows
# ONLY through ownership, ancestor ownership, explicit board/strategic
# membership, or the demo predicates. Org-admin's legitimate reach is org-level
# SETTINGS only (Workspace Preset tier, AI/BYOK config), enforced separately via
# the `is_user_org_admin()` helper — never through these object rules. Django
# superusers retain cross-tenant reach via the default ModelBackend. This aligns
# the django-rules layer with the enforced access path in
# `kanban/simple_access.py` / `ai_assistant.utils.rbac_utils.get_user_board_role`.

# Board permissions.
# is_ancestor_owner: owning a Strategy/Mission/Goal gives automatic board access.
# is_demo_board: official demo boards are accessible to all authenticated users.
rules.add_perm('prizmai.view_board',
               is_record_owner | is_ancestor_owner | has_board_membership | is_demo_board)

rules.add_perm('prizmai.edit_board',
               is_record_owner | is_ancestor_owner | is_board_member_role | is_board_owner_role | is_demo_board)

rules.add_perm('prizmai.delete_board',
               is_record_owner | is_ancestor_owner)

rules.add_perm('prizmai.invite_board_member',
               is_record_owner | is_ancestor_owner | is_board_owner_role)

# Strategic level permissions.
# UPWARD VISIBILITY RULE: has_board_membership is deliberately NOT here.
# Board membership never grants strategic-level edit access.
# is_ancestor_owner IS included: owning a Goal gives Mission/Strategy access.
rules.add_perm('prizmai.edit_strategy',
               is_record_owner | is_ancestor_owner | has_strategic_membership)

rules.add_perm('prizmai.edit_mission',
               is_record_owner | is_ancestor_owner | has_strategic_membership)

rules.add_perm('prizmai.edit_goal',
               is_record_owner)
# Goal is the top level. No ancestor above to traverse. Access requires being
# the Goal's owner/creator (the workspace owner who created it) — org-admin
# status alone no longer grants it.

rules.add_perm('prizmai.view_strategy',
               is_record_owner | is_ancestor_owner | has_strategic_membership | is_descendant_board_member | is_demo_strategic_object)

rules.add_perm('prizmai.view_mission',
               is_record_owner | is_ancestor_owner | has_strategic_membership | is_descendant_board_member | is_demo_strategic_object)

rules.add_perm('prizmai.view_goal',
               is_record_owner | has_strategic_membership | is_descendant_board_member | is_demo_strategic_object)
