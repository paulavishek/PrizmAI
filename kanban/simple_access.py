"""
Simplified Access Control for PrizmAI

PHILOSOPHY: 
- Simple collaboration over complex permissions
- Board creator + members model
- All members have full CRUD access
- No role selection, no permission errors, just works

This replaces the complex RBAC system (56 permissions, 5 roles) with:
- Board creator: Full control (delete board, manage members)
- Board members: Full CRUD on tasks, columns, comments, labels
- Organization members: Can access boards in their org

Spectra Smart Denial:
- When a user is denied access to a board or task, helper functions
  build a contextual Spectra response with an option to send an
  automated access request to the board Owner.
"""

from functools import wraps
from django.http import HttpResponseForbidden, JsonResponse
from django.core.exceptions import PermissionDenied


# ============================================================================
# CORE ACCESS CHECKS (BOARD-MEMBERSHIP ENFORCED)
# ============================================================================

def can_access_board(user, board):
    """
    Check if user can access a board.
    
    Rules:
    - Superuser → always
    - Board creator or board.owner → always
    - Has any BoardMembership on this board → yes
    - Board is an official demo board → yes
    - OrgAdmin of the board's specific organization → yes
    
    Returns:
        Boolean
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True

    # Board creator / owner field
    if board.created_by_id == user.id:
        return True
    if getattr(board, 'owner_id', None) and board.owner_id == user.id:
        return True

    # Official demo board — universally accessible
    if getattr(board, 'is_official_demo_board', False):
        return True

    # Explicit BoardMembership
    from kanban.models import BoardMembership
    if BoardMembership.objects.filter(board=board, user=user).exists():
        return True

    # Scoped OrgAdmin check — user must be admin of the board's specific org
    try:
        if (
            board.organization_id
            and hasattr(user, 'profile')
            and user.profile.organization_id == board.organization_id
        ):
            from kanban.permissions import is_user_org_admin
            if is_user_org_admin(user):
                return True
    except Exception:
        pass

    return False


def can_manage_board(user, board):
    """
    Check if user can manage a board (delete, manage members).
    
    Rules:
    - Superuser / OrgAdmin → always
    - Board creator → always
    - BoardMembership with role='owner' → yes
    
    Returns:
        Boolean
    """
    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    # Scoped OrgAdmin: must be admin of the board's specific org
    from kanban.permissions import is_user_org_admin
    if (
        board.organization_id
        and hasattr(user, 'profile')
        and user.profile.organization_id == board.organization_id
        and is_user_org_admin(user)
    ):
        return True
    
    if board.created_by_id == user.id:
        return True

    from kanban.models import BoardMembership
    return BoardMembership.objects.filter(
        board=board, user=user, role='owner'
    ).exists()


def can_modify_board_content(user, board):
    """
    Check if user can create/edit/delete tasks, columns, comments, etc.
    
    All board members (any role except viewer) can modify content.
    
    Returns:
        Boolean
    """
    if not can_access_board(user, board):
        return False

    # Viewers are read-only
    from kanban.models import BoardMembership
    viewer_only = BoardMembership.objects.filter(
        board=board, user=user, role='viewer'
    ).exists()

    # If user is the creator, owner, superuser, or scoped OrgAdmin they can modify
    from kanban.permissions import is_user_org_admin
    if (
        user.is_superuser
        or board.created_by_id == user.id
        or getattr(board, 'owner_id', None) == user.id
        or getattr(board, 'is_official_demo_board', False)
    ):
        return True

    # Scoped OrgAdmin: must be admin of the board's specific org
    if (
        board.organization_id
        and hasattr(user, 'profile')
        and user.profile.organization_id == board.organization_id
        and is_user_org_admin(user)
    ):
        return True

    # Non-viewer members have full CRUD
    return not viewer_only


def can_access_task(user, task):
    """
    Check if user can access a task.
    
    Rules:
    - User must be able to access the parent board
    
    Returns:
        Boolean
    """
    return can_access_board(user, task.column.board)


def can_modify_task(user, task):
    """
    Check if user can modify a task.
    
    Returns:
        Boolean
    """
    return can_modify_board_content(user, task.column.board)


# ============================================================================
# DECORATORS
# ============================================================================

def require_board_access(view_func):
    """
    Decorator to require board access.
    Returns a Spectra-powered JSON denial for AJAX requests,
    or an HTML denial page for regular requests.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from django.shortcuts import get_object_or_404
        from kanban.models import Board
        
        board_id = kwargs.get('board_id') or kwargs.get('pk')
        if board_id:
            board = get_object_or_404(Board, id=board_id)
        elif 'board' in kwargs:
            board = kwargs['board']
        else:
            raise ValueError("Board not found in view kwargs")
        
        if not can_access_board(request.user, board):
            return _spectra_denial_response(request, board, trigger='board_view')
        
        kwargs['board'] = board
        return view_func(request, *args, **kwargs)
    
    return wrapper


