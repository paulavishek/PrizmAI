Shadow Board: The Parallel Universe Simulator 🌌
Run your project in multiple parallel realities simultaneously
Don't just simulate scenarios—maintain them as living alternatives:
Branching Project Realities: Like Git branches for project plans. Create "Branch A: Hire 3 contractors" and "Branch B: Delay launch 2 weeks" as parallel running simulations
Reality Merge Conflicts: When branches diverge significantly, AI highlights where they conflict (resource contention, stakeholder confusion) and suggests merge strategies
Quantum Standups: Daily updates apply across all active branches simultaneously—see how the same progress affects different timeline realities
The Wow: "Schrödinger's project management—every possibility exists until you commit."


We already have single-scenario simulation. The Shadow Board takes this further — instead of simulating one scenario and discarding it, we save multiple scenarios as living, parallel "branches" that keep updating as your real project progresses.


The Plan: Shadow Board in 4 stages:

Stage 1 — Branch Creation (builds on your Saved Scenarios)
The user takes any What-If scenario they've already saved and "promotes" it into a full Shadow Branch. Each branch stores a complete snapshot of the project state — all the slider values, the feasibility score, the projected timeline — frozen at the moment of branching.
Stage 2 — Living Simulations
This is the key new idea. Unlike a saved scenario that just sits there, a Shadow Branch stays alive. Every time real tasks are completed, team members are added, or deadlines shift on the real board, all active branches automatically recalculate their projected outcomes. The branch stays relevant as the project evolves.
Stage 3 — Quantum Standups
A new daily summary view that shows: "Here's what happened today on the real board — and here's how it changed each of your branches." The PM can see at a glance whether real progress is making Branch A more or less viable compared to Branch B.
Stage 4 — Merge Conflict Detector + Commit
When two branches contradict each other (e.g. Branch A hires people while Branch C cuts budget — they can't both be true), the system flags the conflict. When the PM is ready to commit to a decision, they "merge" that branch into reality and the other branches are archived with a log entry.



Technical Prompt for Claude:

You are helping me build a new feature called "Shadow Board" into an existing Django 5.2 web application called PrizmAI — an AI-powered project management platform. The app uses Google Gemini API, Django REST Framework, Django Channels (WebSockets), Celery for async tasks, Redis for caching, and a PostgreSQL/SQLite database. The frontend uses Bootstrap 5 with vanilla JavaScript.
Context on what already exists:
The app already has a "What-If Scenario Analyzer" (/boards/<id>/what-if/) with three sliders (Add/Remove Tasks ±20, Change Team Size ±5, Shift Deadline ±8 weeks), an "Analyze Impact" button that calls Gemini and returns a feasibility score (0–100), detected conflicts, before/after comparison, and a "Saved Scenarios" section that persists named scenarios to the database.
It also has a "Triple Constraint" dashboard (/boards/<id>/triple-constraint/) showing live Scope, Cost, and Time metrics with a built-in what-if simulator.
What I want to build — Shadow Board (Parallel Universe Simulator):
Shadow Board lets users "promote" any saved What-If scenario into a living, parallel branch of the project. Unlike a static saved scenario, each branch stays alive — it automatically recalculates its projected outcome every time real progress is made on the actual board. Multiple branches can run simultaneously so a PM can compare "hire 3 contractors" vs "delay launch 2 weeks" vs "cut 5 tasks" side-by-side, with all three updating in real time.
Please build the following:
1. Database models (models.py)

ShadowBranch: fields for board (FK), name, description, created_by, created_at, status (choices: active, archived, committed), source_scenario (nullable FK to existing SavedScenario), branch_color (hex string for UI color coding), is_starred (boolean).
BranchSnapshot: fields for branch (FK), captured_at, scope_delta (integer), team_delta (integer), deadline_delta_weeks (integer), feasibility_score (integer 0–100), projected_completion_date, projected_budget_utilization, conflicts_detected (JSONField), gemini_recommendation (TextField).
BranchDivergenceLog: records when real board progress causes a branch's feasibility score to change by more than 5 points — fields: branch, logged_at, old_score, new_score, trigger_event (text description of what changed).

2. Views and URLs

shadow_board_list view at /boards/<id>/shadow/ — shows all active branches as cards in a side-by-side comparison layout.
create_branch view — form to name a branch and optionally link it to an existing saved scenario; pre-fills slider values if linked.
branch_detail view at /boards/<id>/shadow/<branch_id>/ — shows the full simulation detail for one branch including its snapshot history as a mini timeline.
recalculate_branch Celery task — triggered whenever a task is completed, a team member is added/removed, or the board deadline changes. Re-runs the feasibility calculation for all active branches of that board and logs divergences.
commit_branch view — marks one branch as committed, archives all others, and creates an audit log entry. Requires a confirmation step.
merge_conflict_check API endpoint — given two branch IDs, returns a JSON list of detected conflicts between them (e.g. one adds budget, another removes it — flag as contradictory).

3. UI Templates

Shadow Board list page: a clean card grid, each card showing branch name, color indicator, feasibility score as a large number with a colored badge (green ≥70, amber 50–69, red <50), projected completion date, and a sparkline of feasibility score history (last 7 snapshots). Include a "Compare" toggle that when two cards are selected, shows a side-by-side diff table below.
A "Quantum Standup" section at the top of the list page: a collapsible panel showing "Today's real progress" (tasks completed today) and "How it affected your branches" (a compact table showing each branch's score change today with a ▲/▼ delta indicator).
Add a "Shadow Board" button to the existing AI Tools right-hand panel on the Kanban board view (next to What-If and Pre-Mortem).

4. Integration points

When a user saves a scenario in the existing What-If Analyzer, add a "Promote to Shadow Branch" button that calls create_branch pre-filled with that scenario's values.
Use Django signals (post_save on Task completion, board membership changes, and deadline updates) to trigger the recalculate_branch Celery task automatically.
Cache each branch's latest snapshot in Redis with a 15-minute TTL using the existing caching patterns in the codebase.

5. Constraints and style

Follow existing PrizmAI code patterns: class-based views where the codebase uses them, @login_required on all views, existing Bootstrap 5 card/badge styling, and the existing AI Tools right-panel pattern.
Keep Gemini API calls in the Celery worker, not in the request cycle.
All new URLs should be registered in the existing urls.py under the boards/ namespace.
Use the existing AuditLog model for the commit action.
Please begin with the models, then the Celery task, then the views, then the templates.


## Plan: Shadow Board — Parallel Universe Simulator

Here's your comprehensive implementation plan for the Shadow Board feature:

### Overview
Build a "living simulation" system where project managers promote What-If scenarios into parallel execution branches that auto-recalculate as real project changes occur. Core components: 3 new Django models, Celery async tasks triggered by signals, and a card-based UI integrated into the AI Tools panel.

---

### Phase 1: Database Models → `kanban/shadow_models.py`
- **ShadowBranch**: board (FK), name, description, created_by, status (active/archived/committed), source_scenario (FK to WhatIfScenario), branch_color (hex), is_starred
- **BranchSnapshot**: branch (FK), captured_at, scope_delta, team_delta, deadline_delta_weeks (int), feasibility_score (int 0–100), projected_completion_date, projected_budget_utilization, conflicts_detected (JSON), gemini_recommendation
- **BranchDivergenceLog**: branch (FK), logged_at, old_score, new_score, trigger_event

### Phase 2: Celery Tasks → `kanban/tasks/shadow_branch_tasks.py`
- **recalculate_branches_for_board** task: Triggered by signals, re-runs WhatIfEngine.simulate() for each active branch, scales feasibility 0–1 → 0–100, logs divergences (delta > 5 points), creates snapshot, caches branch snapshot in Redis (15 min TTL)
- Helper function: scale_feasibility() and extract_branch_params()

### Phase 3: Views & API → `kanban/shadow_views.py`
1. **ShadowBoardListView** — GET `/boards/<board_id>/shadow/` → shows all branches as cards + Quantum Standup panel (today's progress + branch deltas)
2. **CreateBranchView** — POST to create branch, optionally pre-fill from saved scenario
3. **BranchDetailView** — GET `/boards/<board_id>/shadow/<branch_id>/` → snapshot history timeline, divergence log
4. **CommitBranchView** — POST to mark branch committed, archive others, create audit log
5. **MergeConflictCheckAPI** — GET `/api/boards/<board_id>/shadow/conflicts/?branch_a=id1&branch_b=id2` → returns contradictory parameters
6. **PromoteScenarioView** — POST to convert What-If scenario to Shadow Branch
- Register 6 new URL patterns in urls.py

### Phase 4: Templates & Frontend
- **shadow_board_list.html**: Quantum Standup section (collapsible), branch card grid (name, color, feasibility badge, sparkline), compare toggle for diff table
- **branch_detail.html**: Latest projection, snapshot history, divergence log
- **create_branch_modal.html**: Form with name, description, scenario selector, color picker
- **Update board_detail.html**: Add "Shadow Board" tile to AI Tools offcanvas → `/boards/<board_id>/shadow/`
- **Update whatif_dashboard.html**: Add "Promote to Shadow Branch" button to saved scenarios
- **static/js/shadow_board.js**: Compare checkbox logic, sparkline rendering, AJAX calls

### Phase 5: Integration Points
1. **Django Signals** (add to signals.py):
   - Task post_save (if `_just_completed=True`) → recalculate branches with event "Task XYZ completed"
   - Board pre_save (if `project_deadline` changed) → recalculate with event "Deadline changed"
   - BoardMembership post_save/delete → recalculate with event "Team membership changed"

2. **What-If integration**: Promote button in whatif_dashboard.html calls promote_scenario endpoint

3. **Redis caching**: Branch snapshot cached as `branch_snapshot:{branch_id}` with 15-min TTL

4. **AuditLog integration**: CommitBranchView creates SystemAuditLog record with action='branch.committed'

---

### Decisions Made
✅ Feasibility: 0–100 integer (scaled from 0–1 float)  
✅ Snapshots: Created only on signal triggers (lean approach)  
✅ Quantum Standup: Shows tasks + changes that triggered recalculation  
✅ Compare view: All fields (scope_delta, team_delta, deadline_delta_weeks, feasibility, projections)  
✅ Conflict detection: Parameter-level contradictions only (e.g., +team vs -team)  
✅ Branch colors: User selects from predefined palette at creation  

---

### Files to Create/Modify

**Create (7 new files):**
- `kanban/shadow_models.py` — Models
- `kanban/shadow_views.py` — Views & API
- `kanban/tasks/shadow_branch_tasks.py` — Celery tasks
- `templates/kanban/shadow_board_list.html`
- `templates/kanban/branch_detail.html`
- `static/js/shadow_board.js`
- `tests/test_shadow_board.py` — Tests

**Modify (5 existing files):**
- urls.py — Add 6 URL patterns
- signals.py — Add 3 signal handlers
- board_detail.html — Add Shadow Board tile
- whatif_dashboard.html — Add Promote button

---

### Verification Steps
**Automated**: Unit tests for model creation, branch recalculation, audit logging, conflict detection  
**Manual**:
1. Promote scenario to branch → verify it appears with correct slider values
2. Complete task on real board → verify all branches recalculate  
3. Check branch detail → verify latest snapshot & divergence log  
4. Create 2 conflicting branches → verify merge_conflict_check flags contradictions  
5. Commit branch → verify committed/archived states & audit log  
6. Verify Redis caching: `redis-cli GET "branch_snapshot:{id}"` → should return JSON

---

### Considerations
- **Sparkline library**: Ensure Chart.js or similar is already in PrizmAI frontend (or add to base.html)
- **AI call frequency**: Current plan doesn't re-call Gemini on every branch recalc (to avoid rate-limiting); stores original `gemini_recommendation` from source scenario
- **Performance at scale**: With 50+ branches, consider debouncing recalculations (5–10 sec batch window) or rate-limiting Celery task priority to avoid overwhelming worker queue

---

**Ready to proceed with implementation?** The plan is saved at `/memories/session/plan.md` and covers all requirements from your technical prompt with clear dependencies and integration points.