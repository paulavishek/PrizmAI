# 📅 PrizmAI Demo Data Guide

## Overview

PrizmAI's demo data system is designed to provide a realistic, always-fresh demonstration experience. All dates in the demo are **dynamically generated relative to the current date**, ensuring that no matter when you run the demo - today, next month, or next year - the data will appear current and relevant.

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

### 2. **Zero Configuration Required**

The demo data automatically:
- ✅ Uses `timezone.now()` for all date calculations
- ✅ Applies relative `timedelta` offsets
- ✅ Maintains logical task dependencies
- ✅ Preserves realistic project workflows
- ✅ Keeps completed tasks in the past
- ✅ Schedules future work appropriately

### 3. **Automatic Refresh on Creation**

When you run `python manage.py populate_test_data`, the system automatically:
1. Creates all demo data (users, boards, tasks, milestones, etc.)
2. Sets up task dependencies with Gantt chart visualization
3. **Automatically refreshes all dates** to ensure currency
4. Distributes dates based on task status and column

## 🔄 Maintaining Fresh Demo Data

### When to Refresh

You should refresh demo data dates when:
- ✅ Revisiting the demo after several weeks
- ✅ Preparing for a stakeholder presentation
- ✅ Notice many tasks appearing overdue
- ✅ Demo hasn't been used in 1-2 months

### How to Refresh

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

## 🚀 Quick Reference

```bash
# Create demo data (includes automatic refresh)
python manage.py populate_test_data

# Refresh dates only
python manage.py refresh_demo_dates

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