def require_board_management(view_func):
    """Decorator to require board management permission."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from django.shortcuts import get_object_or_404
        from kanban.models import Board
        
        board_id = kwargs.get('board_id') or kwargs.get('pk')
        if board_id:
            board = get_object_or_404(Board, id=board_id)
        elif 'board' in kwargs:
            board = kwargs['board']
        else:
            raise ValueError("Board not found in view kwargs")
        
        if not can_manage_board(request.user, board):
            return HttpResponseForbidden("Only board owner can perform this action.")
        
        kwargs['board'] = board
        return view_func(request, *args, **kwargs)
    
    return wrapper


def require_task_access(view_func):
    """
    Decorator to require task access.
    Returns a Spectra-powered denial when the parent board is inaccessible.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from django.shortcuts import get_object_or_404
        from kanban.models import Task
        
        task_id = kwargs.get('task_id') or kwargs.get('pk')
        if task_id:
            task = get_object_or_404(Task, id=task_id)
        elif 'task' in kwargs:
            task = kwargs['task']
        else:
            raise ValueError("Task not found in view kwargs")
        
        if not can_access_task(request.user, task):
            board = task.column.board
            return _spectra_denial_response(request, board, trigger='task_view')
        
        kwargs['task'] = task
        return view_func(request, *args, **kwargs)
    
    return wrapper


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def check_access_or_403(user, board):
    """
    Check access and raise PermissionDenied if not granted.
    
    Usage:
        check_access_or_403(request.user, board)
    """
    if not can_access_board(user, board):
        raise PermissionDenied("You don't have access to this board.")


def check_management_or_403(user, board):
    """
    Check management permission and raise PermissionDenied if not granted.
    
    Usage:
        check_management_or_403(request.user, board)
    """
    if not can_manage_board(user, board):
        raise PermissionDenied("Only board owner can perform this action.")


def get_accessible_boards(user, organization=None):
    """
    Get all boards accessible to a user.
    
    Args:
        user: User object
        organization: Optional organization filter
    
    Returns:
        Board queryset
    """
    from kanban.models import Board
    from kanban.utils.demo_protection import get_user_boards
    from django.db.models import Q
    
    if not user or not user.is_authenticated:
        return Board.objects.none()
    
    if user.is_superuser:
        # Even superusers should not see demo boards in My Workspace
        queryset = Board.objects.exclude(
            is_official_demo_board=True
        ).exclude(
            is_sandbox_copy=True
        ).exclude(
            created_by_session__startswith='spectra_demo_'
        )
    else:
        queryset = get_user_boards(user)
    
    if organization:
        queryset = queryset.filter(organization=organization)
    
    return queryset


# ============================================================================
# BACKWARDS COMPATIBILITY FUNCTIONS
# These maintain API compatibility with old RBAC code that may still reference them
# They all resolve to the simple access checks above
# ============================================================================

def user_has_board_permission(user, board, permission):
    """
    Backwards compatible: Check if user has permission on board.
    
    In the simplified model:
    - board.view, board.export, task.*, comment.*, etc. → can_access_board
    - board.delete, board.manage_members → can_manage_board
    """
    management_permissions = [
        'board.delete',
        'board.manage_members',
        'admin.full'
    ]
    
    if permission in management_permissions:
        return can_manage_board(user, board)
    
    return can_access_board(user, board)


def user_has_task_permission(user, task, permission):
    """Backwards compatible: Check if user has permission on task."""
    return can_access_task(user, task)


def user_has_column_permission(user, column, action):
    """Backwards compatible: Check column-level permission."""
    # All column actions allowed for board members
    return can_access_board(user, column.board)


def get_user_board_membership(user, board):
    """
    Backwards compatible: Get board membership.
    
    Returns a minimal object with role info for templates that expect it.
    """
    if not can_access_board(user, board):
        return None
    
    # Return a simple object that templates can use
    class SimpleMembership:
        def __init__(self, user, board):
            self.user = user
            self.board = board
            self.role = SimpleRole(user, board)
            self.is_active = True
        
        def has_permission(self, permission):
            return user_has_board_permission(self.user, self.board, permission)
    
    class SimpleRole:
        def __init__(self, user, board):
            if board.created_by == user:
                self.name = 'Owner'
            else:
                self.name = 'Member'
            self.permissions = ['admin.full'] if board.created_by == user else ['board.view', 'task.create', 'task.edit']
        
        def has_permission(self, permission):
            return True  # All members have all permissions
    
    return SimpleMembership(user, board)


def get_column_permissions_for_user(user, column):
    """Backwards compatible: Get column permissions for user."""
    # No column restrictions - full access
    return {
        'can_move_to': True,
        'can_move_from': True,
        'can_create_in': True,
        'can_edit_in': True
    }


def user_can_move_task_to_column(user, task, target_column):
    """Backwards compatible: Check if user can move task to column."""
    if can_modify_task(user, task):
        return True, None
    return False, "You don't have access to move this task"


def user_can_create_task_in_column(user, column):
    """Backwards compatible: Check if user can create task in column."""
    if can_modify_board_content(user, column.board):
        return True, None
    return False, "You don't have access to create tasks"


