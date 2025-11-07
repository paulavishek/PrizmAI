# 🎯 Where to Find the New Features in PrizmAI UI

## Overview
The demo data now has comprehensive sample data for all advanced features. Here's exactly where to see them:

---

## 🛡️ Risk Management Features

### View Risk on Task Detail Page
1. **Go to any board** (Software Project, Bug Tracking, or Marketing Campaign)
2. **Click on a task** to open the task detail page
3. **Look for the "Risk Assessment" section** - displayed prominently at the top of the right sidebar
4. **You'll see:**
   - Risk level badge (Low/Medium/High/Critical) with color coding
   - Risk score (0-9)
   - Likelihood and Impact scores (1-3)
   - Risk indicators to monitor
   - Mitigation strategies with timeline

**Tasks with Risk Data (Demo Data):**
- "Login page not working on Safari"
- "Inconsistent data in reports"
- "Setup authentication middleware"
- "Error 500 when uploading large files"
- And 8 more...

### Admin Panel
- Go to: `http://localhost:8000/admin`
- Navigate to: **Kanban > Tasks**
- Select any task
- View sections:
  - Risk Assessment Fields (risk_likelihood, risk_impact, risk_score, risk_level)
  - Risk Indicators & Mitigation Suggestions
  - Risk Analysis details

---

## 👥 Stakeholder Management Features

### View Stakeholders on Task Detail Page
1. **Open any task** from the Software Project board
2. **Scroll down in the right sidebar**
3. **Look for the "👥 Stakeholders" section**
4. **You'll see:**
   - Stakeholder name and role
   - Involvement type (Owner, Contributor, Reviewer, Stakeholder)
   - Engagement status (Informed, Consulted, Involved)
   - Satisfaction rating (1-5 stars)

**Sample Stakeholders:**
- Sarah Mitchell (Product Manager) - High Influence/Interest
- Michael Chen (Tech Lead) - High Influence/Interest
- Emily Rodriguez (QA Lead) - Medium Influence/High Interest
- David Park (DevOps Engineer) - Medium Influence/Interest
- Lisa Thompson (UX Designer) - Medium Influence/High Interest

### Admin Panel
- Go to: `http://localhost:8000/admin`
- Navigate to: **Kanban > Project Stakeholders**
  - View all stakeholders per board
  - See influence/interest levels
  - Check engagement strategies

- Navigate to: **Kanban > Stakeholder Task Involvement**
  - See which stakeholders are involved in which tasks
  - View involvement types and engagement status
  - Check satisfaction ratings

- Navigate to: **Kanban > Stakeholder Engagement Records**
  - See engagement history
  - View communication channels used
  - Check follow-up status

- Navigate to: **Kanban > Engagement Metrics**
  - Aggregated metrics per stakeholder
  - Average satisfaction scores
  - Engagement frequency data

---

## 📋 Requirements Management & Task Dependencies

### View Dependencies on Task Detail Page
1. **Open any task** from the board
2. **Scroll down in the right sidebar**
3. **Look for "📋 Dependencies & Requirements" section**
4. **You'll see:**
   - **Parent Task:** If this is a subtask, shows which task it belongs to
   - **Subtasks:** Shows all child tasks under this task
   - **Related Tasks:** Other tasks this depends on
   - **Required Skills:** Skills needed with proficiency level
   - **Complexity Score:** 1-10 visual indicator
   - **Collaboration Indicators:** Whether team work is needed

**Sample Dependency Examples:**
- "Login page not working on Safari" → has subtask "Inconsistent data in reports"
- "Button alignment issue on mobile" → has subtask "Fixed pagination on user list"
- Multiple tasks have required skills like Python, JavaScript, DevOps, etc.

