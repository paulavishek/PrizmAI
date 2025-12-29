"""
Demo Mode Permission Enforcement
Applies role-based restrictions for demo sessions
"""

class DemoPermissions:
    """
    Role-based permission enforcement for demo mode
    
    Roles:
    - Admin: Full access to all features
    - Member: Can create/edit tasks, limited delete, cannot manage board settings
    - Viewer: Read-only access, cannot modify anything
    """
    
    # Permission definitions
    PERMISSIONS = {
        'admin': {
            # Board permissions
            'can_view_board': True,
            'can_edit_board_settings': True,
            'can_delete_board': True,
            'can_add_board_members': True,
            'can_remove_board_members': True,
            'can_create_columns': True,
            'can_edit_columns': True,
            'can_delete_columns': True,
            
            # Task permissions
            'can_create_tasks': True,
            'can_edit_tasks': True,
            'can_delete_tasks': True,
            'can_move_tasks': True,
            'can_assign_tasks': True,
            'can_add_comments': True,
            'can_delete_comments': True,
            'can_add_attachments': True,
            'can_delete_attachments': True,
            
            # Advanced features
            'can_use_ai_features': True,
            'can_view_analytics': True,
            'can_manage_sprints': True,
            'can_manage_milestones': True,
            'can_manage_budget': True,
            'can_view_time_tracking': True,
            'can_log_time': True,
        },
        'member': {
            # Board permissions
            'can_view_board': True,
            'can_edit_board_settings': False,
            'can_delete_board': False,
            'can_add_board_members': False,
            'can_remove_board_members': False,
            'can_create_columns': False,
            'can_edit_columns': False,
            'can_delete_columns': False,
            
            # Task permissions
            'can_create_tasks': True,
            'can_edit_tasks': True,
            'can_delete_tasks': False,  # Can only delete own tasks
            'can_move_tasks': True,
            'can_assign_tasks': True,
            'can_add_comments': True,
            'can_delete_comments': False,  # Can only delete own comments
            'can_add_attachments': True,
            'can_delete_attachments': False,  # Can only delete own attachments
            
            # Advanced features
            'can_use_ai_features': True,
            'can_view_analytics': True,
            'can_manage_sprints': False,
            'can_manage_milestones': False,
            'can_manage_budget': False,
            'can_view_time_tracking': True,
            'can_log_time': True,
        },
        'viewer': {
            # Board permissions
            'can_view_board': True,
            'can_edit_board_settings': False,
            'can_delete_board': False,
            'can_add_board_members': False,
            'can_remove_board_members': False,
            'can_create_columns': False,
            'can_edit_columns': False,
            'can_delete_columns': False,
            
            # Task permissions
            'can_create_tasks': False,
            'can_edit_tasks': False,
            'can_delete_tasks': False,
            'can_move_tasks': False,
            'can_assign_tasks': False,
            'can_add_comments': True,  # Can comment but not modify tasks
            'can_delete_comments': False,
            'can_add_attachments': False,
            'can_delete_attachments': False,
            
            # Advanced features
            'can_use_ai_features': False,
            'can_view_analytics': True,
            'can_manage_sprints': False,
            'can_manage_milestones': False,
            'can_manage_budget': False,
            'can_view_time_tracking': True,
            'can_log_time': False,
        }
    }
    
    @staticmethod
    def has_permission(role, permission):
        """
        Check if a role has a specific permission
        
        Args:
            role (str): Role name ('admin', 'member', 'viewer')
            permission (str): Permission key
            
        Returns:
            bool: True if role has permission, False otherwise
        """
        if role not in DemoPermissions.PERMISSIONS:
            return False
        
        return DemoPermissions.PERMISSIONS[role].get(permission, False)
    
    @staticmethod
    def get_all_permissions(role):
        """
        Get all permissions for a role
        
        Args:
            role (str): Role name
            
        Returns:
            dict: Dictionary of permissions
        """
        return DemoPermissions.PERMISSIONS.get(role, {})
    
    @staticmethod
    def can_perform_action(request, action):
        """
        Check if current demo user can perform an action
        
        Args:
            request: Django request object
            action (str): Permission key
            
        Returns:
            bool: True if can perform action
        """
        # Check if in demo mode
        if not request.session.get('is_demo_mode'):
            return True  # Not in demo mode, allow all actions
        
        # Get current role
        role = request.session.get('demo_role', 'admin')
        
        return DemoPermissions.has_permission(role, action)
    
    @staticmethod
    def get_permission_context(request):
        """
        Get permission context for templates
        
        Args:
            request: Django request object
            
        Returns:
            dict: Permission context for templates
        """
        if not request.session.get('is_demo_mode'):
            # Not in demo mode, return full permissions
            return {perm: True for perm in DemoPermissions.PERMISSIONS['admin'].keys()}
        
        role = request.session.get('demo_role', 'admin')
        return DemoPermissions.get_all_permissions(role)
    
    @staticmethod
    def get_role_description(role):
        """
        Get human-readable description of role permissions
        
        Args:
            role (str): Role name
            
        Returns:
            dict: Role metadata
        """
        descriptions = {
            'admin': {
                'name': 'Alex Chen',
                'title': 'Administrator',
                'icon': 'fa-user-shield',
                'description': 'Full access to all features and settings',
                'can_do': [
                    'Create, edit, and delete boards',
                    'Manage team members and permissions',
                    'Use all AI features',
                    'View analytics and reports',
                    'Manage budgets and milestones'
                ],
                'cannot_do': []
            },
            'member': {
                'name': 'Sam Rivera',
                'title': 'Team Member',
                'icon': 'fa-user',
                'description': 'Create and edit tasks, limited administrative access',
                'can_do': [
                    'Create and edit tasks',
                    'Move tasks between columns',
                    'Add comments and attachments',
                    'Use AI features',
                    'Log time on tasks'
                ],
                'cannot_do': [
                    'Delete tasks created by others',
                    'Edit board settings',
                    'Manage team members',
                    'Delete boards or columns'
                ]
            },
            'viewer': {
                'name': 'Jordan Taylor',
                'title': 'Viewer',
                'icon': 'fa-eye',
                'description': 'View-only access to boards and analytics',
                'can_do': [
                    'View all boards and tasks',
                    'View analytics and reports',
                    'Add comments to discussions',
                    'View time tracking data'
                ],
                'cannot_do': [
                    'Create or edit tasks',
                    'Move tasks',
                    'Delete any content',
                    'Use AI features',
                    'Log time'
                ]
            }
        }
        
        return descriptions.get(role, descriptions['admin'])