def user_can_edit_task_in_column(user, task):
    """Backwards compatible: Check if user can edit task in column."""
    if can_modify_task(user, task):
        return True, None
    return False, "You don't have access to edit this task"


# ============================================================================
# SPECTRA SMART DENIAL RESPONSES
# ============================================================================

def _get_board_owner_name(board):
    """Return the display name of the board's owner."""
    from kanban.models import BoardMembership
    owner_membership = BoardMembership.objects.filter(
        board=board, role='owner'
    ).select_related('user').first()
    owner = owner_membership.user if owner_membership else board.created_by
    if owner:
        return owner.get_full_name() or owner.username
    return 'the board owner'


def get_spectra_denial_context(user, board, trigger='board_view'):
    """
    Build a Spectra-style denial context dict suitable for both
    JSON API responses and template rendering.

    Returns a dict with:
        spectra_message  – The conversational denial message
        board_id         – Board PK
        board_name       – Board name
        owner_name       – Board owner display name
        has_pending      – Whether user already has a pending request
        can_request      – Whether user can send a request
        trigger          – What triggered the denial
    """
    from kanban.access_request_models import AccessRequest

    owner_name = _get_board_owner_name(board)
    has_pending = AccessRequest.has_pending(user, board)

    if has_pending:
        spectra_message = (
            f"I see you're trying to access the **{board.name}** board. "
            f"You already have a pending access request — "
            f"{owner_name} will be notified and can approve it from their dashboard. "
            f"I'll let you know as soon as there's an update!"
        )
        can_request = False
    else:
        spectra_message = (
            f"You don't currently have access to the **{board.name}** board. "
            f"Would you like me to send an automated access request to "
            f"{owner_name}? They'll receive a notification and can approve "
            f"it with one click."
        )
        can_request = True

    return {
        'spectra_message': spectra_message,
        'board_id': board.id,
        'board_name': board.name,
        'owner_name': owner_name,
        'has_pending': has_pending,
        'can_request': can_request,
        'trigger': trigger,
    }


def _spectra_denial_response(request, board, trigger='board_view'):
    """
    Return an HTTP response for a board access denial.

    - AJAX / API callers get a JSON 403 with Spectra context.
    - Regular page requests get rendered to the spectra_access_denied template.
    """
    from django.shortcuts import render

    ctx = get_spectra_denial_context(request.user, board, trigger=trigger)

    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or request.content_type == 'application/json'
        or request.path.startswith('/api/')
    )

    if is_ajax:
        return JsonResponse({
            'error': 'access_denied',
            'spectra': True,
            **ctx,
        }, status=403)

    return render(request, 'kanban/spectra_access_denied.html', ctx, status=403)


def user_can_manage_board_members(user, board):
    """Backwards compatible: Check if user can manage board members."""
    return can_manage_board(user, board)


def user_can_delete_board(user, board):
    """Backwards compatible: Check if user can delete board."""
    return can_manage_board(user, board)


def filter_boards_by_permission(user, queryset, permission):
    """Backwards compatible: Filter boards by permission."""
    # In simplified model, just filter by access
    accessible_board_ids = [
        board.id for board in queryset
        if can_access_board(user, board)
    ]
    return queryset.filter(id__in=accessible_board_ids)


def assign_default_role_to_user(user, board):
    """
    Backwards compatible: Add user as board member.
    
    Uses the new BoardMembership model.
    """
    from kanban.models import BoardMembership
    BoardMembership.objects.get_or_create(
        board=board, user=user,
        defaults={'role': 'member'}
    )
    return get_user_board_membership(user, board)


def get_user_permissions_for_board(user, board):
    """Backwards compatible: Get all permissions for user on board."""
    if can_manage_board(user, board):
        return ['admin.full']
    elif can_access_board(user, board):
        return ['board.view', 'task.create', 'task.edit', 'task.move', 'task.delete',
                'comment.create', 'comment.edit', 'label.assign', 'file.upload']
    return []


def check_permission_or_403(user, board, permission):
    """Backwards compatible: Check permission and raise if denied."""
    if not user_has_board_permission(user, board, permission):
        raise PermissionDenied(f"Access denied")


def get_permission_display_name(permission):
    """Backwards compatible: Get display name for permission."""
    display_names = {
        'board.view': 'View Board',
        'board.edit': 'Edit Board',
        'board.delete': 'Delete Board',
        'board.manage_members': 'Manage Members',
        'task.create': 'Create Tasks',
        'task.edit': 'Edit Tasks',
        'task.delete': 'Delete Tasks',
        'task.move': 'Move Tasks',
        'admin.full': 'Full Access',
    }
    return display_names.get(permission, permission.replace('.', ' ').title())


def get_available_roles_for_organization(organization):
    """Backwards compatible: Return available roles."""
    return ['owner', 'member', 'viewer']


# Decorator aliases for backwards compatibility
require_board_permission = lambda perm: require_board_access
require_task_permission = lambda perm: require_task_access
