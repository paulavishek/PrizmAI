# Testing Guide - Demo Board Access Control

## What Was Fixed

### Problem 1: user8 Not Appearing in Resource Optimization
**Before**: user7 invited user8, but user8 didn't show in team workload
**After**: user8 now appears in team workload and AI suggestions

### Problem 2: Wrong Users in AI Suggestions
**Before**: Suggestions showed "user1 is 100% free" even when logged in as user7
**After**: Suggestions only show users from the logged-in user's organization

## How to Test

### Test 1: Verify user8 Appears (user7's View)

1. **Login as user7**
   - Navigate to http://localhost:8000/
   - Login with user7 credentials

2. **Access Demo Mode**
   - Click "Demo" in the main navigation
   - Select "Software Project" or any demo board

3. **Open Resource Optimization**
   - Click the "Resource Optimization" button/link on the board

4. **Expected Results**:
   ✅ Team Workload section should show:
   - user7: 0 tasks, 0% utilization
   - user8: 0 tasks, 0% utilization
   
   ✅ AI Suggestions should mention:
   - "Assign to user7" or "Assign to user8"
   - NO mention of "user1" or other users

### Test 2: Verify Organization Isolation (user1's View)

1. **Login as user1**
   - Logout from user7 if still logged in
   - Login with user1 credentials

2. **Access Demo Mode**
   - Click "Demo" in the main navigation
   - Select "Software Project" or any demo board

3. **Open Resource Optimization**
   - Click the "Resource Optimization" button/link

4. **Expected Results**:
   ✅ Team Workload section should show:
   - user1: 0 tasks, 0% utilization
   - ONLY user1 (NOT user7 or user8)
   
   ✅ AI Suggestions should mention:
   - "Assign to user1"
   - NO mention of user7, user8, or other users

### Test 3: Verify Invitation Behavior

1. **Login as user7**

2. **Navigate to a Demo Board**
   - Go to Demo → "Bug Tracking"

3. **Try to Invite a New User** (if you have another test user)
   - Look for "Add Member" or member invitation option
   - Try adding a user from user7's organization

4. **Expected Results**:
   ✅ Success message should say: "X added to N demo board(s) successfully!"
   - Where N is the total number of demo boards in that organization (e.g., 2 for Dev Team)
   
   ✅ The invited user should appear in ALL demo boards in that organization

### Test 4: Verify Team Workload Report API

1. **Open Browser Developer Tools** (F12)

2. **Navigate to Demo → Software Project → Resource Optimization**

3. **Check Network Tab**
   - Look for API call to `/api/boards/{board_id}/team-workload/`
   - View the response

4. **Expected Results**:
   ✅ Response should show:
   ```json
   {
     "team_size": 2,
     "members": [
       {"username": "user7", "active_tasks": 0, "utilization": 0},
       {"username": "user8", "active_tasks": 0, "utilization": 0}
     ]
   }
   ```

## Known Behavior

### Organization-Level Access
- When you visit demo for the first time, you're auto-added to ALL demo boards
- When you invite someone, they're added to ALL demo boards in that demo organization

### User Visibility Rules
- Demo boards are in "Dev Team" or "Marketing Team" organizations
- But you only see users from YOUR REAL organization
- Example:
  - user7 and user8 are in "organization"
  - user1 is in "organization 1"
  - Even though all are members of the same demo board, they only see their own org members

### Data Isolation
- Demo data is separate from your main dashboard
- Your real boards won't show demo data
- Demo boards won't show your real board data

## Verification Scripts

Three test scripts are available in the project root:

1. **`debug_demo_members.py`**
   - Shows all demo board members and their organizations
   - Run: `python debug_demo_members.py`

2. **`test_resource_filtering.py`**
   - Tests filtering with user7
   - Run: `python test_resource_filtering.py`

3. **`test_user1_filtering.py`**
   - Tests filtering with user1
   - Run: `python test_user1_filtering.py`

## Troubleshooting

### If user8 Still Doesn't Appear:
1. Check if user8 is a member of demo boards: Run `debug_demo_members.py`
2. If not, run: `python add_user8_to_demo.py`
3. Verify user7 and user8 are in the same organization

### If Wrong Users Still Show in Suggestions:
1. Clear browser cache and reload
2. Restart the development server
3. Check browser console for JavaScript errors

### If Demo Boards Don't Load:
1. Check if Redis is running
2. Check if Celery workers are running
3. Check Django logs for errors

## Success Criteria

✅ user7 sees only user7 and user8 in Resource Optimization
✅ user1 sees only user1 in Resource Optimization
✅ AI suggestions recommend only users from the same organization
✅ Inviting a user adds them to ALL demo boards in that demo org
✅ No cross-organization user visibility in demo mode

## Files Changed
- `kanban/resource_leveling.py` - Added organization filtering
- `kanban/resource_leveling_views.py` - Pass requesting_user parameter
- `kanban/views.py` - Add users to ALL demo boards when invited

For detailed technical documentation, see: `DEMO_ACCESS_CONTROL_COMPLETE.md`
