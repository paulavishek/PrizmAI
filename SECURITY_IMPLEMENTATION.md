# Security Enhancements Implementation Guide

**Version:** 1.0  
**Date:** November 13, 2025

## Overview

This guide helps you implement the enhanced security features in PrizmAI, including:
- Comprehensive audit logging
- Role-based access control (RBAC)
- Permission management system
- Security monitoring

---

## Files Created

### Models
1. **`kanban/audit_models.py`** - Audit logging models
   - `SystemAuditLog` - Comprehensive audit trail
   - `SecurityEvent` - Security incidents tracking
   - `DataAccessLog` - Sensitive data access logs

2. **`kanban/permission_models.py`** - RBAC models
   - `Role` - Define roles with permissions
   - `BoardMembership` - Role-based board access
   - `PermissionOverride` - Fine-grained permission control
   - `ColumnPermission` - Column-specific permissions

### Utilities
3. **`kanban/audit_utils.py`** - Audit logging helpers
4. **`kanban/permission_utils.py`** - Permission checking functions

### Middleware
5. **`kanban/audit_middleware.py`** - Automatic audit logging
   - `AuditLoggingMiddleware` - General request logging
   - `APIRequestLoggingMiddleware` - API request logging
   - `SecurityMonitoringMiddleware` - Threat detection

### Management Commands
6. **`kanban/management/commands/initialize_rbac.py`** - Setup RBAC
7. **`kanban/management/commands/migrate_board_members.py`** - Migrate existing data

---

## Installation Steps

### Step 1: Update models.py

Add imports to `kanban/models.py`:

```python
# Add at the top of kanban/models.py
from kanban.audit_models import SystemAuditLog, SecurityEvent, DataAccessLog
from kanban.permission_models import Role, BoardMembership, PermissionOverride, ColumnPermission
```

Or create a new `kanban/security_models.py` that imports everything:

```python
# kanban/security_models.py
from .audit_models import *
from .permission_models import *
```

### Step 2: Update settings.py

Add new apps and middleware to `kanban_board/settings.py`:

```python
# Add to INSTALLED_APPS (if needed, models work in existing apps)
# No changes needed if models are in kanban app

# Add middleware to MIDDLEWARE list (order matters!)
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    
    # ADD THESE NEW MIDDLEWARE (order is important)
    'kanban.audit_middleware.AuditLoggingMiddleware',         # General audit logging
    'kanban.audit_middleware.APIRequestLoggingMiddleware',    # API logging
    'kanban.audit_middleware.SecurityMonitoringMiddleware',   # Security monitoring
]
```

### Step 3: Create database migrations

```powershell
# Create migrations for new models
python manage.py makemigrations kanban

# Review the migrations
python manage.py showmigrations kanban

# Apply migrations
python manage.py migrate kanban
```

### Step 4: Initialize RBAC system

```powershell
# Create default roles for all organizations
python manage.py initialize_rbac

# Or for specific organization
python manage.py initialize_rbac --org-id 1

# Migrate existing board members to RBAC
python manage.py migrate_board_members

# Or dry-run to see what would happen
python manage.py migrate_board_members --dry-run
```

### Step 5: Update views to use permissions

Example of updating a view to use the new permission system:

**Before:**
```python
@login_required
def create_task(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    
    # Simple access check
    if not (board.members.filter(id=request.user.id).exists() or 
            board.created_by == request.user):
        return HttpResponseForbidden("You don't have access to this board.")
    
    # ... create task
```

**After:**
```python
from kanban.permission_utils import require_board_permission
from kanban.audit_utils import log_model_change

@login_required
@require_board_permission('task.create')
def create_task(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    
    # ... create task
    task = Task.objects.create(...)
    
    # Log the creation
    log_model_change('task.created', task, request.user, request)
    
    return JsonResponse({'status': 'success'})
```

---

## Usage Examples

### 1. Logging User Actions

```python
from kanban.audit_utils import log_audit, log_model_change, AuditLogContext

# Simple logging
log_audit('board.viewed', user=request.user, request=request,
          object_type='board', object_id=board.id, object_repr=board.name)

# Log model changes
task = Task.objects.get(id=task_id)
log_model_change('task.updated', task, request.user, request,
                 changes={'title': {'old': 'Old Title', 'new': 'New Title'}})

# Automatic change tracking with context manager
with AuditLogContext(task, request.user, request):
    task.title = "New Title"
    task.priority = "high"
    task.save()
# Changes automatically logged!
```

### 2. Checking Permissions

```python
from kanban.permission_utils import user_has_board_permission, check_permission_or_403

# Check permission (returns boolean)
if user_has_board_permission(request.user, board, 'task.delete'):
    task.delete()
else:
    return HttpResponseForbidden("Cannot delete tasks")

# Or use check_permission_or_403 (raises PermissionDenied)
check_permission_or_403(request.user, board, 'task.delete')
task.delete()
```

