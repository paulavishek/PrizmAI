# PrizmAI Demo Data Guide

## Overview

The updated demo data script (`kanban/management/commands/populate_test_data.py`) now includes comprehensive sample data for all advanced features in PrizmAI including risk management, resource management, stakeholder engagement, and requirements management.

## Running the Demo Data Setup

### Reset and Repopulate Database

If you want to start fresh with demo data:

```bash
# Remove existing database (optional, only if you want a clean slate)
rm db.sqlite3

# Run migrations
python manage.py migrate

# Populate with demo data
python manage.py populate_test_data
```

### Add to Existing Database

If you already have a database and want to add more demo data:

```bash
python manage.py populate_test_data
```

The script is idempotent and won't duplicate existing data.

## Demo Data Features

### 1. 🛡️ Risk Management

The demo data includes risk assessments on approximately 70% of tasks with:

- **Risk Likelihood**: Low (1), Medium (2), High (3)
- **Risk Impact**: Low (1), Medium (2), High (3)
- **Risk Score**: Calculated as Likelihood × Impact (range 1-9)
- **Risk Level**: Auto-classified as Low/Medium/High/Critical
- **Risk Indicators**: Key metrics to monitor (e.g., "Monitor task progress weekly")
- **Mitigation Suggestions**: AI-generated strategies with timeline and effectiveness
- **Risk Analysis**: Detailed factors and reasoning

**Example Tasks with Risk Data:**
- "Login page not working on Safari" - Critical risk
- "Setup authentication middleware" - High risk
- "Inconsistent data in reports" - High risk

### 2. 📦 Resource Management

Resource forecasting and capacity management for team members:

- **Resource Demand Forecasts**: Predicted workload and availability for each team member
  - Period: Next 4 weeks
  - Predicted workload hours: 120-160 hours
  - Available capacity: 160 hours
  - Confidence scores: 70-95%

- **Team Capacity Alerts**: Alerts when team members are overloaded
  - Alert levels: Warning (80-100% capacity) / Critical (>100%)
  - Shows utilization percentage

- **Workload Distribution Recommendations**: AI suggestions for optimal distribution
  - Recommendation types: Distribute, Reassign, Defer
  - Expected capacity savings: 10-30 hours per recommendation
  - Confidence scores: 60-90%

**Sample Data:**
- Forecasts for John Doe and Robert Johnson on multiple boards
- Capacity alerts when workload exceeds availability
- Distribution recommendations for task optimization

### 3. 👥 Stakeholder Management

Complete stakeholder engagement tracking with 5 sample stakeholders:

#### Stakeholders Created:

1. **Sarah Mitchell** - Product Manager
   - Influence: High | Interest: High
   - Current: Collaborate | Desired: Empower
   - Quadrant: "Manage Closely"

2. **Michael Chen** - Tech Lead
   - Influence: High | Interest: High
   - Current: Involve | Desired: Collaborate
   - Quadrant: "Manage Closely"

3. **Emily Rodriguez** - QA Lead
   - Influence: Medium | Interest: High
   - Current: Consult | Desired: Involve
   - Quadrant: "Keep Informed"

4. **David Park** - DevOps Engineer
   - Influence: Medium | Interest: Medium
   - Current: Inform | Desired: Involve
   - Quadrant: "Monitor"

5. **Lisa Thompson** - UX Designer
   - Influence: Medium | Interest: High
   - Current: Involve | Desired: Collaborate
   - Quadrant: "Keep Informed"

#### Stakeholder Features Included:

- **Stakeholder Tags**: 5 tags for categorization
  - Key Stakeholder
  - Executive
  - Technical
  - Quality Focus
  - Design Focus

- **Task Involvement**: Each stakeholder involved in multiple tasks
  - Involvement types: Owner, Contributor, Reviewer, Stakeholder
  - Engagement status: Informed, Consulted, Involved
  - Satisfaction ratings: 3-5 scale

