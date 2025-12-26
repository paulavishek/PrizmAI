# Enhanced Permission System - UI Access Guide

## 🎯 Where to Find Everything

### 1. **Your Role Badge** (Always Visible)
- **Location**: Board name header
- **Shows**: Your current role on the board (Admin, Editor, Member, Viewer)
- **Visual**: Blue badge next to board title

### 2. **Permission Info Banner** (When Restrictions Apply)
- **Location**: Just below board header (top of board view)
- **Shows**:
  - Your role
  - Which columns have restrictions
  - Quick link to manage permissions
- **Visual**: Info banner with lock icons
- **Dismissible**: Yes (close button)

### 3. **Column Restriction Badges**
- **Location**: On each column header
- **Shows**: Yellow "Restricted" badge when you can't move tasks into that column
- **Visual**: 🔒 Lock icon with warning badge

### 4. **Main Navigation Access**
**For Admins** - Click your username in top-right navigation:
```
Username Dropdown →
  ├── Profile
  ├── Organization
  ├── 🆕 Manage Roles & Permissions
  ├── 🆕 Permission Audit Log
  ├── ─────────────
  ├── AI Usage
  └── Logout
```

### 5. **Board Settings Menu**
**Location**: Board view → Settings gear icon (⚙️)

```
Settings Dropdown →
  ├── Add Column
  ├── Manage Labels
  ├── Manage Stakeholders
  ├── ─────────────
  ├── 🆕 Manage Members & Roles    ← Assign/change roles
  ├── 🆕 Permission Audit Log      ← See who changed what
  ├── ─────────────
  ├── Edit Board
  ├── Board Settings
  ├── Webhooks & Integrations
  └── Delete Board
```

## 📋 Quick Access URLs

### Role Management
```
/permissions/roles/
```
- Create custom roles
- Edit permissions
- View role details
- Delete custom roles (system roles protected)

### Board Member Management
```
/board/{board_id}/members/manage/
```
- Add members with specific roles
- Change member roles (dropdown)
- Remove members
- See role assignments

### Permission Audit Log (Board)
```
/board/{board_id}/permissions/audit/
```
- See all permission changes for a board
- Filter by action type
- View who made changes
- See timestamps and IP addresses

### Permission Audit Log (Organization)
```
/permissions/audit/
```
- Organization-wide audit log
- All boards combined
- Admin only

## 🎨 Visual Indicators

### Role Badges
- **Admin**: Blue badge with shield icon
- **Editor**: Default role
- **Member**: Standard role
- **Viewer**: Read-only

### Column Status Indicators
- **🔒 Restricted** (Yellow): Cannot move tasks INTO this column
- **🚫 Read-Only** (Gray): Cannot edit tasks in this column
- **✅ Full Access** (No badge): No restrictions

### Permission Banners
- **Blue Info Banner**: Shows your active restrictions
- **Dismissible**: Click X to hide (persists for session)

## 🔄 Approval Workflow Example

### Visual Flow
```
┌─────────┐    ┌──────────────┐    ┌─────────┐    ┌──────┐
│ To Do   │ → │ In Progress  │ → │ Review  │ → │ Done │
│ ✅ Free │    │ ✅ Free      │    │ 🔒 Lock │    │ 🔒 Lock│
└─────────┘    └──────────────┘    └─────────┘    └──────┘
   Member           Member           Admin only    Admin only
   access           access            required      required
```

### What Members See
- **To Do**: Full access, green checkmark
- **In Progress**: Full access, green checkmark
- **Review**: 🔒 **Restricted** badge (can't move tasks here)
- **Done**: 🔒 **Restricted** badge (can't approve)

### What Admins See
- All columns: ✅ Full access (no restrictions)

## 💡 User Experience Features

### 1. **Real-Time Feedback**
When trying to move a task to a restricted column:
- Error message: "Cannot move tasks into 'Review'"
- Task stays in original column
- Clear explanation of restriction

### 2. **Proactive Indicators**
- See restrictions BEFORE attempting action
- Visual badges prevent confusion
- Role badge always visible

### 3. **Easy Management**
- One click from board to member management
- Change roles via dropdown (no page reload)
- Instant feedback on permission changes

### 4. **Audit Trail**
- Every change logged automatically
- View history anytime
- Filter by date, user, or action

## 🔍 Testing the UI

### As a Member:
1. Open any board with approval workflow
2. See your "Member" role badge in header
3. See blue info banner with restrictions
4. Notice "🔒 Restricted" badges on Review/Done columns
5. Try to drag a task to "Done" → See error message

### As an Admin:
1. Same board shows "Admin" role badge
2. No restriction banners (full access)
3. No lock badges on columns
4. Can move tasks anywhere
5. Access management via username dropdown or board settings

### Managing Permissions:
1. Click board settings gear (⚙️)
2. Select "Manage Members & Roles"
3. See table of all members with role dropdowns
4. Change a role → Confirmation → Audit log entry created
5. View audit log to see the change recorded

## 📊 Dashboard Integration

Permission features are integrated into:
- ✅ Board list/detail views
- ✅ Task creation forms
- ✅ Task move operations
- ✅ Column management
- ✅ Member invitations
- ✅ Settings menus

## 🎯 Best Practices for Users

### For Team Members:
1. Check your role badge when joining a new board
2. Read the info banner to understand restrictions
3. Don't try to force actions you can't perform
4. Ask admin if you need different permissions

### For Admins:
1. Set up approval workflows early
2. Assign appropriate roles to members
3. Review audit log regularly
4. Use column permissions for quality control
5. Explain workflow to team members

## 🚀 Getting Started

1. **Admin**: Go to `/permissions/roles/` to see all roles
2. **Admin**: Create custom roles if needed
3. **Admin**: Go to board → "Manage Members & Roles"
4. **Admin**: Assign Member role to appropriate users
5. **Everyone**: Refresh board to see new UI indicators
6. **Everyone**: Work within your permissions!

---

**Remember**: The UI shows you exactly what you can/can't do BEFORE you try. Look for badges, banners, and visual cues!
