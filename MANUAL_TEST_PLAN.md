# PrizmAI Pre-Ship Manual Test Plan

**Version:** 1.0  
**Duration:** 2 days  
**Environment:** Local dev (`http://localhost:8000`)  
**Last Setup:** `python manage.py setup_test_environment`

---

## Test Accounts

| Username | Email | Password | Role Context |
|----------|-------|----------|-------------|
| **testuser1** | paul.biotech10@gmail.com | *(your password)* | 6 own boards, member on testuser3's board, viewer on testuser2's board |
| **testuser2** | avip3310@gmail.com | *(your password)* | 6+ own boards, member on testuser1's board, viewer on testuser3's board |
| **testuser3** | avishekpaul1310@gmail.com | *(your password)* | 1 own board, member on testuser2's board, viewer on testuser1's board |

### RBAC Cross-Board Rotation

| Board Owner | Board Name | Member | Viewer |
|-------------|-----------|--------|--------|
| testuser1 | Core AI Protocol Development | testuser2 | testuser3 |
| testuser2 | AI Core Architecture Design | testuser3 | testuser1 |
| testuser3 | testuser3's Test Board | testuser1 | testuser2 |

### Demo Template Boards (3 total, 96 tasks)

| Board | Columns | Tasks |
|-------|---------|-------|
| Software Development | To Do, In Progress, In Review, Done | 36 |
| Marketing Campaign | Backlog, In Progress, Review, Done | 30 |
| Bug Tracking | New, Triaged, In Progress, Resolved | 30 |

---

## Setup Checklist (Phase 0)

Run these before testing. All commands are idempotent.

```bash
cd C:\Users\Avishek Paul\PrizmAI
venv\Scripts\python.exe manage.py setup_test_environment
```

- [ ] All 3 users verified
- [ ] Each user has real org + workspace + Enterprise preset
- [ ] Cross-board RBAC memberships created
- [ ] Each user has 3 sandbox boards (Software Dev + Marketing + Bug Tracking)
- [ ] Start dev server: `start_prizmAI_dev.bat` or `python manage.py runserver`

---

## DAY 1: Core Features & RBAC

### Test 1.1 — Login & Dashboard (each user)

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Login as **testuser1** | Dashboard loads, shows own boards | ☐ |
| 2 | Check sidebar board list | Shows 6 own boards + shared boards | ☐ |
| 3 | Verify "My Workspace" is active (not demo) | Header shows "testuser1's Workspace" | ☐ |
| 4 | Repeat for **testuser2** | Dashboard loads, shows own boards | ☐ |
| 5 | Repeat for **testuser3** | Dashboard loads, shows "testuser3's Test Board" | ☐ |

### Test 1.2 — Board RBAC: Owner Actions

Login as **testuser1** (owner of "Core AI Protocol Development").

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Open "Core AI Protocol Development" board | Board loads with tasks | ☐ |
| 2 | Create a new task | Task created successfully | ☐ |
| 3 | Edit an existing task (title, description, priority) | Changes saved | ☐ |
| 4 | Drag a task to a different column | Column change persists on refresh | ☐ |
| 5 | Delete a task | Task deleted | ☐ |
| 6 | Open Board Settings | Settings panel accessible | ☐ |
| 7 | Add/remove a board member | Membership updated | ☐ |
| 8 | Change a member's role (member ↔ viewer) | Role changed | ☐ |

### Test 1.3 — Board RBAC: Member Actions

Login as **testuser2** (member of "Core AI Protocol Development").

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Open "Core AI Protocol Development" | Board loads, tasks visible | ☐ |
| 2 | Create a new task | Task created successfully | ☐ |
| 3 | Edit a task assigned to you | Changes saved | ☐ |
| 4 | Drag a task to a different column | Column change persists | ☐ |
| 5 | Try to access Board Settings | Settings restricted or limited | ☐ |
| 6 | Try to delete someone else's task | Should be blocked or warned | ☐ |
| 7 | Try to change another member's role | Should be blocked | ☐ |

### Test 1.4 — Board RBAC: Viewer Actions

Login as **testuser3** (viewer of "Core AI Protocol Development").

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Open "Core AI Protocol Development" | Board loads, tasks visible | ☐ |
| 2 | Try to create a new task | Should be blocked | ☐ |
| 3 | Try to edit a task | Should be blocked / read-only | ☐ |
| 4 | Try to drag tasks | Should be blocked | ☐ |
| 5 | Try to access Board Settings | Should be blocked | ☐ |
| 6 | View task details (click to open) | Details visible in read-only | ☐ |

### Test 1.5 — Cross-Board Verification

Repeat Tests 1.2–1.4 for the other two rotation slots:

