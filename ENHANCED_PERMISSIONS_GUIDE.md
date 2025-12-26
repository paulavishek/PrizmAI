# Enhanced Permission System - Complete Guide

## Overview

PrizmAI now features a comprehensive **Role-Based Access Control (RBAC)** system with advanced permission management capabilities. This system provides granular control over user access at multiple levels.

## Key Features Implemented

### ✅ 1. Role-Based Access Control (RBAC)
- **Pre-defined System Roles**: Admin, Editor, Member, Viewer
- **Custom Roles**: Create organization-specific roles with custom permission sets
- **40+ Granular Permissions** covering all system actions
- **Organization-scoped**: Each organization has its own set of roles

### ✅ 2. Board-Level Permissions
- **BoardMembership Model**: Tracks user roles per board
- **Permission Inheritance**: Roles define what users can do
- **Time-Limited Access**: Optional expiration dates for memberships
- **Permission Overrides**: Grant or deny specific permissions per user

### ✅ 3. Column-Level Restrictions
- **ColumnPermission Model**: Control actions within specific columns
- **Move Restrictions**: Control which roles can move tasks in/out of columns
- **Create Restrictions**: Limit task creation to specific columns
- **Edit Restrictions**: Prevent editing tasks in certain workflow stages

### ✅ 4. Task-Level Assignments
- **View Own**: Users can only see tasks assigned to them
- **Edit Own**: Users can only edit their own tasks
- **Task Filtering**: Automatic queryset filtering based on permissions
- **Ownership Validation**: Checks both assigned_to and created_by

### ✅ 5. Permission Audit Logging
- **Complete Audit Trail**: Track all permission changes
- **Actor Tracking**: Who made the change
- **IP & User Agent**: Security logging
- **Change Details**: Before/after values for all modifications

## System Architecture

### Models

#### 1. **Role** (`kanban/permission_models.py`)
```python
- name: str                    # Role name (e.g., "Project Manager")
- description: str             # What this role can do
- organization: FK             # Organization scope
- permissions: JSONField       # List of permission strings
- is_system_role: bool         # Cannot be deleted
- is_default: bool            # Assigned to new members
```

#### 2. **BoardMembership** (`kanban/permission_models.py`)
```python
- board: FK                    # Which board
- user: FK                     # Which user
- role: FK                     # What they can do
- added_at: datetime           # When added
- added_by: FK                 # Who added them
- expires_at: datetime (opt)   # Time-limited access
- is_active: bool             # Can be disabled
```

#### 3. **ColumnPermission** (`kanban/permission_models.py`)
```python
- column: FK                   # Which column
- role: FK                     # Which role
- can_move_to: bool           # Can move tasks INTO this column
- can_move_from: bool         # Can move tasks OUT OF this column
- can_create_in: bool         # Can create tasks in this column
- can_edit_in: bool           # Can edit tasks in this column
```

#### 4. **PermissionAuditLog** (`kanban/permission_models.py`)
```python
- action: str                  # What happened
- timestamp: datetime          # When it happened
- actor: FK                    # Who did it
- affected_user: FK (opt)      # Who was affected
- organization: FK (opt)       # Context
- board: FK (opt)             # Context
- details: JSONField          # Change details
- ip_address: str             # Security
- user_agent: str             # Security
```

### Permission Categories

All 40+ permissions are organized into categories:

**Board Permissions**
- `board.view` - View board and its contents
- `board.create` - Create new boards
- `board.edit` - Modify board settings
- `board.delete` - Delete boards
- `board.manage_members` - Add/remove board members
- `board.export` - Export board data

**Column Permissions**
- `column.create` - Create new columns
- `column.edit` - Modify column settings
- `column.delete` - Delete columns
- `column.reorder` - Change column order

**Task Permissions**
- `task.view` - View all tasks
- `task.view_own` - Only view assigned/created tasks
- `task.create` - Create new tasks
- `task.edit` - Edit any task
- `task.edit_own` - Only edit own tasks
- `task.delete` - Delete any task
- `task.delete_own` - Only delete own tasks
- `task.assign` - Assign tasks to users
- `task.move` - Move tasks between columns

**Comment, Label, File, Analytics, Webhook, API Permissions** (see Role.AVAILABLE_PERMISSIONS)

## Usage Guide

### For Administrators

#### 1. **Creating Custom Roles**

Navigate to: **Dashboard → Permissions → Manage Roles → Create New Role**

```python
# Example: Create a "QA Tester" role
Role:
  Name: QA Tester
  Description: Can view and test, but not create or delete
  Permissions:
    - board.view
    - task.view
    - task.edit_own
    - task.move (for testing workflow)
    - comment.create
    - file.view, file.upload
```

#### 2. **Managing Board Members**

Navigate to: **Board Detail → Settings → Manage Members**

- Add members with specific roles
- Change member roles on-the-fly
- Remove members
- View membership history

#### 3. **Setting Column Restrictions**

```python
# Example: Restrict "Production" column
from kanban.permission_models import ColumnPermission, Role

production_column = Column.objects.get(name="Production")
qa_role = Role.objects.get(name="QA Tester")

ColumnPermission.objects.create(
    column=production_column,
    role=qa_role,
    can_move_to=False,      # QA cannot push to production
    can_move_from=True,     # But can pull back for fixes
    can_create_in=False,    # Cannot create directly in prod
    can_edit_in=False       # Cannot edit production tasks
)
```

#### 4. **Viewing Audit Logs**

Navigate to: **Board Detail → Permissions → Audit Log**

Filter by:
- Action type (role created, member added, etc.)
- Date range
- Specific user
- Board or organization

### For Developers

