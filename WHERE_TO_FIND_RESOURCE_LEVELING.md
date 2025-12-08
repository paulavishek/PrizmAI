# 🎯 Where to Find AI Resource Leveling in the UI

## Location: Board Detail Page

The AI Resource Leveling feature appears as a **prominent widget** on every board page.

### Step-by-Step Guide

1. **Navigate to Your Board**
   ```
   Dashboard → Boards → [Select Any Board]
   
   URL: /boards/{board_id}/
   ```

2. **Look for the Widget**
   
   The **"AI Resource Optimization"** widget appears near the top of the board page, right after:
   - Board header with actions
   - Scope creep alerts (if any)
   - Scope status widget
   
   **→ AI Resource Optimization Widget** ⭐ (You'll see it here!)

3. **Widget Location in Page Structure**
   ```
   ┌─────────────────────────────────────────────┐
   │  Board: "Q4 Product Launch"                 │
   │  [Analytics] [Gantt] [Budget] [Settings]    │
   └─────────────────────────────────────────────┘
   
   ┌─────────────────────────────────────────────┐
   │  ⚠️ Scope Creep Alert (if any)              │
   └─────────────────────────────────────────────┘
   
   ┌─────────────────────────────────────────────┐
   │  📊 Scope Status Widget                     │
   └─────────────────────────────────────────────┘
   
   ┌─────────────────────────────────────────────┐
   │  🎯 AI RESOURCE OPTIMIZATION   [🔄 Refresh] │  ⭐ HERE!
   │  ─────────────────────────────────────────  │
   │                                             │
   │  Team Workload                              │
   │  Bob Smith    8 tasks  [████████░░] 113%    │
   │  Jane Doe     3 tasks  [███░░░░░░░] 37%     │
   │                                             │
   │  💡 Suggestions                             │
   │  Fix API bug: bob → jane (70% faster)       │
   │  [✅ Accept] [❌ Dismiss]                    │
   └─────────────────────────────────────────────┘
   
   ┌─────────────────────────────────────────────┐
   │  🔍 Search Tasks                            │
   └─────────────────────────────────────────────┘
   
   ┌─────────────────────────────────────────────┐
   │  Kanban Columns                             │
   │  [To Do] [In Progress] [Done]               │
   └─────────────────────────────────────────────┘
   ```

## What You'll See

### 1. Team Workload Summary (Top Section)
```
Team Workload
─────────────────────────────────────────────
Bob Smith    8 tasks • 45.5h  [████████░░] 113%  🔴
Jane Doe     3 tasks • 15.0h  [███░░░░░░░] 37%   🔵
Alice Cooper 5 tasks • 32.0h  [██████░░░░] 80%   🟡

⚠️ 1 team member overloaded - Review suggestions below
```

**Color Coding:**
- 🔴 Red bar (>90%): Overloaded
- 🟡 Yellow bar (75-90%): High utilization
- 🟢 Green bar (40-75%): Balanced
- 🔵 Blue bar (<40%): Underutilized

### 2. AI Suggestions (Bottom Section)
```
💡 Fix authentication bug
───────────────────────────────────────────────────────
bob → jane

Move to Jane Doe: 70% faster completion (5.6 hours saved),
Better skill match (82% vs 45%), Bob is overloaded (113%)

     70%              85% confidence
 Time Savings

[✅ Accept]  [❌ Dismiss]
⏰ Expires in 42h
```

### 3. Empty State (When No Suggestions)
```
✓ No optimization suggestions at this time.
  Your team workload is well balanced!
```

## First Time Setup

### After Running Migrations

The widget will be visible, but you might see:
```
Team Workload
Loading team workload...  🔄

No optimization suggestions at this time.
```

**Why?** The system needs historical data to generate suggestions.

### Generate Initial Data

To see suggestions immediately, you need:

1. **Completed Tasks** (with assigned users)
   - At least 5-10 completed tasks per user
   - Spread across different team members

2. **Run Profile Update**
   ```bash
   python manage.py shell
   >>> from kanban.resource_leveling import ResourceLevelingService
   >>> from kanban.models import Board
   >>> board = Board.objects.first()
   >>> service = ResourceLevelingService(board.organization)
   >>> service.update_all_profiles(board)
   ```

3. **Refresh the Board Page**
   - You'll now see team workload metrics
   - Suggestions will appear if optimization opportunities exist

## Quick Test (See It Working Now!)

Want to see it working immediately?

### Option 1: Use Test Script
```bash
python manage.py shell < test_resource_leveling.py
```

This will:
- Create test performance profiles
- Generate sample suggestions
- Show you what the widget will look like

### Option 2: Create Test Data
```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User
from kanban.models import Board, Task
from django.utils import timezone
from datetime import timedelta

# Get your board
board = Board.objects.first()

# Create some completed tasks for team members
for user in board.members.all()[:3]:
    for i in range(5):
        Task.objects.create(
            title=f"Test task {i} for {user.username}",
            description="Sample task to build performance profile",
            column=board.columns.first(),
            assigned_to=user,
            completed_date=timezone.now() - timedelta(days=i),
            created_at=timezone.now() - timedelta(days=i+7)
        )

# Update profiles
from kanban.resource_leveling import ResourceLevelingService
service = ResourceLevelingService(board.organization)
result = service.update_all_profiles(board)
print(f"Updated {result['updated']} profiles")

# Generate suggestions
suggestions = service.get_board_optimization_suggestions(board)
print(f"Generated {len(suggestions)} suggestions")
```

Then refresh your board page!

## Accessing Via Direct URLs

You can also interact with the feature via API:

### View Workload Report
```
GET http://localhost:8000/api/resource-leveling/boards/1/workload-report/
```

### View Suggestions
```
GET http://localhost:8000/api/resource-leveling/boards/1/leveling-suggestions/
```

### Analyze Specific Task
```
POST http://localhost:8000/api/resource-leveling/tasks/123/analyze-assignment/
```

## Troubleshooting

### Widget Not Showing?

1. **Check migrations ran:**
   ```bash
   python manage.py migrate
   ```

2. **Check template was updated:**
   - File: `templates/kanban/board_detail.html`
   - Look for: `{% include 'kanban/resource_leveling_widget.html' %}`
   - Should be around line 352 (after scope status widget)

3. **Clear cache and refresh:**
   ```bash
   # Django cache
   python manage.py shell
   >>> from django.core.cache import cache
   >>> cache.clear()
   ```
   
   Then hard refresh browser (Ctrl+Shift+R)

### Widget Shows "Loading..."?

- **Normal!** First page load fetches data via API
- Should load within 1-2 seconds
- Check browser console for errors (F12)

### No Suggestions Appearing?

**Expected Behavior** - You need:
1. ✅ Completed tasks with assigned users
2. ✅ Performance profiles updated
3. ✅ At least 2 team members on the board
4. ✅ Some workload imbalance (one person overloaded)

**If team is well-balanced**, you'll see:
```
✓ No optimization suggestions at this time.
  Your team workload is well balanced!
```

This is actually **good news!** It means your team is optimally distributed.

## Summary

### Where to Find It:
**📍 Board Detail Page → Top of page (after scope widgets)**

### URL Pattern:
```
/boards/{board_id}/
```

### What You'll See:
1. **Team Workload Summary** - Color-coded utilization bars
2. **AI Suggestions** - Smart reassignment recommendations
3. **One-Click Actions** - Accept or dismiss suggestions

### First Time:
- Widget visible immediately after migration
- Needs historical task data for suggestions
- Run test script to see demo

### Access Points:
- ✅ Board detail page (primary UI)
- ✅ REST API endpoints (programmatic)
- ✅ Admin interface (management)

---

**Ready!** Just navigate to any board and scroll to the top to see your new AI Resource Optimization widget! 🚀