- **Engagement Records**: 2-4 engagement events per stakeholder
  - Communication channels: Email, Phone, Meeting, Video
  - Dates: Spread over past 30 days
  - Sentiment tracking: Positive/Neutral

- **Engagement Metrics**: Aggregated metrics for dashboard
  - Total engagements per stakeholder
  - Average satisfaction ratings
  - Engagement gaps (current vs. desired)
  - Days since last engagement

### 4. 📋 Requirements Management - Task Dependencies

Task dependency and hierarchy support with:

- **Parent-Child Relationships**: Task hierarchies (subtasks)
  - 5-10 parent-child relationships created
  - Dependency chains tracked in database

- **Related Tasks**: Non-hierarchical task relationships
  - 2-5 related tasks per task
  - Bidirectional relationships

- **Resource & Skill Requirements**: For high-priority tasks
  - Required skills: Python, JavaScript, SQL, DevOps, etc.
  - Skill levels: Intermediate, Advanced
  - Skill match scores: 60-95%

- **Optimal Assignee Suggestions**: AI recommendations
  - User IDs with match scores
  - Reasoning provided

- **Collaboration Indicators**: 
  - Collaboration required: Yes/No
  - Suggested team members with roles

- **Complexity Scoring**: 1-10 scale for task complexity

- **Suggested Dependencies**: AI analysis of potential dependencies
  - Related task IDs
  - Confidence scores: 60-95%

## Login Credentials for Demo

Use these credentials to log in and explore the demo data:

| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Admin/Superuser |
| john_doe | test1234 | Developer |
| jane_smith | test1234 | Marketing Manager |
| robert_johnson | test1234 | Senior Developer |

## Boards Included in Demo Data

### Dev Team Organization

1. **Software Project** (Primary development board)
   - Columns: Backlog, To Do, In Progress, Review, Done
   - 15+ tasks with varying priorities
   - Lean Six Sigma labels included
   - All new features have demo data

2. **Bug Tracking** (Issue management board)
   - Columns: New, Investigating, In Progress, Testing, Closed
   - 8+ bug/issue tasks
   - Severity labels: Critical, Major, Minor
   - Resource and risk data included

### Marketing Team Organization

3. **Marketing Campaign** (Marketing project board)
   - Columns: Ideas, Planning, In Progress, Review, Completed
   - 6+ marketing tasks
   - Campaign-specific labels
   - Stakeholder involvement tracking

## Key Metrics in Demo Data

### Risk Assessment Statistics
- Tasks with risk data: ~70%
- Average risk score: 4-5/9 (Medium range)
- Risk levels distribution:
  - Low: 30%
  - Medium: 40%
  - High: 20%
  - Critical: 10%

### Resource Management Statistics
- Forecasts created: 6 (2 users × 3 boards)
- Capacity alerts: 2-3 active alerts
- Average utilization: 85-100%
- Distribution recommendations: 3

### Stakeholder Engagement Statistics
- Total stakeholders: 5
- Stakeholder tags: 5
- Task-stakeholder involvement: 15+ relationships
- Engagement records: 12-15 total
- Average engagement satisfaction: 3.8/5

### Task Dependencies
- Parent-child relationships: 5
- Related task relationships: 10+
- Tasks with skill requirements: 7
- Tasks with dependency analysis: 7

## Exploring the Demo Data

### Via Admin Interface

1. Go to http://localhost:8000/admin
2. Log in with admin credentials
3. Browse models:
   - **Kanban > Tasks**: View risk assessments and dependencies
   - **Kanban > Resource Demand Forecasts**: See workload predictions
   - **Kanban > Team Capacity Alerts**: View capacity warnings
   - **Kanban > Project Stakeholders**: View stakeholder data
   - **Kanban > Stakeholder Task Involvement**: See engagement tracking

### Via Application Interface

1. Go to http://localhost:8000
2. Log in with any demo credentials
3. Navigate to boards to see:
   - Tasks with risk indicators
   - Workload data
   - Stakeholder information (if integrated in UI)
   - Dependency relationships

### Via API Endpoints

