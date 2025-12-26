"""
Permission Audit Utilities
Helper functions for logging permission changes
"""
from kanban.permission_models import PermissionAuditLog


def get_client_ip(request):
    """Extract client IP from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def log_permission_change(action, actor, organization=None, board=None, 
                         affected_user=None, details=None, request=None):
    """
    Log a permission-related change
    
    Args:
        action: Action type (from PermissionAuditLog.ACTION_CHOICES)
        actor: User who performed the action
        organization: Organization context (optional)
        board: Board context (optional)
        affected_user: User who was affected (optional)
        details: Dict with additional details (optional)
        request: HTTP request for IP/user-agent (optional)
    
    Returns:
        PermissionAuditLog instance
    """
    log_data = {
        'action': action,
        'actor': actor,
        'organization': organization,
        'board': board,
        'affected_user': affected_user,
        'details': details or {},
    }
    
    if request:
        log_data['ip_address'] = get_client_ip(request)
        log_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')[:500]
    
    return PermissionAuditLog.objects.create(**log_data)


def log_role_created(role, created_by, request=None):
    """Log when a new role is created"""
    return log_permission_change(
        action='role_created',
        actor=created_by,
        organization=role.organization,
        details={
            'role_name': role.name,
            'role_id': role.id,
            'permissions': role.permissions,
            'is_default': role.is_default,
        },
        request=request
    )


def log_role_updated(role, updated_by, old_data, request=None):
    """Log when a role is modified"""
    return log_permission_change(
        action='role_updated',
        actor=updated_by,
        organization=role.organization,
        details={
            'role_name': role.name,
            'role_id': role.id,
            'old_permissions': old_data.get('permissions', []),
            'new_permissions': role.permissions,
            'changes': old_data,
        },
        request=request
    )


def log_role_deleted(role, deleted_by, request=None):
    """Log when a role is deleted"""
    return log_permission_change(
        action='role_deleted',
        actor=deleted_by,
        organization=role.organization,
        details={
            'role_name': role.name,
            'role_id': role.id,
            'permissions': role.permissions,
        },
        request=request
    )


def log_member_added(membership, added_by, request=None):
    """Log when a member is added to a board"""
    return log_permission_change(
        action='member_added',
        actor=added_by,
        organization=membership.board.organization,
        board=membership.board,
        affected_user=membership.user,
        details={
            'role_name': membership.role.name,
            'role_id': membership.role.id,
            'board_name': membership.board.name,
            'expires_at': membership.expires_at.isoformat() if membership.expires_at else None,
        },
        request=request
    )


def log_member_removed(membership, removed_by, request=None):
    """Log when a member is removed from a board"""
    return log_permission_change(
        action='member_removed',
        actor=removed_by,
        organization=membership.board.organization,
        board=membership.board,
        affected_user=membership.user,
        details={
            'role_name': membership.role.name,
            'board_name': membership.board.name,
        },
        request=request
    )


def log_member_role_changed(membership, changed_by, old_role, new_role, request=None):
    """Log when a member's role is changed"""
    return log_permission_change(
        action='member_role_changed',
        actor=changed_by,
        organization=membership.board.organization,
        board=membership.board,
        affected_user=membership.user,
        details={
            'old_role': old_role.name,
            'old_role_id': old_role.id,
            'new_role': new_role.name,
            'new_role_id': new_role.id,
            'board_name': membership.board.name,
        },
        request=request
    )


def log_permission_override(override, created_by, request=None):
    """Log when a permission override is added"""
    return log_permission_change(
        action='override_added',
        actor=created_by,
        organization=override.membership.board.organization,
        board=override.membership.board,
        affected_user=override.membership.user,
        details={
            'permission': override.permission,
            'override_type': override.override_type,
            'reason': override.reason,
            'expires_at': override.expires_at.isoformat() if override.expires_at else None,
        },
        request=request
    )


def log_column_permission_set(column_permission, set_by, request=None):
    """Log when column permissions are set or changed"""
    return log_permission_change(
        action='column_permission_set',
        actor=set_by,
        organization=column_permission.column.board.organization,
        board=column_permission.column.board,
        details={
            'column_name': column_permission.column.name,
            'role_name': column_permission.role.name,
            'can_move_to': column_permission.can_move_to,
            'can_move_from': column_permission.can_move_from,
            'can_create_in': column_permission.can_create_in,
            'can_edit_in': column_permission.can_edit_in,
        },
        request=request
    )


def get_permission_audit_log(organization=None, board=None, user=None, 
                             action=None, limit=100):
    """
    Query permission audit logs with filters
    
    Args:
        organization: Filter by organization
        board: Filter by board
        user: Filter by actor or affected_user
        action: Filter by action type
        limit: Max number of results
    
    Returns:
        QuerySet of PermissionAuditLog
    """
    queryset = PermissionAuditLog.objects.all()
    
    if organization:
        queryset = queryset.filter(organization=organization)
    
    if board:
        queryset = queryset.filter(board=board)
    
    if user:
        from django.db.models import Q
        queryset = queryset.filter(
            Q(actor=user) | Q(affected_user=user)
        )
    
    if action:
        queryset = queryset.filter(action=action)
    
    return queryset.select_related(
        'actor', 'affected_user', 'organization', 'board'
    )[:limit]
