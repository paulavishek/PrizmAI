"""
Permission Checking Utilities
Helper functions for RBAC enforcement
"""
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden
from functools import wraps
from kanban.permission_models import BoardMembership, PermissionOverride


def get_user_board_membership(user, board):
    """
    Get active board membership for a user
    
    Returns:
        BoardMembership object or None
    """
    try:
        membership = BoardMembership.objects.select_related('role').get(
            user=user,
            board=board,
            is_active=True
        )
        
        # Check expiration
        if membership.expires_at:
            from django.utils import timezone
            if timezone.now() > membership.expires_at:
                return None
        
        return membership
    except BoardMembership.DoesNotExist:
        return None


def user_has_board_permission(user, board, permission):
    """
    Check if user has a specific permission on a board
    
    Args:
        user: User object
        board: Board object
        permission: Permission string (e.g., 'task.create')
    
    Returns:
        Boolean
    """
    # Board creator always has full access
    if board.created_by == user:
        return True
    
    # Organization admin always has full access
    if hasattr(user, 'profile') and user.profile.is_admin:
        if user.profile.organization_id == board.organization_id:
            return True
    
    # Check board membership
    membership = get_user_board_membership(user, board)
    if not membership:
        return False
    
    # Check for explicit deny override
    deny_override = PermissionOverride.objects.filter(
        membership=membership,
        permission=permission,
        override_type='deny'
    ).first()
    
    if deny_override and deny_override.is_active():
        return False
    
    # Check role permission
    has_role_permission = membership.has_permission(permission)
    
    # Check for explicit grant override
    grant_override = PermissionOverride.objects.filter(
        membership=membership,
        permission=permission,
        override_type='grant'
    ).first()
    
    if grant_override and grant_override.is_active():
        return True
    
    return has_role_permission


def user_has_task_permission(user, task, permission):
    """
    Check if user has permission to perform an action on a task
    
    Args:
        user: User object
        task: Task object
        permission: Permission string
    
    Returns:
        Boolean
    """
    board = task.column.board
    
    # For "own" permissions, check if task is assigned to user
    if permission.endswith('_own'):
        base_permission = permission.replace('_own', '')
        if task.assigned_to == user or task.created_by == user:
            return user_has_board_permission(user, board, permission) or \
                   user_has_board_permission(user, board, base_permission)
        return False
    
    return user_has_board_permission(user, board, permission)


def user_has_column_permission(user, column, action):
    """
    Check if user can perform action on a specific column
    
    Args:
        user: User object
        column: Column object
        action: Action to perform (move_to, move_from, create_in, edit_in)
    
    Returns:
        Boolean
    """
    from kanban.permission_models import ColumnPermission
    
    membership = get_user_board_membership(user, column.board)
    if not membership:
        return False
    
    try:
        col_perm = ColumnPermission.objects.get(
            column=column,
            role=membership.role
        )
        return getattr(col_perm, f'can_{action}', True)
    except ColumnPermission.DoesNotExist:
        # No specific column permission, allow by default
        return True


