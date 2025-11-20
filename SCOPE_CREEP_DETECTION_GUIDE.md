# Scope Creep Detection & Tracking

## Overview

The Scope Creep Detection feature helps project managers proactively identify and manage uncontrolled project scope increases. It uses AI-powered analysis to detect scope changes, predict timeline impacts, and provide actionable recommendations.

## Key Features

### 🎯 **Scope Baseline Management**
- Set baseline snapshots at project start or major milestones
- Track task count, complexity points, and priority distribution
- Compare current state against baseline at any time

### 📊 **Automated Scope Monitoring**
- Weekly automatic scope snapshots (configurable via Celery)
- Real-time scope metrics vs. baseline
- Historical trend analysis

### 🤖 **AI-Powered Analysis**
- Google Gemini analyzes scope changes and impact
- Identifies which tasks were added and why
- Estimates timeline delays caused by scope increase
- Provides specific, actionable recommendations

### ⚠️ **Smart Alerts**
- **Info Alert**: 5-15% scope increase
- **Warning Alert**: 15-30% scope increase  
- **Critical Alert**: >30% scope increase
- Alerts include predicted delay days and recommendations

### 📈 **Scope Velocity Tracking**
- Calculate rate of scope change (tasks/week)
- Identify trends: stable, increasing, rapidly increasing
- Early warning before scope spirals out of control

## Models

### `ScopeChangeSnapshot`
Captures board scope metrics at a point in time.

**Key Fields:**
- `total_tasks` - Total task count
- `total_complexity_points` - Sum of complexity scores
- `is_baseline` - Whether this is the baseline snapshot
- `scope_change_percentage` - % change from baseline
- `ai_analysis` - JSON with AI-generated analysis
- `predicted_delay_days` - Estimated timeline impact

### `ScopeCreepAlert`
Alerts when scope exceeds acceptable thresholds.

**Key Fields:**
- `severity` - info/warning/critical
- `status` - active/acknowledged/resolved/dismissed
- `scope_increase_percentage` - % increase in tasks
- `timeline_at_risk` - Boolean flag
- `recommendations` - JSON array of AI suggestions
- `predicted_delay_days` - Estimated delay

### `Board` Model Extensions
Added fields and methods to Board model:
- `baseline_task_count` - Baseline task count
- `baseline_complexity_total` - Baseline complexity
- `baseline_set_date` - When baseline was established
- `create_scope_snapshot()` - Create new snapshot
- `get_current_scope_status()` - Get current vs baseline
- `check_scope_creep_threshold()` - Check if alerts needed

## Usage

### 1. Set Up Demo Data with Baselines

```bash
# Populate demo data (includes baseline creation)
python manage.py populate_test_data
```

This automatically creates baseline snapshots for all demo boards:
- Software Project
- Marketing Campaign  
- Bug Tracking

### 2. Simulate Scope Creep (For Testing)

```bash
# Simulate scope creep on all demo boards (medium intensity)
python manage.py simulate_scope_creep

# Simulate on specific board
python manage.py simulate_scope_creep --board "Software Project"

# Control intensity (low=5-8 tasks, medium=10-15, high=20-30)
python manage.py simulate_scope_creep --intensity high
```

**What it does:**
- Adds new tasks to boards (realistic tasks based on board type)
- Increases complexity on some existing tasks
- Creates "before" and "after" snapshots
- Generates AI analysis and alerts if thresholds exceeded

### 3. Manual Baseline Creation (Python)

```python
from kanban.models import Board
from django.contrib.auth.models import User

board = Board.objects.get(name="My Project")
admin = User.objects.get(username="admin")

# Create baseline snapshot
snapshot = board.create_scope_snapshot(
    user=admin,
    snapshot_type='manual',
    is_baseline=True,
    notes='Project kickoff baseline'
)

print(f"Baseline created: {snapshot.total_tasks} tasks")
```

### 4. Check Current Scope Status

```python
# Get current scope vs baseline
status = board.get_current_scope_status()

if status:
    print(f"Baseline: {status['baseline_tasks']} tasks")
    print(f"Current: {status['current_tasks']} tasks")
    print(f"Change: {status['scope_change_percentage']:.1f}%")
    print(f"Tasks added: {status['tasks_added']}")
```

