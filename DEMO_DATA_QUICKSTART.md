# 🚀 PrizmAI Demo - Quick Start Guide

## What's New in Demo Data?

Your PrizmAI kanban board now includes **complete demo data for all advanced features**:

✅ **Risk Management** - Task risk assessments with mitigation strategies  
✅ **Resource Management** - Team workload forecasts and capacity alerts  
✅ **Stakeholder Management** - Engagement tracking with 5 sample stakeholders  
✅ **Requirements Management** - Task dependencies and hierarchies  

---

## Login Immediately

```
Username: admin
Password: admin123
```

Or try other roles:
- **john_doe / test1234** - Developer role
- **jane_smith / test1234** - Marketing role
- **robert_johnson / test1234** - Senior developer role

---

## Where to See the New Features

### 1️⃣ Risk Management
- Go to any **Software Project** board
- Click on tasks to see risk assessments
- Look for risk badges (🛡️ icons) on task cards
- View: Risk scores, likelihood, impact, indicators, and mitigation strategies

**Sample Tasks with Risk Data:**
- "Login page not working on Safari"
- "Inconsistent data in reports"
- "Setup authentication middleware"

### 2️⃣ Resource Management
- Go to your user dashboard (if UI is integrated)
- View **Resource Demand Forecasts** showing:
  - Team member workload predictions
  - Capacity utilization percentages
  - Active team members: John Doe, Robert Johnson

- Check **Team Capacity Alerts** for:
  - Overload warnings
  - Critical capacity notifications

### 3️⃣ Stakeholder Management
- **5 Key Stakeholders** created:
  1. Sarah Mitchell (Product Manager) - High influence/interest
  2. Michael Chen (Tech Lead) - High influence/interest
  3. Emily Rodriguez (QA Lead) - Medium influence/high interest
  4. David Park (DevOps Engineer) - Medium influence/interest
  5. Lisa Thompson (UX Designer) - Medium influence/high interest

- Each stakeholder is involved in multiple tasks
- View engagement records and satisfaction ratings
- Track engagement frequency and sentiment

### 4️⃣ Task Dependencies & Requirements
- View parent-child task relationships (task hierarchies)
- See skill requirements for high-priority tasks
- Check AI-suggested team member assignments
- Review task complexity scores

---

## Quick Features Overview

### 🛡️ Risk Management Demo Data

| Feature | Example |
|---------|---------|
| Risk Likelihood | Low (1), Medium (2), High (3) |
| Risk Impact | Low (1), Medium (2), High (3) |
| Risk Score | 1-9 scale |
| Risk Level | Low, Medium, High, Critical |
| Indicators | "Monitor weekly", "Check dependencies" |
| Mitigation | 2+ strategies per risky task |

**~70% of tasks have risk assessments** with real-world scenarios.

### 📦 Resource Management Demo Data

| Feature | Details |
|---------|---------|
| Forecasts | 6 forecasts (2 users × 3 boards) |
| Period | Next 4 weeks |
| Capacity | 160 hours available |
| Workload | 120-160 hours predicted |
| Alerts | 2-3 active capacity alerts |
| Confidence | 70-95% accuracy |

### 👥 Stakeholder Management Demo Data

| Feature | Details |
|---------|---------|
| Stakeholders | 5 key people |
| Tags | 5 categories for organization |
| Task Involvement | 15+ relationships |
| Engagement Events | 12-15 records |
| Avg Satisfaction | 3.8/5 stars |
| Communication | Email, Phone, Video, Meetings |

### 📋 Requirements & Dependencies Demo Data

| Feature | Details |
|---------|---------|
| Task Hierarchy | 5 parent-child relationships |
| Related Tasks | 10+ non-hierarchical relationships |
| Skill Requirements | Python, JavaScript, SQL, DevOps |
| Assignee Matching | 60-95% skill match scores |
| Complexity | 1-10 scale for 7 tasks |
| Suggestions | AI-generated dependency recommendations |

---

## Try These Actions

1. **Explore Risk Assessments**
   - Open Software Project board
   - Click on "Setup authentication middleware" task
   - View risk assessment details
   - Check mitigation suggestions

