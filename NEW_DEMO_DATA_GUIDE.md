# 🎉 PrizmAI - New Demo Data & User Guide

## 📋 Overview

The PrizmAI demo has been completely refreshed with comprehensive test data to help you explore and test all features of the platform. This guide provides all the information you need to get started.

---

## 👤 User Credentials

### Admin User
```
Username: admin
Password: admin123
Email: admin@PrizmAI.com
Role: Superuser/Administrator
Organization: Dev Team
```

### Development Team Users
| Username | Password | Email | Full Name | Role |
|----------|----------|-------|-----------|------|
| john_doe | JohnDoe@2024 | john.doe@devteam.com | John Doe | Developer |
| jane_smith | JaneSmith@2024 | jane.smith@devteam.com | Jane Smith | Developer/Admin |
| robert_johnson | RobertJ@2024 | robert.johnson@devteam.com | Robert Johnson | Senior Developer |
| alice_williams | AliceW@2024 | alice.williams@devteam.com | Alice Williams | Developer |
| bob_martinez | BobM@2024 | bob.martinez@devteam.com | Bob Martinez | Developer |

### Marketing Team Users
| Username | Password | Email | Full Name | Role |
|----------|----------|-------|-----------|------|
| carol_anderson | CarolA@2024 | carol.anderson@marketingteam.com | Carol Anderson | Manager/Admin |
| david_taylor | DavidT@2024 | david.taylor@marketingteam.com | David Taylor | Marketing Specialist |

---

## 🎯 Quick Start (Get Started in 5 Minutes)

### Step 1: Start the Development Server
```bash
cd /path/to/PrizmAI
python manage.py runserver
```

### Step 2: Open Your Browser
Navigate to: `http://localhost:8000`

### Step 3: Log In
- **Option A - Admin Access**: Use `admin` / `admin123`
- **Option B - Dev Team**: Use `john_doe` / `JohnDoe@2024`
- **Option C - Marketing Team**: Use `carol_anderson` / `CarolA@2024`

### Step 4: Explore the Demo
- Visit the **Boards** section to see all kanban boards
- Each board has tasks with different statuses
- Test chat rooms by clicking on board names to access the messaging feature

---

## 📊 Demo Data Statistics

### Organizations
- **Dev Team**: 5 developers + 1 admin
- **Marketing Team**: 2 marketers

### Boards Created
1. **Software Project** (Dev Team)
   - 11 tasks across 5 columns
   - Features: Risk assessments, resource forecasts, stakeholder tracking
   - Members: 5 dev team members

2. **Bug Tracking** (Dev Team)
   - 7 bug/issue tasks
   - Features: Severity labels, risk data, team involvement
   - Members: 4 team members

3. **Marketing Campaign** (Marketing Team)
   - 9 marketing tasks
   - Features: Campaign-specific labels, engagement tracking
   - Members: 2 marketing team members

### Total Demo Data
- **Total Tasks**: 27 tasks
- **Risk Assessments**: 12 tasks (44% coverage)
- **Resource Forecasts**: 4 forecasts
- **Stakeholders**: 5 stakeholders
- **Chat Rooms**: 12 rooms (4 per board)
- **Chat Messages**: 60+ messages
- **Task Dependencies**: 5 parent-child relationships
- **Task Skills**: 7 tasks with skill requirements
- **Engagement Records**: 17 engagement records

---

## 🔍 What to Test

### 1. Kanban Board Features
**Location**: Main Dashboard > Click any board

- [ ] Drag and drop tasks between columns
- [ ] Click task to view details
- [ ] Edit task title, description, priority
- [ ] Assign tasks to team members
- [ ] Add labels to tasks
- [ ] View task progress percentage
- [ ] Check task due dates

### 2. Risk Management
**Location**: Any task > "Risk Assessment" section

- [ ] View risk score calculation (Likelihood × Impact)
- [ ] See risk level (Low/Medium/High/Critical)
- [ ] Review risk indicators
- [ ] Read mitigation suggestions
- [ ] Check risk analysis details

