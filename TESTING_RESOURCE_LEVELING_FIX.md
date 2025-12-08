# Quick Start: Testing the AI Resource Leveling Sync Fix

## What Was Fixed

The AI Resource Optimization board now automatically updates when you:
- Assign or reassign tasks manually
- Accept AI suggestions for task reassignment
- Create new tasks with assignees
- Complete tasks

## Step-by-Step Testing

### 1. First-Time Setup: Sync Existing Data

Run this command to bring all existing profiles up to date:

```powershell
python manage.py refresh_performance_profiles
```

**Expected Output:**
```
Starting profile refresh...

Processing organization: YourOrganization
  Found 2 boards
  Found 4 unique team members
    Updated profile for user1: 2 → 2 tasks, 16.0h → 16.0h workload
    Updated profile for user2: 5 → 5 tasks, 40.0h → 40.0h workload
    Updated profile for user3: 3 → 3 tasks, 24.0h → 24.0h workload
    Updated profile for user4: 1 → 1 tasks, 8.0h → 8.0h workload

✓ Successfully refreshed 4 user profiles
All workload data is now in sync!
```

### 2. Test Manual Task Assignment

1. Open your browser and go to a board
2. Click on any task to edit it
3. **Before**: Note the current assignee in the AI Resource Optimization widget
4. **Change**: Assign the task to a different user
5. **Save** the task
6. **Verify**: 
   - The AI Resource Optimization widget should immediately show:
     - Old assignee: task count decreased by 1
     - New assignee: task count increased by 1
     - Workload hours updated for both users

### 3. Test AI Suggestion Acceptance

1. Go to a board with active AI suggestions in the Resource Optimization widget
2. Click "Accept" on a suggestion
3. **Verify after page refresh**:
   - Task shows new assignee on the Kanban board
   - AI widget shows correct task count for new assignee
   - Workload bars reflect the change
   - Both old and new assignee's metrics are updated

### 4. Test New Task Creation

1. Create a new task on any board
2. Assign it to a specific user
3. Save the task
4. **Verify**: 
   - User's task count in AI widget increased by 1
   - Workload hours increased proportionally

### 5. Verify Real-Time Sync

Open Django shell to verify data consistency:

```powershell
python manage.py shell
```

Then run:

```python
from kanban.resource_leveling_models import UserPerformanceProfile
from django.contrib.auth.models import User
from kanban.models import Task

# Replace 'username' with an actual user
user = User.objects.get(username='YOUR_USERNAME')
profile = UserPerformanceProfile.objects.filter(user=user).first()

if profile:
    print(f"Profile shows: {profile.current_active_tasks} tasks")
    print(f"Workload: {profile.current_workload_hours:.1f} hours")
    print(f"Utilization: {profile.utilization_percentage:.1f}%")
    
    # Count actual tasks
    actual = Task.objects.filter(
        assigned_to=user,
        completed_at__isnull=True
    ).exclude(column__name__icontains='done').count()
    
    print(f"\nActual active tasks: {actual}")
    
    if profile.current_active_tasks == actual:
        print("✓ SYNC IS WORKING! Counts match.")
    else:
        print("✗ Mismatch detected. Run: python manage.py refresh_performance_profiles")
else:
    print(f"No profile found for {user.username}")
```

## Troubleshooting

### Widget Still Shows 0 Tasks

**Try:**
1. Hard refresh the page (Ctrl+F5)
2. Run: `python manage.py refresh_performance_profiles`
3. Restart Django server: `python manage.py runserver`

### Changes Not Reflecting Immediately

**Check:**
1. Is the board page cached? Clear browser cache
2. Check browser console for JavaScript errors
3. Verify signals are loading:
   ```python
   python manage.py shell
   from kanban import signals
   print("Signals loaded successfully!")
   ```

### Workload Shows Wrong Hours

**Cause**: Tasks may have incorrect complexity scores or missing data

**Fix:**
```powershell
python manage.py refresh_performance_profiles
```

This recalculates everything from scratch.

## What Happens Behind the Scenes

When you assign a task:

1. **Django Signal** detects the assignment change
2. **Old Assignee's Profile** is updated automatically:
   - Task count decreases
   - Workload hours decrease
   - Utilization percentage recalculated
3. **New Assignee's Profile** is updated:
   - Task count increases
   - Workload hours increase
   - Utilization percentage recalculated
4. **Assignment History** entry is created for audit trail
5. **Widget Data** reflects changes on next page load

## Success Indicators

✅ Task count on widget matches actual assigned tasks  
✅ Workload hours update when assignments change  
✅ Utilization percentage shows correctly (0-100%+)  
✅ Accepting AI suggestions updates widget immediately  
✅ Manual edits update widget immediately  
✅ Creating new tasks updates widget immediately  

## Next Steps

Once you confirm everything is working:

1. **Monitor** the AI Resource Optimization widget over the next few days
2. **Accept AI suggestions** when appropriate
3. **Check assignment history** to see the audit trail
4. **Review team workload** to ensure balanced distribution

## Need Help?

If you encounter issues:

1. Check the documentation: `AI_RESOURCE_LEVELING_SYNC_FIX.md`
2. Run the sync command: `python manage.py refresh_performance_profiles`
3. Check Django logs for errors
4. Verify signal handlers are loaded (see troubleshooting above)
