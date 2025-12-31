"""
Role-Based Access Control (RBAC) Models for PrizmAI
Provides granular permissions and role management
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from accounts.models import Organization
from kanban.models import Board


class Role(models.Model):
    """
    Define roles with specific permissions
    Can be organization-wide or board-specific
    """
    name = models.CharField(max_length=50, help_text="Role name (e.g., 'Project Manager', 'Viewer')")
    description = models.TextField(blank=True, help_text="What this role can do")
    
    # Scope
    organization = models.ForeignKey(
        Organization, 
        on_delete=models.CASCADE, 
        related_name='roles',
        help_text="Organization this role belongs to"
    )
    
    # Permissions (list of permission strings)
    permissions = models.JSONField(
        default=list,
        help_text="List of permission strings (e.g., ['board.view', 'task.create'])"
    )
    
    # System roles cannot be modified or deleted
    is_system_role = models.BooleanField(
        default=False, 
        help_text="System-defined role (cannot be deleted)"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Default role for new board members"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='created_roles'
    )
    updated_at = models.DateTimeField(auto_now=True)
    
    # All Available Permissions
    AVAILABLE_PERMISSIONS = [
        # Board Permissions
        ('board.view', 'View Board', 'Can view board and its contents'),
        ('board.create', 'Create Board', 'Can create new boards'),
        ('board.edit', 'Edit Board', 'Can modify board settings'),
        ('board.delete', 'Delete Board', 'Can delete boards'),
        ('board.manage_members', 'Manage Members', 'Can add/remove board members'),
        ('board.export', 'Export Board', 'Can export board data'),
        
        # Column Permissions
        ('column.create', 'Create Column', 'Can create new columns'),
        ('column.edit', 'Edit Column', 'Can modify column settings'),
        ('column.delete', 'Delete Column', 'Can delete columns'),
        ('column.reorder', 'Reorder Columns', 'Can change column order'),
        
        # Task Permissions
        ('task.view', 'View Tasks', 'Can view all tasks on the board'),
        ('task.view_own', 'View Own Tasks', 'Can only view tasks assigned to them'),
        ('task.create', 'Create Tasks', 'Can create new tasks'),
        ('task.edit', 'Edit Tasks', 'Can modify any task'),
        ('task.edit_own', 'Edit Own Tasks', 'Can only edit tasks assigned to them'),
        ('task.delete', 'Delete Tasks', 'Can delete any task'),
        ('task.delete_own', 'Delete Own Tasks', 'Can only delete tasks they created'),
        ('task.assign', 'Assign Tasks', 'Can assign tasks to users'),
        ('task.move', 'Move Tasks', 'Can move tasks between columns'),
        
        # Comment Permissions
        ('comment.view', 'View Comments', 'Can view task comments'),
        ('comment.create', 'Create Comments', 'Can add comments to tasks'),
        ('comment.edit', 'Edit Comments', 'Can edit any comment'),
        ('comment.edit_own', 'Edit Own Comments', 'Can only edit their own comments'),
        ('comment.delete', 'Delete Comments', 'Can delete any comment'),
        ('comment.delete_own', 'Delete Own Comments', 'Can only delete their own comments'),
        
        # Label Permissions
        ('label.view', 'View Labels', 'Can see task labels'),
        ('label.create', 'Create Labels', 'Can create new labels'),
        ('label.edit', 'Edit Labels', 'Can modify labels'),
        ('label.delete', 'Delete Labels', 'Can delete labels'),
        ('label.assign', 'Assign Labels', 'Can assign labels to tasks'),
        
        # File Permissions
        ('file.view', 'View Files', 'Can view file attachments'),
        ('file.upload', 'Upload Files', 'Can upload file attachments'),
        ('file.download', 'Download Files', 'Can download file attachments'),
        ('file.delete', 'Delete Files', 'Can delete file attachments'),
        
        # Advanced Permissions
        ('webhook.manage', 'Manage Webhooks', 'Can create/edit/delete webhooks'),
        ('api.access', 'API Access', 'Can use API tokens for this board'),
        ('analytics.view', 'View Analytics', 'Can view board analytics and reports'),
        ('audit.view', 'View Audit Logs', 'Can view audit logs for this board'),
        
        # Data Permissions
        ('data.export', 'Export Data', 'Can export board data'),
        ('data.import', 'Import Data', 'Can import data to board'),
        
        # Administrative
        ('admin.full', 'Full Admin', 'Complete administrative access'),
    ]
    
    class Meta:
        ordering = ['organization', 'name']
        unique_together = ['organization', 'name']
        indexes = [
            models.Index(fields=['organization', 'name']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.organization.name})"
    
    def clean(self):
        """Validate permissions"""
        valid_permissions = [p[0] for p in self.AVAILABLE_PERMISSIONS]
        for perm in self.permissions:
            if perm not in valid_permissions:
                raise ValidationError(f"Invalid permission: {perm}")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def has_permission(self, permission):
        """Check if role has a specific permission"""
        return permission in self.permissions or 'admin.full' in self.permissions
    
    def add_permission(self, permission):
        """Add a permission to this role"""
        if permission not in self.permissions:
            self.permissions.append(permission)
            self.save()
    
    def remove_permission(self, permission):
        """Remove a permission from this role"""
        if permission in self.permissions:
            self.permissions.remove(permission)
            self.save()
    
    @classmethod
    def create_default_roles(cls, organization):
        """Create default system roles for an organization"""
        # Admin Role
        admin_role, _ = cls.objects.get_or_create(
            organization=organization,
            name='Admin',
            defaults={
                'description': 'Full administrative access to boards',
                'permissions': ['admin.full'],
                'is_system_role': True,
                'is_default': False
            }
        )
        
        # Editor Role
        editor_role, _ = cls.objects.get_or_create(
            organization=organization,
            name='Editor',
            defaults={
                'description': 'Can create and edit tasks, but limited board management',
                'permissions': [
                    'board.view', 'board.export',
                    'column.create', 'column.edit', 'column.reorder',
                    'task.view', 'task.create', 'task.edit', 'task.delete', 'task.assign', 'task.move',
                    'comment.view', 'comment.create', 'comment.edit_own', 'comment.delete_own',
                    'label.view', 'label.create', 'label.assign',
                    'file.view', 'file.upload', 'file.download', 'file.delete',
                    'analytics.view',
                ],
                'is_system_role': True,
                'is_default': True
            }
        )
        
        # Member Role
        member_role, _ = cls.objects.get_or_create(
            organization=organization,
            name='Member',
            defaults={
                'description': 'Can work on tasks assigned to them',
                'permissions': [
                    'board.view',
                    'task.view', 'task.create', 'task.edit_own', 'task.move',
                    'comment.view', 'comment.create', 'comment.edit_own', 'comment.delete_own',
                    'label.view', 'label.assign',
                    'file.view', 'file.upload', 'file.download',
                ],
                'is_system_role': True,
                'is_default': False
            }
        )
        
        # Viewer Role
        viewer_role, _ = cls.objects.get_or_create(
            organization=organization,
            name='Viewer',
            defaults={
                'description': 'Read-only access to boards',
                'permissions': [
                    'board.view',
                    'task.view',
                    'comment.view',
                    'label.view',
                    'file.view', 'file.download',
                    'analytics.view',
                ],
                'is_system_role': True,
                'is_default': False
            }
        )
        
        return [admin_role, editor_role, member_role, viewer_role]


class BoardMembership(models.Model):
    """
    Replace simple Board.members M2M with role-based membership
    Tracks who has access to a board and what they can do
    """
    board = models.ForeignKey(
        Board, 
        on_delete=models.CASCADE, 
        related_name='memberships'
    )
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='board_memberships'
    )
    role = models.ForeignKey(
        Role, 
        on_delete=models.PROTECT,
        related_name='board_memberships',
        help_text="Role defining user's permissions on this board"
    )
    
    # Metadata
    added_at = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='added_board_members'
    )
    
    # Optional: Time-limited access
    expires_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When this membership expires (optional)"
    )
    
    is_active = models.BooleanField(default=True, db_index=True)
    
    class Meta:
        unique_together = ['board', 'user']
        ordering = ['board', '-added_at']
        indexes = [
            models.Index(fields=['board', 'user']),
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.board.name} ({self.role.name})"
    
    def clean(self):
        """Validate that role belongs to same organization as board"""
        if self.role.organization_id != self.board.organization_id:
            raise ValidationError("Role must belong to the same organization as the board")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def has_permission(self, permission):
        """Check if this membership grants a specific permission"""
        if not self.is_active:
            return False
        
        # Check expiration
        if self.expires_at:
            from django.utils import timezone
            if timezone.now() > self.expires_at:
                return False
        
        return self.role.has_permission(permission)


class PermissionOverride(models.Model):
    """
    Override specific permissions for a user on a board
    Allows fine-tuning beyond role-based permissions
    """
    OVERRIDE_TYPE_CHOICES = [
        ('grant', 'Grant Permission'),
        ('deny', 'Deny Permission'),
    ]
    
    membership = models.ForeignKey(
        BoardMembership, 
        on_delete=models.CASCADE, 
        related_name='permission_overrides'
    )
    permission = models.CharField(
        max_length=50,
        help_text="Permission to override (e.g., 'task.delete')"
    )
    override_type = models.CharField(
        max_length=10, 
        choices=OVERRIDE_TYPE_CHOICES,
        help_text="Whether to grant or explicitly deny this permission"
    )
    
    reason = models.TextField(
        blank=True,
        help_text="Reason for this permission override"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='created_permission_overrides'
    )
    
    # Optional: Time-limited override
    expires_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When this override expires (optional)"
    )
    
    class Meta:
        unique_together = ['membership', 'permission']
        ordering = ['membership', 'permission']
    
    def __str__(self):
        return f"{self.get_override_type_display()}: {self.permission} for {self.membership.user.username}"
    
    def is_active(self):
        """Check if override is still active"""
        if self.expires_at:
            from django.utils import timezone
            return timezone.now() <= self.expires_at
        return True


class ColumnPermission(models.Model):
    """
    Column-specific permissions for workflow enforcement
    E.g., only certain users can move tasks to "Done" column
    """
    from kanban.models import Column
    
    column = models.ForeignKey(
        Column, 
        on_delete=models.CASCADE, 
        related_name='column_permissions'
    )
    role = models.ForeignKey(
        Role, 
        on_delete=models.CASCADE, 
        related_name='column_permissions'
    )
    
    # Permissions for this column
    can_move_to = models.BooleanField(
        default=True, 
        help_text="Can move tasks INTO this column"
    )
    can_move_from = models.BooleanField(
        default=True, 
        help_text="Can move tasks OUT OF this column"
    )
    can_create_in = models.BooleanField(
        default=True, 
        help_text="Can create new tasks in this column"
    )
    can_edit_in = models.BooleanField(
        default=True, 
        help_text="Can edit tasks in this column"
    )
    
    class Meta:
        unique_together = ['column', 'role']


class PermissionAuditLog(models.Model):
    """
    Track permission changes and role assignments for audit purposes
    """
    ACTION_CHOICES = [
        ('role_created', 'Role Created'),
        ('role_updated', 'Role Updated'),
        ('role_deleted', 'Role Deleted'),
        ('member_added', 'Member Added'),
        ('member_removed', 'Member Removed'),
        ('member_role_changed', 'Member Role Changed'),
        ('permission_granted', 'Permission Granted'),
        ('permission_revoked', 'Permission Revoked'),
        ('override_added', 'Permission Override Added'),
        ('override_removed', 'Permission Override Removed'),
        ('column_permission_set', 'Column Permission Set'),
        ('org_member_promoted', 'Organization Member Promoted to Admin'),
        ('org_member_demoted', 'Organization Admin Demoted to Member'),
        ('org_member_removed', 'Organization Member Removed'),
    ]
    
    # What happened
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Who did it
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='permission_actions',
        help_text="User who performed the action"
    )
    
    # Where (context)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='permission_audit_logs',
        null=True,
        blank=True
    )
    board = models.ForeignKey(
        Board,
        on_delete=models.CASCADE,
        related_name='permission_audit_logs',
        null=True,
        blank=True
    )
    
    # Who was affected
    affected_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='permission_changes_received',
        help_text="User who was affected by the action"
    )
    
    # Details
    details = models.JSONField(
        default=dict,
        help_text="Additional details about the change (old/new values, etc.)"
    )
    
    # IP and user agent for security
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'organization']),
            models.Index(fields=['actor', '-timestamp']),
            models.Index(fields=['affected_user', '-timestamp']),
        ]
    
    def __str__(self):
        actor_name = self.actor.username if self.actor else 'System'
        affected = f" affecting {self.affected_user.username}" if self.affected_user else ""
        return f"{actor_name}: {self.get_action_display()}{affected} at {self.timestamp}"
    
    def __str__(self):
        return f"{self.role.name} permissions on {self.column.name}"