If API endpoints are available, test:
- `/api/tasks/{id}/risk/` - Get task risk assessment
- `/api/forecasts/` - Get resource forecasts
- `/api/stakeholders/` - Get stakeholder data
- `/api/dependencies/` - Get task dependencies

## Database Schema

### New Models with Demo Data

1. **Task Model** (Enhanced)
   - Risk fields: risk_likelihood, risk_impact, risk_score, risk_level
   - Resource fields: required_skills, skill_match_score, complexity_score
   - Dependency fields: parent_task, related_tasks, dependency_chain

2. **ResourceDemandForecast**
   - One per user per board per period
   - Tracks workload vs. capacity

3. **TeamCapacityAlert**
   - Created for overloaded resources
   - Links to forecasts

4. **WorkloadDistributionRecommendation**
   - AI-generated optimization suggestions
   - Linked to forecasts

5. **ProjectStakeholder** (New)
   - Board-level stakeholder tracking
   - Power/Interest matrix analysis

6. **StakeholderTaskInvolvement** (New)
   - Links stakeholders to tasks
   - Tracks engagement metrics

7. **StakeholderEngagementRecord** (New)
   - Individual engagement event logs
   - Communication tracking

8. **EngagementMetrics** (New)
   - Aggregated stakeholder metrics
   - Dashboard support

## Customizing Demo Data

To modify demo data generation, edit `kanban/management/commands/populate_test_data.py`:

### Risk Management Data
Edit `create_risk_management_demo_data()` method to:
- Change risk probability (currently 70%)
- Modify risk indicators
- Update mitigation suggestions

### Resource Management Data
Edit `create_resource_management_demo_data()` method to:
- Adjust workload hours
- Change capacity thresholds
- Modify recommendation types

### Stakeholder Data
Edit `create_stakeholder_management_demo_data()` method to:
- Add/remove stakeholders
- Change influence/interest levels
- Modify engagement strategies

### Task Dependencies
Edit `create_task_dependency_demo_data()` method to:
- Create different dependency patterns
- Adjust skill requirements
- Modify complexity scores

## Troubleshooting

### Demo Data Not Created

**Problem**: Script runs but doesn't create new feature data

**Solution**:
1. Verify migrations are applied: `python manage.py migrate`
2. Check model imports in the script
3. Ensure all models are properly installed
4. Run: `python manage.py shell` to test model imports

### Duplicate Data

**Problem**: Running script multiple times creates duplicates

**Solution**: The script uses `get_or_create()` to avoid duplicates. If issues persist:
1. Clear specific models: `python manage.py shell`
   ```python
   from kanban.models import ResourceDemandForecast
   ResourceDemandForecast.objects.all().delete()
   ```
2. Re-run: `python manage.py populate_test_data`

### Missing Stakeholder Features

**Problem**: Stakeholder data not appearing in UI

**Solution**:
1. Verify stakeholder models are installed
2. Check that migrations include stakeholder_models
3. Ensure stakeholder views are properly integrated

## Next Steps

1. **Explore the UI**: Navigate through boards to see demo data
2. **Test Features**: Use demo tasks to test risk, resource, and stakeholder features
3. **Review Docs**: Check specific feature guides (RISK_MANAGEMENT_INTEGRATION.md, etc.)
4. **Customize**: Modify demo data script for your specific use cases
5. **Deploy**: Once satisfied with features, prepare for production deployment

## Additional Resources

- **Risk Management**: See `RISK_MANAGEMENT_INTEGRATION.md`
- **Resource Management**: See `DEPENDENCY_MANAGEMENT_GUIDE.md`
- **Stakeholder Management**: See `STAKEHOLDER_INTEGRATION_GUIDE.md`
- **Requirements Management**: See `REQMANAGER_INTEGRATION_QUICKSTART.md`
- **Setup Guide**: See `SETUP.md` and `SETUP_COMPLETE.md`

---

**Last Updated**: October 2025
**Demo Data Version**: 2.0 (All features included)
**Status**: ✅ Ready for production use
