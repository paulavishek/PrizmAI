# 🧪 PrizmAI Manual Testing Plan
**Pre-Deployment Verification Guide**

**Version:** 1.0  
**Date:** January 8, 2026  
**Purpose:** Comprehensive manual testing checklist before cloud deployment

---

## 📋 Table of Contents

- [Testing Overview](#-testing-overview)
- [Pre-Testing Setup](#-pre-testing-setup)
- [Test Environment Setup](#-test-environment-setup)
- [Core Features Testing](#-core-features-testing)
- [AI Features Testing](#-ai-features-testing)
- [Security & Authentication Testing](#-security--authentication-testing)
- [API Testing](#-api-testing)
- [Performance & Scalability Testing](#-performance--scalability-testing)
- [Integration Testing](#-integration-testing)
- [User Experience Testing](#-user-experience-testing)
- [Error Handling & Edge Cases](#-error-handling--edge-cases)
- [Final Deployment Checklist](#-final-deployment-checklist)

---

## 📊 Testing Overview

### Testing Goals
- ✅ Verify all features work as documented
- ✅ Ensure AI integrations are stable and accurate
- ✅ Validate security and permissions
- ✅ Test performance under realistic load
- ✅ Check mobile and responsive design
- ✅ Verify API endpoints and integrations
- ✅ Test error handling and edge cases

### Testing Scope
This plan covers **all major features** documented in the application including:
- Account Management
- Kanban Boards
- AI Assistance
- Analytics & Reporting
- Budget Management
- Resource Leveling
- Retrospectives
- API Endpoints
- Security Features

### Expected Duration
- **Quick Pass:** 4-6 hours (core features only)
- **Comprehensive Pass:** 12-16 hours (all features + edge cases)
- **Complete Testing:** 20-24 hours (includes API, integrations, performance)

---

## 🔧 Pre-Testing Setup

### 1. Environment Preparation

**Clean Environment Test:**
```bash
# Create fresh test environment
python -m venv test_env
test_env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

**Populated Environment Test:**
```bash
# Populate with demo data
python manage.py populate_test_data

# Verify data creation
python manage.py shell
>>> from kanban.models import Board, Task
>>> Board.objects.count()  # Should be > 0
>>> Task.objects.count()   # Should be > 0
```

### 2. Configure Test Settings

**Create `.env.test` file:**
```ini
DEBUG=True
SECRET_KEY=test-secret-key-for-testing-only
GOOGLE_GEMINI_API_KEY=your-actual-api-key
DATABASE_URL=sqlite:///test_db.sqlite3
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 3. Test Data Preparation

**Pre-Configured Demo Users Available:**

The application includes pre-configured demo users with different access levels. All demo users use the password: **`demo123`**

#### Demo Organization Users (Team Mode)
These users are part of "Demo - Acme Corporation" and have RBAC permissions:

1. **Alex Chen** (Admin - Full Access)
   - Username: `alex_chen_demo`
   - Email: alex.chen@demo.prizmai.local
   - Password: `demo123`
   - Role: Organization Admin
   - Skills: Project Management (Expert), Agile/Scrum (Expert), Leadership (Advanced)

2. **Sam Rivera** (Developer - Member Access)
   - Username: `sam_rivera_demo`
   - Email: sam.rivera@demo.prizmai.local
   - Password: `demo123`
   - Role: Organization Member
   - Skills: Python (Expert), JavaScript (Advanced), Django (Expert), React (Intermediate)

3. **Jordan Taylor** (Viewer - Read-Only)
   - Username: `jordan_taylor_demo`
   - Email: jordan.taylor@demo.prizmai.local
   - Password: `demo123`
   - Role: Organization Viewer
   - Skills: Strategic Planning (Expert), Business Analysis (Advanced)

#### Solo Mode Admin User
For testing solo demo mode with full admin access:

4. **Demo Admin Solo**
   - Username: `demo_admin_solo`
   - Email: demo_admin@prizmaidemo.internal
   - Password: `demo123`
   - Role: Virtual Admin (full access to all features)

#### Standard Test Users (Non-Demo)
These users can be created via `populate_test_data` command:

5. **Admin User** (Superuser)
   - Username: `admin`
   - Password: `admin123`
   - Full system administrator access

6. **Development Team**
   - `john_doe` / Password: `JohnDoe@2024`
   - `jane_smith` / Password: `JaneSmith@2024`
   - `robert_johnson` / Password: `RobertJ@2024`
   - `alice_williams` / Password: `AliceW@2024`
   - `bob_martinez` / Password: `BobM@2024`

7. **Marketing Team**
   - `carol_anderson` / Password: `CarolA@2024`
   - `david_taylor` / Password: `DavidT@2024`

**Quick Setup Command:**
```bash
# Create all test users and demo data
python manage.py populate_test_data

# Or just create demo organization
python manage.py create_demo_organization
```

### 4. Browser Setup

**Test on Multiple Browsers:**
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Edge (latest)
- [ ] Safari (if available)
- [ ] Mobile browsers (Chrome mobile, Safari iOS)

---

## 🌐 Test Environment Setup

### Start the Application

```bash
# Start development server
python manage.py runserver

# In separate terminal, start Celery (if using)
celery -A kanban_board worker --loglevel=info

# Open browser
http://localhost:8000
```

### Verify Environment
- [ ] Landing page loads successfully
- [ ] No console errors in browser DevTools
- [ ] Static files load correctly (CSS, JS, images)
- [ ] Database connection is working
- [ ] Gemini API key is configured (check logs)

---

## 🎯 Core Features Testing

### 1. User Authentication & Account Management

#### Registration & Login
- [ ] **Test Case 1.1:** Register new user
  - Navigate to registration page
  - Fill in valid information (username, email, password)
  - Submit form
  - Verify email confirmation (if enabled)
  - **Expected:** User account created successfully, redirected to dashboard
  
- [ ] **Test Case 1.2:** Login with demo user (recommended)
  - Navigate to login page
  - Enter username: `alex_chen_demo`
  - Enter password: `demo123`
  - Click login
  - **Expected:** Redirected to dashboard, can access demo boards
  
- [ ] **Test Case 1.2a:** Login with admin user
  - Navigate to login page
  - Enter username: `admin`
  - Enter password: `admin123`
  - Click login
  - **Expected:** Redirected to dashboard, superuser access confirmed
  
- [ ] **Test Case 1.2b:** Login with valid credentials
  - Navigate to login page
  - Enter valid username/email and password
  - Click login
  - **Expected:** Redirected to dashboard, user session created
  
- [ ] **Test Case 1.3:** Login with invalid credentials
  - Enter wrong password
  - **Expected:** Error message displayed, no login
  
- [ ] **Test Case 1.4:** Password reset flow
  - Click "Forgot Password"
  - Enter email address
  - Check email for reset link
  - Follow link and reset password
  - **Expected:** Password reset successfully, can login with new password
  
- [ ] **Test Case 1.5:** Logout
  - Click logout button
  - **Expected:** User logged out, redirected to landing page

#### Profile Management
- [ ] **Test Case 1.6:** Update profile information
  - Go to profile settings
  - Update name, email, bio
  - Save changes
  - **Expected:** Changes saved and displayed correctly
  
- [ ] **Test Case 1.7:** Upload profile picture
  - Upload image file
  - **Expected:** Image uploaded and displayed as avatar
  
- [ ] **Test Case 1.8:** Change password
  - Navigate to password change page
  - Enter old password and new password
  - Save
  - **Expected:** Password changed, can login with new password

### 2. Dashboard & Navigation

- [ ] **Test Case 2.1:** Dashboard loads correctly
  - Login and view dashboard
  - **Expected:** Shows user's boards, recent tasks, notifications
  
- [ ] **Test Case 2.2:** Navigation menu works
  - Click each menu item
  - **Expected:** All pages accessible, correct content loads
  
- [ ] **Test Case 2.3:** Breadcrumbs navigation
  - Navigate through multiple levels
  - Click breadcrumb links
  - **Expected:** Correct navigation, no broken links

### 3. Board Management

#### Creating Boards
- [ ] **Test Case 3.1:** Create new board manually
  - Click "Create Board"
  - Enter board name and description
  - Save
  - **Expected:** New board created and displayed in board list
  
- [ ] **Test Case 3.2:** Create board with AI column suggestions
  - Create new board
  - Click "Get AI Suggestions" for columns
  - **Expected:** AI generates relevant column names (e.g., To Do, In Progress, Done)
  - Accept suggestions
  - **Expected:** Columns created automatically
  
- [ ] **Test Case 3.3:** Create board with custom columns
  - Create new board
  - Add custom columns: "Backlog", "Design", "Development", "Testing", "Deployed"
  - **Expected:** Custom columns created in order

#### Board Operations
- [ ] **Test Case 3.4:** Edit board details
  - Open board settings
  - Change name and description
  - Save
  - **Expected:** Changes reflected immediately
  
- [ ] **Test Case 3.5:** Delete board
  - Select a test board
  - Click delete
  - Confirm deletion
  - **Expected:** Board removed, tasks archived/deleted
  
- [ ] **Test Case 3.6:** Archive board
  - Archive a board
  - **Expected:** Board hidden from active list, accessible in archives
  
- [ ] **Test Case 3.7:** Duplicate board
  - Duplicate existing board
  - **Expected:** New board created with same structure, no tasks copied

#### Column Management
- [ ] **Test Case 3.8:** Add new column
  - Add column to existing board
  - **Expected:** Column appears on board
  
- [ ] **Test Case 3.9:** Rename column
  - Edit column name
  - **Expected:** Name updated across board
  
- [ ] **Test Case 3.10:** Reorder columns
  - Drag and drop columns to new positions
  - **Expected:** Column order persists after page reload
  
- [ ] **Test Case 3.11:** Delete column
  - Delete a column
  - **Expected:** Warning if column has tasks, tasks moved or deleted

### 4. Task Management

#### Creating Tasks
- [ ] **Test Case 4.1:** Create simple task manually
  - Click "Add Task" in a column
  - Enter title, description, due date
  - Save
  - **Expected:** Task appears in column
  
- [ ] **Test Case 4.2:** Create task with AI description generation
  - Create task with title only: "Implement user authentication"
  - Click "Generate with AI"
  - **Expected:** AI generates detailed task description with acceptance criteria
  
- [ ] **Test Case 4.3:** Create task with all fields
  - Create task with:
    - Title
    - Description
    - Due date
    - Priority (High/Medium/Low)
    - Assigned user
    - Tags/labels
    - Estimated hours
    - Complexity score
  - **Expected:** All fields saved correctly

#### Task Operations
- [ ] **Test Case 4.4:** Edit task
  - Open task details
  - Modify fields
  - Save
  - **Expected:** Changes saved and visible
  
- [ ] **Test Case 4.5:** Move task between columns (drag & drop)
  - Drag task from "To Do" to "In Progress"
  - **Expected:** Task moves, position persists
  
- [ ] **Test Case 4.6:** Assign task to user
  - Select user from dropdown
  - **Expected:** User receives notification, task appears in their dashboard
  
- [ ] **Test Case 4.7:** Set task priority
  - Change priority to High
  - **Expected:** Task visually highlighted, priority filter works
  
- [ ] **Test Case 4.8:** Add task dependencies
  - Set task A to depend on task B
  - **Expected:** Dependency visible, warning if order is incorrect
  
- [ ] **Test Case 4.9:** Add task comments
  - Open task
  - Add comment
  - **Expected:** Comment saved, timestamp and author displayed
  
- [ ] **Test Case 4.10:** Add task attachments
  - Upload file to task
  - **Expected:** File uploaded, downloadable
  
- [ ] **Test Case 4.11:** Log time on task
  - Add time entry (3 hours)
  - **Expected:** Time logged, visible in task and timesheets
  
- [ ] **Test Case 4.12:** Delete task
  - Delete task with confirmation
  - **Expected:** Task removed or moved to trash
  
- [ ] **Test Case 4.13:** Task filtering
  - Filter by: assigned user, priority, due date, tags
  - **Expected:** Correct tasks displayed
  
- [ ] **Test Case 4.14:** Task search
  - Search by task title or description
  - **Expected:** Relevant tasks found

### 5. Team Collaboration

#### Team Member Management
- [ ] **Test Case 5.1:** Invite team member to board
  - Click "Invite Member"
  - Enter email
  - Send invitation
  - **Expected:** Invitation sent, pending status shown
  
- [ ] **Test Case 5.2:** Accept invitation
  - Login as invited user
  - Accept invitation
  - **Expected:** User added to board, can view tasks
  
- [ ] **Test Case 5.3:** Remove team member
  - Remove user from board
  - **Expected:** User loses access, their tasks remain

#### Real-Time Features
- [ ] **Test Case 5.4:** Real-time task updates
  - Open same board in two browsers (two users)
  - Move task in browser 1
  - **Expected:** Change appears in browser 2 without refresh
  
- [ ] **Test Case 5.5:** Task comment notifications
  - User A comments on task assigned to User B
  - **Expected:** User B receives notification

#### Notifications
- [ ] **Test Case 5.6:** Task assignment notification
  - Assign task to user
  - **Expected:** User receives notification
  
- [ ] **Test Case 5.7:** Due date reminder
  - Create task due tomorrow
  - **Expected:** Reminder notification sent
  
- [ ] **Test Case 5.8:** Mention in comment
  - @mention user in comment
  - **Expected:** User receives notification

---

## 🤖 AI Features Testing

### 1. AI Task Description Generation

- [ ] **Test Case AI-1.1:** Generate task description
  - Create task with title: "Implement OAuth2 authentication"
  - Click "Generate with AI"
  - **Expected:** 
    - Detailed description generated
    - Includes purpose, requirements, acceptance criteria
    - Technical considerations included
    - Generation completes within 10 seconds
  
- [ ] **Test Case AI-1.2:** Regenerate description
  - Click "Regenerate" if not satisfied
  - **Expected:** New description generated with different approach
  
- [ ] **Test Case AI-1.3:** AI generation quota tracking
  - Generate 20+ descriptions
  - **Expected:** Quota counter updates, limit warning displayed (if demo mode)

### 2. AI-Powered Recommendations

#### Task Assignment Recommendations
- [ ] **Test Case AI-2.1:** Get assignee recommendation
  - Create complex task (e.g., "Build REST API")
  - Click "Get AI Recommendation" for assignee
  - **Expected:**
    - AI recommends best team member
    - Includes skill match score (e.g., 92%)
    - Shows reasoning ("Jane has Expert Python skills")
    - Displays confidence level (e.g., 88%)
  
- [ ] **Test Case AI-2.2:** View alternative assignee options
  - View full recommendation details
  - **Expected:** Shows top 3 candidates with comparison

#### Priority Recommendations
- [ ] **Test Case AI-2.3:** Get priority recommendation
  - Create task
  - Click "AI Priority Suggestion"
  - **Expected:**
    - AI suggests priority (High/Medium/Low)
    - Includes reasoning (urgency, dependencies, impact)
  
#### Deadline Predictions
- [ ] **Test Case AI-2.4:** Get deadline prediction
  - Create task with complexity estimate
  - Click "Predict Deadline"
  - **Expected:**
    - AI predicts completion date
    - Shows confidence interval (±2 days)
    - Explains calculation (similar historical tasks)
    - Includes optimistic/realistic/pessimistic scenarios

### 3. Explainable AI

- [ ] **Test Case AI-3.1:** View risk assessment explanation
  - Select high-risk task
  - Click "Why?" button
  - **Expected:**
    - Detailed explanation shown
    - Factors breakdown (complexity 35%, dependencies 30%, etc.)
    - AI confidence level displayed
    - Model assumptions listed
    - Alternative perspectives shown
  
- [ ] **Test Case AI-3.2:** View deadline explanation
  - Click "Why?" on deadline prediction
  - **Expected:**
    - Shows similar historical tasks
    - Calculation breakdown displayed
    - Risk factors identified
    - Scenarios (optimistic/realistic/pessimistic) shown
  
- [ ] **Test Case AI-3.3:** View assignee recommendation explanation
  - Click "Why?" on assignee suggestion
  - **Expected:**
    - Skill match breakdown
    - Historical performance data
    - Current workload consideration
    - Comparison with other candidates

### 4. AI Coach

- [ ] **Test Case AI-4.1:** View coach suggestions
  - Navigate to AI Coach dashboard
  - **Expected:** List of proactive suggestions displayed
  
- [ ] **Test Case AI-4.2:** Coach detects velocity drop
  - Simulate velocity drop (complete fewer tasks this week)
  - **Expected:**
    - Coach generates alert
    - Severity: HIGH
    - Includes explanation and recommended actions
  
- [ ] **Test Case AI-4.3:** Coach detects resource overload
  - Assign 10+ tasks to one person
  - **Expected:**
    - Coach alerts overload
    - Suggests reassignment
  
- [ ] **Test Case AI-4.4:** Coach detects risk convergence
  - Create 3 high-risk tasks due same week
  - **Expected:**
    - Coach flags risk convergence
    - Recommends timeline adjustment
  
- [ ] **Test Case AI-4.5:** Provide feedback on suggestion
  - Mark suggestion as "Helpful" or "Not Helpful"
  - **Expected:**
    - Feedback recorded
    - System learns for future suggestions
  
- [ ] **Test Case AI-4.6:** Dismiss suggestion
  - Dismiss a suggestion
  - **Expected:** Suggestion hidden, doesn't reappear

### 5. Smart Column Suggestions

- [ ] **Test Case AI-5.1:** AI suggests columns for software project
  - Create board named "Software Development"
  - Request AI suggestions
  - **Expected:** Suggests relevant columns (Backlog, To Do, In Progress, Review, Done)
  
- [ ] **Test Case AI-5.2:** AI suggests columns for marketing project
  - Create board named "Marketing Campaign"
  - Request AI suggestions
  - **Expected:** Suggests marketing-relevant columns (Ideation, Content Creation, Review, Scheduling, Published)

### 6. AI-Powered Budget Analysis

- [ ] **Test Case AI-6.1:** Get budget health analysis
  - Set up project with budget
  - Click "AI Analysis"
  - **Expected:**
    - Health rating provided (Excellent/Good/Concerning/Critical)
    - Risk identification
    - Positive indicators
    - Action recommendations
  
- [ ] **Test Case AI-6.2:** View budget recommendations
  - Review AI budget recommendations
  - **Expected:**
    - 3-7 targeted recommendations
    - Each has confidence score
    - Estimated cost savings shown
    - Priority level indicated
    - Implementation difficulty noted

---

## 📊 Analytics & Reporting Testing

### 1. Burndown Charts

- [ ] **Test Case BR-1.1:** View burndown chart
  - Navigate to board
  - Click "Burndown Chart"
  - **Expected:**
    - Chart displays with ideal line and actual progress
    - Current progress metrics shown
    - Completion forecast displayed
  
- [ ] **Test Case BR-1.2:** Forecast completion date
  - View forecast
  - **Expected:**
    - Predicted date shown (e.g., Nov 22 ±2 days)
    - Confidence level displayed (90%)
    - Scenarios: optimistic, realistic, pessimistic
  
- [ ] **Test Case BR-1.3:** View velocity metrics
  - Check velocity section
  - **Expected:**
    - Current velocity (tasks/week)
    - Velocity trend (increasing/stable/decreasing)
    - Historical velocity chart
  
- [ ] **Test Case BR-1.4:** Identify risks in burndown
  - **Expected:**
    - Risk level indicator (LOW/MEDIUM/HIGH)
    - Miss probability calculated
    - Alerts for blockers or delays

### 2. Scope Creep Detection

- [ ] **Test Case SC-2.1:** Establish baseline
  - Create new board with 50 tasks
  - Click "Establish Baseline"
  - **Expected:**
    - Baseline snapshot created
    - Original scope metrics captured
  
- [ ] **Test Case SC-2.2:** Add tasks and detect scope creep
  - Add 15 new tasks over 3 days
  - **Expected:**
    - Scope creep alert generated
    - Growth percentage calculated (+30%)
    - Impact analysis shown (timeline, budget)
  
- [ ] **Test Case SC-2.3:** View scope growth metrics
  - Navigate to scope tracking dashboard
  - **Expected:**
    - Shows original vs current tasks
    - Complexity growth
    - Effort growth
    - Impact on timeline and budget
  
- [ ] **Test Case SC-2.4:** View scope change history
  - Check audit trail
  - **Expected:** All scope changes listed with timestamps and users

### 3. Conflict Detection

- [ ] **Test Case CD-3.1:** Detect resource conflict
  - Assign same person to 3 tasks with overlapping dates
  - **Expected:**
    - Conflict detected and flagged
    - Severity: CRITICAL
    - AI suggests resolutions (reassign, extend deadline, split task)
  
- [ ] **Test Case CD-3.2:** Detect schedule conflict
  - Create task with deadline before its dependency is complete
  - **Expected:**
    - Schedule conflict detected
    - Explanation provided
    - Suggestions to resolve
  
- [ ] **Test Case CD-3.3:** Detect circular dependency
  - Create Task A depends on Task B, Task B depends on Task A
  - **Expected:**
    - Circular dependency detected
    - Warning displayed
    - Suggestion to break cycle
  
- [ ] **Test Case CD-3.4:** Resolve conflict
  - Apply AI-suggested resolution
  - **Expected:**
    - Conflict marked resolved
    - Changes applied
    - Outcome tracked

### 4. Budget Tracking & ROI

- [ ] **Test Case BT-4.1:** Set project budget
  - Create board
  - Set budget: $100,000
  - Set warning threshold: 80%
  - **Expected:** Budget saved, displayed on board
  
- [ ] **Test Case BT-4.2:** Log task costs
  - Create task
  - Set estimated cost: $5,000
  - Log actual cost: $5,500
  - **Expected:**
    - Costs tracked
    - Variance calculated
    - Board budget updated
  
- [ ] **Test Case BT-4.3:** Log time and labor costs
  - Log 40 hours of work at $100/hour
  - **Expected:**
    - Labor cost calculated ($4,000)
    - Added to project budget
  
- [ ] **Test Case BT-4.4:** Monitor budget utilization
  - Check budget dashboard
  - **Expected:**
    - Shows spent vs remaining
    - Utilization percentage
    - Status indicator (OK/WARNING/CRITICAL)
  
- [ ] **Test Case BT-4.5:** Budget alerts
  - Spend until 85% of budget used
  - **Expected:**
    - Warning alert displayed
    - Email notification sent (if configured)
  
- [ ] **Test Case BT-4.6:** Burn rate calculation
  - View burn rate metrics
  - **Expected:**
    - Daily spending rate shown
    - Days remaining calculated
    - Trend analysis displayed
  
- [ ] **Test Case BT-4.7:** Budget overrun prediction
  - Check predictions
  - **Expected:**
    - Overrun warning if trending over
    - Predicted exhaustion date
  
- [ ] **Test Case BT-4.8:** Create ROI snapshot
  - Create ROI snapshot
  - Set expected value: $200,000
  - **Expected:**
    - ROI calculated: ((200000-100000)/100000) = 100%
    - Snapshot saved with timestamp
  
- [ ] **Test Case BT-4.9:** Compare ROI over time
  - Create multiple snapshots
  - View comparison
  - **Expected:** Historical ROI trend displayed

### 5. Time Tracking & Timesheets

- [ ] **Test Case TT-5.1:** Log work time
  - Open task
  - Add time entry: 3 hours
  - Add description
  - **Expected:** Time logged, displayed in task
  
- [ ] **Test Case TT-5.2:** Edit time entry
  - Edit previous time entry
  - **Expected:** Changes saved
  
- [ ] **Test Case TT-5.3:** Delete time entry
  - Remove time entry
  - **Expected:** Time entry deleted, totals updated
  
- [ ] **Test Case TT-5.4:** View timesheet
  - Navigate to timesheets
  - **Expected:**
    - All time entries displayed
    - Grouped by task/project
    - Total hours calculated
  
- [ ] **Test Case TT-5.5:** Filter timesheet by date range
  - Select date range: Last 7 days
  - **Expected:** Shows only entries in range
  
- [ ] **Test Case TT-5.6:** Team utilization report
  - View team utilization
  - **Expected:**
    - Shows hours logged per person
    - Utilization percentage
    - Capacity analysis

### 6. Retrospectives

- [ ] **Test Case RT-6.1:** Create retrospective
  - Complete a sprint
  - Click "Create Retrospective"
  - **Expected:** Retrospective form displayed
  
- [ ] **Test Case RT-6.2:** Add retrospective items
  - Add items in categories:
    - What went well
    - What didn't go well
    - Action items
  - **Expected:** Items saved in categories
  
- [ ] **Test Case RT-6.3:** AI retrospective insights
  - Click "Get AI Insights"
  - **Expected:**
    - AI analyzes sprint data
    - Generates insights
    - Suggests improvements
  
- [ ] **Test Case RT-6.4:** Vote on retrospective items
  - Team members vote on items
  - **Expected:** Vote counts displayed
  
- [ ] **Test Case RT-6.5:** Create action items from retrospective
  - Convert retrospective item to task
  - **Expected:** Task created on board

---

## 🔐 Security & Authentication Testing

### 1. Access Control & Permissions

- [ ] **Test Case SEC-1.1:** Role-based access (Admin)
  - Login as: `alex_chen_demo` / `demo123`
  - Navigate to organization settings
  - **Expected:** Can access all features, settings, user management
  
- [ ] **Test Case SEC-1.2:** Role-based access (Member/Developer)
  - Login as: `sam_rivera_demo` / `demo123`
  - Try to access organization settings
  - **Expected:** Can manage assigned projects and tasks, limited admin access
  
- [ ] **Test Case SEC-1.3:** Role-based access (Viewer)
  - Login as: `jordan_taylor_demo` / `demo123`
  - Try to edit tasks
  - **Expected:** Read-only access, cannot edit tasks or boards
  
- [ ] **Test Case SEC-1.4:** Superuser access
  - Login as: `admin` / `admin123`
  - Navigate to Django admin (/admin/)
  - **Expected:** Full superuser access, can access Django admin panel
  
- [ ] **Test Case SEC-1.5:** Board-level permissions
  - Create private board
  - Try accessing as non-member
  - **Expected:** Access denied, 403 error
  
- [ ] **Test Case SEC-1.6:** Task-level permissions
  - Create task
  - Try editing as non-assigned user
  - **Expected:** Edit restricted based on board permissions

### 2. Authentication Security

- [ ] **Test Case SEC-2.1:** Session timeout
  - Login and wait 30 minutes inactive
  - Try to perform action
  - **Expected:** Session expired, redirect to login
  
- [ ] **Test Case SEC-2.2:** Password strength validation
  - Try creating account with weak password
  - **Expected:** Error message, password requirements shown
  
- [ ] **Test Case SEC-2.3:** Brute force protection
  - Attempt 5 failed logins
  - **Expected:** Account locked or CAPTCHA required
  
- [ ] **Test Case SEC-2.4:** SQL injection protection
  - Try SQL injection in search: `' OR '1'='1`
  - **Expected:** Query sanitized, no data leak
  
- [ ] **Test Case SEC-2.5:** XSS protection
  - Try adding script tag in task description: `<script>alert('XSS')</script>`
  - **Expected:** Script escaped, not executed
  
- [ ] **Test Case SEC-2.6:** CSRF protection
  - Try POST request without CSRF token
  - **Expected:** Request rejected

### 3. Data Privacy

- [ ] **Test Case SEC-3.1:** User data isolation
  - Create board as User A
  - Login as User B
  - **Expected:** User B cannot see User A's private boards
  
- [ ] **Test Case SEC-3.2:** Deleted data
  - Delete task
  - Check database
  - **Expected:** Data deleted or soft-deleted, not accessible

### 4. Demo Mode Security

- [ ] **Test Case SEC-4.1:** Demo limitations enforced
  - Access demo mode
  - Try creating 3rd project
  - **Expected:** Blocked with upgrade message
  
- [ ] **Test Case SEC-4.2:** Demo export restriction
  - Try exporting data in demo mode
  - **Expected:** Blocked, upgrade prompt shown
  
- [ ] **Test Case SEC-4.3:** Demo AI quota limits
  - Use 20 AI generations
  - Try 21st generation
  - **Expected:** Blocked, quota message shown
  
- [ ] **Test Case SEC-4.4:** Demo session expiry
  - Demo session older than 48 hours
  - **Expected:** Warning banner, data reset scheduled

---

## 🔌 API Testing

### 1. API Authentication

- [ ] **Test Case API-1.1:** Create API token
  - Run command: `python manage.py create_api_token testuser "Test Token"`
  - **Expected:** Token generated and displayed
  
- [ ] **Test Case API-1.2:** Use API token
  - Make request with Bearer token
  - **Expected:** Authenticated, request succeeds
  
- [ ] **Test Case API-1.3:** Invalid token
  - Use invalid token
  - **Expected:** 401 Unauthorized
  
- [ ] **Test Case API-1.4:** Expired token
  - Use expired token
  - **Expected:** 401 Unauthorized, error message
  
- [ ] **Test Case API-1.5:** Token scopes
  - Use token with `boards.read` scope
  - Try to create board (write operation)
  - **Expected:** 403 Forbidden

### 2. API Endpoints Testing

#### Status Endpoint
- [ ] **Test Case API-2.1:** Check API status
  ```bash
  GET /api/v1/status/
  ```
  - **Expected:** 200 OK, status info returned

#### Boards Endpoints
- [ ] **Test Case API-2.2:** List boards
  ```bash
  GET /api/v1/boards/
  ```
  - **Expected:** 200 OK, array of boards
  
- [ ] **Test Case API-2.3:** Get board details
  ```bash
  GET /api/v1/boards/{id}/
  ```
  - **Expected:** 200 OK, board details with columns and tasks
  
- [ ] **Test Case API-2.4:** Create board
  ```bash
  POST /api/v1/boards/
  {
    "name": "Test Board",
    "description": "Created via API"
  }
  ```
  - **Expected:** 201 Created, board object returned
  
- [ ] **Test Case API-2.5:** Update board
  ```bash
  PATCH /api/v1/boards/{id}/
  {
    "name": "Updated Name"
  }
  ```
  - **Expected:** 200 OK, updated board
  
- [ ] **Test Case API-2.6:** Delete board
  ```bash
  DELETE /api/v1/boards/{id}/
  ```
  - **Expected:** 204 No Content

#### Tasks Endpoints
- [ ] **Test Case API-2.7:** List tasks
  ```bash
  GET /api/v1/tasks/
  ```
  - **Expected:** 200 OK, paginated task list
  
- [ ] **Test Case API-2.8:** Get task details
  ```bash
  GET /api/v1/tasks/{id}/
  ```
  - **Expected:** 200 OK, task details
  
- [ ] **Test Case API-2.9:** Create task
  ```bash
  POST /api/v1/tasks/
  {
    "board": 1,
    "column": 1,
    "title": "API Test Task",
    "description": "Created via API",
    "priority": "high"
  }
  ```
  - **Expected:** 201 Created, task object
  
- [ ] **Test Case API-2.10:** Update task
  ```bash
  PATCH /api/v1/tasks/{id}/
  {
    "status": "in_progress"
  }
  ```
  - **Expected:** 200 OK, updated task
  
- [ ] **Test Case API-2.11:** Delete task
  ```bash
  DELETE /api/v1/tasks/{id}/
  ```
  - **Expected:** 204 No Content

#### Comments Endpoints
- [ ] **Test Case API-2.12:** Add comment to task
  ```bash
  POST /api/v1/tasks/{id}/comments/
  {
    "content": "This is a test comment"
  }
  ```
  - **Expected:** 201 Created, comment object

### 3. API Rate Limiting

- [ ] **Test Case API-3.1:** Check rate limit headers
  - Make API request
  - **Expected:** Headers include:
    - `X-RateLimit-Limit: 1000`
    - `X-RateLimit-Remaining: 999`
    - `X-RateLimit-Reset: <timestamp>`
  
- [ ] **Test Case API-3.2:** Exceed rate limit
  - Make 1001 requests in one hour
  - **Expected:** 429 Too Many Requests

### 4. API Error Handling

- [ ] **Test Case API-4.1:** Invalid request body
  - Send malformed JSON
  - **Expected:** 400 Bad Request, error details
  
- [ ] **Test Case API-4.2:** Missing required fields
  - Create board without name
  - **Expected:** 400 Bad Request, field error
  
- [ ] **Test Case API-4.3:** Resource not found
  - Request non-existent board ID
  - **expected:** 404 Not Found
  
- [ ] **Test Case API-4.4:** Server error handling
  - Trigger server error (if possible)
  - **Expected:** 500 Internal Server Error, error logged

### 5. API Pagination

- [ ] **Test Case API-5.1:** Default pagination
  - List tasks
  - **Expected:** Returns page 1, 50 items (default)
  
- [ ] **Test Case API-5.2:** Custom page size
  - Request with `?page_size=10`
  - **Expected:** Returns 10 items
  
- [ ] **Test Case API-5.3:** Next/previous links
  - **Expected:** Response includes `next` and `previous` URLs

### 6. API Filtering & Search

- [ ] **Test Case API-6.1:** Filter tasks by status
  ```bash
  GET /api/v1/tasks/?status=in_progress
  ```
  - **Expected:** Returns only in-progress tasks
  
- [ ] **Test Case API-6.2:** Filter by date range
  ```bash
  GET /api/v1/tasks/?due_date_after=2025-01-01&due_date_before=2025-12-31
  ```
  - **Expected:** Returns tasks in date range
  
- [ ] **Test Case API-6.3:** Search tasks
  ```bash
  GET /api/v1/tasks/?search=authentication
  ```
  - **Expected:** Returns tasks matching search term

---

## ⚡ Performance & Scalability Testing

### 1. Load Testing

- [ ] **Test Case PERF-1.1:** Dashboard load time
  - Load dashboard with 50 tasks
  - **Expected:** Page loads within 2 seconds
  
- [ ] **Test Case PERF-1.2:** Board with many tasks
  - Create board with 200+ tasks
  - Load board
  - **Expected:** Page loads within 3 seconds, pagination works
  
- [ ] **Test Case PERF-1.3:** Concurrent users
  - Simulate 10 users accessing boards simultaneously
  - **Expected:** No performance degradation, no errors

### 2. Database Performance

- [ ] **Test Case PERF-2.1:** Query optimization
  - Check database queries in DevTools
  - **Expected:** No N+1 queries, efficient queries
  
- [ ] **Test Case PERF-2.2:** Large dataset
  - Populate 1000+ tasks
  - Run complex filters
  - **Expected:** Queries complete within 1 second

### 3. AI Performance

- [ ] **Test Case PERF-3.1:** AI response time
  - Request AI task description
  - **Expected:** Response within 10 seconds
  
- [ ] **Test Case PERF-3.2:** Multiple AI requests
  - Make 5 AI requests simultaneously
  - **Expected:** All complete, no timeout errors
  
- [ ] **Test Case PERF-3.3:** AI error handling
  - Trigger AI API error (disconnect network)
  - **Expected:** Graceful error message, app still functional

### 4. Real-Time Performance

- [ ] **Test Case PERF-4.1:** WebSocket connection
  - Check WebSocket connection in DevTools
  - **Expected:** Connection established, stable
  
- [ ] **Test Case PERF-4.2:** Real-time update latency
  - Move task in one browser
  - Measure time to appear in second browser
  - **Expected:** Update appears within 2 seconds

---

## 🔗 Integration Testing

### 1. Email Integration

- [ ] **Test Case INT-1.1:** Email notifications
  - Trigger notification (assign task)
  - **Expected:** Email sent, received in inbox
  
- [ ] **Test Case INT-1.2:** Password reset email
  - Request password reset
  - **Expected:** Email received with valid reset link

### 2. Webhook Integration

- [ ] **Test Case INT-2.1:** Create webhook
  - Configure webhook for task creation
  - **Expected:** Webhook saved
  
- [ ] **Test Case INT-2.2:** Webhook triggers
  - Create task
  - **Expected:** Webhook fires, payload sent to endpoint
  
- [ ] **Test Case INT-2.3:** Webhook failure handling
  - Configure webhook to invalid URL
  - Create task
  - **Expected:** Error logged, retry attempted

### 3. External Services

- [ ] **Test Case INT-3.1:** Google Gemini API
  - Trigger AI feature
  - **Expected:** API call succeeds, response processed
  
- [ ] **Test Case INT-3.2:** API quota handling
  - Exhaust Gemini API quota
  - **Expected:** Graceful error message, no app crash

---

## 📱 User Experience Testing

### 1. Responsive Design

- [ ] **Test Case UX-1.1:** Mobile view (320px width)
  - Resize browser to 320px
  - **Expected:** Layout adapts, no horizontal scroll, all features accessible
  
- [ ] **Test Case UX-1.2:** Tablet view (768px width)
  - **Expected:** Layout optimized for tablet
  
- [ ] **Test Case UX-1.3:** Desktop view (1920px width)
  - **Expected:** Full desktop layout

### 2. Accessibility

- [ ] **Test Case UX-2.1:** Keyboard navigation
  - Navigate using Tab key
  - **Expected:** All interactive elements accessible
  
- [ ] **Test Case UX-2.2:** Screen reader compatibility
  - Use screen reader (NVDA/JAWS)
  - **Expected:** All content and actions announced
  
- [ ] **Test Case UX-2.3:** Color contrast
  - Check with contrast checker
  - **Expected:** Meets WCAG AA standards
  
- [ ] **Test Case UX-2.4:** Alt text for images
  - Inspect images
  - **Expected:** All images have descriptive alt text

### 3. User Flows

- [ ] **Test Case UX-3.1:** First-time user onboarding
  - Create new account
  - Follow onboarding
  - **Expected:** Clear guidance, tutorial helpful
  
- [ ] **Test Case UX-3.2:** Task creation flow
  - Complete task creation from start to finish
  - **Expected:** Intuitive, minimal clicks, clear feedback
  
- [ ] **Test Case UX-3.3:** Board collaboration flow
  - Invite member, assign tasks, collaborate
  - **Expected:** Smooth workflow, clear notifications

### 4. Forms & Validation

- [ ] **Test Case UX-4.1:** Form validation
  - Submit forms with invalid data
  - **Expected:** Clear error messages, field highlighting
  
- [ ] **Test Case UX-4.2:** Form autosave
  - Start filling form, navigate away
  - Return to form
  - **Expected:** Data preserved (if autosave enabled)
  
- [ ] **Test Case UX-4.3:** Date picker usability
  - Use date picker for due dates
  - **Expected:** Easy to select date, mobile-friendly

---

## 🐛 Error Handling & Edge Cases

### 1. Input Validation

- [ ] **Test Case ERR-1.1:** Empty required fields
  - Submit form without required fields
  - **Expected:** Error message, form not submitted
  
- [ ] **Test Case ERR-1.2:** Extremely long input
  - Enter 10,000 character description
  - **Expected:** Either truncated or validation error
  
- [ ] **Test Case ERR-1.3:** Special characters
  - Use special characters in task title: `<>&"'`
  - **Expected:** Characters escaped, displayed correctly
  
- [ ] **Test Case ERR-1.4:** Unicode characters
  - Use emoji and non-Latin characters: 🚀 こんにちは
  - **Expected:** Saved and displayed correctly

### 2. Network Errors

- [ ] **Test Case ERR-2.1:** Offline mode
  - Disconnect network
  - Try to perform action
  - **Expected:** Clear error message, option to retry
  
- [ ] **Test Case ERR-2.2:** Slow network
  - Throttle network to slow 3G
  - Load page
  - **Expected:** Loading indicators, graceful degradation
  
- [ ] **Test Case ERR-2.3:** Timeout handling
  - Simulate timeout (block AI API)
  - **Expected:** Timeout message, option to retry

### 3. Concurrent Modifications

- [ ] **Test Case ERR-3.1:** Edit conflict
  - Open same task in two browsers
  - Edit in both, save
  - **Expected:** Conflict detected, resolution options
  
- [ ] **Test Case ERR-3.2:** Deleted resource
  - User A deletes task
  - User B tries to edit same task
  - **Expected:** "Task not found" error

### 4. Edge Cases

- [ ] **Test Case ERR-4.1:** Empty board
  - Create board with no tasks
  - **Expected:** Helpful message, call-to-action to add tasks
  
- [ ] **Test Case ERR-4.2:** Zero team members
  - Create board without inviting anyone
  - **Expected:** Works correctly, prompt to invite
  
- [ ] **Test Case ERR-4.3:** Past due date
  - Create task with due date in the past
  - **Expected:** Warning or validation error
  
- [ ] **Test Case ERR-4.4:** Circular dependencies
  - Create Task A → Task B → Task A dependency cycle
  - **Expected:** Prevented or detected with warning
  
- [ ] **Test Case ERR-4.5:** Maximum limits
  - Create board with 1000+ tasks
  - **Expected:** Performance acceptable or limit enforced
  
- [ ] **Test Case ERR-4.6:** Deleted user assignments
  - Delete user who has assigned tasks
  - **Expected:** Tasks either reassigned or show deleted user

---

## ✅ Final Deployment Checklist

### Pre-Deployment Configuration

- [ ] **Environment variables set correctly**
  - [ ] `DEBUG=False`
  - [ ] `SECRET_KEY` is strong and unique
  - [ ] `ALLOWED_HOSTS` configured
  - [ ] Database URL set
  - [ ] Gemini API key configured
  - [ ] Email settings configured
  
- [ ] **Database ready**
  - [ ] Migrations applied
  - [ ] Database backed up
  - [ ] Connection pool configured
  
- [ ] **Static files**
  - [ ] `python manage.py collectstatic` run
  - [ ] Static files served correctly
  
- [ ] **Security**
  - [ ] HTTPS enabled
  - [ ] Security headers configured
  - [ ] CSRF protection enabled
  - [ ] XSS protection enabled
  - [ ] SQL injection protection verified

### Performance Checks

- [ ] **Caching configured**
  - [ ] Redis/Memcached set up (if using)
  - [ ] Cache settings optimized
  
- [ ] **Database optimizations**
  - [ ] Indexes created
  - [ ] Query optimization verified
  
- [ ] **CDN configured** (if using)
  - [ ] Static assets on CDN
  - [ ] Media files on CDN/S3

### Monitoring & Logging

- [ ] **Error tracking**
  - [ ] Sentry or error tracking configured
  - [ ] Test error reporting
  
- [ ] **Logging**
  - [ ] Application logs configured
  - [ ] Log rotation set up
  - [ ] Log level appropriate (INFO/WARNING)
  
- [ ] **Analytics**
  - [ ] Google Analytics configured
  - [ ] Demo analytics working
  - [ ] Conversion tracking tested

### Backup & Recovery

- [ ] **Backup strategy**
  - [ ] Automated database backups
  - [ ] Media files backed up
  - [ ] Backup restoration tested
  
- [ ] **Disaster recovery plan**
  - [ ] Recovery procedures documented
  - [ ] Recovery tested

### Documentation

- [ ] **User documentation updated**
  - [ ] README.md accurate
  - [ ] USER_GUIDE.md current
  - [ ] API_DOCUMENTATION.md complete
  
- [ ] **Admin documentation**
  - [ ] Deployment gu (Use Demo Users)

- [ ] **Homepage loads**
- [ ] **User can register**
- [ ] **Demo user can login** (`alex_chen_demo` / `demo123`)
- [ ] **Demo boards are visible**
- [ ] **User can create new board**
- [ ] **User can create task**
- [ ] **AI features work** (task description generation)
- [ ] **API endpoints respond** (create API token for `alex_chen_demo`)
- [ ] **Different roles work** (test with `jordan_taylor_demo` for viewer)
- [ ] **Mobile view works**
- [ ] **Demo mode accessible** (visit /demo/ URL)k**
- [ ] **AI features work**
- [ ] **API endpoints respond**
- [ ] **Email notifications sent**
- [ ] **Mobile view works**

### Launch Day

- [ ] **Domain configured**
- [ ] **SSL certificate installed**
- [ ] **DNS propagated**
- [ ] **Monitoring active**
- [ ] **Support channels ready**
- [ ] **Announcement ready**

---

## 📊 Testing Report Template

After completing testing, document results:

### Summary

- **Testing Date:** [Date]
- **Tester:** [Name]
- **Environment:** [Development/Staging/Production]
- **Duration:** [Hours]

### Results

- **Total Test Cases:** [Number]
- **Passed:** [Number] ✅
- **Failed:** [Number] ❌
- **Skipped:** [Number] ⏭️
- **Pass Rate:** [Percentage]%

### Critical Issues Found

| Issue ID | Description | Severity | Status |
|----------|-------------|----------|--------|
| 1 | [Description] | High/Medium/Low | Open/Fixed |

### Recommendations

- [ ] [Recommendation 1]
- [ ] [Recommendation 2]

### Sign-off

**Tester Signature:** _________________  
**Date:** _________________  

**Approved for Deployment:** ☐ Yes ☐ No  
**Approver Signature:** _________________  
**Date:** _________________

---

## 📚 Additional Resources

- **Bug Tracking:** Use GitHub Issues to track bugs found during testing
- **Test Data:** Use `python manage.py populate_test_data` for consistent test data
- **API Testing Tools:** Postman, Insomnia, or curl
- **Performance Tools:** Chrome DevTools, Lighthouse
- **Accessibility Tools:** WAVE, axe DevTools

---

## 🎯 Testing Tips

1. **Start with critical path** - Test core user flows first
2. **Use real data** - Test with realistic scenarios
3. **Test on multiple devices** - Don't rely on desktop only
4. **Document everything** - Screenshots, error messages, steps to reproduce
5. **Test as different users** - Admin, manager, developer, viewer
6. **Test integrations** - Don't forget external services
7. **Test edge cases** - Empty states, maximum limits, special characters
8. **Test security** - Try to break authentication and permissions
9. **Performance matters** - Monitor load times and database queries
10. **Automate where possible** - But manual testing catches UX issues

---

**Good luck with your testing! 🚀**

*Remember: Better to find issues now than after deployment!*
