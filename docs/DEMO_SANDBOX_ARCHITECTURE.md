# PrizmAI Demo Sandbox — Architecture, Issues & Resolution Guide

> **Author:** AI-assisted audit — April 2026  
> **Scope:** Complete reference for the Demo Sandbox subsystem: architecture, data isolation, bug history, fixes applied, and enterprise scalability analysis.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Data Model](#3-data-model)
4. [Sandbox Lifecycle](#4-sandbox-lifecycle)
5. [Data Isolation Design](#5-data-isolation-design)
6. [Issues Found & Fixes Applied](#6-issues-found--fixes-applied)
7. [Files Modified](#7-files-modified)
8. [Data Cleanup Performed](#8-data-cleanup-performed)
9. [Enterprise Scalability Analysis](#9-enterprise-scalability-analysis)
10. [Recommendations for Improvement](#10-recommendations-for-improvement)
11. [Testing Checklist](#11-testing-checklist)

---

## 1. Overview

The Demo Sandbox allows any authenticated user to explore PrizmAI's full feature set — boards, tasks, missions, strategies, goals, budgets, analytics, messaging, wiki, knowledge graph, conflict detection, and more — without affecting their real workspace data. Each user gets a **private, persistent copy** of the demo template boards that they can freely edit, reset, or delete.

### Key Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Immutable templates** | Template boards (`is_official_demo_board=True`) are never modified by user actions |
| **Per-user isolation** | Each user's sandbox is an independent deep copy; no user can see another user's sandbox |
| **Demo/real separation** | Demo data and real workspace data never mix in any view, API, or query |
| **Persistent sandboxes** | Sandboxes survive across sessions — users can re-enter demo mode at any time |
| **Non-destructive toggle** | Entering/leaving demo mode switches context without deleting anything |

---

## 2. Architecture

### 2.1 Three-Tier Board Classification

```
┌──────────────────────────────────────────────────────────────────┐
│                     TEMPLATE LAYER                                │
│  Board.is_official_demo_board = True                              │
│  Board.is_seed_demo_data = True                                   │
│  Immutable source of truth.  Never shown directly to users.       │
│  Contains: 36 tasks, 4 columns, 15 labels, 53 comments,          │
│            3 demo persona memberships                             │
└──────────────────────────────────┬───────────────────────────────┘
                                   │ _duplicate_board()
                    ┌──────────────┴──────────────┐
                    ▼                              ▼
┌──────────────────────────┐   ┌──────────────────────────┐
│   USER A's SANDBOX        │   │   USER B's SANDBOX        │
│  is_sandbox_copy = True   │   │  is_sandbox_copy = True   │
│  owner = User A           │   │  owner = User B           │
│  cloned_from = Template   │   │  cloned_from = Template   │
│  Fully editable           │   │  Fully editable           │
│  Isolated from User B     │   │  Isolated from User A     │
└──────────────────────────┘   └──────────────────────────┘
```

### 2.2 Organization & Workspace Switching

When a user enters demo mode, their profile switches to the demo organization:

```
REAL MODE                              DEMO MODE
─────────                              ─────────
profile.organization = "User's Org"    profile.organization = demo_org (is_demo=True)
profile.active_workspace = real_ws     profile.active_workspace = demo_ws
profile.is_viewing_demo = False        profile.is_viewing_demo = True
```

This org/workspace switch is the mechanism that drives all downstream query scoping. When `is_viewing_demo=True`, every view and helper returns only sandbox/demo data. When `False`, only real workspace data is returned.

### 2.3 Demo Personas

Three synthetic users serve as team members across all sandbox boards:

| Username | Email | Role |
|----------|-------|------|
| `alex_chen_demo` | `alex.chen@demo.prizmai.local` | Member |
| `sam_rivera_demo` | `sam.rivera@demo.prizmai.local` | Member |
| `jordan_taylor_demo` | `jordan.taylor@demo.prizmai.local` | Member |

These personas are identified by their `@demo.prizmai.local` email domain. This identifier is used as the authoritative check when deciding which memberships to copy during board duplication.

---

## 3. Data Model

### 3.1 Core Models

#### `DemoSandbox` (OneToOne → User)
| Field | Type | Purpose |
|-------|------|---------|
| `user` | OneToOneField(User) | Owner of the sandbox |
| `created_at` | DateTimeField | When sandbox was provisioned |
| `last_reset_at` | DateTimeField | Timestamp of last reset |
| `reassigned_tasks` | JSONField | Maps task IDs → original assignee IDs |

#### Board Flags
| Flag | Meaning |
|------|---------|
| `is_official_demo_board` | Immutable template board — never shown to users directly |
| `is_sandbox_copy` | User's personal editable copy |
| `is_seed_demo_data` | Data loaded from the seed management command |
| `cloned_from` | FK to the template board this was cloned from |
| `owner` | The user who owns this sandbox board |

#### UserProfile Flags
| Flag | Meaning |
|------|---------|
| `is_viewing_demo` | True when user is in demo mode |
| `active_workspace` | Current workspace (demo or real) |
| `organization` | Temporarily switched to demo org during demo mode |

### 3.2 Models Duplicated During Provisioning

The `_duplicate_board()` function deep-copies the following per template board:

**Board-level:** Board, BoardMembership (demo personas only), TaskLabel, Column  
**Task-level:** Task, Comment, TaskActivity  
**Budget & Tracking:** ProjectBudget, TaskCost, TimeEntry, ProjectROI  
**Analytics:** TeamVelocitySnapshot, BurndownPrediction, BurndownAlert, SprintMilestone  
**Skills:** TeamSkillProfile, SkillGap, SkillDevelopmentPlan  
**Scope:** ScopeChangeSnapshot, ScopeCreepAlert  
**Retrospectives:** ProjectRetrospective, LessonLearned, ImprovementMetric, RetrospectiveActionItem, RetrospectiveTrend  
**AI Coaching:** CoachingSuggestion, PMMetrics  
**Stakeholders:** ProjectStakeholder, StakeholderTaskInvolvement, EngagementMetrics, StakeholderTag  
**Conflicts:** ConflictDetection, ConflictResolution, ConflictNotification, ResolutionPattern  
**Messaging:** ChatRoom, ChatMessage, TaskThreadComment  
**Knowledge:** ProjectKnowledgeBase, AITaskRecommendation  
**Decision Center:** DecisionItem  
**Wiki:** WikiLink  
**Commitments:** CommitmentProtocol + child models  

---

## 4. Sandbox Lifecycle

### 4.1 Provisioning Flow

```
User clicks "Try Demo"
       │
       ▼
POST /toggle-demo-mode/
       │
       ├─ Existing sandbox? ──YES──► _join_demo_org() → _reassign_tasks()
       │                              → set is_viewing_demo=True → redirect /dashboard/
       │
       └─ No sandbox ──► provision_sandbox_task.delay(user_id)
                                │
                                ▼
                         Celery Worker (or sync fallback)
                                │
                         1. _purge_existing_sandbox()  (safety cleanup)
                         2. For each template board:
                            └─ _duplicate_board(template, user)
                         3. DemoSandbox.objects.create(user=user)
                         4. _join_demo_org(user)
                         5. _reassign_demo_tasks_to_user()
                         6. profile.is_viewing_demo = True
                         7. WebSocket → "Your workspace is ready!"
```

### 4.2 Leaving Demo Mode

```
POST /toggle-demo-mode/  (when is_viewing_demo=True)
       │
       ▼
1. _restore_demo_task_assignments()   ← undo the 3 task re-assignments
2. _leave_demo_org(user)              ← restore real org from user's workspace
3. profile.is_viewing_demo = False
4. profile.active_workspace = real_ws
5. Redirect to /dashboard/
                                       Note: sandbox boards are NOT deleted
```

### 4.3 Reset Flow

```
POST /demo/reset-mine/
       │
       ▼
1. _purge_existing_sandbox()          ← delete all sandbox boards + DemoSandbox record
2. provision_sandbox_task(user_id, is_reset=True)
3. Fresh copy created from templates
```

### 4.4 URL Routes

| Route | View | Method | Purpose |
|-------|------|--------|---------|
| `/toggle-demo-mode/` | `views.toggle_demo_mode` | POST | Enter or leave demo mode |
| `/demo/start-experimenting/` | `sandbox_views.toggle_browsing` | POST | Switch from browse to edit mode |
| `/demo/reset-mine/` | `sandbox_views.reset_my_demo` | POST | Wipe and re-provision sandbox |
| `/sandbox/save/` | `sandbox_views.save_sandbox_board` | POST | Mark one board to survive deletion |
| `/sandbox/delete/` | `sandbox_views.delete_sandbox` | POST | Delete sandbox immediately |
| `/sandbox/status/` | `sandbox_views.sandbox_status` | GET | JSON status (polled every 60s) |
| `/sandbox/extend/` | `sandbox_views.extend_demo_session` | POST | Extend session (legacy, max 3x) |

---

## 5. Data Isolation Design

### 5.1 Centralized Query Helpers

All data-fetching views use three centralized helpers in `kanban/utils/demo_protection.py`:

```python
get_user_boards(user)     # → Board queryset
get_user_missions(user)   # → Mission queryset
get_user_goals(user)      # → OrganizationGoal queryset
get_demo_workspace()      # → Workspace instance
```

Each helper follows the same decision tree:

```
is_viewing_demo?
  └─ YES → owner=user, is_sandbox_copy=True
  └─ NO  → active_workspace set?
              └─ YES → workspace=active_ws, exclude demo flags
              └─ NO  → org admin?
                         └─ YES → organization=org, exclude demo flags
                         └─ NO  → created_by|memberships, exclude demo flags
```

### 5.2 Critical Isolation Rules

1. **NEVER look up `demo_ws` from `profile.organization`** — during demo mode, the profile's org is the demo org. Use `get_demo_workspace()` which resolves from `Organization.objects.filter(is_demo=True)`.

2. **NEVER use `Q(created_by=user)` alone in demo mode** — this leaks real data into the demo workspace. Always combine with `is_sandbox_copy=True` or `is_official_demo_board=True`.

3. **In real mode, always exclude demo flags**: `is_official_demo_board=False, is_sandbox_copy=False`, and exclude `spectra_demo_*` session boards.

4. **Template boards must never gain real-user memberships** — `join_board()` and `add_board_member()` have explicit guards blocking this.

5. **Sandbox boards are private** — `join_board()` blocks joining another user's `is_sandbox_copy` board. `add_board_member()` blocks adding members to sandbox boards.

### 5.3 Self-Healing Middleware

`accounts/middleware.py → WorkspaceMiddleware._heal_workspace_state()` auto-repairs four corruption patterns on every request:

| Pattern | Repair |
|---------|--------|
| `is_viewing_demo=True` but `active_workspace` is not demo | Set `active_workspace = demo_ws` |
| `is_viewing_demo=True` but `organization` is not demo | Set `organization = demo_org` |
| `is_viewing_demo=False` but `active_workspace` is demo | Set `active_workspace = real_ws` |
| `is_viewing_demo=False` but `organization` is demo | Set `organization = real_org` |

### 5.4 Context Processor (`kanban/context_processors.py`)

The `demo_context()` processor runs on every request and adds to the template context:
- `is_viewing_demo` — boolean flag for template conditionals
- `sandbox_expires_at` — expiry datetime (legacy, no longer applicable)
- `user_workspaces` — list scoped to current org
- `real_workspaces` — non-demo workspaces (for "Back to My Workspace" button)
- `demo_workspace` — the demo workspace instance

### 5.5 View-Level Guards

Multiple views have explicit demo guards:

| View | File | Guard |
|------|------|-------|
| `board_detail()` | `kanban/views.py` | Redirects from template → user's sandbox copy |
| `join_board()` | `kanban/views.py` | Blocks joining template or another user's sandbox |
| `add_board_member()` | `kanban/views.py` | Blocks adding members to template boards |
| `organization_boards()` | `kanban/views.py` | Redirects to `board_list` when in demo mode |
| `dashboard()` | `kanban/views.py` | Uses `get_user_boards()` exclusively |
| `board_list()` | `kanban/views.py` | Org admin path scoped by organization |
| `goal_list()` / `mission_list()` | `kanban/mission_views.py` | Org admin path scoped |
| `BoardViewSet` / `TaskViewSet` | `api/v1/views.py` | Org admin path scoped |
| `messaging_hub()` | `messaging/views.py` | Uses `get_user_boards()` for message filtering |

---

## 6. Issues Found & Fixes Applied

### 6.1 Critical Issue — Cross-User Sandbox Data Leakage

**Symptom:** When testuser1 and testuser2 were both in demo mode, testuser1's sandbox showed testuser2's name as a board member. Clicking "Boards" in demo mode also showed real workspace boards from both users.

**Root Cause Chain:**

```
1. testuser1 invites testuser2 to a real board (normal flow)
2. Both users end up as members of the template board
   (via join_board() or demo_dashboard auto-grant — no template guard existed)
3. User provisions sandbox → _duplicate_board() copies ALL memberships
   from template, including the other real user
4. testuser2 is now a member of testuser1's sandbox board
5. get_user_boards() returns boards where user is member →
   testuser2 sees testuser1's sandbox board
```

**Fix:** `_duplicate_board()` now filters membership copies by `@demo.prizmai.local` email domain. Only demo personas are copied. The real user gets a fresh `owner` membership.

### 6.2 Org Admin Path — Global Data Exposure

**Symptom:** Users with org admin privileges saw ALL boards/missions/goals across ALL organizations when their view fell through to the org admin query path.

**Root Cause:** The org admin fallback path in `get_user_boards()`, `get_user_missions()`, `get_user_goals()`, and 6+ individual views used `Board.objects.filter(...)` without an `organization=org` constraint.

**Fix:** All org admin paths now filter by `organization=profile.organization`.

### 6.3 Template Board Membership Pollution

**Symptom:** Real users were found as members of the template board (`is_official_demo_board=True`), which should only have demo persona memberships.

**Root Cause:** Three code paths could add real users to template boards:
1. `join_board()` — no check for `is_official_demo_board`
2. `add_board_member()` — no check for `is_official_demo_board`
3. `demo_dashboard()` and `load_demo_data()` (old demo system) — auto-granted membership to demo org boards

**Fix:** Added explicit guards in `join_board()` and `add_board_member()` that reject requests targeting template or cross-user sandbox boards.

### 6.4 Spectra AI Using Template Boards Instead of Sandbox

**Symptom:** Spectra AI chat referenced template board data instead of the user's sandbox copy when in demo mode.

**Root Cause:** `get_accessible_boards_for_spectra()` used `is_official_demo_board=True` in the demo path instead of `is_sandbox_copy=True`.

**Fix:** Demo path now returns `Board.objects.filter(owner=user, is_sandbox_copy=True)`.

### 6.5 Messaging Unread Count Using Template Boards

**Symptom:** Unread message count was calculated against template boards (which have demo chat rooms) instead of the user's sandbox copies.

**Root Cause:** `get_unread_message_count()` had a 30-line inline query that checked membership on template boards.

**Fix:** Replaced with `get_user_boards(request.user)` centralized helper.

### 6.6 Wiki Form Board Dropdown Leakage

**Symptom:** Wiki link form showed boards from all users in the organization dropdown.

**Root Cause:** Inline query used `demo_boards | user_boards` union without proper scoping.

**Fix:** Replaced with `get_user_boards(user)` centralized helper.

### 6.7 Knowledge Graph Global Archive Check

**Symptom:** The "archived boards" indicator checked `Board.objects.filter(is_archived=True)` globally instead of scoping to the current user's boards.

**Fix:** Changed to `Board.objects.filter(id__in=user_board_ids, is_archived=True)`.

### 6.8 Dashboard & Board List Real Data in Demo Mode

**Symptom:** Dashboard showed all 6 real boards when in demo mode. The board_list page showed real boards via unscoped org admin paths.

**Root Cause:** Multiple inline queries using `Q(created_by=user)` without demo exclusion flags.

**Fix:** All dashboard and board_list paths now call `get_user_boards()`.

### 6.9 Hierarchy Navigator Contamination

**Symptom:** Missions, strategies, and boards in the hierarchy navigator showed real workspace data mixed with demo data.

**Root Cause:** `goal_list()` and `mission_list()` org admin paths used unscoped queries.

**Fix:** Org admin paths now filter by `Q(workspace__organization=org)`.

---

## 7. Files Modified

| # | File | Changes |
|---|------|---------|
| 1 | `kanban/utils/demo_protection.py` | Org admin fallback scoped by `organization` in all 3 helpers |
| 2 | `kanban/views.py` | `dashboard()`, `board_list()`, `organization_boards()` — org admin scoping; `join_board()` — template/sandbox guards; `add_board_member()` — template guard |
| 3 | `kanban/mission_views.py` | `goal_list()`, `mission_list()` — org admin paths scoped |
| 4 | `kanban/sandbox_views.py` | `_duplicate_board()` — only copy `@demo.prizmai.local` memberships |
| 5 | `api/v1/views.py` | `BoardViewSet.get_queryset()`, `TaskViewSet.get_queryset()` — org admin scoped |
| 6 | `messaging/views.py` | `messaging_hub()` — org admin scoped; `get_unread_message_count()` — centralized helper |
| 7 | `ai_assistant/utils/rbac_utils.py` | `get_accessible_boards_for_spectra()` — demo path returns sandbox copies |
| 8 | `wiki/forms/__init__.py` | Board dropdown uses `get_user_boards()` |
| 9 | `knowledge_graph/views.py` | `archived_exists` scoped to user's boards |

---

## 8. Data Cleanup Performed

After applying code fixes, existing corrupted data was cleaned up:

```
Template Board 1 (Software Development):
  REMOVED: testuser1 (paul.biotech10@gmail.com) — real user membership
  REMOVED: testuser2 (avip3310@gmail.com) — real user membership
  KEPT:    jordan_taylor_demo, sam_rivera_demo, alex_chen_demo

Sandbox Board 71 (testuser1's copy):
  REMOVED: testuser2 (avip3310@gmail.com) — cross-user membership
  KEPT:    testuser1 (owner) + 3 demo personas

Sandbox Board 44 (testuser2's copy):
  Already clean — testuser2 (owner) + 3 demo personas
```

### Cleanup Script (for future use)

```python
# Run from Django shell: python manage.py shell
from kanban.models import Board, BoardMembership
from django.db.models import F

# Step 1: Remove real users from template boards
BoardMembership.objects.filter(
    board__is_official_demo_board=True
).exclude(
    user__email__contains='@demo.prizmai.local'
).delete()

# Step 2: Remove cross-user members from sandbox boards
BoardMembership.objects.filter(
    board__is_sandbox_copy=True
).exclude(
    user__email__contains='@demo.prizmai.local'
).exclude(
    user=F('board__owner')
).delete()
```

---

## 9. Enterprise Scalability Analysis

### 9.1 Current State

| Metric | Value |
|--------|-------|
| Template boards | 1 |
| Objects per template board | ~36 tasks, 4 columns, 15 labels, 53 comments, 3 memberships |
| Objects duplicated per user | ~110+ rows (tasks + comments + labels + columns + memberships + related models) |
| Active sandboxes | 2 (testuser1, testuser2) |

### 9.2 Scalability Projection

#### Scenario: 100 users, 6 template boards, ~200 tasks per board

| Resource | Calculation | Total |
|----------|-------------|-------|
| Sandbox boards | 100 users × 6 boards | **600 boards** |
| Tasks | 100 × 6 × 200 | **120,000 tasks** |
| Comments (avg 1.5/task) | 120,000 × 1.5 | **180,000 comments** |
| Labels (avg 15/board) | 600 × 15 | **9,000 labels** |
| Columns (avg 5/board) | 600 × 5 | **3,000 columns** |
| Board Memberships | 600 × 4 (owner + 3 personas) | **2,400 memberships** |
| **Total rows created** | | **~334,400 rows** |

#### Scenario: 1,000 users, 6 template boards, ~200 tasks per board

| Resource | Total |
|----------|-------|
| Sandbox boards | **6,000** |
| Tasks | **1,200,000** |
| Total rows | **~3.3 million** |

### 9.3 Can It Scale? — Honest Assessment

#### What Works Well at Scale

1. **Query isolation is sound.** Every query path uses `owner=user, is_sandbox_copy=True` for demo mode. This is a simple indexed filter — Django ORM will generate efficient SQL even with millions of rows, provided proper indexes exist.

2. **No cross-user joins.** Sandbox queries never need to join across users. Each user's sandbox is self-contained.

3. **Toggle is O(1).** Entering/leaving demo mode just flips a boolean and swaps org/workspace references. No data copying on re-entry.

4. **Reset is bounded.** Resetting deletes only the user's own sandbox boards (typically 1–6 boards) and re-provisions.

#### What Needs Attention for Enterprise Scale

##### 9.3.1 Provisioning Time (MODERATE RISK)

**Current:** `_duplicate_board()` creates each row individually in a loop — one `INSERT` per task, comment, label, etc. For 1 template board with 36 tasks, this is fast (~2–5 seconds). For 6 boards with 200 tasks each = 1,200 tasks + 1,800 comments = ~3,000+ individual INSERTs.

**At scale:** With 1,000 concurrent provisioning requests (e.g., onboarding event), the database will see 3,000,000 individual INSERTs across all Celery workers.

**Recommendation:**
- Use `bulk_create()` for tasks, comments, labels, and columns instead of individual `.save()` calls.
- Batch the deep-copy into a single transaction per board using `transaction.atomic()`.
- Consider pre-generating sandbox snapshots and restoring from SQL dump for very large templates.
- **Expected improvement: 5–10x faster provisioning per user.**

##### 9.3.2 Database Storage (LOW RISK)

At 3.3 million rows for 1,000 users: this is well within PostgreSQL's comfort zone (PostgreSQL handles billions of rows routinely). SQLite (current dev DB) would struggle beyond ~100 users — **production must use PostgreSQL**.

**Recommendation:** Ensure indexes exist on:
- `Board.owner_id` + `Board.is_sandbox_copy`
- `Board.is_official_demo_board`
- `Task.column_id` (for board → tasks joins)
- `BoardMembership.board_id` + `BoardMembership.user_id`

##### 9.3.3 Sandbox Cleanup / Garbage Collection (MODERATE RISK)

**Current:** Sandboxes are persistent (no expiry). Over time, inactive users' sandboxes accumulate, consuming storage.

**Recommendation:**
- Add a periodic Celery task that marks sandboxes as `stale` if the user hasn't entered demo mode in 30+ days.
- Optionally, auto-delete stale sandboxes after 90 days (with an email warning).
- Track `last_accessed_at` on `DemoSandbox` to measure usage.

##### 9.3.4 Multiple Boards per Workspace (LOW RISK)

**Current:** Only 1 template board exists. The architecture supports N template boards — `provision_sandbox_task` iterates over `Board.objects.filter(is_official_demo_board=True)` and duplicates each one.

**At scale:** With 6 template boards, provisioning takes 6x longer (linear). This is acceptable for async Celery provisioning but may be noticeable for sync fallback (when Redis is down).

**Recommendation:** If template count exceeds 10, consider parallelizing `_duplicate_board()` calls across Celery subtasks.

##### 9.3.5 Demo Persona Scalability (LOW RISK)

**Current:** 3 demo personas are added to every sandbox board. This is O(1) per persona per board — negligible overhead.

**At scale:** Even at 6,000 boards × 3 personas = 18,000 membership rows. Trivial.

##### 9.3.6 Concurrent Demo Mode Toggle (LOW RISK)

**Current:** `toggle_demo_mode()` modifies `UserProfile.is_viewing_demo`, `organization`, and `active_workspace`. These are per-user fields — no contention across users.

**At scale:** 1,000 users toggling simultaneously would cause 1,000 individual `UPDATE` statements on `UserProfile`. This is well within DB capacity.

### 9.4 Enterprise Scalability Verdict

| Aspect | Ready for Enterprise? | Action Needed |
|--------|-----------------------|---------------|
| Data isolation | **YES** | None — centralized helpers with proper scoping |
| Query performance | **YES** (with PostgreSQL) | Add composite indexes |
| Provisioning throughput | **NEEDS WORK** | Switch to `bulk_create()`, add transaction wrapping |
| Storage management | **NEEDS WORK** | Add stale sandbox garbage collection |
| Multi-board templates | **YES** | Works out of the box, linear scaling |
| Concurrent users | **YES** | No shared state, no contention |
| Multi-workspace orgs | **YES** | Workspace scoping already architecture-aware |

**Bottom line:** The current sandbox architecture can scale to **hundreds of users** without code changes (assuming PostgreSQL). To reach **thousands of concurrent users**, implement `bulk_create()` optimization and stale sandbox cleanup. The data isolation model is architecturally sound and does not require redesign for enterprise scale.

---

## 10. Recommendations for Improvement

### 10.1 High Priority

#### A. Performance: Use `bulk_create()` in `_duplicate_board()`

Replace the per-row `.save()` calls with batched inserts:

```python
# Current (slow):
for task in template_tasks:
    new_task = Task(...)
    new_task.save()

# Recommended (fast):
new_tasks = [Task(...) for task in template_tasks]
Task.objects.bulk_create(new_tasks, batch_size=500)
```

This requires a two-pass approach (first create parents, then children with correct FKs) but yields 5–10x faster provisioning.

#### B. Add a Management Command for Data Cleanup

Create `manage.py cleanup_sandbox_memberships` that runs the cleanup script from Section 8 on demand. Schedule it as a periodic Celery task.

#### C. Add `last_accessed_at` to DemoSandbox

Track when the user last entered demo mode. This enables:
- Analytics on demo engagement
- Stale sandbox identification
- Automated cleanup after 90 days of inactivity

### 10.2 Medium Priority

#### D. Database Indexes for Production

```python
# In a migration:
class Meta:
    indexes = [
        models.Index(fields=['owner', 'is_sandbox_copy'], name='idx_board_sandbox_owner'),
        models.Index(fields=['is_official_demo_board'], name='idx_board_template'),
    ]
```

#### E. Sandbox Provisioning Progress Caching

Currently, provisioning progress is streamed via WebSocket (Django Channels). If the user refreshes the page mid-provisioning, progress is lost. Consider caching provisioning state in Redis with a TTL so the frontend can recover.

#### F. Template Board Versioning

When template content is updated (e.g., new seed tasks), existing sandboxes become stale. Consider:
- A `template_version` field on Board
- A `sandbox_version` field on DemoSandbox
- Warning the user when their sandbox is based on an older template version
- One-click "Update my sandbox" that preserves user edits and adds new template content

### 10.3 Low Priority

#### G. Rate-Limit Sandbox Reset

Currently unlimited resets. For abuse prevention, consider limiting to 5 resets per 24 hours.

#### H. Sandbox Analytics Dashboard (Admin)

Build an admin view showing:
- Total active sandboxes
- Provisioning success/failure rate
- Average provisioning time
- Stale sandbox count
- Template board utilization

#### I. Pre-Generated Sandbox Pool

For very high-traffic scenarios (e.g., product launch), pre-generate a pool of unassigned sandboxes and assign them to users on demand, avoiding the provisioning delay entirely.

---

## 11. Testing Checklist

Use this checklist when making changes to the sandbox system:

### Isolation Tests

- [ ] **Demo → Real separation:** Enter demo mode. Verify only sandbox boards appear in dashboard, board list, sidebar, hierarchy navigator.
- [ ] **Real → Demo separation:** Leave demo mode. Verify no sandbox or template boards appear anywhere.
- [ ] **Cross-user isolation:** With two users in demo mode simultaneously, verify User A cannot see User B's sandbox boards, tasks, or memberships.
- [ ] **Template immutability:** Verify template board memberships contain ONLY demo personas (`@demo.prizmai.local`).
- [ ] **Org admin path:** If user is org admin, verify board/mission/goal queries scope by `organization=org`, not global.

### Lifecycle Tests

- [ ] **First-time provisioning:** New user enters demo mode → sandbox created → correct boards, tasks, memberships.
- [ ] **Re-entry:** User leaves and re-enters demo mode → same sandbox boards appear, no duplication.
- [ ] **Reset:** User resets sandbox → old boards deleted, fresh copy from templates.
- [ ] **Browse → Edit toggle:** User starts in browsing mode → "Start Experimenting" → editing enabled.

### Feature Integration Tests

- [ ] **Spectra AI:** In demo mode, Spectra references sandbox boards (not templates).
- [ ] **Messaging:** Unread count uses sandbox board chat rooms, not template chat rooms.
- [ ] **Wiki:** Wiki link form dropdown shows only user's boards (sandbox or real, depending on mode).
- [ ] **Knowledge Graph:** Archived board check scoped to user's boards.
- [ ] **Decision Center:** Briefings generated for sandbox boards after provisioning.
- [ ] **Calendar:** Calendar events scoped to sandbox boards in demo mode.

### Scalability Tests

- [ ] **Multi-board provisioning:** With N template boards, verify all N are duplicated correctly.
- [ ] **Concurrent provisioning:** Trigger provisioning for multiple users simultaneously. Verify no cross-contamination.
- [ ] **Large template:** Add 200+ tasks to template board. Verify provisioning completes successfully (may be slow with current per-row saves).

### Cleanup Verification Script

Run after any sandbox-related changes:

```python
python manage.py shell -c "
from kanban.models import Board, BoardMembership
from django.db.models import F

# Check 1: No real users on template boards
real_on_tpl = BoardMembership.objects.filter(
    board__is_official_demo_board=True
).exclude(user__email__contains='@demo.prizmai.local')
assert not real_on_tpl.exists(), f'FAIL: {real_on_tpl.count()} real users on template boards'

# Check 2: No cross-user members on sandbox boards
cross_user = BoardMembership.objects.filter(
    board__is_sandbox_copy=True
).exclude(user__email__contains='@demo.prizmai.local').exclude(user=F('board__owner'))
assert not cross_user.exists(), f'FAIL: {cross_user.count()} cross-user sandbox memberships'

print('ALL CHECKS PASSED')
"
```

---

## Appendix: Key File Reference

| File | Purpose |
|------|---------|
| `kanban/utils/demo_protection.py` | Centralized helpers: `get_user_boards()`, `get_user_missions()`, `get_user_goals()`, `get_demo_workspace()`, `is_demo_object()` |
| `kanban/sandbox_views.py` | `_duplicate_board()`, `_join_demo_org()`, `_leave_demo_org()`, `_purge_existing_sandbox()`, `toggle_browsing()`, `reset_my_demo()`, `sandbox_status()` |
| `kanban/views.py` | `toggle_demo_mode()`, `dashboard()`, `board_list()`, `board_detail()`, `join_board()`, `add_board_member()`, `organization_boards()` |
| `kanban/tasks/sandbox_provisioning.py` | `provision_sandbox_task()` — async Celery task for deep-copy provisioning |
| `kanban/context_processors.py` | `demo_context()` — template-level demo/real scoping |
| `accounts/middleware.py` | `WorkspaceMiddleware._heal_workspace_state()` — auto-repairs profile corruption |
| `kanban/mission_views.py` | `goal_list()`, `mission_list()` — hierarchy navigator with demo scoping |
| `api/v1/views.py` | `BoardViewSet`, `TaskViewSet` — REST API with demo scoping |
| `messaging/views.py` | `messaging_hub()`, `get_unread_message_count()` — messaging with demo scoping |
| `ai_assistant/utils/rbac_utils.py` | `get_accessible_boards_for_spectra()` — AI assistant board access |

---

*Last updated: April 9, 2026*
