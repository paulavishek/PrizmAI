# AI Resource Leveling Synchronization Fix

## Problem Description

After implementing AI-powered resource leveling and accepting assignment suggestions, there was a discrepancy between:
1. The actual task assignments on the Kanban board
2. The task counts shown in the AI Resource Optimization widget
3. The workload metrics displayed for each team member

**Symptoms:**
- Tasks were reassigned to new users based on AI suggestions
- The new assignee appeared on the task ticket
- BUT the AI Resource Optimization board still showed 0 tasks for that assignee
- Workload hours and utilization percentages were not updating

## Root Cause

The `UserPerformanceProfile.update_current_workload()` method was only being called:
1. When accepting AI suggestions through the API
2. Manually through management commands

It was NOT being called when:
1. Tasks were edited manually through the web interface
2. Tasks were created with an assignee
3. Tasks were moved or reassigned through drag-and-drop

This caused the workload metrics to be stale and out of sync with actual assignments.

## Solution Implemented

### 1. Automatic Signal-Based Updates

Created `kanban/signals.py` with Django signal handlers that automatically:
- Track when task assignments change (before save)
- Update both old and new assignee's workload profiles (after save)
- Create assignment history records for audit trail
- Update performance metrics when tasks are completed

**Key Features:**
- `track_task_assignment_change`: Pre-save signal to detect assignment changes
- `update_workload_on_assignment_change`: Post-save signal to refresh profiles
- `update_profile_on_task_completion`: Updates metrics when tasks complete

### 2. Signal Registration

Updated `kanban/apps.py` to automatically load signal handlers when Django starts:
```python
def ready(self):
    import kanban.signals  # Load signal handlers
```

### 3. View Updates

Modified task creation and editing views to pass the user context:
- `create_task` view: Sets `task._changed_by_user = request.user`
- `edit_task` view: Sets `task._changed_by_user = request.user`

This allows the signal handlers to know who made the assignment change.

### 4. AI Suggestion Handling

Updated `ResourceLevelingSuggestion.accept()` to:
- Set `task._ai_suggestion_accepted = True` flag
- Prevent duplicate assignment history entries
- Keep backup manual profile updates in case signals don't fire

### 5. Manual Sync Command

Created a management command to manually refresh all profiles if needed:
```bash
python manage.py refresh_performance_profiles
```

Options:
- `--organization <ID>`: Only refresh specific organization

## How It Works Now

### When a Task is Assigned (New or Changed):

1. **Pre-save signal** (`track_task_assignment_change`):
   - Fetches the old task state
   - Stores old assignee in `_old_assigned_to`
   - Marks if assignment changed in `_assignment_changed`

2. **Task saves** (form submission or API call)

3. **Post-save signal** (`update_workload_on_assignment_change`):
   - Checks if assignment actually changed
   - **Updates old assignee's profile** (if exists):
     - Recalculates `current_active_tasks`
     - Recalculates `current_workload_hours`
     - Updates `utilization_percentage`
   - **Updates new assignee's profile**:
     - Adds this task to their workload
     - Recalculates metrics
   - Creates `TaskAssignmentHistory` entry

4. **Result**: AI Resource Optimization board shows accurate, real-time data

### When a Task is Completed:

1. **Post-save signal** (`update_profile_on_task_completion`):
   - Detects task completion
   - Calls `profile.update_metrics()` to recalculate:
     - Total tasks completed
     - Average completion time
     - Velocity score
     - On-time completion rate
   - Updates assignment history with actual completion data

## Testing the Fix

### Step 1: Run the Sync Command

First, sync all existing data to get current profiles up to date:

```bash
python manage.py refresh_performance_profiles
```

You should see output like:
```
Processing organization: YourOrg
  Found 3 boards
  Found 5 unique team members
    Updated profile for alice: 3 → 3 tasks, 24.0h → 24.0h workload
    Updated profile for bob: 5 → 5 tasks, 40.0h → 40.0h workload
    ...
✓ Successfully refreshed 5 user profiles
```

### Step 2: Test Manual Assignment

1. Go to a board and edit a task
2. Change the assignee from User A to User B
3. Save the task
4. Check the AI Resource Optimization widget
   - User A should show one fewer task
   - User B should show one more task
   - Workload hours should update accordingly

### Step 3: Test AI Suggestion Acceptance

1. Go to a board with the AI Resource Optimization widget
2. Accept an AI suggestion to reassign a task
3. The page will refresh
4. Verify:
   - Task shows new assignee on Kanban board
   - AI widget shows correct task count for both users
   - Workload bars reflect the change

### Step 4: Test Task Creation

1. Create a new task and assign it to a user
2. Check the AI Resource Optimization widget
3. Verify the user's task count increased by 1

## Verification Queries

You can verify the fix is working using Django shell:

```python
from kanban.resource_leveling_models import UserPerformanceProfile
from django.contrib.auth.models import User
from kanban.models import Task

# Check a user's profile
user = User.objects.get(username='alice')
profile = UserPerformanceProfile.objects.get(user=user)

print(f"Active tasks: {profile.current_active_tasks}")
print(f"Workload hours: {profile.current_workload_hours}")
print(f"Utilization: {profile.utilization_percentage}%")

# Compare with actual task count
actual_tasks = Task.objects.filter(
    assigned_to=user,
    completed_at__isnull=True
).exclude(column__name__icontains='done').count()

print(f"Actual active tasks: {actual_tasks}")
print(f"Match: {profile.current_active_tasks == actual_tasks}")
```

## What Gets Updated Automatically

Now these operations automatically update workload profiles:

✅ Creating a task with an assignee  
✅ Editing a task to change assignee  
✅ Accepting AI resource leveling suggestions  
✅ Completing a task (updates velocity and metrics)  
✅ Moving tasks between columns (if assignment changes)

## Troubleshooting

### Issue: Workload still shows 0 after assignment

**Solution**: Run the sync command manually:
```bash
python manage.py refresh_performance_profiles
```

### Issue: Signal handlers not firing

**Check**:
1. Verify `kanban.apps.KanbanConfig` is in `INSTALLED_APPS`
2. Check `kanban/apps.py` has the `ready()` method
3. Restart Django server after making changes

### Issue: Duplicate assignment history entries

**Cause**: Signals firing multiple times or old code paths  
**Solution**: The code now sets `task._ai_suggestion_accepted` flag to prevent duplicates

## Files Modified

1. **kanban/signals.py** (NEW) - Signal handlers for automatic updates
2. **kanban/apps.py** - Added `ready()` method to load signals
3. **kanban/views.py** - Updated `create_task` and task edit to pass user context
4. **kanban/resource_leveling_models.py** - Updated `accept()` method with flag
5. **kanban/management/commands/refresh_performance_profiles.py** (NEW) - Manual sync command

## Benefits

- **Real-time accuracy**: Workload metrics update instantly
- **Zero maintenance**: No manual refresh needed
- **Audit trail**: All assignment changes tracked in history
- **Better AI**: More accurate data for future suggestions
- **Consistent UI**: Board and widget always show same data

## Future Enhancements

Potential improvements:
- WebSocket notifications when workload updates
- Real-time widget refresh without page reload
- Batch updates for better performance
- Caching layer for frequently accessed profiles
