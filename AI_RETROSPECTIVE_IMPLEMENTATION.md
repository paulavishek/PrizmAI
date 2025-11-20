# AI-Powered Retrospective Generator - Implementation Guide

## Overview

The AI-Powered Retrospective Generator is a comprehensive feature that automatically analyzes project/sprint data and generates insightful retrospectives using Google Gemini AI. It helps teams capture organizational learning, track improvements over time, and foster continuous improvement.

## Features Implemented

### 1. **Automated Retrospective Generation**
- Analyzes tasks, metrics, and team performance for any date range
- AI generates insights on what went well, what needs improvement, and lessons learned
- Creates actionable recommendations with priority levels
- Sentiment analysis and team morale indicators

### 2. **Lessons Learned Tracking**
- Categorized lessons (process, technical, communication, etc.)
- Priority-based action tracking (critical, high, medium, low)
- Status tracking (identified → planned → in progress → implemented → validated)
- Recurring issue detection across multiple retrospectives
- AI confidence scores for each lesson

### 3. **Improvement Metrics**
- Track key performance indicators over time
- Automatic trend analysis (improving/stable/declining)
- Comparison with previous retrospectives
- Visual representation of progress

### 4. **Action Items Management**
- Generate actionable items from AI recommendations
- Assign ownership and set target dates
- Progress tracking with percentage completion
- Blocking status and resolution tracking
- Link to related tasks and lessons

### 5. **Trend Analysis Dashboard**
- Aggregated view of improvements across retrospectives
- Implementation and completion rates
- Recurring issues identification
- Velocity and quality trends
- Top improvement categories

## Architecture

### Models (`kanban/retrospective_models.py`)

1. **ProjectRetrospective**
   - Main retrospective entity
   - Stores AI-generated analysis, metrics snapshot, and team notes
   - Links to previous retrospectives for trend comparison

2. **LessonLearned**
   - Individual lessons from retrospectives
   - Tracks implementation status and impact
   - Detects recurring patterns

3. **ImprovementMetric**
   - Quantitative metrics tracked over time
   - Automatic change calculation and trend determination

4. **RetrospectiveActionItem**
   - Actionable tasks from retrospectives
   - Integrated with project management workflow
   - Progress and impact tracking

5. **RetrospectiveTrend**
   - Aggregated trends across multiple retrospectives
   - Organizational learning analytics

### AI Generator (`kanban/utils/retrospective_generator.py`)

The `RetrospectiveGenerator` class handles:
- **Metrics Collection**: Gathers comprehensive project data
  - Task completion rates, velocity, complexity
  - Quality indicators, risk factors
  - Team activity and collaboration metrics
  - Scope creep and timeline data

- **Pattern Analysis**: Identifies success patterns and challenges
  - High performers and bottlenecks
  - Recurring issues
  - Completion trends

- **AI Insights Generation**: Uses Gemini AI to:
  - Analyze collected data
  - Generate natural language insights
  - Create structured recommendations
  - Assess sentiment and morale

- **Auto-creation**: Automatically creates:
  - Lesson learned records
  - Action items with priorities
  - Improvement metrics for tracking

### Views (`kanban/retrospective_views.py`)

Key views:
- `retrospective_list`: Browse all retrospectives
- `retrospective_create`: Generate new AI retrospective
- `retrospective_detail`: View full retrospective analysis
- `retrospective_dashboard`: Improvement trends dashboard
- `retrospective_finalize`: Lock and finalize retrospective
- `lessons_learned_list`: Browse and filter all lessons
- Status update APIs for lessons and actions

### URLs (`kanban/retrospective_urls.py`)

All retrospective URLs are namespaced under `/board/<board_id>/retrospectives/`

## Usage

### 1. Generate a Retrospective

```python
from kanban.utils.retrospective_generator import RetrospectiveGenerator
from datetime import date, timedelta

# Define period
period_end = date.today()
period_start = period_end - timedelta(days=14)  # 2 weeks

# Generate retrospective
generator = RetrospectiveGenerator(board, period_start, period_end)
retrospective = generator.create_retrospective(
    created_by=user,
    retrospective_type='sprint'
)
```

### 2. Via Web Interface

1. Navigate to Board → Retrospectives
2. Click "Generate New Retrospective"
3. Select date range and type
4. AI analyzes data (10-30 seconds)
5. Review generated insights
6. Add team notes and finalize