### Admin Panel
- Go to: `http://localhost:8000/admin`
- Navigate to: **Kanban > Tasks**
- For any task, view these sections:
  - **Task Dependencies** (expandable):
    - parent_task (if it's a subtask)
    - related_tasks (connected tasks)
    - dependency_chain (full hierarchy)
  - **AI-Suggested Dependencies** (expandable):
    - suggested_dependencies
    - last_dependency_analysis

---

## 📦 Resource Management Features

### View Resource Info on Task Detail Page
1. **Open any task**
2. **Scroll down in the right sidebar**
3. **Look for "📦 Resource Information" section**
4. **You'll see:**
   - **Skill Match Score:** Percentage match for assigned person
   - **Workload Impact:** Low/Medium/High/Critical impact on assignee
   - **Collaboration Required:** Whether team work is needed
   - **Complexity Score:** Visual indicator of task complexity

### View Resource Forecasts (Admin Only)
- Go to: `http://localhost:8000/admin`
- Navigate to: **Kanban > Resource Demand Forecasts**
  - View workload predictions for each team member
  - See capacity utilization percentages
  - Check confidence scores

- Navigate to: **Kanban > Team Capacity Alerts**
  - See overload warnings
  - View critical capacity notifications

- Navigate to: **Kanban > Workload Distribution Recommendations**
  - View AI-generated optimization suggestions
  - Expected capacity savings
  - Recommendation status

---

## 📊 Task Metadata with New Features

### Create Task Form (Advanced Features)
1. **Go to any board**
2. **Click "Add Task"**
3. **Fill in basic info:** Title, Description, Priority, etc.
4. **Scroll down to see "Advanced Features (Optional)" section**
   - This is a collapsible section showing:
   - ℹ️ Risk & Resources will be auto-analyzed
   - ℹ️ Stakeholder management available after creation
   - ℹ️ Task dependencies can be configured after creation

**Note:** Advanced features are automatically calculated after task creation!

---

## 🔍 How to See Specific Demo Data

### Risk Management Demo Data
**Command to verify:**
```bash
python manage.py shell
from kanban.models import Task
tasks = Task.objects.filter(risk_level__isnull=False)
for task in tasks[:5]:
    print(f"{task.title}: Risk {task.risk_level} ({task.risk_score}/9)")
```

### Stakeholder Demo Data
**Command to verify:**
```bash
python manage.py shell
from kanban.stakeholder_models import ProjectStakeholder
stakeholders = ProjectStakeholder.objects.all()
for sh in stakeholders:
    print(f"{sh.name} - {sh.role} ({sh.influence_level}/{sh.interest_level})")
```

### Task Dependency Demo Data
**Command to verify:**
```bash
python manage.py shell
from kanban.models import Task
parent_tasks = Task.objects.filter(parent_task__isnull=False)
print(f"Subtasks: {parent_tasks.count()}")
for task in parent_tasks[:3]:
    print(f"  {task.title} → parent: {task.parent_task.title}")
```

### Resource Forecast Demo Data
**Command to verify:**
```bash
python manage.py shell
from kanban.models import ResourceDemandForecast
forecasts = ResourceDemandForecast.objects.all()
for forecast in forecasts[:5]:
    print(f"{forecast.resource_user.username}: {forecast.utilization_percentage:.0f}% utilized")
```

---

## 🎯 Dashboard Integration Points

### Board View
- Risk indicators appear on task cards (if UI integrated)
- Stakeholder involvement shown (if UI integrated)
- Dependency relationships visible (if UI integrated)

### Task List Views
- Complexity scores shown
- Risk levels displayed
- Resource availability indicators

### Kanban Board View
- Task cards can show risk badges
- Stakeholder avatars
- Dependency connections
- Workload indicators

---

## 📱 Mobile/Responsive Views

All new features are visible in:
- Desktop view (full details)
- Tablet view (optimized layout)
- Mobile view (collapsed sections available)

The stakeholder and dependency sections are collapsible for better mobile experience.

---

## 🔗 Related URLs

### Admin Panel URLs
- `http://localhost:8000/admin/kanban/task/` - View/edit tasks with risk data
- `http://localhost:8000/admin/kanban/projectstakeholder/` - View stakeholders
- `http://localhost:8000/admin/kanban/stakeholdertaskinvolvement/` - Task-stakeholder links
- `http://localhost:8000/admin/kanban/resourcedemandforecast/` - Resource forecasts
- `http://localhost:8000/admin/kanban/teamcapacityalert/` - Capacity alerts

### Application URLs
- `http://localhost:8000/kanban/board/` - View boards with tasks
- `http://localhost:8000/kanban/task/<id>/` - Individual task detail with all features

---

## ✅ Quick Checklist - Where to Look

- [ ] **Risk Assessment**: Task detail page → right sidebar → top section
- [ ] **Stakeholders**: Task detail page → right sidebar → "👥 Stakeholders" section
- [ ] **Dependencies**: Task detail page → right sidebar → "📋 Dependencies" section
- [ ] **Resource Info**: Task detail page → right sidebar → "📦 Resource Information" section
- [ ] **Create Form**: New task form → scroll down → "Advanced Features (Optional)" section
- [ ] **Admin Panel**: `http://localhost:8000/admin/` → Each model listed above

---

## 🚀 Next Steps to Explore

1. **View Risk Assessment**
   - Open "Login page not working on Safari" task
   - See risk level, score, indicators, and mitigation strategies

2. **Check Stakeholders**
   - Open "Implement user authentication" task
   - Scroll to stakeholders section
   - See Sarah Mitchell, Michael Chen involvement

3. **Review Dependencies**
   - Open "Login page not working on Safari" task
   - See it has subtask "Inconsistent data in reports"
   - View related tasks

4. **Explore Resources**
   - View skill requirements on high-priority tasks
   - Check complexity scores
   - See collaboration needs

5. **Check Forecasts** (Admin)
   - Go to Resource Demand Forecasts
   - See team member workload data
   - View capacity utilization

---

## 💡 Tips

- **Demo data is realistic:** Uses real-world scenarios and naming
- **All features interconnected:** Risk affects resources, dependencies affect risk
- **AI analysis:** Many fields were populated by AI analysis
- **Power/Interest Matrix:** Stakeholders are positioned using influence × interest
- **Complexity-Based:** Task complexity affects resource requirements
- **Cascading Effects:** Parent task issues can cascade to subtasks

---

**Status**: ✅ All UI components added and ready to explore!

Visit any task to see the new features in action!
