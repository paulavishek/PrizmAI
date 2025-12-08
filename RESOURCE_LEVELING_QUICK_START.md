# AI Resource Leveling - Quick Start Guide

## What You Get

AI automatically suggests: **"Move this task to Jane instead of Bob (70% faster)"**

The system considers:
- ✅ Current workload
- ✅ Skill fit from past work
- ✅ Historical performance
- ✅ Team velocity

## 5-Minute Setup

### Step 1: Run Migrations

```bash
python manage.py makemigrations kanban
python manage.py migrate
```

### Step 2: Add to Main URLs

The URLs are already included in `kanban/urls.py`, so no changes needed!

### Step 3: Add Widget to Board Page

Edit `templates/kanban/board_detail.html` and add near the top:

```django
{% include 'kanban/resource_leveling_widget.html' %}
```

### Step 4: Register Admin (Optional)

Edit `kanban/admin.py` and add at the bottom:

```python
# Import admin classes
from kanban.resource_leveling_admin import *
```

### Step 5: Start Using!

Navigate to any board and you'll see:
- **Team Workload Summary** - Who's overloaded, who's available
- **AI Suggestions** - Smart reassignment recommendations
- **One-Click Accept** - Apply suggestions instantly

## How to Use

### View Team Workload

The widget shows:
- Each team member's utilization (%)
- Active task count
- Estimated workload hours
- Color-coded status (red = overloaded, green = balanced)

### Review Suggestions

Each suggestion shows:
- **Current** → **Suggested** assignee
- **Time savings** (percentage and hours)
- **Confidence score** (AI certainty)
- **Reasoning** (why this change helps)

### Accept or Reject

- Click **Accept** to reassign the task instantly
- Click **Dismiss** to ignore the suggestion
- Suggestions expire after 48 hours

## API Usage (For Custom Integrations)

### Get Suggestions for a Board

```javascript
fetch('/api/resource-leveling/boards/1/leveling-suggestions/')
    .then(response => response.json())
    .then(data => {
        console.log(`${data.total_suggestions} suggestions found`);
        console.log(`Potential savings: ${data.total_potential_savings_hours} hours`);
    });
```

### Analyze Specific Task

```javascript
fetch('/api/resource-leveling/tasks/123/analyze-assignment/', {
    method: 'POST',
    headers: {
        'X-CSRFToken': csrfToken,
        'Content-Type': 'application/json'
    }
})
.then(response => response.json())
.then(data => {
    console.log('Best assignee:', data.top_recommendation.username);
    console.log('Estimated hours:', data.top_recommendation.estimated_hours);
    console.log('Skill match:', data.top_recommendation.skill_match + '%');
});
```

### Get Team Workload Report

```javascript
fetch('/api/resource-leveling/boards/1/workload-report/')
    .then(response => response.json())
    .then(data => {
        // Show overloaded members
        data.bottlenecks.forEach(member => {
            console.log(`${member.name} is ${member.utilization}% utilized!`);
        });
        
        // Show underutilized members
        data.underutilized.forEach(member => {
            console.log(`${member.name} has capacity: ${member.utilization}%`);
        });
    });
```

### Accept Suggestion via API

```javascript
fetch('/api/resource-leveling/suggestions/456/accept/', {
    method: 'POST',
    headers: {'X-CSRFToken': csrfToken}
})
.then(response => response.json())
.then(data => {
    if (data.success) {
        alert(`Task reassigned to ${data.new_assignee}`);
    }
});
```

## Background Tasks (Optional but Recommended)

### Enable Celery Beat for Automatic Updates

Add to `kanban_board/celery.py`:

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    # Expire old suggestions every 6 hours
    'expire-old-suggestions': {
        'task': 'kanban.resource_leveling_tasks.expire_old_suggestions',
        'schedule': crontab(hour='*/6'),
    },
    
    # Update all profiles daily at 2 AM
    'daily-profile-update': {
        'task': 'kanban.resource_leveling_tasks.daily_profile_update',
        'schedule': crontab(hour='2', minute='0'),
    },
}
```

### Run Celery Workers

```bash
# Terminal 1: Start worker
celery -A kanban_board worker -l info

