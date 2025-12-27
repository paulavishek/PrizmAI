# Demo System Quick Reference

## Key Points

### 1. Admin vs Demo Users
- **Admin (Superuser)**: NO RBAC restrictions - full access to everything
- **Demo Users**: RBAC restrictions apply - experience real permission limits

### 2. Pre-populated Demo Users
```
Admins:  admin
Editors: emily_chen, michael_brown, sarah_davis, james_wilson
Members: john_doe, jane_smith, robert_johnson, alice_williams, 
         bob_martinez, carol_anderson, david_taylor
```

### 3. Reset Demo
- **Web**: http://localhost:8000/demo/reset/ (Superusers only)
- **Command**: `python manage.py reset_demo`
- **Effect**: Deletes all demo data → Recreates fresh → Resets dates

### 4. RBAC Features in Demo
✓ Role-based access (Admin/Editor/Member/Viewer)
✓ Column restrictions (Review/Done locked for Members)
✓ Approval workflows
✓ Visual indicators (badges, locks, warnings)
✓ Audit logging
✓ Permission management UI

### 5. Testing Scenarios

**As Admin:**
- Login as superuser
- Access /demo/
- Create, edit, delete anything
- No restrictions apply

**As Member:**
- Login as john_doe
- Access /demo/
- See role badge "Member"
- Try moving task to "Done" → Blocked!

**Reset Demo:**
- Login as superuser
- Access /demo/
- Click "Reset Demo" button
- Confirm → Demo restored

## Files Changed
- `kanban/permission_utils.py` - Added superuser bypass
- `kanban/demo_views.py` - Added reset view
- `kanban/urls.py` - Added reset URL
- `kanban/management/commands/reset_demo.py` - New command
- `templates/kanban/reset_demo_confirm.html` - New template
- `templates/kanban/demo_dashboard.html` - Added reset button

## Security
- Only superusers can reset demo
- Two-step confirmation required
- Transaction-protected reset
- All changes audited

---

**Full documentation:** See [DEMO_SYSTEM_IMPLEMENTATION.md](DEMO_SYSTEM_IMPLEMENTATION.md)