### 5. Create Regular Snapshots

```python
# Create scheduled snapshot (e.g., weekly via Celery)
snapshot = board.create_scope_snapshot(
    user=admin,
    snapshot_type='scheduled',
    notes='Weekly scope check'
)

# Automatically calculates changes from baseline
print(f"Scope change: {snapshot.scope_change_percentage}%")
```

### 6. Generate Alerts

```python
from kanban.utils.scope_analysis import create_scope_alert_if_needed

# Check if alert is needed based on snapshot
alert = create_scope_alert_if_needed(snapshot)

if alert:
    print(f"ALERT: {alert.get_severity_display()}")
    print(f"Scope increase: {alert.scope_increase_percentage}%")
    print(f"Predicted delay: {alert.predicted_delay_days} days")
    print(f"Recommendations: {alert.recommendations}")
```

### 7. View Scope Trends

```python
from kanban.utils.scope_analysis import get_scope_trend_data, calculate_scope_velocity

# Get 30-day trend
trend = get_scope_trend_data(board, days=30)
for point in trend:
    print(f"{point['date']}: {point['total_tasks']} tasks ({point['scope_change_pct']}%)")

# Calculate velocity
velocity = calculate_scope_velocity(board, weeks=4)
print(f"Average tasks added per week: {velocity['avg_tasks_added_per_week']}")
print(f"Trend: {velocity['trend']}")
```

## API Integration

### Create Snapshot via API (Add to api_views.py)

```python
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['POST'])
def create_scope_snapshot(request, board_id):
    board = Board.objects.get(id=board_id)
    
    snapshot = board.create_scope_snapshot(
        user=request.user,
        snapshot_type=request.data.get('snapshot_type', 'manual'),
        is_baseline=request.data.get('is_baseline', False),
        notes=request.data.get('notes', '')
    )
    
    return Response({
        'id': snapshot.id,
        'total_tasks': snapshot.total_tasks,
        'scope_change_percentage': snapshot.scope_change_percentage,
        'predicted_delay_days': snapshot.predicted_delay_days
    })
```

## Admin Interface

All scope tracking models are registered in Django Admin:

### ScopeChangeSnapshot Admin
- View all snapshots with filtering by board, date, baseline status
- See scope metrics and AI analysis
- Manage baselines

### ScopeCreepAlert Admin
- View all alerts with filtering by severity, status
- Bulk acknowledge or resolve alerts
- View AI recommendations and predicted delays
- Track alert lifecycle

**Admin Actions:**
- Mark alerts as acknowledged
- Mark alerts as resolved
- Filter by board, severity, status

## Celery Task (Automated Snapshots)

Create a periodic task for automated scope monitoring:

```python
# kanban/tasks.py
from celery import shared_task
from kanban.models import Board
from kanban.utils.scope_analysis import create_scope_alert_if_needed

@shared_task
def weekly_scope_check():
    """Run weekly scope analysis on all active boards"""
    boards = Board.objects.all()
    
    for board in boards:
        if not board.baseline_task_count:
            continue  # Skip boards without baseline
        
        # Create snapshot
        snapshot = board.create_scope_snapshot(
            snapshot_type='scheduled',
            notes='Automated weekly scope check'
        )
        
        # Create alert if needed
        alert = create_scope_alert_if_needed(snapshot)
        
        if alert:
            # Send notifications, etc.
            pass

# In celery.py or settings.py, schedule the task:
from celery.schedules import crontab

app.conf.beat_schedule = {
    'weekly-scope-check': {
        'task': 'kanban.tasks.weekly_scope_check',
        'schedule': crontab(day_of_week=1, hour=9, minute=0),  # Every Monday at 9 AM
    },
}
```

## UI Integration Ideas

