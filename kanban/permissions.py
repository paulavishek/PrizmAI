"""
PrizmAI RBAC — django-rules predicates and permission rules.

4 roles: Org Admin, Owner, Member, Viewer.
Core rule: access flows DOWN automatically, never UP without an explicit invitation.

Created in Phase 1 of the RBAC rollout.
"""
import rules


# ── Core predicates ──────────────────────────────────────────────────────────

@rules.predicate
def is_org_admin(user, obj=None):
    """System-wide admin — the platform owner. Single Django Group."""
    return user.groups.filter(name='OrgAdmin').exists()


@rules.predicate
def is_record_owner(user, obj):
    """Direct owner of this specific record (Board, Strategy, Mission, Goal)."""
    owner = getattr(obj, 'owner', None)
    if owner is None:
        # Orphaned record (owner account deleted) — only Org Admin can act
        return user.groups.filter(name='OrgAdmin').exists()
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


# ── Permission rules ─────────────────────────────────────────────────────────

# Board permissions.
# is_ancestor_owner: owning a Strategy/Mission/Goal gives automatic board access.
rules.add_perm('prizmai.view_board',
               is_org_admin | is_record_owner | is_ancestor_owner | has_board_membership)

rules.add_perm('prizmai.edit_board',
               is_org_admin | is_record_owner | is_ancestor_owner | is_board_member_role | is_board_owner_role)

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
               is_org_admin | is_record_owner | is_ancestor_owner | has_strategic_membership)

rules.add_perm('prizmai.view_mission',
               is_org_admin | is_record_owner | is_ancestor_owner | has_strategic_membership)

rules.add_perm('prizmai.view_goal',
               is_org_admin | is_record_owner | has_strategic_membership)