| User | Board | Expected Role |
|------|-------|--------------|
| testuser3 | AI Core Architecture Design (testuser2's) | Member |
| testuser1 | AI Core Architecture Design (testuser2's) | Viewer |
| testuser1 | testuser3's Test Board | Member |
| testuser2 | testuser3's Test Board | Viewer |

- [ ] Each role works correctly for each board

### Test 1.6 — Cross-Workspace Data Isolation

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Login as **testuser1**, note board list | See only own boards + shared boards | ☐ |
| 2 | Login as **testuser2**, note board list | See only own boards + shared boards — NO testuser1 private boards | ☐ |
| 3 | Login as **testuser3**, note board list | See testuser3's Test Board + shared boards — NO testuser1/2 private boards | ☐ |
| 4 | As testuser2, try URL `/boards/<testuser1_private_board_id>/` | Should get 403 or redirect, NOT board data | ☐ |
| 5 | As testuser3, try URL `/boards/<testuser2_private_board_id>/` | Should get 403 or redirect | ☐ |
| 6 | Verify goals/missions don't leak across users | Each user sees only own hierarchy | ☐ |

### Test 1.7 — Workspace Preset System

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Open Workspace Settings → Preset | Shows "Enterprise" | ☐ |
| 2 | Verify all Enterprise features enabled | Gantt, budgets, time tracking, etc. visible | ☐ |
| 3 | Switch to "Lean" preset | Feature panels hide/simplify | ☐ |
| 4 | Switch back to "Enterprise" | All features re-appear | ☐ |

### Test 1.8 — Goal → Mission → Strategy → Board Hierarchy

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Navigate to Goals page | Organization goals visible | ☐ |
| 2 | Click into a goal → missions | Missions listed under goal | ☐ |
| 3 | Click into a mission → strategies | Strategies listed under mission | ☐ |
| 4 | Click through to linked board | Board opens from strategy | ☐ |
| 5 | Verify progress rolls up | Board task completion reflects in strategy/mission % | ☐ |

---

## DAY 2: Demo Sandbox, Spectra AI, & Advanced Features

### Test 2.1 — Demo Sandbox Provisioning

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Login as **testuser1** | Lands on "My Workspace" | ☐ |
| 2 | Toggle to "Demo Mode" | Switches to demo workspace | ☐ |
| 3 | Verify 3 sandbox boards appear | Software Development, Marketing Campaign, Bug Tracking | ☐ |
| 4 | Verify sandbox boards have tasks | SW=36, Marketing=30, Bug Tracking=30 | ☐ |
| 5 | Edit a task in sandbox (change title) | Change saved | ☐ |
| 6 | Toggle back to "My Workspace" | Own boards reappear, sandbox changes isolated | ☐ |
| 7 | Toggle back to Demo Mode | Previous sandbox edit persists | ☐ |
| 8 | Repeat for **testuser2** and **testuser3** | Each user has independent sandbox copies | ☐ |

### Test 2.2 — Demo Sandbox Isolation

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | As **testuser1**, edit a sandbox task title to "TESTUSER1 WAS HERE" | Saved | ☐ |
| 2 | As **testuser2**, view same-named sandbox board | Title should NOT show "TESTUSER1 WAS HERE" | ☐ |
| 3 | As **testuser1**, create a new task in sandbox | Task created | ☐ |
| 4 | As **testuser2**, check same sandbox board | New task should NOT appear | ☐ |
| 5 | Delete a sandbox task as **testuser1** | Deleted in testuser1's sandbox only | ☐ |

### Test 2.3 — Demo Reset

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Make several changes in sandbox (testuser1) | Changes visible | ☐ |
| 2 | Click "Reset Demo" button | Sandbox wipes and re-provisions | ☐ |
| 3 | Verify all 3 boards restored to original state | Tasks back to template state | ☐ |
| 4 | Verify own workspace unaffected | Switch to "My Workspace" — no data lost | ☐ |

### Test 2.4 — Spectra AI Assistant (Basic)

Login as **testuser1** (owner of own boards).

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Open Spectra (AI chat panel) | Chat interface loads | ☐ |
| 2 | Ask: "What's the status of my boards?" | Spectra gives board summary | ☐ |
| 3 | Ask: "Show me overdue tasks" | Lists tasks past due date | ☐ |
| 4 | Ask: "Create a task called 'Test AI Task' on [board name]" | Task created via Spectra | ☐ |
| 5 | Verify task exists on the board | Navigate to board, confirm task | ☐ |
| 6 | Ask: "Summarize the Bug Tracking board" | Summary with bug distribution | ☐ |

### Test 2.5 — Spectra AI RBAC Enforcement

**Critical test**: Spectra must respect board roles.

#### As Owner (testuser1 on own board):

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Ask Spectra to create a task on your board | Task created | ☐ |
| 2 | Ask Spectra to delete a task | Task deleted or prompt confirms | ☐ |
| 3 | Ask Spectra to move a task to Done | Task moved | ☐ |

#### As Member (testuser2 on testuser1's "Core AI Protocol Development"):

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Ask Spectra to create a task on "Core AI Protocol Development" | Task created (members can create) | ☐ |
| 2 | Ask Spectra to delete a task on that board | Should be blocked | ☐ |
| 3 | Verify denial message includes role and board name | Message like "As a **member** on **Core AI Protocol Development**, you cannot..." | ☐ |

#### As Viewer (testuser3 on testuser1's "Core AI Protocol Development"):

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Ask Spectra to create a task on "Core AI Protocol Development" | Should be blocked | ☐ |
| 2 | Verify denial message | "As a **viewer** on **Core AI Protocol Development**, you cannot..." | ☐ |
| 3 | Ask Spectra to read/list tasks on that board | Should succeed (viewers can read) | ☐ |
| 4 | Ask Spectra to edit a task on that board | Should be blocked with role in message | ☐ |

### Test 2.6 — Spectra Cross-Workspace Data Bleed

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | As **testuser3**, ask Spectra: "Show all boards" | Should only list boards testuser3 can access | ☐ |
| 2 | As **testuser3**, ask: "Show tasks on [testuser1 private board name]" | Should refuse — not a member | ☐ |
| 3 | As **testuser1**, ask: "List testuser2's tasks" | Should not reveal testuser2's private data | ☐ |

### Test 2.7 — Analytics & Dashboard

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Open Analytics / Dashboard page | Charts and metrics render | ☐ |
| 2 | Check burndown chart | Shows forecast line | ☐ |
| 3 | Check velocity chart | Shows team velocity data | ☐ |
| 4 | Verify data scoped to current workspace | No data from other workspaces | ☐ |

### Test 2.8 — Gantt Chart

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Open a board with phased tasks | Gantt chart renders | ☐ |
| 2 | Verify task bars show correct phases | Phase 1, 2, 3 groupings correct | ☐ |
| 3 | Verify dependencies shown | Lines between dependent tasks | ☐ |
| 4 | Drag a task to reschedule | Dates update | ☐ |

### Test 2.9 — Wiki Module

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Open Wiki section | Categories and pages visible | ☐ |
| 2 | View a wiki page | Content renders as markdown | ☐ |
| 3 | Create a new wiki page | Page created and saved | ☐ |
| 4 | Edit existing wiki page | Changes saved | ☐ |
| 5 | Verify wiki links between pages | Internal links work | ☐ |

### Test 2.10 — Messaging / Chat

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Open Messaging section | Chat rooms visible | ☐ |
| 2 | Send a message in a chat room | Message appears | ☐ |
| 3 | Check notifications | Notifications from other users' actions | ☐ |

### Test 2.11 — Time Tracking & Budget

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Open a board → Time Tracking | Time entry list/form visible | ☐ |
| 2 | Log a new time entry | Entry saved | ☐ |
| 3 | View budget dashboard | Budget metrics render | ☐ |
| 4 | Verify time entries scoped to board | No cross-board leakage | ☐ |

### Test 2.12 — Conflict Detection

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Open Conflict Detection panel | Conflicts displayed | ☐ |
| 2 | View conflict details | Shows resource/schedule/dependency info | ☐ |
| 3 | Resolve a conflict | Resolution recorded | ☐ |

### Test 2.13 — Retrospectives & Coaching

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Open a completed board → Retrospective | Retro UI loads | ☐ |
| 2 | View AI coaching suggestions | Suggestions displayed | ☐ |
| 3 | View PM metrics | Metrics render | ☐ |

---

## Edge Cases & Regression

### Test E.1 — Session & Auth Edge Cases

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Open two browser tabs with different users (incognito) | Each sees own data | ☐ |
| 2 | Let session expire → try action | Redirected to login, no data corruption | ☐ |
| 3 | Login → logout → login as different user | Clean switch, no stale data | ☐ |

### Test E.2 — Demo ↔ Real Workspace Boundary

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Create a task in Demo Mode | Task only in sandbox | ☐ |
| 2 | Switch to My Workspace | Demo task NOT visible here | ☐ |
| 3 | Create a task in My Workspace | Task only in real workspace | ☐ |
| 4 | Switch to Demo Mode | Real workspace task NOT visible here | ☐ |

### Test E.3 — Idempotent Setup

| # | Step | Expected | Pass? |
|---|------|----------|-------|
| 1 | Run `python manage.py setup_test_environment` again | All output says [EXISTS]/[OK] | ☐ |
| 2 | Verify no duplicate boards, memberships, or sandboxes | DB state unchanged | ☐ |
| 3 | Run `python manage.py populate_all_demo_data` again | No duplicate tasks created | ☐ |

---

## Bug Report Template

When a test fails, record it here:

| Test ID | Summary | Steps to Reproduce | Expected | Actual | Severity |
|---------|---------|---------------------|----------|--------|----------|
| | | | | | |

---

## Sign-Off

| Day | Tester | Date | Passed | Failed | Blocked | Notes |
|-----|--------|------|--------|--------|---------|-------|
| Day 1 | | | /22 | | | |
| Day 2 | | | /42 | | | |
| Total | | | /64+ | | | |