### 1. Dashboard Widget
```html
<div class="scope-status-widget">
    <h3>Scope Status</h3>
    <div class="metric">
        <span class="value">+{{ scope_status.scope_change_percentage }}%</span>
        <span class="label">Scope Change</span>
    </div>
    <div class="metric">
        <span class="value">{{ scope_status.tasks_added }}</span>
        <span class="label">Tasks Added</span>
    </div>
    {% if scope_alert %}
    <div class="alert alert-{{ scope_alert.severity }}">
        ⚠️ {{ scope_alert.get_severity_display }}
        <br>Predicted delay: {{ scope_alert.predicted_delay_days }} days
    </div>
    {% endif %}
</div>
```

### 2. Board Header Indicator
```html
{% if board.get_current_scope_status %}
    {% with status=board.get_current_scope_status %}
    <span class="scope-indicator" 
          data-scope-change="{{ status.scope_change_percentage }}"
          title="Scope: {{ status.scope_change_percentage|floatformat:1 }}% vs baseline">
        📊 Scope: {{ status.scope_change_percentage|floatformat:1 }}%
    </span>
    {% endwith %}
{% endif %}
```

### 3. Scope Trend Chart
Use Chart.js to visualize scope changes over time:
```javascript
const trendData = {{ scope_trend|safe }};
new Chart(ctx, {
    type: 'line',
    data: {
        labels: trendData.map(d => d.date),
        datasets: [{
            label: 'Total Tasks',
            data: trendData.map(d => d.total_tasks),
            borderColor: 'rgb(75, 192, 192)',
        }]
    }
});
```

## Testing

```bash
# Run tests
python manage.py test kanban.tests.test_scope_tracking

# Manual testing workflow:
1. python manage.py populate_test_data  # Creates baselines
2. python manage.py simulate_scope_creep --intensity medium
3. Check admin for alerts
4. View snapshots and AI analysis
```

## Configuration

### Threshold Settings
Modify in `Board.check_scope_creep_threshold()`:
```python
def check_scope_creep_threshold(
    self, 
    warning_threshold=15,    # Warning at 15% increase
    critical_threshold=30    # Critical at 30% increase
):
```

### AI Model
Change in `kanban/utils/scope_analysis.py`:
```python
# Line ~86
model = genai.GenerativeModel('gemini-pro')  # Or 'gemini-1.5-pro'
```

## Benefits

### For Project Managers
- **Early Warning**: Detect scope creep before it becomes critical
- **Data-Driven**: Make decisions based on metrics, not gut feeling
- **Stakeholder Communication**: Show evidence of scope changes
- **Timeline Accuracy**: Better deadline predictions

### For Teams
- **Transparency**: Everyone sees scope changes
- **Prioritization**: AI helps identify what to cut or defer
- **Workload Management**: Understand capacity impact

### Competitive Advantage
**No other PM tool has this feature:**
- Asana: No automated scope tracking
- Monday.com: No AI-powered scope analysis
- Jira: No built-in scope creep detection
- MS Project: Manual tracking only

## Future Enhancements

1. **Scope Velocity Dashboard**: Visual trends and forecasting
2. **Slack/Teams Integration**: Real-time alerts
3. **Automatic Scope Freezes**: Block new tasks when threshold exceeded
4. **Scope Change Requests**: Formal approval workflow
5. **Historical Comparison**: Compare to similar past projects
6. **Budget Impact**: Link scope changes to cost increases

## Troubleshooting

### No baseline found
```python
# Check if baseline exists
board = Board.objects.get(name="My Project")
baseline = board.scope_snapshots.filter(is_baseline=True).first()

if not baseline:
    # Create one
    board.create_scope_snapshot(user=admin, is_baseline=True)
```

### AI analysis failing
The system automatically falls back to rule-based analysis if Gemini API fails.

Check `ai_analysis` field for `'analysis_type': 'rule_based'` to confirm.

### Alerts not generating
```python
# Manual alert check
from kanban.utils.scope_analysis import create_scope_alert_if_needed

snapshot = board.scope_snapshots.latest('snapshot_date')
alert = create_scope_alert_if_needed(snapshot)
```

## Support

For issues or questions:
1. Check Django Admin for scope data
2. Review `ScopeChangeSnapshot` records
3. Check `ai_analysis` JSON field for details
4. Review `ScopeCreepAlert` for recommendations

---

**Status**: ✅ **Production Ready**

All models, migrations, admin interfaces, management commands, and utility functions are implemented and tested.
