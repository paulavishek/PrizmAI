# Stakeholder Engagement Tracking Integration Guide

## Overview

This document describes the integration of **Stakeholder Engagement Tracking** features into PrizmAI, adapted from the Stakeholder Management project. The integration provides simple yet powerful stakeholder tagging, involvement tracking, and engagement metrics.

## Features

### 1. **Project Stakeholders** (Simple Tagging)
- Add stakeholders to projects (Boards)
- Track stakeholder information (name, role, organization, contact details)
- Analyze stakeholders using Power/Interest matrix (influence + interest levels)
- Set current and desired engagement levels
- Categorize into quadrants: "Manage Closely", "Keep Satisfied", "Keep Informed", "Monitor"

### 2. **Stakeholder Involvement Tracking**
- Track each stakeholder's involvement in specific tasks
- Define involvement types: Owner, Contributor, Reviewer, Stakeholder, Beneficiary, Impacted
- Record satisfaction ratings for task outcomes
- Capture feedback and concerns from stakeholders
- Track engagement frequency and timestamps

### 3. **Engagement Records**
- Log detailed engagement activities (meetings, emails, phone calls, presentations, surveys)
- Track communication channels and engagement outcomes
- Record stakeholder sentiment and satisfaction ratings
- Manage follow-ups and track completion
- Maintain complete audit trail of all stakeholder interactions

### 4. **Engagement Metrics Dashboard**
- View quadrant distribution (Power/Interest matrix visualization)
- Monitor engagement level distribution across stakeholders
- Track engagement frequency and average satisfaction ratings
- Identify stakeholders with engagement gaps
- Generate recommendations for increasing engagement

## File Structure

### Models
- **ProjectStakeholder**: Main stakeholder model linked to Board
- **StakeholderTaskInvolvement**: Junction model for stakeholder involvement in tasks
- **StakeholderEngagementRecord**: Detailed engagement event logging
- **EngagementMetrics**: Aggregated metrics for dashboard display
- **StakeholderTag**: Tags for organizing stakeholders
- **ProjectStakeholderTag**: Through model for stakeholder-tag relationship

### Views
All views in `kanban/stakeholder_views.py`:
- `stakeholder_list`: Display all stakeholders for a board
- `stakeholder_create/update/delete`: CRUD operations for stakeholders
- `stakeholder_detail`: View detailed stakeholder profile with engagement history
- `engagement_record_create`: Log stakeholder engagement activities
- `task_stakeholder_involvement`: Manage stakeholder involvement in tasks
- `engagement_metrics_dashboard`: View engagement metrics and analytics
- `engagement_analytics`: Detailed analytics over time periods
- `stakeholder_api_data`: API endpoint for chart data

### Forms
All forms in `kanban/stakeholder_forms.py`:
- `ProjectStakeholderForm`: Create/update stakeholder information
- `StakeholderTaskInvolvementForm`: Record task involvement
- `StakeholderEngagementRecordForm`: Log engagement activities
- `StakeholderTagForm`: Create tags for stakeholders
- `BulkStakeholderImportForm`: Batch import from CSV

### Templates
- `stakeholder_list.html`: Stakeholder listing with filters
- `stakeholder_form.html`: Create/edit stakeholder form with guidance
- `stakeholder_detail.html`: Comprehensive stakeholder profile page
- `engagement_record_form.html`: Log engagement activities
- `engagement_metrics_dashboard.html`: Metrics and analytics dashboard
- `task_stakeholder_involvement.html`: Manage task stakeholder roles
- `engagement_analytics.html`: Detailed engagement analytics

### URLs
Routes in `kanban/stakeholder_urls.py`:
```
/stakeholder/boards/<board_id>/stakeholders/                    # List stakeholders
/stakeholder/boards/<board_id>/stakeholders/create/             # Create stakeholder
/stakeholder/boards/<board_id>/stakeholders/<pk>/               # View stakeholder details
/stakeholder/boards/<board_id>/stakeholders/<pk>/update/        # Edit stakeholder
/stakeholder/boards/<board_id>/stakeholders/<pk>/delete/        # Delete stakeholder
/stakeholder/boards/<board_id>/stakeholders/<pk>/engagement/create/  # Log engagement
/stakeholder/boards/<board_id>/engagement-metrics/              # Metrics dashboard
/stakeholder/boards/<board_id>/engagement-analytics/            # Analytics
```

## Database Models