**Sample Risk Tasks**:
- Create component library (Critical)
- Implement dashboard layout (Medium)
- Review homepage design (Medium)

### 3. Resource Management
**Location**: Board settings or task details

- [ ] View resource demand forecasts
- [ ] Check team member utilization percentages
- [ ] See capacity alerts (if any)
- [ ] Review workload distribution recommendations
- [ ] Analyze team availability

**Sample Data**:
- john_doe: 82-100% utilized across boards
- robert_johnson: 88% utilized

### 4. Stakeholder Management
**Location**: Board settings > Stakeholders

- [ ] View stakeholder profiles
  - Sarah Mitchell (Product Manager, High Power/Interest)
  - Michael Chen (Tech Lead, High Power/Interest)
  - Emily Rodriguez (QA Lead, Medium Power/High Interest)
  - David Park (DevOps, Medium Power/Medium Interest)
  - Lisa Thompson (UX Designer, Medium Power/High Interest)

- [ ] Check stakeholder involvement in tasks
- [ ] View engagement records and communication history
- [ ] Review satisfaction ratings
- [ ] See engagement metrics and gaps

### 5. Requirements Management (Task Dependencies)
**Location**: Any task > "Dependencies" section

- [ ] View parent-child task relationships
  - "Implement user authentication" has subtasks
  - "Implement dashboard layout" has subtasks

- [ ] Check related tasks (non-hierarchical)
- [ ] Review skill requirements for tasks
- [ ] See optimal assignee suggestions
- [ ] View task complexity scores

### 6. Messaging & Chat Rooms
**Location**: Click on board name to see chat rooms

- [ ] Access chat rooms (General Discussion, Technical Support, etc.)
- [ ] View existing chat messages
- [ ] Send new messages
- [ ] See messages timestamped and attributed to users
- [ ] Chat rooms available for each board
- [ ] 4 chat rooms per board:
  - General Discussion
  - Technical Support
  - Feature Planning
  - Random Chat

### 7. Lean Six Sigma Labels
**Location**: Any task > Labels section

On every board, tasks are labeled with Lean Six Sigma categories:
- **Value-Added** (Green) - Adds value to customer/business
- **Necessary Non-Value-Added** (Yellow) - Required but doesn't add value
- **Waste/Eliminate** (Red) - Should be eliminated or minimized

---

## 📝 Demo Scenarios to Test

### Scenario 1: Project Manager Role
**User**: carol_anderson (Marketing Manager)

1. Log in as carol_anderson
2. Navigate to "Marketing Campaign" board
3. Check the resource forecasts for the team
4. Review stakeholder engagement metrics
5. Send a message in the "General Discussion" chat room
6. Create a new task for the team

### Scenario 2: Developer Role
**User**: john_doe (Developer)

1. Log in as john_doe
2. Navigate to "Software Project" board
3. Review assigned tasks in "My Tasks"
4. Check risk assessments on high-priority tasks
5. View task dependencies and subtasks
6. Discuss with team in "Technical Support" chat room

### Scenario 3: Admin/PM Role
**User**: admin or jane_smith

1. Log in as admin
2. Switch between Dev Team and Marketing Team organizations
3. View all boards and their members
4. Check stakeholder management features
5. Review resource forecasts and capacity alerts
6. Analyze team engagement metrics

### Scenario 4: Multi-Board Testing
1. Create a message in "Software Project" > "General Discussion"
2. Switch to "Bug Tracking" board
3. Create a message in its chat room
4. Compare data across boards
5. Test task assignment across different boards

---

## 🎨 Board Details

### 1. Software Project Board (Dev Team)
**Status**: Complete development workflow

**Columns**:
- Backlog (3 tasks) - Future work
- To Do (2 tasks) - Ready to start
- In Progress (2 tasks) - Currently being worked on
- Review (1 task) - Needs review
- Done (3 tasks) - Completed

**Key Tasks**:
- "Implement user authentication" - High priority, assigned to john_doe
- "Setup authentication middleware" - Urgent, assigned to robert_johnson
- "Setup project repository" - Done, assigned to admin