### 3. Using Permission Decorators

```python
from kanban.permission_utils import require_board_permission, require_task_permission

@login_required
@require_board_permission('task.create')
def create_task(request, board_id):
    # Board automatically added to kwargs
    board = kwargs['board']
    # ... create task

@login_required
@require_task_permission('task.delete')
def delete_task(request, task_id):
    # Task automatically added to kwargs
    task = kwargs['task']
    task.delete()
```

### 4. Managing Roles

```python
from kanban.permission_models import Role, BoardMembership
from kanban.permission_utils import assign_default_role_to_user

# Create custom role
custom_role = Role.objects.create(
    name='Project Manager',
    organization=organization,
    description='Can manage all aspects of projects',
    permissions=[
        'board.view', 'board.edit',
        'task.view', 'task.create', 'task.edit', 'task.delete', 'task.assign',
        'board.manage_members',
        'analytics.view',
    ]
)

# Assign role to user on a board
membership = BoardMembership.objects.create(
    board=board,
    user=user,
    role=custom_role,
    added_by=request.user
)

# Or use default role
membership = assign_default_role_to_user(user, board)

# Check what permissions a user has
from kanban.permission_utils import get_user_permissions_for_board
permissions = get_user_permissions_for_board(user, board)
print(permissions)  # ['board.view', 'task.create', ...]
```

### 5. Permission Overrides

```python
from kanban.permission_models import PermissionOverride

# Grant specific permission to a user (beyond their role)
override = PermissionOverride.objects.create(
    membership=membership,
    permission='board.delete',
    override_type='grant',
    reason='Temporary permission for migration project'
)

# Deny specific permission (even if role grants it)
override = PermissionOverride.objects.create(
    membership=membership,
    permission='data.export',
    override_type='deny',
    reason='Security restriction'
)
```

### 6. Column-Specific Permissions

```python
from kanban.permission_models import ColumnPermission

# Only admins can move tasks to "Done" column
done_column = Column.objects.get(board=board, name='Done')
admin_role = Role.objects.get(organization=board.organization, name='Admin')
viewer_role = Role.objects.get(organization=board.organization, name='Viewer')

# Admins can do everything
ColumnPermission.objects.create(
    column=done_column,
    role=admin_role,
    can_move_to=True,
    can_move_from=True,
    can_create_in=True,
    can_edit_in=True
)

# Viewers cannot move tasks to Done
ColumnPermission.objects.create(
    column=done_column,
    role=viewer_role,
    can_move_to=False,
    can_move_from=False,
    can_create_in=False,
    can_edit_in=False
)
```

### 7. Logging Authentication Events

```python
from kanban.audit_utils import log_authentication_event

# In your login view
def login_view(request):
    # ... authentication logic
    if authenticated:
        log_authentication_event('user.login', user=user, request=request, success=True)
    else:
        log_authentication_event('user.login_failed', user=None, request=request, 
                                success=False, reason='Invalid credentials')
```

### 8. Viewing Audit Logs

```python
from kanban.audit_models import SystemAuditLog
from django.utils import timezone
from datetime import timedelta

# Get recent audit logs for a user
recent_logs = SystemAuditLog.objects.filter(
    user=user,
    timestamp__gte=timezone.now() - timedelta(days=7)
).order_by('-timestamp')

# Get all task changes for a board
task_changes = SystemAuditLog.objects.filter(
    board_id=board.id,
    action_type__startswith='task.'
).order_by('-timestamp')

# Get security events
from kanban.audit_models import SecurityEvent
security_events = SecurityEvent.objects.filter(
    status='new'
).order_by('-timestamp')
```

---

## Available Permissions

### Board Permissions
- `board.view` - View board and contents
- `board.create` - Create new boards
- `board.edit` - Modify board settings
- `board.delete` - Delete boards
- `board.manage_members` - Add/remove members
- `board.export` - Export board data

### Task Permissions
- `task.view` - View all tasks
- `task.view_own` - View only assigned tasks
- `task.create` - Create tasks
- `task.edit` - Edit any task
- `task.edit_own` - Edit only assigned tasks
- `task.delete` - Delete any task
- `task.delete_own` - Delete only own tasks
- `task.assign` - Assign tasks to users
- `task.move` - Move tasks between columns

### Comment Permissions
- `comment.view` - View comments
- `comment.create` - Add comments
- `comment.edit` - Edit any comment
- `comment.edit_own` - Edit own comments only
- `comment.delete` - Delete any comment
- `comment.delete_own` - Delete own comments only

### Advanced Permissions
- `webhook.manage` - Manage webhooks
- `api.access` - Use API tokens
- `analytics.view` - View analytics
- `audit.view` - View audit logs
- `data.export` - Export data
- `admin.full` - Full administrative access

---

## Default Roles