def require_board_permission(permission):
    """
    Decorator to require specific board permission
    
    Usage:
        @login_required
        @require_board_permission('task.create')
        def create_task(request, board_id):
            board = get_object_or_404(Board, id=board_id)
            # ... create task
    
    Assumes view has board_id parameter or board object in kwargs
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from django.shortcuts import get_object_or_404
            from kanban.models import Board
            
            # Try to get board from kwargs
            board_id = kwargs.get('board_id') or kwargs.get('pk')
            if board_id:
                board = get_object_or_404(Board, id=board_id)
            elif 'board' in kwargs:
                board = kwargs['board']
            else:
                raise ValueError("Board not found in view kwargs")
            
            # Check permission
            if not user_has_board_permission(request.user, board, permission):
                # Log access denied
                from kanban.audit_utils import log_access_denied
                log_access_denied(
                    user=request.user,
                    request=request,
                    resource_type='board',
                    resource_id=board.id,
                    permission_required=permission
                )
                return HttpResponseForbidden(
                    f"You don't have permission to perform this action. Required permission: {permission}"
                )
            
            # Add board to kwargs for convenience
            kwargs['board'] = board
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def require_task_permission(permission):
    """
    Decorator to require specific task permission
    
    Usage:
        @login_required
        @require_task_permission('task.delete')
        def delete_task(request, task_id):
            task = get_object_or_404(Task, id=task_id)
            # ... delete task
    
    Assumes view has task_id parameter or task object in kwargs
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from django.shortcuts import get_object_or_404
            from kanban.models import Task
            
            # Try to get task from kwargs
            task_id = kwargs.get('task_id') or kwargs.get('pk')
            if task_id:
                task = get_object_or_404(Task, id=task_id)
            elif 'task' in kwargs:
                task = kwargs['task']
            else:
                raise ValueError("Task not found in view kwargs")
            
            # Check permission
            if not user_has_task_permission(request.user, task, permission):
                # Log access denied
                from kanban.audit_utils import log_access_denied
                log_access_denied(
                    user=request.user,
                    request=request,
                    resource_type='task',
                    resource_id=task.id,
                    permission_required=permission
                )
                return HttpResponseForbidden(
                    f"You don't have permission to perform this action. Required permission: {permission}"
                )
            
            # Add task to kwargs for convenience
            kwargs['task'] = task
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def check_permission_or_403(user, board, permission):
    """
    Check permission and raise PermissionDenied if not granted
    
    Usage:
        check_permission_or_403(request.user, board, 'task.create')
    """
    if not user_has_board_permission(user, board, permission):
        raise PermissionDenied(f"Required permission: {permission}")


def get_user_permissions_for_board(user, board):
    """
    Get all permissions a user has on a board
    
    Returns:
        List of permission strings
    """
    membership = get_user_board_membership(user, board)
    if not membership:
        return []
    
    permissions = set(membership.role.permissions)
    
    # Apply overrides
    overrides = PermissionOverride.objects.filter(membership=membership)
    for override in overrides:
        if override.is_active():
            if override.override_type == 'grant':
                permissions.add(override.permission)
            elif override.override_type == 'deny':
                permissions.discard(override.permission)
    
    return list(permissions)


def user_can_manage_board_members(user, board):
    """Check if user can add/remove board members"""
    return user_has_board_permission(user, board, 'board.manage_members')


def user_can_delete_board(user, board):
    """Check if user can delete a board"""
    # Only creator or org admin can delete boards
    if board.created_by == user:
        return True
    
    if hasattr(user, 'profile') and user.profile.is_admin:
        return user.profile.organization_id == board.organization_id
    
    return user_has_board_permission(user, board, 'board.delete')


def filter_boards_by_permission(user, queryset, permission):
    """
    Filter board queryset to only boards where user has specific permission
    
    Args:
        user: User object
        queryset: Board queryset
        permission: Permission string to check
    
    Returns:
        Filtered queryset
    """
    accessible_boards = []
    
    for board in queryset:
        if user_has_board_permission(user, board, permission):
            accessible_boards.append(board.id)
    
    return queryset.filter(id__in=accessible_boards)


def get_permission_display_name(permission):
    """
    Get human-readable name for permission
    
    Args:
        permission: Permission string (e.g., 'task.create')
    
    Returns:
        Display name (e.g., 'Create Tasks')
    """
    from kanban.permission_models import Role
    
    for perm, name, desc in Role.AVAILABLE_PERMISSIONS:
        if perm == permission:
            return name
    
    return permission.replace('_', ' ').replace('.', ' - ').title()


def get_available_roles_for_organization(organization):
    """
    Get all available roles for an organization
    
    Returns:
        QuerySet of Role objects
    """
    from kanban.permission_models import Role
    return Role.objects.filter(organization=organization).order_by('name')


def assign_default_role_to_user(user, board):
    """
    Assign default role to user on a board
    
    Args:
        user: User to assign role to
        board: Board object
    
    Returns:
        BoardMembership object
    """
    from kanban.permission_models import Role
    
    # Get default role for organization
    default_role = Role.objects.filter(
        organization=board.organization,
        is_default=True
    ).first()
    
    if not default_role:
        # Fallback to Editor role
        default_role = Role.objects.filter(
            organization=board.organization,
            name='Editor'
        ).first()
    
    if not default_role:
        raise ValueError("No default role found for organization")
    
    # Create membership
    membership, created = BoardMembership.objects.get_or_create(
        board=board,
        user=user,
        defaults={
            'role': default_role,
            'added_by': board.created_by
        }
    )
    
    return membership
