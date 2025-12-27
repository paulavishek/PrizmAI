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
    # Superusers bypass all RBAC restrictions
    if user.is_superuser:
        return True
    
    # Board creator always has full access
    if board.created_by == user:
        return True
    
    # Organization admin always has full access
    if hasattr(user, 'profile') and user.profile.is_admin:
        if user.profile.organization_id == board.organization_id:
            return True
    
    # Demo boards: organization-level access
    # If user is a member of ANY board in this demo org, they can access ALL boards in that org
    demo_org_names = ['Dev Team', 'Marketing Team']
    if board.organization.name in demo_org_names:
        from kanban.models import Board as BoardModel
        user_has_demo_org_access = BoardModel.objects.filter(
            organization=board.organization,
            members=user
        ).exists()
        if user_has_demo_org_access:
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
    # Superusers bypass all RBAC restrictions
    if user.is_superuser:
        return True
    
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
    
    # Superusers bypass all RBAC restrictions
    if user.is_superuser:
        return True
    
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


def user_can_move_task_to_column(user, task, target_column):
    """
    Check if user can move a task to a specific column
    Combines task.move permission with column-level restrictions
    
    Args:
        user: User object
        task: Task object
        target_column: Column object (destination)
    
    Returns:
        (Boolean, error_message)
    """
    from kanban.permission_models import ColumnPermission
    
    # First check if user has basic task.move permission
    if not user_has_task_permission(user, task, 'task.move'):
        return False, "You don't have permission to move tasks"
    
    # Check if user can move FROM source column
    source_column = task.column
    membership = get_user_board_membership(user, source_column.board)
    if membership:
        try:
            source_perm = ColumnPermission.objects.get(
                column=source_column,
                role=membership.role
            )
            if not source_perm.can_move_from:
                return False, f"Cannot move tasks out of '{source_column.name}'"
        except ColumnPermission.DoesNotExist:
            pass  # No restriction
    
    # Check if user can move TO target column
    if membership:
        try:
            target_perm = ColumnPermission.objects.get(
                column=target_column,
                role=membership.role
            )
            if not target_perm.can_move_to:
                return False, f"Cannot move tasks into '{target_column.name}'"
        except ColumnPermission.DoesNotExist:
            pass  # No restriction
    
    return True, None


def user_can_create_task_in_column(user, column):
    """
    Check if user can create a task in a specific column
    
    Args:
        user: User object
        column: Column object
    
    Returns:
        (Boolean, error_message)
    """
    from kanban.permission_models import ColumnPermission
    
    # First check if user has basic task.create permission
    if not user_has_board_permission(user, column.board, 'task.create'):
        return False, "You don't have permission to create tasks"
    
    # Check column-level restriction
    membership = get_user_board_membership(user, column.board)
    if membership:
        try:
            col_perm = ColumnPermission.objects.get(
                column=column,
                role=membership.role
            )
            if not col_perm.can_create_in:
                return False, f"Cannot create tasks in '{column.name}'"
        except ColumnPermission.DoesNotExist:
            pass  # No restriction
    
    return True, None


def user_can_edit_task_in_column(user, task):
    """
    Check if user can edit a task in its current column
    
    Args:
        user: User object
        task: Task object
    
    Returns:
        (Boolean, error_message)
    """
    from kanban.permission_models import ColumnPermission
    
    # Check if user has edit permission (regular or own)
    can_edit = user_has_task_permission(user, task, 'task.edit')
    can_edit_own = user_has_task_permission(user, task, 'task.edit_own')
    
    if not (can_edit or can_edit_own):
        return False, "You don't have permission to edit this task"
    
    # Check column-level restriction
    column = task.column
    membership = get_user_board_membership(user, column.board)
    if membership:
        try:
            col_perm = ColumnPermission.objects.get(
                column=column,
                role=membership.role
            )
            if not col_perm.can_edit_in:
                return False, f"Cannot edit tasks in '{column.name}'"
        except ColumnPermission.DoesNotExist:
            pass  # No restriction
    
    return True, None


def filter_tasks_by_permission(user, queryset, permission='task.view'):
    """
    Filter task queryset based on user permissions
    Handles task.view_own by only showing assigned/created tasks
    
    Args:
        user: User object
        queryset: Task queryset
        permission: Permission to check (default: 'task.view')
    
    Returns:
        Filtered queryset
    """
    from django.db.models import Q
    
    # Get all boards the queryset covers
    boards = queryset.values_list('column__board', flat=True).distinct()
    
    accessible_tasks = []
    restricted_boards = []
    
    for board_id in boards:
        from kanban.models import Board
        try:
            board = Board.objects.get(id=board_id)
            
            # Check if user has full view permission
            if user_has_board_permission(user, board, permission):
                # User can see all tasks from this board
                accessible_tasks.extend(
                    queryset.filter(column__board=board).values_list('id', flat=True)
                )
            # Check if user has view_own permission
            elif user_has_board_permission(user, board, f'{permission}_own'):
                # User can only see their own tasks
                restricted_boards.append(board_id)
            # else: user has no access to this board
            
        except Board.DoesNotExist:
            pass
    
    # Build final queryset
    if restricted_boards:
        own_tasks = queryset.filter(
            column__board_id__in=restricted_boards
        ).filter(
            Q(assigned_to=user) | Q(created_by=user)
        ).values_list('id', flat=True)
        accessible_tasks.extend(own_tasks)
    
    return queryset.filter(id__in=accessible_tasks)


def get_column_permissions_for_user(user, column):
    """
    Get all column permissions for a user
    
    Args:
        user: User object
        column: Column object
    
    Returns:
        dict with permission flags or None if no restrictions
    """
    from kanban.permission_models import ColumnPermission
    
    membership = get_user_board_membership(user, column.board)
    if not membership:
        return None
    
    try:
        col_perm = ColumnPermission.objects.get(
            column=column,
            role=membership.role
        )
        return {
            'can_move_to': col_perm.can_move_to,
            'can_move_from': col_perm.can_move_from,
            'can_create_in': col_perm.can_create_in,
            'can_edit_in': col_perm.can_edit_in,
        }
    except ColumnPermission.DoesNotExist:
        # No restrictions - all allowed
        return {
            'can_move_to': True,
            'can_move_from': True,
            'can_create_in': True,
            'can_edit_in': True,
        }


def bulk_assign_role(users, board, role, added_by=None):
    """
    Assign a role to multiple users on a board
    
    Args:
        users: List of User objects
        board: Board object
        role: Role object
        added_by: User who is adding members (optional)
    
    Returns:
        (created_count, updated_count)
    """
    created = 0
    updated = 0
    
    for user in users:
        membership, was_created = BoardMembership.objects.update_or_create(
            board=board,
            user=user,
            defaults={
                'role': role,
                'added_by': added_by,
                'is_active': True
            }
        )
        if was_created:
            created += 1
        else:
            updated += 1
    
    return created, updated
