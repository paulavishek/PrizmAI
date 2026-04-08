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
    """Check if a user can create Organization Goals.
    Allowed: Org Admin (group, org creator, or UI-promoted admin).
    If in demo context, always True.
    """
    if request and is_demo_context(request):
        return True
    return is_user_org_admin(user)


def can_user_create_missions(user, request=None, parent_goal=None):
    """Check if a user can create Missions.
    Allowed: Org Admin, org creator, UI-promoted admin, or owner/creator of
    the parent Goal.  If in demo context, always True.
    """
    if request and is_demo_context(request):
        return True
    if is_user_org_admin(user):
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
    """Org admin scoped to the object's organization.
    Only grants access if the user is an org admin AND belongs to the
    same organization as the object being checked."""
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

# Board permissions.
# is_ancestor_owner: owning a Strategy/Mission/Goal gives automatic board access.
# is_demo_board: official demo boards are accessible to all authenticated users.
rules.add_perm('prizmai.view_board',
               is_org_admin | is_record_owner | is_ancestor_owner | has_board_membership | is_demo_board)

rules.add_perm('prizmai.edit_board',
               is_org_admin | is_record_owner | is_ancestor_owner | is_board_member_role | is_board_owner_role | is_demo_board)

rules.add_perm('prizmai.delete_board',
               is_org_admin | is_record_owner | is_ancestor_owner)

rules.add_perm('prizmai.invite_board_member',
               is_org_admin | is_record_owner | is_ancestor_owner | is_board_owner_role)

# Strategic level permissions.
# UPWARD VISIBILITY RULE: has_board_membership is deliberately NOT here.
# Board membership never grants strategic-level edit access.
# is_ancestor_owner IS included: owning a Goal gives Mission/Strategy access.
rules.add_perm('prizmai.edit_strategy',
               is_org_admin | is_record_owner | is_ancestor_owner | has_strategic_membership)

rules.add_perm('prizmai.edit_mission',
               is_org_admin | is_record_owner | is_ancestor_owner | has_strategic_membership)

rules.add_perm('prizmai.edit_goal',
               is_org_admin | is_record_owner)
# Goal is the top level. No ancestor above to traverse.
# Only Org Admin can be Goal Owner — effectively Org Admin only.

rules.add_perm('prizmai.view_strategy',
               is_org_admin | is_record_owner | is_ancestor_owner | has_strategic_membership | is_descendant_board_member | is_demo_strategic_object)

rules.add_perm('prizmai.view_mission',
               is_org_admin | is_record_owner | is_ancestor_owner | has_strategic_membership | is_descendant_board_member | is_demo_strategic_object)

rules.add_perm('prizmai.view_goal',
               is_org_admin | is_record_owner | has_strategic_membership | is_descendant_board_member | is_demo_strategic_object)