#### 1. **Checking Permissions in Views**

```python
from kanban.permission_utils import user_has_board_permission, user_can_move_task_to_column

@login_required
def my_view(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    
    # Check board permission
    if not user_has_board_permission(request.user, board, 'task.create'):
        return HttpResponseForbidden("Cannot create tasks")
    
    # Check column permission for task move
    can_move, error = user_can_move_task_to_column(request.user, task, target_column)
    if not can_move:
        return JsonResponse({'error': error}, status=403)
```

#### 2. **Using Decorators**

```python
from kanban.permission_utils import require_board_permission, require_task_permission

@login_required
@require_board_permission('board.edit')
def edit_board(request, board_id, **kwargs):
    board = kwargs['board']  # Injected by decorator
    # ... edit logic

@login_required
@require_task_permission('task.delete')
def delete_task(request, task_id, **kwargs):
    task = kwargs['task']  # Injected by decorator
    # ... delete logic
```

#### 3. **Filtering Tasks by Permission**

```python
from kanban.permission_utils import filter_tasks_by_permission

@login_required
def my_tasks(request):
    # Get all tasks, then filter by what user can see
    all_tasks = Task.objects.filter(column__board__organization=request.user.profile.organization)
    
    # Automatically filters based on task.view vs task.view_own
    visible_tasks = filter_tasks_by_permission(request.user, all_tasks, 'task.view')
    
    return render(request, 'my_tasks.html', {'tasks': visible_tasks})
```

#### 4. **Logging Permission Changes**

```python
from kanban.permission_audit import log_member_added, log_role_created

# When adding a member
membership = BoardMembership.objects.create(...)
log_member_added(membership, request.user, request)

# When creating a role
role = Role.objects.create(...)
log_role_created(role, request.user, request)
```

## API Endpoints

### New Permission Management Endpoints

```
GET  /permissions/roles/                          # List all roles
POST /permissions/roles/create/                   # Create custom role
POST /permissions/roles/{id}/edit/                # Edit role
POST /permissions/roles/{id}/delete/              # Delete role

GET  /board/{id}/members/manage/                  # Manage board members
POST /board/{id}/members/add/                     # Add member with role
POST /board/membership/{id}/change-role/          # Change member role
POST /board/membership/{id}/remove/               # Remove member

GET  /board/{id}/permissions/audit/               # Board audit log
GET  /permissions/audit/                          # Organization audit log
```

## Database Migrations

To apply the new permission system:

```bash
# Create migration for PermissionAuditLog model
python manage.py makemigrations kanban

# Apply migration
python manage.py migrate kanban

# Create default roles for existing organizations
python manage.py shell
>>> from accounts.models import Organization
>>> from kanban.permission_models import Role
>>> for org in Organization.objects.all():
>>>     Role.create_default_roles(org)
```

## Best Practices

### 1. **Use Least Privilege Principle**
- Start with minimal permissions
- Add more as needed
- Regularly audit permissions

### 2. **Leverage System Roles**
- Don't reinvent Admin, Editor, Member, Viewer
- Create custom roles only for specific needs
- Keep role count manageable

### 3. **Column Permissions for Workflow**
- Use for approval workflows
- Prevent unauthorized state changes
- Guide users through proper process

### 4. **Audit Everything**
- Review audit logs regularly
- Investigate unexpected changes
- Use for compliance reporting

### 5. **Task-Level Security**
- Use `view_own`/`edit_own` for sensitive projects
- Combine with proper role assignment
- Consider data sensitivity

## Common Use Cases

### Case 1: **Approval Workflow**
```
Columns: To Do → In Progress → Review → Done

Member Role:
  - can_move_to: Review (NO) - Cannot self-approve
  - can_move_from: Review (YES) - Can fix issues

Admin Role:
  - can_move_to: Done (YES) - Final approval
  - Full access to all columns
```

### Case 2: **Client Portal Access**
```
Client Role:
  - board.view only
  - task.view only
  - comment.create
  - file.view, file.download
  - NO editing or deletion
```

### Case 3: **Contractor Time-Limited Access**
```
BoardMembership:
  - role: Editor
  - expires_at: End of contract date
  - Automatic access revocation
```

## Troubleshooting

### Issue: User can't see tasks they created
**Solution**: Grant `task.view` or `task.view_own` permission to their role

### Issue: Column restrictions not working
**Solution**: Check if ColumnPermission exists for that role/column combination

### Issue: Audit log empty
**Solution**: Ensure you're using the log_* helper functions from permission_audit.py

### Issue: Permission denied despite being board creator
**Solution**: Board creators bypass all permission checks - this is by design

## Security Considerations

1. **Never expose permission internals to frontend** - Use API endpoints
2. **Always check permissions server-side** - Don't trust client
3. **Log security-relevant actions** - Use audit system
4. **Regularly review permissions** - Especially for admin roles
5. **Use HTTPS in production** - Protect audit data in transit

## Performance Optimization

1. **Permission checks are cached** at request level
2. **Use select_related** when querying memberships
3. **Prefetch roles** when checking multiple permissions
4. **Index audit logs** by timestamp and organization

## Future Enhancements

- [ ] Permission templates for common scenarios
- [ ] Bulk permission operations UI
- [ ] Permission analytics dashboard
- [ ] Role cloning functionality
- [ ] Advanced permission inheritance
- [ ] API rate limiting per role
- [ ] Permission simulation/dry-run mode

## Support

For questions or issues with the permission system:
1. Check this documentation
2. Review audit logs for permission denials
3. Verify role configuration
4. Check ColumnPermission settings

---

**Last Updated**: December 26, 2025
**Version**: 1.0
**Status**: Production Ready ✅