**Labels**: Front-end, Back-end, Bug, Feature, Documentation, Lean Six Sigma

### 2. Bug Tracking Board (Dev Team)
**Status**: Active bug management

**Columns**:
- New (2 bugs) - Recently reported
- Investigating (1 bug) - Being analyzed
- In Progress (1 bug) - Being fixed
- Testing (1 bug) - Awaiting QA verification
- Closed (2 bugs) - Resolved

**Priority Bugs**:
- "Login page not working on Safari" - Critical
- "Inconsistent data in reports" - High
- "Error 500 when uploading large files" - Critical (resolved)

### 3. Marketing Campaign Board (Marketing Team)
**Status**: Active marketing execution

**Columns**:
- Ideas (2) - Brainstorming stage
- Planning (1) - Under development
- In Progress (2) - Active execution
- Review (1) - Awaiting approval
- Completed (3) - Finished campaigns

**Campaign Types**: Social Media, Email, Content, Design, Analytics

---

## 💬 Chat Rooms Available

### By Board

**Software Project** - 4 rooms:
1. General Discussion - Team updates and announcements
2. Technical Support - Technical questions and debugging
3. Feature Planning - Discussion about new features
4. Random Chat - Off-topic and team building

**Bug Tracking** - 4 rooms:
1. General Discussion - Bug status updates
2. Technical Support - Debugging discussions
3. Feature Planning - Enhancement ideas
4. Random Chat - Casual chat

**Marketing Campaign** - 4 rooms:
1. General Discussion - Campaign updates
2. Technical Support - Technical marketing questions
3. Feature Planning - Campaign planning
4. Random Chat - Team casual chat

**Total**: 12 chat rooms with 5-10 sample messages each

---

## 🔗 Feature Integration Examples

### Example 1: Risk-Managed Development
See how risk management integrates with tasks:
- Task: "Implement user authentication"
- Risk Score: High
- Mitigation: Allocate additional resources
- Stakeholder: Michael Chen (Tech Lead)
- Status: In Progress with 65% completion

### Example 2: Resource Planning
How resource management tracks team capacity:
- john_doe: 82-100% utilized
- Alert: Capacity at warning level
- Recommendation: Distribute high-priority tasks
- Action: Assign to less utilized team members

### Example 3: Stakeholder Engagement
How stakeholder engagement is tracked:
- Stakeholder: Sarah Mitchell (Product Manager)
- Involvement: 3 tasks, Owner role
- Engagement: 4 records, 3.8/5 satisfaction
- Gap: Current=collaborate, Desired=empower

### Example 4: Dependency Management
How task dependencies are organized:
- Parent: "Implement user authentication"
- Subtask: "Create component library"
- Dependency: Must complete parent first
- Skill Match: 85% match for john_doe
- Complexity: 7/10

---

## 🧪 Testing Workflows

### Test 1: Create and Assign a Task
1. Log in as admin
2. Go to "Software Project" board
3. Click "Add Task" in any column
4. Enter title: "Test Feature XYZ"
5. Assign to john_doe
6. Set priority to High
7. Add a label
8. Save and verify it appears on the board

### Test 2: Communicate in Chat
1. Open any board
2. Click the board name to show chat rooms
3. Select "General Discussion"
4. Type a message: "@john_doe Can you review this?"
5. Send the message
6. Switch to another user and see the message
7. Reply with @mention

### Test 3: Track Risk Assessment
1. Open "Software Project" board
2. Click "Login page not working on Safari" task (from Bug Tracking)
3. Scroll to Risk Assessment section
4. View:
   - Risk Score: 6 (High)
   - Likelihood: 2, Impact: 3
   - Indicators and mitigations
5. Save any notes

### Test 4: Check Stakeholder Involvement
1. Open "Software Project" board
2. Click any task (e.g., "Implement user authentication")
3. Go to Stakeholders section
4. See which stakeholders are involved
5. View their engagement history
6. Check satisfaction ratings

---

## 🎓 Learning Resources