### 3. View Dashboard

Access `/board/<board_id>/retrospectives/dashboard/` to see:
- Implementation rates
- Completion rates
- Recurring issues
- Velocity and quality trends
- Recent retrospectives

## Database Migration

Run migrations to create the new tables:

```bash
python manage.py makemigrations kanban
python manage.py migrate
```

This creates 5 new tables:
- `kanban_projectretrospective`
- `kanban_lessonlearned`
- `kanban_improvementmetric`
- `kanban_retrospectiveactionitem`
- `kanban_retrospectivetrend`

## Admin Interface

All retrospective models are registered in Django admin with:
- List filters and search
- Custom actions (finalize, mark implemented, etc.)
- Readonly fields for AI metadata
- Inline editing where appropriate

Access: `/admin/kanban/`

## AI Model Configuration

The feature uses Google Gemini AI (configured in settings):
- Model: `gemini-2.0-flash-exp` (default, configurable)
- Task complexity routing: Complex analysis uses advanced model
- System prompt: Expert agile coach persona
- Temperature: 0.7 for balanced creativity
- Stateless mode: No session persistence to control costs

## API Endpoints

### Update Lesson Status
```javascript
POST /board/<board_id>/lessons/<lesson_id>/status/
{
    "status": "implemented"
}
```

### Update Action Status
```javascript
POST /board/<board_id>/actions/<action_id>/status/
{
    "status": "completed",
    "progress": 100
}
```

## Templates

Created templates:
- `retrospective_list.html`: List view with filters
- `retrospective_create.html`: Generation form
- `retrospective_detail.html`: Full retrospective view
- `retrospective_dashboard.html`: Trends dashboard
- `lessons_learned_list.html`: All lessons with filters

## Integration Points

### With Existing Features

1. **Burndown Predictions**: Uses velocity data for insights
2. **Scope Tracking**: Analyzes scope creep in retrospectives
3. **Task Analytics**: Pulls completion data and metrics
4. **Team Velocity**: Integrates velocity snapshots
5. **Risk Management**: References risk assessments

### Navigation Integration

Add to board detail template:
```html
<a href="{% url 'retrospective_dashboard' board.id %}" class="btn btn-info">
    <i class="fas fa-history"></i> Retrospectives
</a>
```

## Best Practices

1. **Regular Cadence**: Generate retrospectives every 1-2 weeks
2. **Meaningful Periods**: Align with sprint/milestone dates
3. **Review & Finalize**: Add team notes before finalizing
4. **Action Ownership**: Assign owners to action items
5. **Track Progress**: Update lesson and action statuses regularly
6. **Monitor Trends**: Use dashboard to track improvement rates

## Performance Considerations

- AI generation takes 10-30 seconds depending on data volume
- Use background tasks for large retrospectives (optional enhancement)
- Metrics collection is optimized with select_related/prefetch_related
- Dashboard queries are cached where appropriate

## Future Enhancements

Potential improvements:
1. Export to PDF format
2. Email notifications for action items
3. Integration with calendar for scheduled generation
4. Comparison view between retrospectives
5. Team voting on lessons and actions
6. Advanced analytics with charts
7. AI-powered action item suggestions based on lessons

## Testing

Test the feature:
```bash
# Create test retrospective
python manage.py shell
from kanban.models import Board
from kanban.utils.retrospective_generator import RetrospectiveGenerator
from datetime import date, timedelta

board = Board.objects.first()
period_end = date.today()
period_start = period_end - timedelta(days=14)

generator = RetrospectiveGenerator(board, period_start, period_end)
retro = generator.create_retrospective(board.created_by, 'sprint')
print(f"Created retrospective: {retro.id}")
```

## Troubleshooting

### AI Generation Fails
- Check GEMINI_API_KEY in settings
- Verify google-generativeai package is installed
- Check API quota limits
- Review logs for detailed errors

### No Metrics Displayed
- Ensure tasks have completion dates
- Verify date range includes task data
- Check velocity snapshots exist

### Permissions Issues
- Verify user is board member or owner
- Check BoardMembership records

## Credits

Implemented as part of PrizmAI's continuous improvement features.
Uses Google Gemini AI for natural language analysis and insights generation.