# Terminal 2: Start beat scheduler
celery -A kanban_board beat -l info
```

## How It Learns (No Training Required!)

The system automatically:

1. **Tracks completion times** - How long each person takes
2. **Builds skill profiles** - Extracts keywords from tasks they complete
3. **Calculates velocity** - Tasks per week
4. **Monitors workload** - Current task load and capacity
5. **Improves predictions** - Learns from actual outcomes

### Example Learning Process

1. **Week 1**: Bob completes 3 "API" tasks in 8 hours each
2. **System learns**: Bob's average = 8h, keywords include "API"
3. **Week 2**: New "API endpoint" task created
4. **AI suggests**: "Assign to Bob (high skill match: 85%)"
5. **User accepts**: Task assigned to Bob
6. **Bob completes in 7h**: System updates (Bob is faster than average!)
7. **Future tasks**: AI now predicts Bob will take 7h for similar work

## Scoring Algorithm

Each candidate is scored (0-100) based on:

- **30%** - Skill match (keyword overlap with past work)
- **25%** - Availability (free capacity)
- **20%** - Velocity (tasks completed per week)
- **15%** - Reliability (on-time completion rate)
- **10%** - Quality (average quality rating)

**Reassignment recommended when**: New assignee scores 15+ points higher

## Real-World Examples

### Example 1: Skill-Based Suggestion

```
Task: "Fix authentication bug in Django API"

Current: Alice (Backend: 45%, Util: 90%)
Suggested: Bob (Backend: 85%, Util: 60%)

Time savings: 70% (12h → 4h)
Confidence: 88%
Reasoning: Bob has better skill match (85% vs 45%), 
           and Alice is overloaded (90% utilization)
```

### Example 2: Workload Balancing

```
Task: "Write user documentation"

Current: Charlie (Writer: 60%, Util: 95%)
Suggested: Diana (Writer: 55%, Util: 40%)

Time savings: 20% (10h → 8h)
Confidence: 72%
Reasoning: Balance workload - Charlie is 95% utilized, 
           Diana has capacity
```

### Example 3: No Suggestion

```
Task: "Design new logo"

Current: Emma (Designer: 92%, Util: 70%)
Suggested: None

Confidence: N/A
Reasoning: Emma is the best match and not overloaded
```

## Troubleshooting

### "No suggestions generated"

**Problem**: Not enough historical data  
**Solution**: Complete a few tasks with assigned users, then run:

```bash
python manage.py shell
>>> from kanban.resource_leveling import ResourceLevelingService
>>> from kanban.models import Board
>>> board = Board.objects.first()
>>> service = ResourceLevelingService(board.organization)
>>> result = service.update_all_profiles(board)
>>> print(result)
```

### "Predictions seem inaccurate"

**Problem**: Profiles need updating  
**Solution**: Profiles auto-update daily. For immediate update:

```bash
python manage.py shell
>>> from kanban.resource_leveling_models import UserPerformanceProfile
>>> for profile in UserPerformanceProfile.objects.all():
...     profile.update_metrics()
```

### "Widget not showing"

**Problem**: Template not included  
**Solution**: Add to `board_detail.html`:

```django
{% include 'kanban/resource_leveling_widget.html' %}
```

## Testing Your Setup

### 1. Create Test Data

```python
from django.contrib.auth.models import User
from kanban.models import Board, Column, Task
from datetime import timedelta
from django.utils import timezone

# Get or create board
board = Board.objects.first()

# Create tasks completed by different users
for i, user in enumerate(board.members.all()[:3]):
    for j in range(5):
        task = Task.objects.create(
            title=f"Test task {i}-{j}",
            description="Testing resource leveling",
            column=board.columns.first(),
            assigned_to=user,
            completed_date=timezone.now() - timedelta(days=j),
            created_at=timezone.now() - timedelta(days=j+7)
        )
```

### 2. Update Profiles

```python
from kanban.resource_leveling import ResourceLevelingService

service = ResourceLevelingService(board.organization)
result = service.update_all_profiles(board)
print(f"Updated {result['updated']} profiles")
```

### 3. Generate Suggestions

```python
suggestions = service.get_board_optimization_suggestions(board)
for s in suggestions:
    print(f"{s.task.title}: {s.current_assignee} → {s.suggested_assignee}")
    print(f"  Savings: {s.time_savings_percentage}%")
    print(f"  Confidence: {s.confidence_score}%")
```

### 4. View in UI

Navigate to your board and you should see:
- Team workload summary
- AI suggestions (if any optimization opportunities exist)

## What's Next?

### Use it daily:
1. Create/update tasks as normal
2. Check AI suggestions regularly
3. Accept beneficial suggestions
4. System learns and improves automatically

### Monitor performance:
- Admin interface: `/admin/kanban/userperformanceprofile/`
- Track acceptance rate of suggestions
- Review prediction accuracy over time

### Customize (optional):
- Adjust scoring weights in `resource_leveling.py`
- Change target utilization (default: 75%)
- Modify suggestion expiry time (default: 48h)

## Support

For issues or questions:
1. Check logs: `logs/django.log`
2. Review admin interface for profile status
3. Ensure Celery workers are running (if using background tasks)

## Summary

You now have **AI-powered resource leveling** that:

✅ Automatically tracks team performance  
✅ Suggests optimal task assignments  
✅ Predicts completion times  
✅ Balances workload  
✅ Learns from outcomes  

**No ML training required!** The system works immediately with even small amounts of historical data and improves automatically over time.

Happy optimizing! 🚀
