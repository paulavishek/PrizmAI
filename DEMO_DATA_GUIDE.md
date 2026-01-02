# 📅 PrizmAI Demo Data Guide

## Overview

PrizmAI's demo data system is designed to provide a realistic, always-fresh demonstration experience. All dates in the demo are **dynamically generated relative to the current date**, ensuring that no matter when you run the demo - today, next month, or next year - the data will appear current and relevant.

## 🔄 Automatic Date Refresh (NEW!)

**Demo data dates are automatically refreshed daily** when users access demo mode. This means:
- ✅ Demo data always appears fresh and current
- ✅ Users see the same experience whether they try the demo today or in a year
- ✅ Metrics like overdue tasks, velocity, and burndown remain consistent
- ✅ No manual intervention required
- ✅ **User-created content is NOT affected** - only original demo data is refreshed

The automatic refresh is handled by `DemoSessionMiddleware` which checks once per day and updates all date-related demo data relative to the current date.

### Important: User-Created Content is Preserved

The date refresh system distinguishes between:
1. **Seed Demo Data** (original demo content) - dates ARE refreshed daily
2. **User-Created Content** (tasks/boards users create in demo mode) - dates are NOT touched

User-created content is identified by the `created_by_session` field. Content created by demo users is automatically cleaned up after 48 hours by the demo session expiry system.

## 🎯 Single Source of Truth: Official Demo Boards

**IMPORTANT:** PrizmAI maintains a single set of official demo boards with **1000+ tasks** in dedicated demo organizations:
- **Dev Team** organization: Software Project, Bug Tracking boards
- **Marketing Team** organization: Marketing Campaign board

These boards contain comprehensive demo data including:
- 300-350 tasks per board (total ~1000 tasks across all 3 boards)
- Complete feature demonstrations
- Historical task data for AI predictions
- Risk management, resource forecasting, budget tracking
- Milestones, dependencies, and stakeholder management

**Users should NEVER create their own demo boards.** Instead, use the "Load Demo Data" feature to get access to these official shared boards.

## ✨ Key Features

### 1. **Intelligent Date Distribution**

Demo data is automatically distributed across time periods based on task status:

| Task Status | Date Range | Purpose |
|------------|-----------|----------|
| **Completed (Done)** | Last 60 days | Shows recent accomplishments |
| **In Review/Testing** | ±5 days from today | Tasks nearing completion |
| **In Progress** | -10 to +15 days | Active work items |
| **To Do** | +2 to +20 days | Upcoming planned work |
| **Backlog** | +15 to +60 days | Future planning |
| **Historical (Analytics)** | Last 180 days | Training data for AI predictions |

### 2. **Comprehensive Coverage**

The dynamic date refresh covers ALL demo data features:
- ✅ Task due dates and start dates
- ✅ Milestones (target and completion dates)
- ✅ Sprint milestones
- ✅ Time tracking entries
- ✅ Retrospectives (period start/end)
- ✅ Velocity snapshots
- ✅ Coaching suggestions
- ✅ Conflict detection timestamps
- ✅ Wiki page dates
- ✅ AI assistant sessions
- ✅ Improvement metrics
- ✅ Burndown predictions
- ✅ Resource leveling suggestions
- ✅ ROI snapshots
- ✅ Stakeholder engagement records

### 3. **Zero Configuration Required**

The demo data automatically:
- ✅ Uses `timezone.now()` for all date calculations
- ✅ Applies relative `timedelta` offsets
- ✅ Maintains logical task dependencies
- ✅ Preserves realistic project workflows
- ✅ Keeps completed tasks in the past
- ✅ Schedules future work appropriately

### 4. **Automatic Refresh on Creation**

When you run `python manage.py populate_test_data`, the system automatically:
1. Creates all demo data (users, boards, tasks, milestones, etc.)
2. Sets up task dependencies with Gantt chart visualization
3. **Automatically refreshes all dates** to ensure currency
4. Distributes dates based on task status and column

## 🔄 Maintaining Fresh Demo Data

### Automatic Refresh (Recommended)

Demo dates refresh automatically once per day when any user accesses demo mode. No action required!

### Manual Refresh (Optional)

You can manually trigger a refresh when:
- ✅ Preparing for a stakeholder presentation
- ✅ Want to reset dates immediately after data changes
- ✅ Testing the refresh mechanism

### How to Refresh Manually

#### Option 1: Command Line
```bash
python manage.py refresh_demo_dates
```

#### Option 2: Windows Batch Script
```bash
refresh_demo_dates.bat
```

### What Gets Refreshed

The refresh command updates:
- **Tasks**: Due dates and start dates (1,629 tasks)
- **Milestones**: Target dates and completion dates
- **Time Entries**: Work dates (historical logs)
- **Stakeholder Engagement**: Interaction dates
- **Dependencies**: Maintains logical relationships

## 📊 Expected Demo Data Health

After a refresh, you should see:

| Metric | Target | Acceptable Range |
|--------|--------|------------------|
| **Overdue Incomplete Tasks** | 0-5% | < 10% |
| **Tasks Due Next Week** | 20-40 | 15-50 |
| **Tasks Due Next Month** | 80-120 | 60-150 |
| **Completed in Last 60 Days** | 1400-1500 | > 1200 |

### Check Demo Health

Run this command to check your demo data status:

```bash
python manage.py shell -c "from kanban.models import Task; from django.utils import timezone; from datetime import timedelta; now = timezone.now(); incomplete = Task.objects.filter(progress__lt=100); print(f'Overdue: {incomplete.filter(due_date__lt=now).count()}/{incomplete.count()} ({incomplete.filter(due_date__lt=now).count()/incomplete.count()*100:.1f}%)')"
```

## 🏗️ Architecture

### Dynamic Date Generation

All demo data files use this pattern:

```python
from django.utils import timezone
from datetime import timedelta

# Always relative to current date
base_date = timezone.now().date()

# Task in the past (completed)
task.due_date = timezone.now() - timedelta(days=30)

# Task in near future
task.due_date = timezone.now() + timedelta(days=7)
```

### Key Files

1. **`populate_test_data.py`**: Main demo data creation
   - Creates users, organizations, boards, tasks
   - Automatically calls refresh at the end

2. **`refresh_demo_dates.py`**: Date refresh logic
   - Smart date distribution by task status
   - Preserves logical dependencies
   - Bulk updates for performance

3. **`fix_gantt_demo_data.py`**: Gantt chart setup
   - Creates realistic task dependencies
   - Sets up Finish-to-Start relationships
   - Uses dynamic dates

## 🎯 Best Practices

### For Demo Users

1. **First Time Setup**: Just run `populate_test_data`
   ```bash
   python manage.py populate_test_data
   ```
   Dates are automatically fresh!

2. **Periodic Maintenance**: Refresh every 1-2 months
   ```bash
   python manage.py refresh_demo_dates
   ```

3. **Before Presentations**: Always refresh to ensure current dates
   ```bash
   python manage.py refresh_demo_dates
   ```

### For Developers

1. **Use `timezone.now()`**: Never hardcode dates
   ```python
   # ✅ Good
   due_date = timezone.now() + timedelta(days=7)
   
   # ❌ Bad
   due_date = datetime(2024, 12, 31)
   ```

2. **Use Relative Offsets**: Calculate based on task state
   ```python
   # Completed task: in the past
   if task.progress == 100:
       days_offset = -(task.id % 60 + 3)
   
   # Active task: near present
   elif column_name == 'in progress':
       days_offset = (task.id % 26) - 10
   
   # Future task: in the future
   else:
       days_offset = (task.id % 46) + 15
   ```

3. **Test Date Distribution**: Ensure realistic spread
   ```python
   # Check distribution after changes
   past = Task.objects.filter(due_date__lt=now).count()
   future = Task.objects.filter(due_date__gte=now).count()
   ```

## 🔍 Troubleshooting

### Too Many Overdue Tasks

**Problem**: More than 10% of incomplete tasks are overdue

**Solution**: Run the refresh command
```bash
python manage.py refresh_demo_dates
```

### Tasks Have Very Old Dates

**Problem**: Tasks show dates from months/years ago

**Solution**: Demo data needs refreshing
```bash
python manage.py refresh_demo_dates
```

### Milestones Not Showing

**Problem**: No milestones in the system

**Solution**: Re-run demo data creation
```bash
python manage.py populate_test_data
```

### All Tasks in the Future

**Problem**: No completed tasks showing recent history

**Solution**: Check if refresh command was run incorrectly. Re-run:
```bash
python manage.py refresh_demo_dates
```

## 📈 Performance Notes

- **Bulk Updates**: Commands use bulk operations for speed
- **Typical Refresh Time**: 5-10 seconds for 1,600+ tasks
- **Minimal Signal Overhead**: Avoids triggering signals during bulk updates
- **Database Friendly**: Uses batch sizes to prevent memory issues

## 🎓 Learning Resources

- **API Documentation**: See [API_DOCUMENTATION.md](API_DOCUMENTATION.md)
- **Setup Guide**: See [SETUP.md](SETUP.md)
- **User Guide**: See [USER_GUIDE.md](USER_GUIDE.md)

## 🧹 Handling Duplicate Demo Boards

### Problem: Users See Duplicate Boards

If users report seeing duplicate demo boards (e.g., two "Software Project" boards with different task counts), this usually happens when:
- Demo boards were accidentally created in user organizations
- Old demo data exists alongside new demo data
- `populate_test_data` was run before the cleanup improvements

### Solution: Cleanup Command

Run the cleanup command to automatically fix duplicates:

```bash
# Check for duplicates (dry run - no changes)
python manage.py cleanup_duplicate_demo_boards --dry-run

# Automatically remove duplicates and migrate users
python manage.py cleanup_duplicate_demo_boards --auto-fix
```

This command will:
1. ✅ Identify official demo boards in demo organizations
2. ✅ Find duplicate boards in user organizations
3. ✅ Migrate users to official demo boards
4. ✅ Remove duplicate boards and their tasks

### Prevention

**Always use the "Load Demo Data" feature** from the dashboard or getting started wizard. Never manually create boards named "Software Project", "Bug Tracking", or "Marketing Campaign" in user organizations.

## 🚀 Quick Reference

```bash
# Create demo data (includes automatic refresh, 1000+ tasks)
python manage.py populate_test_data

# Refresh dates only (keeps existing tasks)
python manage.py refresh_demo_dates

# Remove duplicate demo boards
python manage.py cleanup_duplicate_demo_boards --auto-fix

# Fix Gantt chart dates
python manage.py fix_gantt_demo_data

# Check demo health
python manage.py shell -c "from kanban.models import Task; ..."

# Windows: Refresh with batch script
refresh_demo_dates.bat
```

---

**Last Updated**: December 2025  
**Version**: 1.0  
**Status**: ✅ Fully Implemented