### Admin
- **Permissions:** `admin.full` (all permissions)
- **Use Case:** Board owners, project managers
- **Assigned to:** Board creators

### Editor
- **Permissions:** Can create, edit, and manage tasks; limited board management
- **Use Case:** Active team members
- **Default:** Yes (default role for new members)

### Member
- **Permissions:** Can work on assigned tasks; limited editing
- **Use Case:** Contributors who only work on their tasks
- **Default:** No

### Viewer
- **Permissions:** Read-only access
- **Use Case:** Stakeholders, observers
- **Default:** No

---

## Admin Interface

To use audit logs and roles in Django admin, register them:

```python
# kanban/admin.py

from django.contrib import admin
from .audit_models import SystemAuditLog, SecurityEvent, DataAccessLog
from .permission_models import Role, BoardMembership, PermissionOverride

@admin.register(SystemAuditLog)
class SystemAuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'action_type', 'user_username', 'object_type', 'severity']
    list_filter = ['action_type', 'severity', 'timestamp']
    search_fields = ['user_username', 'user_email', 'message', 'object_repr']
    readonly_fields = [f.name for f in SystemAuditLog._meta.fields]  # All fields read-only
    
    def has_add_permission(self, request):
        return False  # Cannot add audit logs manually
    
    def has_delete_permission(self, request, obj=None):
        return False  # Cannot delete audit logs

@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'event_type', 'user', 'ip_address', 'status', 'risk_score']
    list_filter = ['event_type', 'status', 'timestamp']
    search_fields = ['description', 'user__username']

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'is_system_role', 'is_default']
    list_filter = ['organization', 'is_system_role', 'is_default']
    search_fields = ['name', 'description']

@admin.register(BoardMembership)
class BoardMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'board', 'role', 'added_at', 'is_active']
    list_filter = ['is_active', 'role']
    search_fields = ['user__username', 'board__name']
```

---

## Security Best Practices

1. **Always check permissions** before sensitive operations
2. **Log all important actions** (create, update, delete)
3. **Review security events** regularly
4. **Use least privilege** principle - give minimum required permissions
5. **Set role expiration** for temporary access
6. **Monitor audit logs** for suspicious patterns
7. **Rotate API tokens** regularly
8. **Enable webhook signatures** for external integrations

---

## Troubleshooting

### Issue: Migrations fail

**Solution:**
```powershell
# Check for conflicting migrations
python manage.py showmigrations

# Make fresh migrations
python manage.py makemigrations kanban --name security_enhancements

# Apply with verbosity
python manage.py migrate --verbosity 2
```

### Issue: Permission denied for all users

**Solution:**
```python
# Check if roles are created
from kanban.permission_models import Role
print(Role.objects.all())

# Initialize RBAC
python manage.py initialize_rbac

# Check memberships
from kanban.permission_models import BoardMembership
print(BoardMembership.objects.filter(user=user))
```

### Issue: Audit logs not appearing

**Solution:**
```python
# Check middleware is enabled
# In settings.py, verify AuditLoggingMiddleware is in MIDDLEWARE list

# Manually test logging
from kanban.audit_utils import log_audit
log_audit('test.action', user=request.user, object_type='test', object_id=1)

# Check database
from kanban.audit_models import SystemAuditLog
print(SystemAuditLog.objects.count())
```

---

## Performance Considerations

### Indexing
All audit and permission models include database indexes for performance:
- Timestamp fields
- User foreign keys
- Action types
- Organization/Board IDs

### Query Optimization
```python
# Use select_related for foreign keys
memberships = BoardMembership.objects.select_related('user', 'role', 'board')

# Use prefetch_related for many-to-many
audit_logs = SystemAuditLog.objects.prefetch_related('security_events')

# Filter at database level
recent_logs = SystemAuditLog.objects.filter(
    timestamp__gte=last_week
).only('timestamp', 'action_type', 'user_username')
```

### Archiving Old Logs
```python
# Archive logs older than 1 year (create separate script)
from datetime import timedelta
from django.utils import timezone

cutoff = timezone.now() - timedelta(days=365)

# Export to JSON before deletion (if needed)
old_logs = SystemAuditLog.objects.filter(timestamp__lt=cutoff)
# ... export logic ...

# Note: Audit logs have delete protection, need to override
```

---

## Next Steps

1. Update all views to use permission decorators
2. Add audit logging to all CRUD operations
3. Create admin dashboard for security monitoring
4. Implement email notifications for security events
5. Add user-facing audit trail UI
6. Create permission management UI for board admins
7. Implement data retention policies
8. Set up automated security reports

---

## Support

For issues or questions:
1. Check this guide
2. Review `SECURITY_AUDIT.md` for detailed analysis
3. Check audit logs for error details
4. Test with `--dry-run` flags before making changes

---

**Last Updated:** November 13, 2025