### ProjectStakeholder
```python
- name: CharField (100)
- role: CharField (100)
- organization: CharField (100, blank)
- email: EmailField (blank)
- phone: CharField (20, blank)
- board: ForeignKey(Board)
- influence_level: Choice(low, medium, high) - default: medium
- interest_level: Choice(low, medium, high) - default: medium
- current_engagement: Choice(inform, consult, involve, collaborate, empower) - default: inform
- desired_engagement: Choice(inform, consult, involve, collaborate, empower) - default: involve
- notes: TextField (blank)
- is_active: BooleanField - default: True
- created_by: ForeignKey(User)
- created_at, updated_at: DateTimeField
```

### StakeholderTaskInvolvement
```python
- stakeholder: ForeignKey(ProjectStakeholder)
- task: ForeignKey(Task)
- involvement_type: Choice(owner, contributor, reviewer, stakeholder, beneficiary, impacted)
- engagement_status: Choice(not_engaged, informed, consulted, involved, collaborated, satisfied)
- engagement_count: IntegerField - default: 0
- last_engagement: DateTimeField (nullable)
- satisfaction_rating: IntegerField (1-5, nullable)
- feedback: TextField (blank)
- concerns: TextField (blank)
- metadata: JSONField (blank)
- created_at, updated_at: DateTimeField
```

### StakeholderEngagementRecord
```python
- stakeholder: ForeignKey(ProjectStakeholder)
- task: ForeignKey(Task, nullable)
- date: DateField - default: today
- description: TextField
- communication_channel: Choice(email, phone, meeting, video, chat, presentation, survey, other)
- outcome: TextField (blank)
- follow_up_required: BooleanField - default: False
- follow_up_date: DateField (nullable)
- follow_up_completed: BooleanField - default: False
- engagement_sentiment: Choice(positive, neutral, negative) - default: neutral
- satisfaction_rating: IntegerField (1-5, nullable)
- created_by: ForeignKey(User)
- created_at: DateTimeField
- notes: TextField (blank)
```

### EngagementMetrics
```python
- board: ForeignKey(Board)
- stakeholder: OneToOneField(ProjectStakeholder)
- total_engagements: IntegerField
- engagements_this_month: IntegerField
- engagements_this_quarter: IntegerField
- average_engagements_per_month: DecimalField
- primary_channel: CharField (20, blank)
- channels_used: JSONField (list of channel/count pairs)
- average_satisfaction: DecimalField (1-5 range)
- positive_engagements_count: IntegerField
- negative_engagements_count: IntegerField
- days_since_last_engagement: IntegerField
- pending_follow_ups: IntegerField
- engagement_gap: IntegerField
- period_start, period_end: DateField
- calculated_at: DateTimeField (auto_now)
```

## Utility Functions

### `calculate_engagement_metrics(board)`
Calculates metrics for all stakeholders in a board over the last 30 days. Can be called periodically (e.g., daily via management command or Celery task).

### `update_stakeholder_engagement(stakeholder, task=None)`
Updates stakeholder engagement status based on recent activities.

### `get_stakeholder_summary(board)`
Returns summary statistics including total stakeholders, engagement counts, quadrant distribution, and average satisfaction.

### `identify_at_risk_stakeholders(board, days=30)`
Identifies stakeholders who haven't been engaged recently and may need attention.

### `get_engagement_recommendations(stakeholder)`
Generates recommendations for improving engagement with a specific stakeholder based on their profile and history.

## Engagement Strategy Levels

The integration uses a 5-level engagement strategy framework:

1. **Inform** - Provide information to help stakeholders understand issues and decisions
2. **Consult** - Obtain feedback and input from stakeholders
3. **Involve** - Work with stakeholders to ensure their concerns are understood
4. **Collaborate** - Partner with stakeholders in decision-making process
5. **Empower** - Place decision-making authority in stakeholders' hands

## Power/Interest Matrix

Stakeholders are categorized into four quadrants based on influence and interest levels:

| Quadrant | Influence | Interest | Strategy |
|----------|-----------|----------|----------|
| Manage Closely | High | High | Active engagement and collaboration |
| Keep Satisfied | High | Low | Keep satisfied with periodic updates |
| Keep Informed | Low | High | Keep informed and involved |
| Monitor | Low | Low | Monitor with minimal effort |

## Setup Instructions

### 1. Run Migrations
```bash
python manage.py migrate kanban
```

This creates all stakeholder-related tables.

### 2. Update URLs
The `kanban_board/urls.py` has been updated to include stakeholder URLs:
```python
path('stakeholder/', include('kanban.stakeholder_urls')),
```

### 3. Calculate Initial Metrics
```bash
python manage.py calculate_stakeholder_metrics
```

This command calculates engagement metrics for all boards.

## Usage Guide

### Adding Stakeholders to a Project

1. Navigate to project board
2. Click "Manage Stakeholders" or go to `/stakeholder/boards/<board_id>/stakeholders/`
3. Click "Add Stakeholder"
4. Fill in stakeholder information:
   - Name, Role, Organization
   - Contact details (Email, Phone)
   - Influence level (Low/Medium/High)
   - Interest level (Low/Medium/High)
   - Current engagement strategy
   - Desired engagement strategy
