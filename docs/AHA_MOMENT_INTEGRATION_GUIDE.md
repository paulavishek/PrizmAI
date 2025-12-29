"""
Aha Moment Detection - Integration Guide
=======================================

This guide shows how to integrate aha moment detection into existing views.

## Server-Side Detection

Import and use the helper function in your views:

```python
from kanban.demo_views import trigger_aha_moment_server_side

@login_required
def board_analytics(request, board_id):
    # ... existing view logic ...
    
    # Trigger aha moment when user views burndown chart
    if request.session.get('is_demo_mode'):
        trigger_aha_moment_server_side(
            request, 
            'burndown_viewed',
            {'board_id': board_id}
        )
    
    return render(request, 'kanban/board_analytics.html', context)
```

## Aha Moment Types

### 1. AI Suggestion Accepted
**Trigger:** User accepts an AI-generated suggestion
**Detection:** Client-side (aha_moment_detection.js)
**Auto-tracked:** Yes, watches for `.accept-ai-suggestion` clicks

### 2. Burndown Viewed
**Trigger:** User views analytics/burndown chart for 10+ seconds
**Detection:** Client-side timer
**Auto-tracked:** Yes, on analytics pages

### 3. RBAC Workflow
**Trigger:** User switches roles or explores permissions
**Detection:** Client-side, watches role switching buttons
**Auto-tracked:** Yes
**Server-side option:** Call when accessing permission-related pages

### 4. Time Tracking Used
**Trigger:** User starts/stops timer or logs time manually
**Detection:** Client-side, watches timer buttons and time inputs
**Auto-tracked:** Yes

### 5. Dependency Created
**Trigger:** User creates a task dependency
**Detection:** Both client and server-side
**Server-side:** Call in task creation/update views:

```python
if 'depends_on' in request.POST and request.POST['depends_on']:
    trigger_aha_moment_server_side(request, 'dependency_created')
```

### 6. Gantt Viewed
**Trigger:** User views Gantt chart for 3+ seconds
**Detection:** Client-side timer
**Auto-tracked:** Yes, on Gantt pages

### 7. Skill Gap Viewed
**Trigger:** User views skill gap analysis for 5+ seconds
**Detection:** Client-side timer
**Auto-tracked:** Yes, on skill gap pages

### 8. Conflict Detected
**Trigger:** User views conflict resolution feature
**Detection:** Client-side, watches conflict-related elements
**Auto-tracked:** Yes

## Manual Triggering

### From JavaScript:
```javascript
// Trigger an aha moment manually
showAhaMoment('ai_suggestion_accepted', {
    custom_data: 'value'
});
```

### From Django View:
```python
from kanban.demo_views import trigger_aha_moment_server_side

trigger_aha_moment_server_side(request, 'moment_type', {
    'additional': 'data'
})
```

## Integration Checklist

- [x] Aha moment celebration component created
- [x] Client-side detection script created
- [x] Server-side helper functions created
- [x] Event tracking endpoint configured
- [x] Demo dashboard integrated
- [x] Demo board detail integrated
- [ ] Board analytics view enhanced (optional)
- [ ] Task detail view enhanced (optional)
- [ ] Gantt chart view enhanced (optional)
- [ ] Skill gap view enhanced (optional)

## Testing Aha Moments

1. Start demo mode: http://localhost:8000/demo/start/
2. Select Solo or Team mode
3. Navigate to different pages:
   - Analytics page (wait 10 seconds for burndown aha moment)
   - Gantt chart (wait 3 seconds)
   - Skill gap analysis (wait 5 seconds)
4. Interact with features:
   - Accept AI suggestion
   - Start/stop time tracker
   - Create task dependency
   - Switch roles (Team mode)
5. Check console for detection logs
6. Verify celebration appears only once per moment type

## Customization

### Add New Aha Moment:

1. Add definition to `aha_moment_celebration.html`:
```javascript
const AHA_MOMENTS = {
    new_moment_type: {
        icon: '🎉',
        title: 'New Feature Discovered!',
        description: 'You found something awesome!',
        cta: 'Learn More',
        ctaUrl: '#details'
    }
};
```

2. Add detection in `aha_moment_detection.js`:
```javascript
function detectNewMoment() {
    // Detection logic
    if (conditionMet) {
        showAhaMoment('new_moment_type', {
            custom_data: 'value'
        });
    }
}
```

3. Call from server-side (optional):
```python
trigger_aha_moment_server_side(request, 'new_moment_type')
```

## Analytics

All aha moments are tracked in:
- DemoAnalytics model (event_type='aha_moment')
- DemoSession.aha_moments (count)
- DemoSession.aha_moments_list (list of types)
- Session variable: request.session['aha_moments']

Query aha moments:
```python
from analytics.models import DemoAnalytics

aha_events = DemoAnalytics.objects.filter(
    event_type='aha_moment',
    session_id=session_id
)
```
"""
