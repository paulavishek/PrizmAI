# Enhanced Permissions - Quick Reference Card

## 🚀 Quick Start

### Access Points
```
📋 Manage Roles:           /permissions/roles/
👥 Manage Board Members:   /board/{id}/members/manage/
📊 View Audit Log:          /permissions/audit/
📊 Board Audit Log:         /board/{id}/permissions/audit/
```

### Default Roles Created
| Role    | Permissions | Use Case |
|---------|-------------|----------|
| Admin   | Full access (admin.full) | Organization admins |
| Editor  | Create, edit, delete tasks | Regular team members |
| Member  | Edit own tasks only | Contributors |
| Viewer  | Read-only access | Stakeholders |

## 🔐 Permission Categories

### Board (6 permissions)
- `board.view`, `board.create`, `board.edit`, `board.delete`
- `board.manage_members`, `board.export`

### Column (4 permissions)
- `column.create`, `column.edit`, `column.delete`, `column.reorder`

### Task (9 permissions)
- `task.view`, `task.view_own`, `task.create`
- `task.edit`, `task.edit_own`
- `task.delete`, `task.delete_own`
- `task.assign`, `task.move`

### Comments, Labels, Files, Analytics, etc.
- See `Role.AVAILABLE_PERMISSIONS` for full list (40+ total)

## 📝 Common Tasks

### Create Custom Role
```python
# Via UI: /permissions/roles/ → "Create New Role"

# Via Code:
from kanban.permission_models import Role

role = Role.objects.create(
    organization=my_org,
    name="QA Tester",
    description="Can test but not deploy",
    permissions=[
        'board.view', 'task.view', 'task.edit_own',
        'task.move', 'comment.create'
    ]
)
```

### Add Member with Role
```python
# Via UI: /board/{id}/members/manage/ → "Add Member"

# Via Code:
from kanban.permission_models import BoardMembership

membership = BoardMembership.objects.create(
    board=my_board,
    user=user,
    role=qa_role,
    added_by=request.user
)
```

### Set Column Restrictions
```python
from kanban.permission_models import ColumnPermission

# Example: Only admins can move to "Production"
ColumnPermission.objects.create(
    column=production_column,
    role=member_role,
    can_move_to=False,      # Members cannot push to prod
    can_move_from=True,     # But can pull back
    can_create_in=False,    # Cannot create in prod
    can_edit_in=False       # Cannot edit prod tasks
)
```

## 🔍 Check Permissions in Code

### Simple Check
```python
from kanban.permission_utils import user_has_board_permission

if user_has_board_permission(request.user, board, 'task.create'):
    # Allow task creation
    pass
```

### Column Permission Check
```python
from kanban.permission_utils import user_can_move_task_to_column

can_move, error_msg = user_can_move_task_to_column(user, task, target_column)
if not can_move:
    return JsonResponse({'error': error_msg}, status=403)
```

### Using Decorators
```python
from kanban.permission_utils import require_board_permission

@login_required
@require_board_permission('board.edit')
def my_view(request, board_id, **kwargs):
    board = kwargs['board']  # Auto-injected
    # Your logic here
```

### Filter Tasks by Permission
```python
from kanban.permission_utils import filter_tasks_by_permission

# Get only tasks user can see
visible_tasks = filter_tasks_by_permission(
    request.user, 
    all_tasks, 
    'task.view'
)
```

## 📊 Audit Logging

### Automatic Logging (Built-in)
These actions are automatically logged:
- Role created/updated/deleted
- Member added/removed
- Member role changed
- Permission overrides

### Manual Logging
```python
from kanban.permission_audit import log_permission_change

log_permission_change(
    action='custom_action',
    actor=request.user,
    board=board,
    affected_user=target_user,
    details={'reason': 'Special access granted'},
    request=request
)
```

### Query Audit Logs
```python
from kanban.permission_audit import get_permission_audit_log

# Last 100 changes for a board
logs = get_permission_audit_log(board=my_board, limit=100)

# Changes by specific user
logs = get_permission_audit_log(user=my_user)

# Specific action type
logs = get_permission_audit_log(action='member_added')
```

## ⚙️ Configuration

### Make Role Default
```python
role.is_default = True
role.save()

# Auto-removes default from other roles in same org
```

### Time-Limited Access
```python
from datetime import datetime, timedelta

membership.expires_at = datetime.now() + timedelta(days=30)
membership.save()
```

### Permission Override
```python
from kanban.permission_models import PermissionOverride

# Grant specific permission
PermissionOverride.objects.create(
    membership=membership,
    permission='task.delete',
    override_type='grant',
    reason='Temporary cleanup access'
)

# Deny specific permission
PermissionOverride.objects.create(
    membership=membership,
    permission='board.delete',
    override_type='deny',
    reason='Safety precaution'
)
```

## 🎯 Use Cases

### Approval Workflow
```python
# Restrict "Done" column to managers only
done_column = Column.objects.get(name="Done")
member_role = Role.objects.get(name="Member")

ColumnPermission.objects.create(
    column=done_column,
    role=member_role,
    can_move_to=False  # Can't self-approve
)
```

### Client Access
```python
# Create read-only client role
client_role = Role.objects.create(
    organization=org,
    name="Client",
    permissions=[
        'board.view', 'task.view',
        'comment.create', 'file.download'
    ]
)
```

### Contractor Access
```python
# Time-limited contractor access
BoardMembership.objects.create(
    board=board,
    user=contractor,
    role=editor_role,
    expires_at=contract_end_date
)
```

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| User can't see board | Grant `board.view` permission to their role |
| Can't move task | Check ColumnPermission `can_move_to`/`can_move_from` |
| Can't see own tasks | Grant `task.view_own` permission |
| Column restriction not working | Verify ColumnPermission exists for that role |
| Permission denied but should work | Check for deny PermissionOverride |
| Audit log empty | Ensure using helper functions from `permission_audit.py` |

## 📚 Documentation Files

- `ENHANCED_PERMISSIONS_GUIDE.md` - Complete documentation
- `PERMISSION_ENHANCEMENT_SUMMARY.md` - Implementation details
- This file - Quick reference

## 🔑 Key Concepts

1. **Roles** define WHAT users can do (list of permissions)
2. **BoardMembership** defines WHO has WHICH role on a board
3. **ColumnPermission** adds workflow restrictions
4. **PermissionOverride** grants/denies specific permissions
5. **PermissionAuditLog** tracks all changes

## ⚡ Performance Tips

- Permission checks are cached per request
- Use `select_related('role')` when querying memberships
- Filter tasks at database level with `filter_tasks_by_permission()`
- Audit logs are indexed - query efficiently

## 🔒 Security Notes

- Board creators always have full access (by design)
- System roles cannot be deleted
- Audit logs cannot be deleted
- IP addresses are logged for security
- Use HTTPS in production

---

**Quick Help:** For issues, check [ENHANCED_PERMISSIONS_GUIDE.md](ENHANCED_PERMISSIONS_GUIDE.md)
**Status:** ✅ Production Ready
**Version:** 1.0