2. **Check Resource Forecasts**
   - Go to admin panel (http://localhost:8000/admin)
   - Navigate to "Resource Demand Forecasts"
   - See workload predictions for team members
   - Notice capacity alerts for overloaded staff

3. **Review Stakeholders**
   - Check if stakeholder views are integrated in UI
   - Or go to admin panel > "Project Stakeholders"
   - See engagement records and involvement tracking
   - Check satisfaction ratings per stakeholder

4. **Trace Task Dependencies**
   - Open "Bug Tracking" board
   - Find a parent task and view its subtasks
   - Check related tasks for non-hierarchical relationships
   - Review suggested task dependencies

---

## Admin Panel Access

For detailed exploration, visit:
```
http://localhost:8000/admin
Username: admin
Password: admin123
```

**Browse these models:**
- **Tasks** → View risk, resource, dependency fields
- **Resource Demand Forecasts** → Team workload data
- **Team Capacity Alerts** → Overload warnings
- **Project Stakeholders** → Stakeholder profiles
- **Stakeholder Task Involvement** → Task engagement
- **Engagement Records** → Communication history
- **Engagement Metrics** → Aggregated analytics

---

## Customize Demo Data

Want to regenerate or modify demo data?

### Regenerate All Demo Data
```bash
python manage.py populate_test_data
```

This command:
- Won't delete existing data (idempotent)
- Creates new risk, resource, stakeholder data
- Won't duplicate existing records

### Reset Database (Clean Start)
```bash
# Remove database
rm db.sqlite3

# Run migrations
python manage.py migrate

# Populate fresh demo data
python manage.py populate_test_data
```

### Edit Demo Data Generation
See file: `kanban/management/commands/populate_test_data.py`
- `create_risk_management_demo_data()` - Modify risk scenarios
- `create_resource_management_demo_data()` - Adjust forecasts
- `create_stakeholder_management_demo_data()` - Change stakeholders
- `create_task_dependency_demo_data()` - Modify dependencies

---

## Key Statistics

### Demo Database Size
- **Users**: 4 test accounts
- **Organizations**: 2 (Dev Team, Marketing)
- **Boards**: 3 (Software Project, Bug Tracking, Marketing Campaign)
- **Tasks**: 25+
- **Stakeholders**: 5
- **Risk Assessments**: 12-15 tasks
- **Resource Forecasts**: 6 entries
- **Engagement Records**: 12-15 entries

### Feature Coverage
- ✅ 70% of tasks have risk assessments
- ✅ All team members have workload forecasts
- ✅ All stakeholders have engagement tracking
- ✅ 50% of tasks have dependency relationships
- ✅ 50% of high-priority tasks have skill requirements

---

## Boards Available

### Software Project (Dev Team)
Primary development board with demo data for all features.
- Columns: Backlog, To Do, In Progress, Review, Done
- Status: ✅ All features have demo data

### Bug Tracking (Dev Team)
Issue management board with risk and resource data.
- Columns: New, Investigating, In Progress, Testing, Closed
- Status: ✅ Risk and resource management data included

### Marketing Campaign (Marketing Team)
Marketing project board with stakeholder involvement.
- Columns: Ideas, Planning, In Progress, Review, Completed
- Status: ✅ Stakeholder engagement data included

---

## Next Steps

1. **Explore the Boards** - Get familiar with task organization
2. **Review Risk Assessments** - Understand risk scoring
3. **Check Resource Forecasts** - See workload predictions
4. **Track Stakeholders** - Monitor engagement metrics
5. **Analyze Dependencies** - Review task relationships

---

## Documentation Files

For deeper dives into each feature:

- 📖 **DEMO_DATA_GUIDE.md** - Complete demo data documentation
- 🛡️ **RISK_MANAGEMENT_INTEGRATION.md** - Risk management guide
- 📦 **DEPENDENCY_MANAGEMENT_GUIDE.md** - Resource & requirements guide
- 👥 **STAKEHOLDER_INTEGRATION_GUIDE.md** - Stakeholder management guide
- 📋 **REQMANAGER_INTEGRATION_QUICKSTART.md** - Requirements management quickstart
- 🚀 **SETUP.md** - Initial setup instructions
- ✅ **SETUP_COMPLETE.md** - Setup completion status

---

## Support

**Need help?**
- Check DEMO_DATA_GUIDE.md for detailed information
- Review specific feature guides (Risk, Resource, Stakeholder)
- Run the verification script: `python verify_risk_management.py`
- Check admin panel for raw data inspection

**Issues?**
- Verify all migrations: `python manage.py migrate`
- Check models are imported in populate_test_data.py
- Run: `python manage.py shell` to test imports

---

**Version**: 2.0 (All Features Included)  
**Last Updated**: October 2025  
**Status**: ✅ Ready to Explore!

🎉 **Enjoy exploring the full-featured PrizmAI kanban board with comprehensive demo data!**
