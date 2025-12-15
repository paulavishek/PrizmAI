# Demo Board Access Issue - Fixed

## Problem Summary

Users who gained access to demo boards were unable to access the dashboard and got stuck in the "getting started wizard" loop. This occurred specifically when:

1. User had access to demo boards (as a member)
2. User's `completed_wizard` flag was `False`
3. User had no boards in their own organization
4. User had no tasks assigned in their own organization

## Root Cause

The dashboard view ([kanban/views.py](kanban/views.py#L31-L45)) checks if a user needs the wizard by looking for boards in their **own organization** only:

```python
if not profile.completed_wizard:
    user_boards = Board.objects.filter(
        Q(organization=organization) & 
        (Q(created_by=request.user) | Q(members=request.user))
    ).distinct()
    
    if user_boards.count() == 0 and user_tasks.count() == 0:
        return redirect('getting_started_wizard')  # ❌ Redirects even if user has demo boards!
```

Demo boards are in different organizations (Dev Team, Marketing Team), so they weren't counted. This caused users with demo access to be treated as "brand new users" and redirected to the wizard.

## Changes Made

### 1. Dashboard View - Check for Demo Board Access
**File:** [kanban/views.py](kanban/views.py#L31-L50)

Added a check for demo board memberships before redirecting to wizard:

```python
# Check if user has access to demo boards
demo_board_access = Board.objects.filter(
    members=request.user,
    name__in=['Software Project', 'Bug Tracking', 'Marketing Campaign']
).exists()

# Only show wizard for completely new users (no boards and no demo access)
if user_boards.count() == 0 and user_tasks.count() == 0 and not demo_board_access:
    return redirect('getting_started_wizard')
```

### 2. Load Demo Data View - Mark Wizard as Completed
**File:** [kanban/views.py](kanban/views.py#L2227-L2256)

When users get demo board access (or already have it), mark their wizard as completed:

```python
# Mark wizard as completed since user now has access to boards
profile = request.user.profile
if not profile.completed_wizard:
    profile.completed_wizard = True
    profile.save()
```

This fix is applied in two places:
- When user clicks "Get Access" and is added to boards
- When user already has access and clicks the button again

### 3. Immediate Fix for Existing Users
**Script:** [fix_demo_users_wizard_status.py](fix_demo_users_wizard_status.py)

Created a helper script to fix any existing users with this issue:
- Finds users with demo board access but `completed_wizard=False`
- Marks their wizard as completed
- Can be run anytime: `python fix_demo_users_wizard_status.py`

### 4. Fixed user2 Immediately
Ran: `python manage.py shell -c "...mark wizard as completed for user2..."`

## Testing

Verified the fix for user2:
- ✓ `completed_wizard` set to `True`
- ✓ Dashboard query returns 3 boards: Software Project, Bug Tracking, Marketing Campaign
- ✓ User can now access dashboard without wizard redirect

## Impact

- **Existing affected users:** Will be able to access dashboard immediately
- **New users:** Will have wizard marked as completed when they get demo access
- **Users returning to "Access Demo Boards":** Will have wizard marked as completed even if already have access

## Prevention

The fix ensures this issue cannot occur again by:
1. Checking for demo board membership before wizard redirect
2. Automatically marking wizard as completed when users get demo access
3. Handling both new access and existing access scenarios

## Related Files

- [kanban/views.py](kanban/views.py) - Main fixes (dashboard & load_demo_data views)
- [fix_demo_users_wizard_status.py](fix_demo_users_wizard_status.py) - Helper script to fix existing users
- [add_users_to_demo.py](add_users_to_demo.py) - Related utility for manually adding users to demo boards
