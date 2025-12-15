# Demo Board Access Control - Complete Implementation

## Problem Summary
Two issues were identified in demo board Resource Optimization:
1. **user8 not appearing**: user7 invited user8, but user8 didn't appear in Resource Optimization
2. **Wrong users in suggestions**: AI suggestions showed "user1" instead of users from user7's organization

## Root Cause Analysis

### Issue 1: user8 Not Appearing
- **Cause**: When user7 invited user8, user8 was only added to the specific board, not all demo boards
- **Impact**: Resource Optimization filters by `board.members.filter(profile__organization=user_org)`, so user8 didn't appear since they weren't a board member
- **Expected Behavior**: Demo boards use organization-level access (being member of one demo board = access to all in that demo org)

### Issue 2: Wrong Users in Suggestions
- **Cause**: AI suggestion functions didn't pass `requesting_user` parameter, so they couldn't filter by organization
- **Impact**: Suggestions showed all demo board members regardless of the viewing user's organization
- **Expected Behavior**: Demo boards should show only users from the viewer's REAL organization

## Solution Implementation

### 1. Updated Resource Leveling Service Functions
**File**: `kanban/resource_leveling.py`

#### a) `analyze_task_assignment` (lines 50-81)
- Added `requesting_user` parameter
- Filter potential assignees by requesting user's organization for demo boards
```python
# For demo boards, filter to only users from requesting user's organization
demo_org_names = ['Dev Team', 'Marketing Team']
if board.organization.name in demo_org_names and requesting_user:
    try:
        user_org = requesting_user.profile.organization
        potential_assignees = potential_assignees.filter(profile__organization=user_org)
    except Exception:
        potential_assignees = potential_assignees.filter(id=requesting_user.id)
```

#### b) `create_suggestion` (line 278)
- Added `requesting_user` parameter to signature
- Pass `requesting_user` to `analyze_task_assignment` (line 289)

#### c) `get_board_optimization_suggestions` (lines 360-410)
- Added `requesting_user` parameter to signature
- Filter tasks by requesting user's organization for demo boards (lines 390-401)
- Pass `requesting_user` to `create_suggestion` (line 408)

#### d) `get_team_workload_report` (lines 465-485)
- Already had `requesting_user` parameter
- Filter verified: `board.members.filter(profile__organization=user_org)`

### 2. Updated Resource Leveling Views
**File**: `kanban/resource_leveling_views.py`

#### a) `analyze_task_assignment` view (line 76)
```python
analysis = service.analyze_task_assignment(task, requesting_user=request.user)
```

#### b) `create_suggestion` view (line 119)
```python
suggestion = service.create_suggestion(task, requesting_user=request.user)
```

#### c) `get_board_suggestions` view (line 267)
```python
suggestions = service.get_board_optimization_suggestions(board, limit=20, requesting_user=request.user)
```

### 3. Updated Board Member Addition
**File**: `kanban/views.py` - `add_board_member` function (lines 1060-1100)

Added logic to detect demo boards and add users to ALL demo boards in that organization:
```python
# Check if this is a demo board
demo_org_names = ['Dev Team', 'Marketing Team']
is_demo_board = board.organization.name in demo_org_names

if is_demo_board:
    # For demo boards: add user to ALL boards in this demo organization
    demo_boards = Board.objects.filter(organization=board.organization)
    added_count = 0
    for demo_board in demo_boards:
        if user not in demo_board.members.all():
            demo_board.members.add(user)
            added_count += 1
    
    if added_count > 0:
        messages.success(request, f'{user.username} added to {added_count} demo board(s) successfully!')
```

### 4. Fixed Existing Data
**Script**: `add_user8_to_demo.py`

Added user8 to all 3 demo boards to fix the immediate issue:
- Software Project (Dev Team)
- Bug Tracking (Dev Team)
- Marketing Campaign (Marketing Team)

## Verification Results

### Test 1: user7's View (organization: "organization")
```
Team Workload Report:
  - user7: 0 tasks, 0.0% utilization
  - user8: 0 tasks, 0.0% utilization

Task Assignment Analysis:
  All candidates (2):
    - user7: score 73.0
    - user8: score 73.0

Board Optimization Suggestions:
  All suggestions recommend: user7 or user8 only
```

### Test 2: user1's View (organization: "organization 1")
```
Team Workload Report:
  - user1: 0 tasks, 0.0% utilization

Expected: user1 only sees user1
Actual: ✓ Correct - user7 and user8 NOT shown
```

## Access Control Model

### Demo Board Access Rules
1. **Organization-Level Access**: Being a member of ONE demo board grants access to ALL boards in that demo organization
2. **User Visibility Filtering**: Users only see other users from their REAL organization, not the demo org
3. **Invitation Behavior**: Inviting a user adds them to ALL demo boards in that demo organization
4. **Auto-Access**: First visit to demo dashboard auto-adds user to all demo boards

### Data Isolation
- **Demo boards** (in "Dev Team" or "Marketing Team" orgs) are isolated from main dashboard
- **Real organizations** maintain separate member visibility even within shared demo boards
- **AI suggestions** respect organization boundaries and only recommend users from viewer's org

## Files Modified
1. `kanban/resource_leveling.py` - Added requesting_user filtering throughout
2. `kanban/resource_leveling_views.py` - Pass requesting_user to service methods
3. `kanban/views.py` - Add users to ALL demo boards when invited
4. `add_user8_to_demo.py` - Script to fix existing data

## Testing Scripts Created
1. `debug_demo_members.py` - Show demo board membership details
2. `test_resource_filtering.py` - Test filtering with user7
3. `test_user1_filtering.py` - Test filtering with user1

## Summary
✅ **Issue 1 Fixed**: user8 now appears in Resource Optimization after being invited
✅ **Issue 2 Fixed**: AI suggestions now show only users from requesting user's organization
✅ **Organization Isolation**: Each real organization sees only their own members in demo boards
✅ **Consistent Access**: Demo board access is now organization-level and invitation-based
