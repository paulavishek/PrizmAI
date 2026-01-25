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
- Organization members: Can access all boards in their org
"""

from functools import wraps
from django.http import HttpResponseForbidden
from django.core.exceptions import PermissionDenied


# ============================================================================
# CORE ACCESS CHECKS (SIMPLIFIED)
# ============================================================================

def can_access_board(user, board):
    """
    Check if user can access a board.
    
    Rules:
    - Superusers can access everything
    - Board creator can access
    - Board members can access
    - Organization members can access their org's boards
    
    Returns:
        Boolean
    """
    if not user or not user.is_authenticated:
        return False
    
    # Superusers bypass all checks
    if user.is_superuser:
        return True
    
    # Board creator always has access
    if board.created_by == user:
        return True
    
    # Board members have access
    if user in board.members.all():
        return True
    
    # Organization members can access org boards
    if hasattr(user, 'profile') and user.profile.organization_id == board.organization_id:
        return True
    
    return False


def can_manage_board(user, board):
    """
    Check if user can manage a board (delete, manage members).
    
    Only:
    - Board creator
    - Organization admins
    - Superusers
    
    Returns:
        Boolean
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser:
        return True
    
    if board.created_by == user:
        return True
    
    # Organization admin
    if hasattr(user, 'profile') and user.profile.is_admin:
        if user.profile.organization_id == board.organization_id:
            return True
    
    return False


def can_modify_board_content(user, board):
    """
    Check if user can create/edit/delete tasks, columns, comments, etc.
    
    All board members (including creator) can modify content.
    
    Returns:
        Boolean
    """
    # Same as can_access_board - all members have full CRUD
    return can_access_board(user, board)


def can_access_task(user, task):
    """
    Check if user can access a task.
    
    Rules:
    - User must be able to access the board
    
    Returns:
        Boolean
    """
    return can_access_board(user, task.column.board)


def can_modify_task(user, task):
    """
    Check if user can modify a task.
    
    All board members can modify any task.
    
    Returns:
        Boolean
    """
    return can_modify_board_content(user, task.column.board)


# ============================================================================
# DECORATORS (SIMPLIFIED)
# ============================================================================

def require_board_access(view_func):
    """
    Decorator to require board access.
    
    Usage:
        @login_required
        @require_board_access
        def my_view(request, board_id):
            ...
    
    Assumes board_id is in kwargs.
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
            return HttpResponseForbidden("You don't have access to this board.")
        
        kwargs['board'] = board
        return view_func(request, *args, **kwargs)
    
    return wrapper


def require_board_management(view_func):
    """
    Decorator to require board management permission.
    
    Usage:
        @login_required
        @require_board_management
        def delete_board(request, board_id):
            ...
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
        
        if not can_manage_board(request.user, board):
            return HttpResponseForbidden("Only board owner can perform this action.")
        
        kwargs['board'] = board
        return view_func(request, *args, **kwargs)
    
    return wrapper


def require_task_access(view_func):
    """
    Decorator to require task access.
    
    Usage:
        @login_required
        @require_task_access
        def task_detail(request, task_id):
            ...
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
            return HttpResponseForbidden("You don't have access to this task.")
        
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
    from django.db.models import Q
    
    if not user or not user.is_authenticated:
        return Board.objects.none()
    
    if user.is_superuser:
        queryset = Board.objects.all()
    else:
        # Boards created by user OR where user is member OR in user's org
        queryset = Board.objects.filter(
            Q(created_by=user) |
            Q(members=user) |
            Q(organization=user.profile.organization if hasattr(user, 'profile') else None)
        ).distinct()
    
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
    
    In simplified model, just add to Board.members.
    """
    board.members.add(user)
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
    """Backwards compatible: Return empty since we don't use roles."""
    # Return empty queryset to avoid breaking code that expects this
    from kanban.permission_models import Role
    return Role.objects.none()


# Decorator aliases for backwards compatibility
require_board_permission = lambda perm: require_board_access
require_task_permission = lambda perm: require_task_access