### Core Features
- **Kanban**: Traditional task management with columns and drag-drop
- **Lean Six Sigma**: Categorize tasks as Value-Added or Waste
- **AI Assistant**: (Coming soon) Get intelligent recommendations

### Advanced Features
- **Risk Management**: Assess and mitigate project risks
- **Resource Management**: Forecast team capacity and workload
- **Stakeholder Management**: Track engagement and satisfaction
- **Requirements**: Manage task dependencies and hierarchies
- **Messaging**: Real-time team communication with chat rooms

---

## 🐛 Known Test Data Notes

### Intentional Demo Scenarios
1. Some tasks have high risk levels - good for testing risk features
2. Some users are over-utilized - good for testing capacity alerts
3. Multiple stakeholders are assigned to same task - good for testing collaboration
4. Task dependencies are set up - good for testing hierarchy features
5. Chat rooms have existing messages - good for testing messaging timeline

### Areas to Verify
- All users can access their respective organizations' boards ✓
- Chat rooms have messages from different users ✓
- Risk assessments are properly calculated ✓
- Resource forecasts show utilization percentages ✓
- Stakeholder engagement records show satisfaction ratings ✓

---

## 🚀 Next Steps

1. **Explore the Dashboard**
   - Log in with any user
   - Navigate to "My Tasks" to see assigned work
   - Check the Dashboard for analytics

2. **Test Each Feature**
   - Try the kanban board operations
   - Review risk assessments
   - Check resource forecasts
   - Explore stakeholder profiles
   - Test chat messaging

3. **Customize the Data** (Optional)
   - Edit tasks to test workflows
   - Add new tasks to test creation
   - Send messages to test chat functionality
   - Modify assignments to test resource management

4. **Provide Feedback**
   - Note any issues or improvements
   - Test cross-browser compatibility
   - Check mobile responsiveness
   - Validate all calculations and metrics

---

## 📞 Support & Troubleshooting

### Reset Demo Data
If you need to reset the demo data to its original state:
```bash
# Delete the database
rm db.sqlite3

# Run migrations
python manage.py migrate

# Repopulate demo data
python manage.py populate_test_data

# Verify
python verify_demo_data.py
```

### Database Issues
If you encounter database errors:
```bash
# Clear and reset
python manage.py migrate accounts zero
python manage.py migrate kanban zero
python manage.py migrate messaging zero
python manage.py migrate
python manage.py populate_test_data
```

### Common Issues

**Issue**: Can't log in with a user
- **Solution**: Check the credentials table above - make sure you're using the exact username and password

**Issue**: Chat rooms not showing
- **Solution**: Click on the board name in the navigation to expand chat room options

**Issue**: Risk assessments not visible
- **Solution**: Some tasks have risk data, others don't. Check the "Sample Risk Tasks" section

**Issue**: Resource forecasts showing 0%
- **Solution**: Forecasts are created for specific users. Check "Resource Management" section for details

---

## 📊 Feature Coverage Summary

| Feature | Status | Demo Data | Test Users | Chat Rooms |
|---------|--------|-----------|------------|-----------|
| Kanban Boards | ✅ Complete | 27 tasks | 8 users | 12 rooms |
| Risk Management | ✅ Complete | 12 assessments | Multiple roles | Enabled |
| Resource Management | ✅ Complete | 4 forecasts | 2 primary | Enabled |
| Stakeholder Management | ✅ Complete | 5 stakeholders | Involved | Enabled |
| Requirements (Deps) | ✅ Complete | 5 hierarchies | Testing | Enabled |
| Messaging (Chat) | ✅ Complete | 60+ messages | All users | 12 rooms |
| Lean Six Sigma | ✅ Complete | Labeled tasks | All boards | N/A |

---

## 🎉 You're All Set!

Your PrizmAI demo is ready to explore. Start by logging in as any user and navigating to the boards. Each section of the application has comprehensive sample data to test all features.

**Happy testing!** 🚀

---

**Created**: October 30, 2024  
**Version**: 2.0 - Complete Feature Set  
**Last Updated**: Fresh Demo Data Generated
