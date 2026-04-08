# PrizmAI RBAC (Role-Based Access Control) — Complete Reference

> **Last updated:** April 9, 2026  
> **Scope:** My Workspace only — Demo Workspace bypasses all RBAC checks.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Technology Stack](#2-technology-stack)
3. [Roles & Permission Levels](#3-roles--permission-levels)
4. [Permission Rules Reference](#4-permission-rules-reference)
5. [Strategic Hierarchy & Access Flow](#5-strategic-hierarchy--access-flow)
6. [Org Admin Unification](#6-org-admin-unification)
7. [Spectra AI RBAC Integration](#7-spectra-ai-rbac-integration)
8. [Demo Workspace Bypass](#8-demo-workspace-bypass)
9. [Enforcement Patterns (Code Reference)](#9-enforcement-patterns-code-reference)
10. [Key Files Reference](#10-key-files-reference)
11. [Issues Found & Fixed](#11-issues-found--fixed)
12. [Feature-by-Feature RBAC Coverage](#12-feature-by-feature-rbac-coverage)
13. [Suggestions for Future Improvement](#13-suggestions-for-future-improvement)

---

## 1. Architecture Overview

PrizmAI implements a **multi-layered RBAC system** that operates at both the board level and the strategic hierarchy level (Goals → Missions → Strategies → Boards → Tasks).

### Core Principles

1. **Access flows DOWN automatically** — Owning a Goal grants automatic access to all Missions, Strategies, and Boards beneath it.
2. **Access never flows UP without an explicit invitation** — Board membership gives read-only visibility upward to the parent Goal, but never edit access.
3. **Demo workspaces are RBAC-exempt** — All permission checks are bypassed in the Demo workspace.
4. **Organization-scoped isolation** — An Org Admin of Organization A cannot access boards in Organization B, even with the same role.
5. **Defense in depth** — Multiple enforcement layers (view → service → model) ensure no single bypass compromises the system.

### Enforcement Layers

```
┌──────────────────────────────────────────────────────────────┐
│  Layer 1: URL/View Layer                                      │
│  @login_required + has_perm() / check_access_or_403()         │
├──────────────────────────────────────────────────────────────┤
│  Layer 2: django-rules Predicate Engine                       │
│  Evaluates predicates (is_org_admin | is_record_owner | ...)  │
├──────────────────────────────────────────────────────────────┤
│  Layer 3: Simple Access Helpers                               │
│  can_access_board(), can_manage_board(), can_modify_content() │
├──────────────────────────────────────────────────────────────┤
│  Layer 4: Demo Protection Middleware                          │
│  Prevents writes to seed demo data via pre_save signals       │
├──────────────────────────────────────────────────────────────┤
│  Layer 5: Organization Scoping                                │
│  Workspace isolation, org-based queryset filtering            │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Permission engine** | [django-rules](https://github.com/dfunckt/django-rules) | Declarative predicate-based permissions |
| **Predicate evaluation** | `request.user.has_perm('prizmai.xxx', obj)` | Object-level permission checks |
| **Group management** | Django Auth Groups (`OrgAdmin`) | Org Admin role via group membership |
| **Board-level access** | `BoardMembership` model | Owner / Member / Viewer roles |
| **Strategic access** | `StrategicMembership` model | Goal / Mission / Strategy roles |
| **Demo protection** | `pre_save` / `pre_delete` signals | Immutable seed data |
| **Workspace isolation** | `WorkspaceMiddleware` | Request-scoped workspace context |

---

## 3. Roles & Permission Levels

### Board-Level Roles (via `BoardMembership`)

| Role | View Board | Edit Tasks/Columns | Delete Board | Invite Members |
|------|:---:|:---:|:---:|:---:|
| **Owner** | ✅ | ✅ | ✅ | ✅ |
| **Member** | ✅ | ✅ | ❌ | ❌ |
| **Viewer** | ✅ | ❌ | ❌ | ❌ |

### Organization-Level Roles

| Role | How Determined | Scope |
|------|---------------|-------|
| **Org Admin** | `OrgAdmin` Django Group, OR `Organization.created_by`, OR `UserProfile.is_admin` | Full access to all boards/goals/missions/strategies within their org |
| **Regular User** | Default — not in any admin group | Access only to boards they are members of, and strategic objects they own or are invited to |

### Strategic Hierarchy Roles (via `StrategicMembership`)

- **Owner**: Full control + invite rights on the Goal/Mission/Strategy
- **Member**: Contribute/edit
- **Viewer**: Read-only

---

## 4. Permission Rules Reference

All permissions are defined in `kanban/permissions.py` using django-rules:

### Board Permissions

```
prizmai.view_board =
    is_org_admin | is_record_owner | is_ancestor_owner | has_board_membership | is_demo_board

prizmai.edit_board =
    is_org_admin | is_record_owner | is_ancestor_owner | is_board_member_role | is_board_owner_role | is_demo_board

prizmai.delete_board =
    is_org_admin | is_record_owner | is_ancestor_owner

prizmai.invite_board_member =
    is_org_admin | is_record_owner | is_ancestor_owner | is_board_owner_role
```

### Strategic Permissions

```
prizmai.view_goal =
    is_org_admin | is_record_owner | has_strategic_membership | is_descendant_board_member | is_demo_strategic_object

prizmai.edit_goal =
    is_org_admin | is_record_owner
    (Note: No is_ancestor_owner — Goal is the top level)

prizmai.view_mission =
    is_org_admin | is_record_owner | is_ancestor_owner | has_strategic_membership | is_descendant_board_member | is_demo_strategic_object

prizmai.edit_mission =
    is_org_admin | is_record_owner | is_ancestor_owner | has_strategic_membership

prizmai.view_strategy =
    is_org_admin | is_record_owner | is_ancestor_owner | has_strategic_membership | is_descendant_board_member | is_demo_strategic_object

prizmai.edit_strategy =
    is_org_admin | is_record_owner | is_ancestor_owner | has_strategic_membership
```

### Predicate Definitions

| Predicate | Logic |
|-----------|-------|
| `is_org_admin` | User is Org Admin AND belongs to the same org as the object |
| `is_record_owner` | User is the `owner` field on the object (falls back to `created_by`) |
| `is_ancestor_owner` | User owns any ancestor: Board → Strategy → Mission → Goal |
| `has_board_membership` | User has ANY `BoardMembership` on the board (any role) |
| `is_board_member_role` | User has specifically the `'member'` role on the board |
| `is_board_owner_role` | User has the `'owner'` role in `BoardMembership` |
| `has_strategic_membership` | User has a `StrategicMembership` on the Goal/Mission/Strategy |
| `is_descendant_board_member` | User is a member of ANY board under this Goal/Mission/Strategy |
| `is_demo_board` | Board has `is_official_demo_board=True` |
| `is_demo_strategic_object` | Object has `is_demo=True` or `is_seed_demo_data=True` |

---

## 5. Strategic Hierarchy & Access Flow

```
Organization
  └── OrganizationGoal       ← Only Org Admin can create/edit
       └── Mission            ← Org Admin or Goal Owner can create
            └── Strategy      ← Mission Owner+ can create
                 └── Board    ← Strategy Owner+ can create
                      └── Task
```

### Downward Access Flow (Automatic)

Owning a higher-level object automatically grants access to all descendants:

| If you own... | You get access to... |
|---------------|---------------------|
| Goal | All Missions, Strategies, Boards, and Tasks under it |
| Mission | All Strategies, Boards, and Tasks under it |
| Strategy | All Boards and Tasks under it |

This is implemented by the `is_ancestor_owner` predicate, which walks up the hierarchy from the target object checking ownership at each level.

### Upward Visibility (Read-Only)

Board membership grants **read-only visibility** upward:

- A Member of Board X can **view** (not edit) the Strategy, Mission, and Goal above Board X.
- This is implemented by the `is_descendant_board_member` predicate in `view_*` rules.
- The `edit_*` rules deliberately exclude `is_descendant_board_member`.

### Critical Design Decision: Goal Editing

`edit_goal` does NOT include `is_ancestor_owner` (there is no ancestor above a Goal). Only:
- The **Goal's owner/creator**, or
- An **Org Admin**

can edit a Goal. This is by design — Goals represent top-level organizational objectives.

---

## 6. Org Admin Unification

### The Problem (Pre-Fix)

PrizmAI had **three disconnected admin detection systems**:

1. **`OrgAdmin` Django Group** — Used by django-rules predicates
2. **`UserProfile.is_admin`** — Toggled via the Organization Members UI
3. **`Organization.created_by`** — Set during org creation

A user promoted via the UI (`is_admin=True`) would NOT be in the `OrgAdmin` Group, so django-rules predicates would deny them. The org creator might also not be in the group if they created the org before the group system existed.

### The Fix

1. **Canonical helper `is_user_org_admin(user)`** in `kanban/permissions.py` — Checks all three sources. Every permission check now routes through this.

2. **Group sync in `toggle_admin`** (`accounts/views.py`) — When `profile.is_admin` is toggled, the `OrgAdmin` Django Group is also added/removed.

3. **Auto-assignment during onboarding** — Org creators are automatically added to the `OrgAdmin` group during the commit and skip flows.

4. **Data migration `0118`** — Retroactively adds all existing org creators and `is_admin=True` users to the `OrgAdmin` group.

5. **20+ inline checks replaced** — All scattered `user.groups.filter(name='OrgAdmin').exists()` calls were replaced with `is_user_org_admin(user)`.

### Files Changed

- `kanban/permissions.py` — `is_user_org_admin()` helper + updated predicates
- `accounts/views.py` — `toggle_admin` group sync
- `kanban/onboarding_utils.py` + `kanban/onboarding_views.py` — Auto-group assignment
- `kanban/mission_views.py` — Goal creation + dead code removal
- `kanban/views.py` — Import flow auto-creates org + assigns group
- `kanban/simple_access.py`, `kanban/access_request_views.py`, `api/v1/views.py`, `ai_assistant/utils/rbac_utils.py`, `messaging/views.py`, `messaging/consumers.py` — Inline check replacement

---

## 7. Spectra AI RBAC Integration

The Spectra AI assistant has **6 layers of defense** to enforce RBAC:

### Defense Layers

| Layer | Location | What It Does |
|-------|----------|-------------|
| 1. **View layer** | `ai_assistant/views.py` | Board dropdown filters by `get_accessible_boards_for_spectra()`. `send_message()` checks `can_spectra_read_board()`. |
| 2. **Response gate** | `chatbot_service.py → get_response()` | If user has no read access, returns denial immediately without building context. |
| 3. **System prompt** | `chatbot_service.py → generate_system_prompt()` | RBAC context block injected into AI prompt. Anti-social-engineering rules prevent "I'm an admin" bypasses. |
| 4. **Conversation flow pre-checks** | `conversation_flow.py` | Permission checked before collecting data for task/automation flows. |
| 5. **Execution gate** | `conversation_flow.py → _execute_pending_action()` | Final permission check before executing a confirmed action. |
| 6. **Action service** | `action_service.py` | Each write method checks `can_spectra_write_board()`, management actions check `can_spectra_manage_board()`. |

### Spectra Permission Mapping

| Spectra Action | Required Level | Who Can |
|---------------|---------------|---------|
| Read board data | `can_spectra_read_board` | Owner, Member, Viewer |
| Create/edit tasks | `can_spectra_write_board` | Owner, Member |
| Manage automations | `can_spectra_manage_board` | Owner only |
| Non-member | Denied | Returns denial + access request option |

### Key File

`ai_assistant/utils/rbac_utils.py` — Centralized utilities:
- `get_user_board_role(user, board)` → `'owner'` / `'member'` / `'viewer'` / `None`
- `check_spectra_action_permission(user, board, action)` → `(allowed, denial_msg)`
- `ACTION_PERMISSION_MAP` — Maps each action to `'read'` / `'write'` / `'manage'`
- `build_rbac_context_for_prompt(user, board)` — Full system prompt RBAC block
- `get_accessible_boards_for_spectra(user, is_demo, org)` — RBAC-filtered board list

---

## 8. Demo Workspace Bypass

### How It Works

- Each organization has one demo `Workspace` with `is_demo=True`.
- `is_demo_context(request, board, workspace)` in `kanban/permissions.py` checks the current workspace.
- The `is_demo_board` and `is_demo_strategic_object` predicates are included in all `view_*` and `edit_*` rules.
- `@demo_write_guard` decorator on write endpoints prevents persistent modifications in demo mode.
- Demo data is protected at the model level via `pre_save` / `pre_delete` signals in `kanban/utils/demo_protection.py`.

### Detection Hierarchy

```python
is_demo_context(request, board=None, workspace=None):
    1. workspace.is_demo
    2. board.workspace.is_demo
    3. request.workspace.is_demo (set by WorkspaceMiddleware)
    4. user.profile.is_viewing_demo (fallback)
```

### What This Means for RBAC

- **My Workspace**: Full RBAC enforcement. Users only see/edit what they have permission for.
- **Demo Workspace**: All RBAC bypassed. Everyone can view and interact with all demo content.

---

## 9. Enforcement Patterns (Code Reference)

### Standard Patterns Used Across the Codebase

#### READ operations (HTML views)
```python
@login_required
def some_view(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    if not request.user.has_perm('prizmai.view_board', board):
        raise Http404
    # ... render template
```

#### WRITE operations (HTML views)
```python
@login_required
def some_view(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    if not request.user.has_perm('prizmai.edit_board', board):
        raise Http404
    # ... process POST
```

#### READ operations (API/AJAX)
```python
@login_required
def some_api(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    if not request.user.has_perm('prizmai.view_board', board):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    # ... return JSON
```

#### WRITE operations (API/AJAX)
```python
@login_required
def some_api(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    if not request.user.has_perm('prizmai.edit_board', board):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    # ... mutate and return JSON
```

#### List views (queryset filtering)
```python
@login_required
def board_list(request):
    boards = get_user_boards(request.user)  # RBAC-filtered queryset
    # ... render
```

#### Organization-scoped views (no board context)
```python
@login_required
def cemetery(request):
    user_org = getattr(getattr(request.user, 'profile', None), 'organization', None)
    if user_org:
        entries = CemeteryEntry.objects.filter(board__organization=user_org)
    else:
        entries = CemeteryEntry.objects.none()
```

#### Simple access helper (exit_protocol, stakeholders)
```python
from kanban.simple_access import check_access_or_403, check_management_or_403

@login_required
def some_view(request, board_id):
    board = get_object_or_404(Board, id=board_id)
    check_access_or_403(request.user, board)  # raises PermissionDenied
```

---

## 10. Key Files Reference

### Core RBAC Engine

| File | Purpose |
|------|---------|
| `kanban/permissions.py` | All django-rules predicates + permission rules + `is_user_org_admin()` + `is_demo_context()` |
| `kanban/simple_access.py` | `can_access_board()`, `can_manage_board()`, `can_modify_board_content()`, `check_access_or_403()` |
| `kanban/models.py` | `BoardMembership` (Owner/Member/Viewer), `StrategicMembership` (GenericFK) |
| `ai_assistant/utils/rbac_utils.py` | Spectra-specific RBAC utilities |

### Models with RBAC Significance

| Model | Key Fields |
|-------|-----------|
| `BoardMembership` | `board`, `user`, `role` (owner/member/viewer) — unique on `(board, user)` |
| `StrategicMembership` | `content_type`, `object_id`, `user`, `role` — GenericFK to Goal/Mission/Strategy |
| `Board` | `owner`, `created_by`, `organization`, `workspace`, `is_official_demo_board` |
| `OrganizationGoal` | `owner`, `created_by`, `organization`, `workspace`, `is_demo` |
| `Mission` | `owner`, `created_by`, `organization_goal` (FK), `is_demo` |
| `Strategy` | `owner`, `created_by`, `mission` (FK) |
| `Workspace` | `organization`, `created_by`, `is_demo` |

### Middleware & Utilities

| File | Purpose |
|------|---------|
| `accounts/middleware.py` | `WorkspaceMiddleware` — sets `request.workspace` |
| `kanban/utils/demo_protection.py` | Demo data protection signals + `get_user_boards()` helper |
| `kanban/decorators.py` | `@demo_write_guard`, `@demo_ai_guard` |

### View Files with RBAC Enforcement

| File | # of RBAC-protected endpoints |
|------|------------------------------|
| `kanban/views.py` | 60+ views |
| `kanban/api_views.py` | 50+ endpoints |
| `kanban/mission_views.py` | 28 views |
| `messaging/views.py` | 23 views |
| `kanban/budget_views.py` | 25 views |
| `kanban/stakeholder_views.py` | 16 views |
| `exit_protocol/views.py` | 16 views |
| `wiki/views.py` | 15 views |
| `wiki/api_views.py` | 8 endpoints |
| `knowledge_graph/views.py` | 6 views |
| `kanban/conflict_views.py` | 10 views |
| `decision_center/views.py` | 7 views |
| `kanban/calendar_views.py` | 7 views |
| `ai_assistant/views.py` | 23 views |
| `api/v1/views.py` | 14 endpoints |
| `kanban/access_request_views.py` | 8 views |

---

## 11. Issues Found & Fixed

### Audit #1 — Initial RBAC Rollout (April 2026)

**Problem:** ~50 views across the codebase had `"Access restriction removed"` comments where board membership checks had been stripped out (replaced with `pass`), leaving endpoints open to any authenticated user.

**Scope of fixes:**

| File | Endpoints Fixed |
|------|----------------|
| `kanban/api_views.py` | 28 — All AI, dependency, prediction, priority, skill, PDF endpoints |
| `kanban/views.py` | 17 — Labels, columns, export, file management, wizard, dependency views |
| `messaging/views.py` | 8 — Thread comments, message history, mark read, file operations |
| `knowledge_graph/views.py` | 3 — board_knowledge, add_manual_memory, deja_vu_check |
| `wiki/views.py` | 1 — delete_wiki_link |
| `wiki/api_views.py` | 3 — analyze_wiki_documentation, analyze_meeting_notes, create_tasks_from_analysis |
| `kanban/conflict_views.py` | 1 — get_conflict_notifications |
| `kanban/budget_views.py` | 3 — time_entry_create, quick_time_entry, delete_time_entry |
| `kanban/stakeholder_views.py` | 1 — check_board_access helper |

### Audit #2 — Comprehensive Re-Audit (April 9, 2026)

**Problem:** A deeper audit found 27 additional gaps across 6 files — a mix of completely missing checks, auth-only checks (no board permission), and hardcoded membership logic that bypassed the django-rules engine.

#### kanban/views.py — 6 gaps fixed

| View | Issue | Fix Applied |
|------|-------|------------|
| `add_gantt_milestone` | No board permission check — any authenticated user could create milestones on any board | Added `has_perm('prizmai.edit_board', board)` |
| `delete_gantt_milestone` | No board permission check — any authenticated user could delete milestones | Added `has_perm('prizmai.edit_board', board)` |
| `milestone_detail` | No permission check — information disclosure + unauthorized editing | Added `has_perm('view_board')` for GET, `has_perm('edit_board')` for POST |
| `board_calendar` | Hardcoded membership check bypassed Org Admin and ancestor owner rules | Replaced with `has_perm('prizmai.view_board', board)` |
| `update_task_progress` | No board permission check — any user could update task progress | Added `has_perm('prizmai.edit_board', board)` |
| `link_board_to_strategy_dashboard` | Hardcoded membership check | Replaced with `has_perm('prizmai.edit_board', board)` |

#### kanban/api_views.py — 9 gaps fixed

| Endpoint | Issue | Fix Applied |
|----------|-------|------------|
| `delete_phase` | Comment: "All restrictions removed" — completely open | Added `has_perm('prizmai.edit_board', board)` |
| `add_phase` | Same as above | Added `has_perm('prizmai.edit_board', board)` |
| `update_task_dates_api` | Auth-only check, no board permission | Added `has_perm('prizmai.edit_board', board)` |
| `reschedule_task_api` | Hardcoded `board.created_by` / `board.memberships.filter()` — bypassed rule engine | Replaced with `has_perm('prizmai.edit_board', board)` |
| `update_task_fields_api` | Same hardcoded pattern | Replaced with `has_perm('prizmai.edit_board', board)` |
| `reorder_checklist_items` | No board check at all — any user could reorder any checklist | Added board lookup from first item + `has_perm('prizmai.edit_board', board)` |
| `get_team_skill_profile_api` | Auth-only check, leaked board data to non-members | Replaced with `has_perm('prizmai.view_board', board)` |
| `get_skill_gaps_list_api` | Same auth-only pattern | Replaced with `has_perm('prizmai.view_board', board)` |
| `get_development_plans_api` | Same auth-only pattern | Replaced with `has_perm('prizmai.view_board', board)` |

#### wiki/views.py — 2 gaps fixed

| View | Issue | Fix Applied |
|------|-------|------------|
| `wiki_page_history` | Unscoped slug lookup — any user could view version history of any wiki page in any org | Scoped query to `organization=org` |
| `wiki_page_restore` | Same — any user could restore any wiki page version across orgs | Scoped query to `organization=org` |

#### wiki/api_views.py — 2 gaps fixed

| Endpoint | Issue | Fix Applied |
|----------|-------|------------|
| `get_meeting_analysis_details` | No org check — any user could view analysis details from other orgs | Added org ownership verification |
| `mark_analysis_reviewed` | No org check — any user could mark analyses as reviewed | Added org ownership verification |

#### exit_protocol/views.py — 6 gaps fixed

| View | Issue | Fix Applied |
|------|-------|------------|
| `cemetery` | `CemeteryEntry.objects.all()` — showed archived projects from ALL organizations | Scoped to `board__organization=user_org` |
| `autopsy_report` | Any authenticated user could view any autopsy report | Added org check, `raise Http404` on mismatch |
| `update_lessons` | Any user could edit lessons on any cemetery entry | Added org check, return 403 on mismatch |
| `resurrect_project` | Any user could resurrect any archived project | Added org check, `raise Http404` on mismatch |
| `export_autopsy_pdf` | Any user could download any autopsy PDF | Added org check, `raise Http404` on mismatch |
| `organ_library` | Showed transplantable organs from ALL organizations | Scoped to `source_board__organization=user_org` |

#### kanban/budget_views.py — 2 gaps fixed

| View | Issue | Fix Applied |
|------|-------|------------|
| `task_cost_edit` | No board permission check — any user could edit any task's cost | Added `has_perm('prizmai.edit_board', board)`, `raise Http404` |
| `create_split_time_entries` | No per-task board permission in batch creation | Added per-task `has_perm('prizmai.edit_board', board)` check |

---

## 12. Feature-by-Feature RBAC Coverage

### Left Sidebar Features

| Feature | RBAC Status | Enforcement Method |
|---------|:-----------:|-------------------|
| **Dashboard** | ✅ Secure | `get_user_boards()` queryset filtering |
| **Goals** | ✅ Secure | `has_perm('view_goal')` / `has_perm('edit_goal')` + Org Admin check for create |
| **Missions** | ✅ Secure | `has_perm('view_mission')` / `has_perm('edit_mission')` |
| **Boards** | ✅ Secure | `get_user_boards()` for list, `has_perm('view_board')` for detail |
| **Calendar** | ✅ Secure | All 7 views use `_user_boards()` filter |
| **Wiki** | ✅ Secure | Org-scoped filtering via `_wiki_org_filter()` |
| **Messages** | ✅ Secure | `has_perm('view_board')` on chat rooms, `get_user_boards()` for notifications |

### Tools Section

| Feature | RBAC Status | Enforcement Method |
|---------|:-----------:|-------------------|
| **Time Tracking** | ✅ Secure | `has_perm('edit_board')` on entry creation, `get_user_boards()` for search |
| **Decisions** | ✅ Secure | `get_user_boards()` scoping, `created_for=user` filtering |
| **Memory** | ✅ Secure | `has_perm('view_board')` / `has_perm('edit_board')`, `_get_user_boards()` |
| **Conflicts** | ✅ Secure | All 10 views use `get_user_boards()` scoping |
| **Notifications** | ✅ Secure | `get_user_boards()` scoping |
| **Project Cemetery** | ✅ Secure | Org-scoped filtering on all 5 views |

### Board-Level Features

| Feature | RBAC Status | Enforcement Method |
|---------|:-----------:|-------------------|
| **Board Detail** | ✅ Secure | `has_perm('view_board')` |
| **Task CRUD** | ✅ Secure | `has_perm('edit_board')` |
| **Columns** | ✅ Secure | `has_perm('edit_board')` |
| **Labels** | ✅ Secure | `has_perm('edit_board')` |
| **Gantt Chart** | ✅ Secure | `has_perm('view_board')` |
| **Milestones** | ✅ Secure | `has_perm('view_board')` / `has_perm('edit_board')` |
| **Board Calendar** | ✅ Secure | `has_perm('view_board')` |
| **Phases** | ✅ Secure | `has_perm('edit_board')` |
| **Board Analytics** | ✅ Secure | `has_perm('view_board')` |
| **Export** | ✅ Secure | `has_perm('view_board')` |
| **File Management** | ✅ Secure | `has_perm('view_board')` / `has_perm('edit_board')` |
| **Dependencies** | ✅ Secure | `has_perm('view_board')` / `has_perm('edit_board')` |
| **Stakeholders** | ✅ Secure | `check_board_access()` helper (16 views) |
| **Budget** | ✅ Secure | `_require_budget_access()` (Owner-only for budget management) |
| **Exit Protocol** | ✅ Secure | `check_access_or_403()` / `check_management_or_403()` + org checks |
| **Checklist** | ✅ Secure | `has_perm('edit_board')` on all CRUD operations |
| **Member Management** | ✅ Secure | `has_perm('invite_board_member')` |

### AI Tools (API endpoints in `kanban/api_views.py`)

| Feature | RBAC Status | Enforcement Method |
|---------|:-----------:|-------------------|
| **Generate Task Description** | ✅ Secure | `has_perm('view_board')` when task context provided |
| **Summarize Comments** | ✅ Secure | `has_perm('view_board')` |
| **Generate Board Summary** | ✅ Secure | `has_perm('view_board')` |
| **Task Prediction** | ✅ Secure | `has_perm('view_board')` |
| **Deadline Prediction** | ✅ Secure | `has_perm('view_board')` |
| **Priority Suggestion** | ✅ Secure | `has_perm('view_board')` when board context provided |
| **Skill Gap Analysis** | ✅ Secure | `has_perm('view_board')` |
| **Team Skill Profile** | ✅ Secure | `has_perm('view_board')` |
| **Task Risk Calculation** | ✅ Secure | `has_perm('view_board')` |
| **Workflow Optimization** | ✅ Secure | `has_perm('view_board')` |
| **Semantic Search** | ✅ Secure | `has_perm('view_board')` or `get_user_boards()` |
| **Column Recommendations** | ✅ Secure | `has_perm('view_board')` |
| **Task Breakdown** | ✅ Secure | `has_perm('view_board')` |
| **Subtask Creation** | ✅ Secure | `has_perm('edit_board')` |
| **PDF Downloads** | ✅ Secure | `has_perm('view_board')` |
| **Dependency Analysis** | ✅ Secure | `has_perm('view_board')` |

### Spectra AI Assistant

| Feature | RBAC Status | Enforcement Method |
|---------|:-----------:|-------------------|
| **Chat Interface** | ✅ Secure | Board dropdown filtered by `get_accessible_boards_for_spectra()` |
| **Send Message** | ✅ Secure | `can_spectra_read_board()` check |
| **Task Creation via Spectra** | ✅ Secure | 6-layer defense (see Section 7) |
| **Automation via Spectra** | ✅ Secure | Owner-only via `can_spectra_manage_board()` |

### Admin / Settings

| Feature | RBAC Status | Enforcement Method |
|---------|:-----------:|-------------------|
| **Organization Members** | ✅ Secure | Org Admin only (sidebar hides for non-admins) |
| **Manage Roles** | ✅ Secure | Org Admin only |
| **Workspace Settings** | ✅ Secure | Org Admin only |
| **Analytics Dashboard** | ✅ Secure | `@staff_member_required` |
| **AI Usage** | ✅ Secure | User-scoped, non-demo only |

---

## 13. Suggestions for Future Improvement

### High Priority

1. **Automated RBAC Test Suite**  
   Create a comprehensive test suite that programmatically tests every view endpoint with different role combinations (Owner, Member, Viewer, Non-member, Org Admin). This would catch future regressions during development. A test matrix like:
   ```
   For each view:
     - Org Admin → should access? YES/NO
     - Board Owner → should access? YES/NO
     - Board Member → should access? YES/NO
     - Board Viewer → should access? YES/NO
     - Non-member → should access? NO
   ```

2. **RBAC Middleware/Decorator Approach**  
   Instead of adding `has_perm()` checks manually in every view function body, consider a class-based view mixin or decorator that automatically extracts `board_id` from URL kwargs and checks permissions:
   ```python
   @board_permission_required('prizmai.edit_board')
   def some_view(request, board_id):
       # board is already verified, available as request.board
   ```
   This would eliminate the entire class of "forgot to add the check" bugs.

3. **Viewer Role Enforcement Review**  
   Currently, the `edit_board` permission includes `is_board_member_role` (the "member" role), which correctly excludes viewers. However, views that use the simpler `can_access_board()` from `simple_access.py` don't distinguish between member and viewer. Consider auditing all `can_access_board()` usages to ensure viewers can't modify data through those paths.

### Medium Priority

4. **Audit Logging for Permission Denials**  
   Log all permission denial events (403 responses) to a dedicated audit table. This helps detect:
   - Potential unauthorized access attempts
   - Misconfigured permissions (legitimate users being denied)
   - Security incidents

5. **Board-Level Role Inheritance for Strategic Objects**  
   Currently, `StrategicMembership` and `BoardMembership` are separate systems. Consider allowing board role assignments to automatically propagate to the parent strategy with a `viewer` role, eliminating the need for the `is_descendant_board_member` predicate traversal at read time.

6. **Permission Caching**  
   The `is_ancestor_owner` predicate walks up the Goal → Mission → Strategy → Board hierarchy on every check, potentially issuing multiple DB queries. Consider caching permission evaluation results per user per request using `request._perm_cache` or a middleware-level cache.

7. **Wiki RBAC Enhancement**  
   Wiki pages are currently org-scoped (any org member can view/edit any page). For larger organizations, consider adding per-page or per-category permissions to restrict sensitive documentation.

### Low Priority

8. **API Token Scope Enforcement**  
   The REST API (`api/v1/views.py`) uses `ScopePermission` with scope strings like `tasks.read` / `tasks.write`. Ensure that API token scopes are validated in addition to board-level RBAC, not as a replacement.

9. **Consolidate Access Check Patterns**  
   The codebase has three overlapping access check patterns:
   - `request.user.has_perm('prizmai.xxx', board)` — django-rules
   - `can_access_board()` / `check_access_or_403()` — simple_access.py
   - `get_user_boards()` — queryset filtering

   While all are valid, having a single canonical pattern documented and enforced would reduce confusion. The django-rules `has_perm()` approach should be the default for single-object checks; `get_user_boards()` for list views.

10. **Rate Limiting on Permission-Denied Endpoints**  
    If a user repeatedly hits 403 on the same resource, consider rate-limiting or alerting. This helps detect enumeration attacks where an attacker tries sequential board IDs.

---

## Appendix: Quick Reference Card

### "How do I check permissions in a new view?"

```python
# For a view that reads a board:
if not request.user.has_perm('prizmai.view_board', board):
    raise Http404  # HTML view
    # OR
    return JsonResponse({'error': 'Permission denied'}, status=403)  # API

# For a view that writes to a board:
if not request.user.has_perm('prizmai.edit_board', board):
    raise Http404  # HTML view
    # OR
    return JsonResponse({'error': 'Permission denied'}, status=403)  # API

# For a list view:
from kanban.utils.demo_protection import get_user_boards
boards = get_user_boards(request.user)

# For org-scoped views (no board context):
user_org = getattr(getattr(request.user, 'profile', None), 'organization', None)
if user_org:
    entries = SomeModel.objects.filter(board__organization=user_org)
else:
    entries = SomeModel.objects.none()

# For checking if user is Org Admin:
from kanban.permissions import is_user_org_admin
if not is_user_org_admin(request.user):
    raise Http404
```

### "What permission do I need?"

| Action | Permission |
|--------|-----------|
| View board / read tasks | `prizmai.view_board` |
| Create/edit/delete tasks | `prizmai.edit_board` |
| Delete board | `prizmai.delete_board` |
| Invite members | `prizmai.invite_board_member` |
| View/edit goals | `prizmai.view_goal` / `prizmai.edit_goal` |
| View/edit missions | `prizmai.view_mission` / `prizmai.edit_mission` |
| View/edit strategies | `prizmai.view_strategy` / `prizmai.edit_strategy` |