5. Submit form

### Recording Engagement

1. On stakeholder detail page, click "Record Engagement"
2. Enter engagement details:
   - Date of engagement
   - Communication channel (Email, Phone, Meeting, etc.)
   - Description of what was discussed
   - Outcome and any decisions made
   - Stakeholder sentiment (Positive/Neutral/Negative)
   - Satisfaction rating (1-5)
   - Whether follow-up is needed and when
3. Submit form

### Linking Stakeholders to Tasks

1. On task detail page, go to "Stakeholders" section
2. Add stakeholders with their role:
   - Task Owner, Contributor, Reviewer, Stakeholder, Beneficiary, or Impacted
3. Update involvement status and satisfaction as work progresses

### Viewing Engagement Metrics

1. Navigate to `/stakeholder/boards/<board_id>/engagement-metrics/`
2. View dashboard with:
   - Power/Interest quadrant distribution
   - Engagement level breakdown
   - Stakeholder metrics table
3. Click individual stakeholder names to drill into details

## API Endpoints

### Get Stakeholder Data for Charts
```
GET /stakeholder/api/boards/<board_id>/stakeholders-data/
```

Returns JSON with stakeholder positions on Power/Interest matrix and engagement distribution.

## Recommended Workflows

### Weekly Stakeholder Check-in
1. Review "Manage Closely" quadrant stakeholders
2. Schedule engagement activities (meetings, calls, updates)
3. Log engagement records with outcome and sentiment
4. Update task involvement as work progresses

### Monthly Metrics Review
1. Run `python manage.py calculate_stakeholder_metrics`
2. Review engagement metrics dashboard
3. Identify stakeholders with growing gaps
4. Plan engagement improvement activities
5. Review satisfaction trends

### Project Planning
1. Identify all stakeholders during project setup
2. Map to Power/Interest matrix
3. Define engagement strategies per stakeholder
4. Plan engagement activities based on quadrant
5. Assign task involvement roles

## Integration Points

### With Kanban Board
- Stakeholders linked to Board level
- Task-stakeholder involvement tracked for individual tasks
- Stakeholder information visible when viewing tasks

### With AI Risk Management
- Can extend Task model to include stakeholder risk analysis
- Stakeholder engagement status can inform risk assessments
- Communication of risks to stakeholders can be logged

### With Resource Management
- Stakeholder involvement can inform resource allocation
- Engagement status affects project communication needs

## Best Practices

1. **Regular Updates**: Log engagement activities within 24 hours while fresh
2. **Satisfaction Tracking**: Always rate satisfaction after stakeholder interactions
3. **Follow-ups**: Set follow-up dates and ensure they're completed
4. **Gap Management**: Proactively increase engagement for stakeholders with gaps
5. **Documentation**: Use notes field to capture important context
6. **Quadrant Review**: Periodically review and update stakeholder quadrant positions
7. **Channel Preference**: Note preferred communication channels for each stakeholder
8. **Sentiment Tracking**: Monitor sentiment trends to catch issues early

## Troubleshooting

### Stakeholders Not Appearing
- Ensure stakeholder `is_active` is True
- Check board membership for current user
- Verify stakeholder is assigned to correct board

### Metrics Not Calculating
- Run `python manage.py calculate_stakeholder_metrics --board_id=<board_id>`
- Check for database errors in Django logs
- Ensure EngagementMetrics records are being created

### Engagement Records Not Linking to Tasks
- Ensure task exists in correct board
- Task should be optional (nullable) for general engagement records
- Unrelated engagement activities don't require task linkage

## Future Enhancements

Potential additions to the stakeholder management system:

1. **Automated Engagement Reminders**: Notify project managers when stakeholder engagement is overdue
2. **Communication Templates**: Pre-built templates for different engagement types
3. **Stakeholder Segments**: Group similar stakeholders for batch communications
4. **Engagement Timeline View**: Calendar view of planned and logged engagements
5. **Stakeholder Health Scores**: Automated calculation of engagement health
6. **Export Reports**: Generate PDF/Excel reports of stakeholder engagement
7. **Historical Analysis**: Track how stakeholder sentiment changes over project lifecycle
8. **Integration with Email**: Log email communications automatically
9. **Mobile App**: Record engagement on-the-go
10. **Notifications**: Alert team when stakeholder sentiment becomes negative

## Support & Questions

For issues or questions about the stakeholder engagement tracking integration, refer to:
- Task model documentation in `kanban/models.py`
- Template examples in `templates/kanban/`
- Utility functions in `kanban/stakeholder_utils.py`
