"""
Permission Management Views
Views for managing roles, permissions, and board memberships
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Count, Q
from django.contrib.auth.models import User

from kanban.models import Board
from accounts.models import Organization
from kanban.permission_models import Role, BoardMembership, PermissionOverride, ColumnPermission
from kanban.permission_utils import user_has_board_permission, get_user_board_membership
from kanban.permission_audit import (
    log_role_created, log_role_updated, log_role_deleted,
    log_member_added, log_member_removed, log_member_role_changed,
    log_permission_override, get_permission_audit_log
)


@login_required
def manage_roles(request, organization_id=None):
    """View and manage roles for an organization"""
    # Get user's organization
    if organization_id:
        organization = get_object_or_404(Organization, id=organization_id)
        # Check if user is admin of this organization
        if not request.user.profile.is_admin or request.user.profile.organization != organization:
            return HttpResponseForbidden("You don't have permission to manage roles for this organization.")
    else:
        organization = request.user.profile.organization
    
    # Get all roles for this organization
    roles = Role.objects.filter(organization=organization).annotate(
        member_count=Count('board_memberships')
    ).order_by('-is_system_role', 'name')
    
    # Get permission categories
    permission_categories = {}
    for perm, name, desc in Role.AVAILABLE_PERMISSIONS:
        category = perm.split('.')[0]
        if category not in permission_categories:
            permission_categories[category] = []
        permission_categories[category].append({
            'code': perm,
            'name': name,
            'description': desc
        })
    
    context = {
        'organization': organization,
        'roles': roles,
        'permission_categories': permission_categories,
    }
    
    return render(request, 'kanban/permissions/manage_roles.html', context)


@login_required
def create_role(request, organization_id=None):
    """Create a new custom role"""
    if organization_id:
        organization = get_object_or_404(Organization, id=organization_id)
    else:
        organization = request.user.profile.organization
    
    # Check if user is admin
    if not request.user.profile.is_admin or request.user.profile.organization != organization:
        return HttpResponseForbidden("You don't have permission to create roles.")
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        is_default = request.POST.get('is_default') == 'on'
        selected_permissions = request.POST.getlist('permissions')
        
        if not name:
            messages.error(request, 'Role name is required.')
            return redirect('manage_roles')
        
        # Check if role name already exists
        if Role.objects.filter(organization=organization, name=name).exists():
            messages.error(request, f'Role "{name}" already exists.')
            return redirect('manage_roles')
        
        # Validate permissions
        valid_permissions = [p[0] for p in Role.AVAILABLE_PERMISSIONS]
        filtered_permissions = [p for p in selected_permissions if p in valid_permissions]
        
        # Create role
        role = Role.objects.create(
            organization=organization,
            name=name,
            description=description,
            is_default=is_default,
            permissions=filtered_permissions,
            created_by=request.user
        )
        
        # If set as default, remove default from other roles
        if is_default:
            Role.objects.filter(
                organization=organization
            ).exclude(id=role.id).update(is_default=False)
        
        # Log the creation
        log_role_created(role, request.user, request)
        
        messages.success(request, f'Role "{role.name}" created successfully!')
        return redirect('manage_roles')
    
    return redirect('manage_roles')


@login_required
def edit_role(request, role_id):
    """Edit an existing role"""
    role = get_object_or_404(Role, id=role_id)
    organization = role.organization
    
    # Check if user is admin
    if not request.user.profile.is_admin or request.user.profile.organization != organization:
        return HttpResponseForbidden("You don't have permission to edit roles.")
    
    # System roles cannot be fully edited
    if role.is_system_role:
        messages.warning(request, 'System roles cannot be modified.')
        return redirect('manage_roles')
    
    if request.method == 'POST':
        # Store old data for audit
        old_data = {
            'name': role.name,
            'description': role.description,
            'permissions': role.permissions.copy(),
            'is_default': role.is_default,
        }
        
        role.name = request.POST.get('name', role.name).strip()
        role.description = request.POST.get('description', '').strip()
        role.is_default = request.POST.get('is_default') == 'on'
        role.permissions = request.POST.getlist('permissions')
        
        try:
            role.save()
            
            # If set as default, remove default from other roles
            if role.is_default:
                Role.objects.filter(
                    organization=organization
                ).exclude(id=role.id).update(is_default=False)
            
            # Log the update
            log_role_updated(role, request.user, old_data, request)
            
            messages.success(request, f'Role "{role.name}" updated successfully!')
        except Exception as e:
            messages.error(request, f'Error updating role: {str(e)}')
        
        return redirect('manage_roles')
    
    return redirect('manage_roles')


@login_required
def delete_role(request, role_id):
    """Delete a custom role"""
    role = get_object_or_404(Role, id=role_id)
    organization = role.organization
    
    # Check if user is admin
    if not request.user.profile.is_admin or request.user.profile.organization != organization:
        return HttpResponseForbidden("You don't have permission to delete roles.")
    
    # System roles cannot be deleted
    if role.is_system_role:
        messages.error(request, 'System roles cannot be deleted.')
        return redirect('manage_roles')
    
    # Check if role is in use
    member_count = BoardMembership.objects.filter(role=role).count()
    if member_count > 0:
        messages.error(request, f'Cannot delete role "{role.name}" because it is assigned to {member_count} member(s). Reassign members first.')
        return redirect('manage_roles')
    
    role_name = role.name
    log_role_deleted(role, request.user, request)
    role.delete()
    
    messages.success(request, f'Role "{role_name}" deleted successfully!')
    return redirect('manage_roles')


@login_required
def manage_board_members(request, board_id):
    """Manage members and their roles on a specific board"""
    board = get_object_or_404(Board, id=board_id)
    
    # Check if user can manage members
    if not user_has_board_permission(request.user, board, 'board.manage_members'):
        return HttpResponseForbidden("You don't have permission to manage board members.")
    
    # Get all memberships with role info
    memberships = BoardMembership.objects.filter(
        board=board
    ).select_related('user', 'user__profile', 'role', 'added_by').order_by('-added_at')
    
    # Get available roles (all roles since organization restrictions are removed)
    available_roles = Role.objects.all().order_by('name')
    
    # Get all users who aren't members yet (organization restrictions removed)
    org_users = User.objects.exclude(
        id__in=memberships.values_list('user_id', flat=True)
    ).select_related('profile')
    
    context = {
        'board': board,
        'memberships': memberships,
        'available_roles': available_roles,
        'org_users': org_users,
    }
    
    return render(request, 'kanban/permissions/manage_board_members.html', context)


@login_required
def change_member_role(request, membership_id):
    """Change a member's role on a board"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    membership = get_object_or_404(BoardMembership, id=membership_id)
    board = membership.board
    
    # Check permission
    if not user_has_board_permission(request.user, board, 'board.manage_members'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    new_role_id = request.POST.get('role_id')
    new_role = get_object_or_404(Role, id=new_role_id, organization=board.organization)
    
    old_role = membership.role
    membership.role = new_role
    membership.save()
    
    # Log the change
    log_member_role_changed(membership, request.user, old_role, new_role, request)
    
    messages.success(request, f'Updated {membership.user.username} to {new_role.name} role.')
    return JsonResponse({'success': True, 'new_role': new_role.name})


@login_required
def add_board_member_with_role(request, board_id):
    """Add a new member to a board with a specific role"""
    if request.method != 'POST':
        return redirect('manage_board_members', board_id=board_id)
    
    board = get_object_or_404(Board, id=board_id)
    
    # Check permission
    if not user_has_board_permission(request.user, board, 'board.manage_members'):
        return HttpResponseForbidden("You don't have permission to add members.")
    
    user_id = request.POST.get('user_id')
    role_id = request.POST.get('role_id')
    
    user = get_object_or_404(User, id=user_id)
    # Get role without organization filter since restrictions are removed
    role = get_object_or_404(Role, id=role_id)
    
    # Organization check removed - all users can be added to any board
    
    # Create or update membership
    membership, created = BoardMembership.objects.update_or_create(
        board=board,
        user=user,
        defaults={
            'role': role,
            'added_by': request.user,
            'is_active': True
        }
    )
    
    # Add to board members M2M (for backward compatibility)
    if user not in board.members.all():
        board.members.add(user)
    
    # Log the addition
    log_member_added(membership, request.user, request)
    
    action = 'added' if created else 'updated'
    messages.success(request, f'{user.username} {action} as {role.name}.')
    return redirect('manage_board_members', board_id=board_id)


@login_required
def remove_board_member_role(request, membership_id):
    """Remove a member from a board"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=400)
    
    membership = get_object_or_404(BoardMembership, id=membership_id)
    board = membership.board
    user = membership.user
    
    # Check permission
    if not user_has_board_permission(request.user, board, 'board.manage_members'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    # Don't allow removing the board creator
    if user == board.created_by:
        return JsonResponse({'error': 'Cannot remove board creator'}, status=400)
    
    # Log the removal
    log_member_removed(membership, request.user, request)
    
    username = user.username
    membership.delete()
    
    # Remove from board members M2M
    board.members.remove(user)
    
    messages.success(request, f'Removed {username} from board.')
    return JsonResponse({'success': True})


@login_required
def view_permission_audit(request, board_id=None):
    """View permission audit log for a board or organization"""
    if board_id:
        board = get_object_or_404(Board, id=board_id)
        # Access restriction removed - all authenticated users can access
        
        audit_logs = get_permission_audit_log(board=board, limit=200)
        context = {
            'board': board,
            'audit_logs': audit_logs,
            'title': f'Permission Audit Log - {board.name}'
        }
    else:
        # Organization-level audit - all authenticated users can access
        
        organization = request.user.profile.organization
        audit_logs = get_permission_audit_log(organization=organization, limit=200)
        context = {
            'organization': organization,
            'audit_logs': audit_logs,
            'title': f'Permission Audit Log - {organization.name}'
        }
    
    return render(request, 'kanban/permissions/audit_log.html', context)
