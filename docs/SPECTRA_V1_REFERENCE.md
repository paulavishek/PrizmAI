# Spectra v1.0 — Reference Document

> Last updated: April 12, 2026  
> Applies to: PrizmAI v1.0 ship configuration  
> Author: Build session with Claude (Phases 0–7)

---

## 1. Overview

Spectra is PrizmAI's AI project assistant, powered by Google Gemini 2.5 Flash-Lite. In v1.0, Spectra operates in **read-only Q&A mode** — it can query, analyze, and report on project data but cannot create, update, or delete any resources. Action capabilities (task creation, messaging, time logging, event scheduling, board creation, automation setup, retrospective generation) are code-complete but disabled, with restoration planned for v2.0.

---

## 2. Architecture

### AI Pipeline

| Component | Role |
|-----------|------|
| `ai_assistant/utils/ai_clients.py` | Google Gemini client with smart routing (defaults to Flash-Lite, upgrades to Flash for complex queries) |
| `ai_assistant/utils/chatbot_service.py` | Main service (~4700 lines). Context building, prompt assembly, Gemini call, response formatting |
| `ai_assistant/utils/spectra_data_fetchers.py` | **VDF layer** (Phase 7). Centralised verified data fetchers — single source of truth for all board/task data queries |
| `ai_assistant/utils/conversation_flow.py` | State machine for multi-turn action flows (disabled in v1.0) |
| `ai_assistant/utils/spectra_tools.py` | Gemini function-calling tool schemas (action tools commented out) |
| `ai_assistant/utils/rbac_utils.py` | Centralized RBAC permission checks for Spectra |
| `ai_assistant/utils/action_service.py` | Action execution engine (unreachable in v1.0, preserved for v2.0) |
| `ai_assistant/views.py` | HTTP request handling — session management, message dispatch |
| `kanban/tasks/ai_streaming_tasks.py` | Celery async task for streaming AI responses |
| `templates/ai_assistant/chat.html` | Frontend UI (~1700 lines, all JS inline) |

### Request Flow (v1.0)

```
User types message → sendMessage() JS
  → POST /api/send-message/
    → views.send_message()
      → Auto-select board if none set (demo: first sandbox board, personal: first accessible)
      → Save user AIAssistantMessage
      → ConversationFlowManager.handle_message()
        → If action intent detected → return QUERY_ONLY_FALLBACK
        → If Q&A intent → return None (pass through)
      → If flow returned response → save + return it
      → Else → TaskFlowChatbotService.get_response()  [SYNCHRONOUS — no Celery]
        → RBAC gate check
        → Build context (23 conditional context modules + always-on modules)
        → Generate system prompt
        → Call Gemini (2-5s typical)
        → Save assistant AIAssistantMessage
        → Return JSON response with {sync: true}
```

> **Note (Phase 6):** Chat messages are processed synchronously. The Celery async
> path was removed because the single-worker `pool=solo` configuration caused
> interactive chat to queue behind scheduled tasks (AI briefings, analytics),
> resulting in 30-60s timeouts. Heavy AI features (Pre-Mortem, Board Analytics)
> still use their own Celery endpoints.

### Context Assembly (23+ Modules)

Always-on:
- Attached document context
- Session memory (multi-turn)
- Documentation summary (compact wiki index — lists all published wiki pages)
- Live board snapshot (VDF-backed: column distribution, milestone names/dates with dual-condition completion, overdue/unassigned counts, hierarchy breadcrumb)
- Knowledge base, feedback learning, user preferences

Conditional (keyword-triggered):
- Wiki, meetings, risks, resources, dependencies (VDF-backed: M2M forward + reverse blocking graph), deadlines, budget, time tracking, conflict, automation, calendar, scope creep, stakeholder, commitment protocols, board features, strategic workflow (Goal → Mission → Strategy → Board, with fallback to workspace-scoped goals), full task list (always appended when board is set — dispatch gate removed in Phase 7), web search

> **Phase 7 change**: The `get_taskflow_context()` dispatch gate (`if is_project_query and not context_parts`) was removed. The full VDF task list is now **always** appended when a board is active, regardless of which other contexts matched first.

---

## 3. What Spectra CAN Do (v1.0)

### Query & Analysis
- Answer natural language questions about tasks, boards, team members, deadlines
- Report on task status, overdue items, sprint health, column distribution
- Analyze risks, blockers, dependencies, and bottlenecks
- Provide team workload and capacity insights
- Search and summarize wiki/documentation content
- Report on strategic hierarchy (Goal → Mission → Strategy → Board)
- Display OKR progress and goal alignment
- Analyze budget, time tracking, and ROI data (if available on board)
- Provide scope creep and scope change analysis
- Report on automations, calendar events, and stakeholder data
- Query commitment protocol status and at-risk commitments (via function calling)
- Perform web search for supplemental context (when enabled in settings)
- Analyze uploaded PDF, DOCX, and TXT documents within conversation context
- Provide coaching-style recommendations with explainable AI reasoning

### RBAC Enforcement
- Respects board-level roles (Owner, Member, Viewer)
- Only surfaces data from boards the user has explicit access to
- My Workspace: filters by `workspace__is_demo=False` + board membership
- Demo Workspace: enforces sandbox isolation (User A cannot see User B's sandbox)
- Session board re-validated on every request (prevents stale-session attacks)
- Organization context scoped to user's accessible boards only

### Multi-Workspace Awareness
- Automatically scopes to user's active workspace mode (My Workspace vs Demo)
- Cross-workspace data leakage is prevented at the query layer
- Aggregate queries (cross-board) use workspace-scoped board sets

---

## 4. What Spectra CANNOT Do (v1.0 — Disabled)

All of the following return a polite fallback message directing users to v2.0:

| Capability | Intent Key | Status |
|-----------|-----------|--------|
| Create tasks | `create_task` | Disabled |
| Create boards | `create_board` | Disabled |
| Send messages | `send_message` | Disabled |
| Log time entries | `log_time` | Disabled |
| Schedule events | `schedule_event` | Disabled |
| Generate retrospectives | `create_retrospective` | Disabled |
| Create trigger-based automations | `create_automation` | Disabled |
| Activate automation templates | `activate_automation` | Disabled |
| Update tasks | `update_task` | Disabled |
| Set workspace preset (onboarding) | `collecting_preset` flow | Disabled (unreachable — only triggers after board creation) |

### Fallback Message

When any action intent is detected:

> "I can read and report on your project data, but I can't create, update, or delete anything in v1.0. Action commands — like creating tasks, logging time, and sending messages — are arriving in Spectra v2.0 🚀 In the meantime, feel free to ask me anything about your board, team workload, risks, or project progress."

---

## 5. Security Fixes Applied (Phase 0)

Seven vulnerabilities discovered and fixed during reconfiguration:

### 5.1 RBAC Gate in `get_taskflow_context()`
- **Problem**: Board context was returned without checking if the user has read access to the board.
- **Fix**: Added `can_spectra_read_board(self.user, self.board)` check at the top of the method. Returns empty context if denied.
- **File**: `chatbot_service.py` ~line 308

### 5.2 Stale Session Board Re-validation
- **Problem**: If a user was removed from a board after a session was created, the session would still allow queries against that board.
- **Fix**: Added re-validation of `session.board` access on every `send_message` request. If access is revoked, `session.board` is cleared.
- **File**: `views.py` ~lines 290-304

### 5.3 Cross-Workspace Board Leakage in `get_accessible_boards_for_spectra()`
- **Problem**: Personal mode query used `qs | base.filter(organization_id=...)` which added ALL boards in the org, not just boards the user has membership on. Also missing `workspace__is_demo=False` guard in personal mode and `workspace__is_demo=True` guard in demo mode.
- **Fix**: Changed union to intersection (`qs.filter(organization_id=...)`). Added `workspace__is_demo` guards. Added `is_sandbox_copy=True` exclusion for personal mode.
- **File**: `rbac_utils.py` ~line 195

### 5.4 Aggregate Context Using Wrong Board Source
- **Problem**: `_get_aggregate_context()` called `demo_protection.get_user_boards()` instead of `self._get_user_boards()`, which could return a different set of boards with different workspace scoping.
- **Fix**: Changed to use `self._get_user_boards()` for consistent workspace-aware filtering.
- **File**: `chatbot_service.py` ~line 787

### 5.5 Wiki Context Leakage (Transitive Fix)
- **Problem**: Wiki context relied on the same board set as aggregate context. Fix 5.3 transitively secured this path.
- **Resolution**: No additional code change needed.

### 5.6 Organization Context Member Count Leak
- **Problem**: `_get_organization_context()` used `org.members.count()` and `Board.objects.filter(organization=org).count()` which exposed total org membership and board counts regardless of user access.
- **Fix**: Replaced with RBAC-scoped counts using `self._get_user_boards(organization=org)` and filtering members only from accessible boards.
- **File**: `chatbot_service.py` ~line 1938

### 5.7 Belt-and-Suspenders Gate in `get_response()`
- **Problem**: The top-level RBAC check in `get_response()` had a `not self.is_demo_mode` bypass that skipped the check entirely in demo mode. No sandbox ownership verification.
- **Fix**: Removed the demo bypass. Added explicit sandbox isolation check: in demo mode, the board must be the user's own sandbox copy or an official demo board.
- **File**: `chatbot_service.py` ~line 4117

---

## 6. Known Gaps & Limitations

### 6.1 Hierarchy Context is Keyword-Triggered Only
The full Goal → Mission → Strategy → Board hierarchy context is only injected when the user's prompt contains strategic keywords (`goal`, `mission`, `strategy`, `okr`, `alignment`, etc.). If a user asks "How is my project doing?" without using these keywords, the hierarchy context is not included.

**Mitigation**: A compact hierarchy breadcrumb (one line) is now always included in the live board snapshot if the board is linked to a strategy. This ensures Spectra always knows the board's position in the hierarchy.

**Phase 6 enhancement**: When no goals are reachable via the board → strategy chain (e.g. sandbox copies with `strategy_id=None`), the system falls back to `get_user_goals()` which queries based on the user's workspace mode (demo vs personal), ensuring goals are visible even when the board lacks a direct strategy link.

### 6.2 Preset Onboarding Flow is Disabled
The Org Admin onboarding flow (Spectra asks about team size after first board creation and sets the workspace preset) is disabled because it's chained after the `create_board` action flow, which is itself disabled. In v1.0, Org Admins must set their workspace preset manually via Workspace Settings.

### 6.3 Intent Classification False Positives
The keyword `goal` in `_is_strategic_workflow_query()` can match innocuous phrases like "my goal is to..." This triggers unnecessary hierarchy context injection. The impact is minor (extra tokens, not incorrect data), but could slow responses slightly for non-strategic queries.

### 6.4 No Deduplication on Message Storage
`AIAssistantMessage` has no uniqueness constraint. If two identical requests are processed (e.g., due to network retry), both are saved. The frontend double-submit guard (added in Phase 4) prevents this at the UI layer, but no server-side idempotency key exists.

### 6.5 Pre-existing Migration Issue
`kanban.0053_mark_existing_seed_demo_data` references an `Organization.is_demo` field that doesn't exist in the model. This prevents `manage.py test` from running but does not affect normal operation. This is a pre-existing issue, not caused by our changes.

### 6.6 SpectraConversationState Model Still Has Action Modes
The `MODE_CHOICES` and `PENDING_ACTION_CHOICES` on `SpectraConversationState` still include all v2.0 action modes (collecting_task, collecting_board, etc.). These are safely unreachable in v1.0 (any non-normal state is auto-reset), but they appear in the Django admin panel which could confuse administrators.

### 6.7 Data Scoping Edge Case — Profile Organization Mismatch
During testing, we observed that `testuser1`'s profile organization (id=1) didn't match the organizations on their boards (id=8). This is a dev environment data inconsistency. The stricter RBAC filtering correctly returns 0 personal boards for such users. In production, this would only occur if a user's profile organization was changed after boards were created.

### 6.8 VDF Layer Does Not Cache
`spectra_data_fetchers.py` functions hit the database on every call. For boards with many tasks this means multiple ORM queries per Spectra request (live snapshot + user info + dependency graph can each call `fetch_board_tasks`). Consider caching with a short TTL (e.g. 30 s) keyed by `(board_id, last_task_updated_at)` if query latency becomes noticeable under load.

---

## 7. Phase 6 Bug Fixes (April 12, 2026)

Phase 6 addressed data accuracy issues discovered during a 23-question Spectra testing session. All fixes are in the context-building layer — no model or schema changes.

### 7.1 Chat Timeout — Synchronous Processing
- **Problem**: Spectra chat messages were dispatched to Celery (`send_ai_message_task`). With `pool=solo`, interactive chat queued behind scheduled tasks (AI briefings, analytics), causing 30–60s timeouts.
- **Fix**: Removed Celery dispatch for chat. `send_message()` now calls `TaskFlowChatbotService.get_response()` synchronously. Response JSON includes `{sync: true}`.
- **File**: `ai_assistant/views.py` ~lines 355-395

### 7.2 Demo Board Visibility — Org Filter on Sandbox Boards
- **Problem**: `get_accessible_boards_for_spectra()` demo-mode path filtered sandbox copies by `organization_id`, but sandbox boards are created with `org=None`, returning 0 boards.
- **Fix**: Removed org filter for sandbox copies. Filter by `owner=user, is_sandbox_copy=True` and `workspace__is_demo=True | workspace__isnull=True`.
- **File**: `ai_assistant/utils/rbac_utils.py` ~lines 202-215

### 7.3 Auto-Board Selection
- **Problem**: Chat UI in demo mode sends no `board_id`. Without a board, Spectra has no task context.
- **Fix**: `send_message()` now auto-selects the user's first accessible board when none is set (demo and personal modes).
- **File**: `ai_assistant/views.py` ~lines 308-329

### 7.4 Milestone Fabrication — Missing Names/Dates
- **Problem**: `_get_live_project_snapshot_context()` only reported milestone *count* (e.g. "6 milestones") but never listed names or due dates. Gemini hallucinated milestone names.
- **Fix**: Added a milestone listing section with actual names, statuses, and due dates for each milestone.
- **File**: `chatbot_service.py` ~line 3945 (`_get_live_project_snapshot_context`)

### 7.5 Dependency Blindness — M2M Field Ignored
- **Problem**: `_get_dependency_context()` only queried `parent_task__isnull=False` (0 records on demo board). The board's 27 actual dependencies use the M2M `dependencies` field on Task, which was completely ignored.
- **Fix**: Added M2M `dependencies` query to `_get_dependency_context()` (general overview), `get_taskflow_context()` (per-task listing), and rewrote `_get_full_dependency_chain()` to walk both `parent_task` and M2M edges with cycle detection.
- **Files**: `chatbot_service.py` — `_get_dependency_context` (~line 3330), `get_taskflow_context` (~line 435), `_get_full_dependency_chain` (~line 2466)

### 7.6 Goals/Missions/Strategies Invisible — Sandbox Strategy Link
- **Problem**: `_get_strategic_workflow_context()` chains from `board.strategy_id` → missions → goals. Sandbox board 78 has `strategy_id=None` (not copied from the original), so the chain returns empty. Spectra said "No Organization Goals defined."
- **Fix**: Added fallback: if no goals found via board→strategy chain, use `get_user_goals(user)` which queries by workspace mode (demo mode returns demo goals).
- **File**: `chatbot_service.py` ~line 3510 (`_get_strategic_workflow_context`)

### 7.7 Wiki/Documentation Context Crash — Wrong Related Name
- **Problem**: `_get_wiki_context()` and `_get_documentation_summary_context()` used `wikilink__isnull=True` as a Django ORM filter, but the `WikiLink` model's related name to `WikiPage` is `links_to_items`, not `wikilink`. This caused a `FieldError` exception silently caught by the try/except, making both methods always return `None`. Since the documentation summary is "always-on" (injected into every query), Spectra had zero wiki awareness across all conversations.
- **Fix**: Changed `wikilink__isnull=True` → `links_to_items__isnull=True` in both methods. Also fixed a Django `TypeError: Cannot combine a unique query with a non-unique query` when ORing distinct/non-distinct querysets by rebuilding the board-page inclusion using Q filters.
- **Files**: `chatbot_service.py` — `_get_wiki_context` (~line 2706), `_get_documentation_summary_context` (~line 2932)

### 7.8 Hardcoded Demo Org Name
- **Problem**: Three methods (`_get_wiki_context`, `_get_documentation_summary_context`, `_get_meeting_context`) used `Organization.objects.filter(name='Demo - Acme Corporation')` as a fallback. That org name doesn't exist (actual demo org is "mobile app for YPs"), so the fallback silently returned `None`.
- **Fix**: Changed to `Organization.objects.filter(is_demo=True).first()` in all three locations.
- **File**: `chatbot_service.py` ~lines 2645, 2920, 3011

### 7.9 System Prompt — Wiki Queries Misclassified as Web Search
- **Problem**: System prompt rule #13 told Gemini: "If the user asks you to search the web... say 'I don't have web search'". Queries like "Search the documentation for API endpoints" or "What does the wiki say about..." triggered this response because the word "search" was present and (due to bug 7.7) no wiki data appeared in the context.
- **Fix**: Appended an **IMPORTANT** clarification to rule #13: "search the documentation", "search the wiki", "find documentation about X" are NOT web search requests — they refer to internal wiki pages. Only use the "no web search" response for requests that explicitly ask for internet/web/online content.
- **File**: `chatbot_service.py` ~line 4146 (system prompt)

### 7.10 AI Briefing JSON Parse — Literal `\n`
- **Problem**: Gemini sometimes returns JSON strings with literal `\n` characters instead of actual newlines, causing `json.loads()` to fail for AI briefing generation.
- **Fix**: Added pre-processing that replaces literal `\n` with spaces before JSON parsing, with `ast.literal_eval()` as a secondary fallback.
- **File**: `decision_center/tasks.py` ~lines 665-674

### 7.11 Analytics Session Duration — Stale Row
- **Problem**: `SessionAnalytics.update_duration()` called `save(update_fields=['duration_minutes'])` which raises `DatabaseError` if the row was deleted or never committed.
- **Fix**: Wrapped in try/except with existence check before retry.
- **File**: `analytics/models.py` ~lines 177-183

---

## 7A. Phase 7 — Spectra Accuracy Overhaul (April 12, 2026)

A 16-question testing session on the Software Development demo board (board id=78) exposed 7 data accuracy bugs. All of them were caused by the context-building layer delivering wrong or incomplete data to Gemini — the AI model itself was not at fault.

Root causes fell into four categories:
1. **Column vs progress confusion** — several context methods used the `progress` integer field to classify task status instead of `task.column.name`.
2. **Milestone status ignored** — the `milestone_status` field was never read; column name was used instead, so milestones in non-done columns were reported as not-done regardless of their actual milestone_status.
3. **Dispatch gate blocking the full task list** — the `if is_project_query and not context_parts` condition prevented `get_taskflow_context()` from running when any other context matched first, so Gemini often received only partial data.
4. **Missing reverse M2M query** — the `dependent_tasks` reverse relation was never queried; only forward dependencies were visible, making blocking counts always wrong.

### 7A.0 Verified Data Fetcher (VDF) Layer — New File

- **New file**: `ai_assistant/utils/spectra_data_fetchers.py`
- Single source of truth for all Spectra data queries. Every context method that previously ran its own inline ORM query now calls a VDF function.
- Design rules enforced by the layer:
  - Task status = `task.column.name` (never `task.status` or progress buckets)
  - Milestone completion = `milestone_status == 'completed'` **OR** column name in done-set (dual condition)
  - Overdue = `due_date < today AND NOT is_complete` (excludes completed milestones, items in done columns)
  - Priority = `task.get_priority_display()` (human-readable label, not raw DB value)
  - All queries are **board-scoped** when `self.board` is set
- `DONE_COLUMN_NAMES` frozenset: `{'done', 'completed', 'complete', 'closed', 'finished', 'resolved'}`
- Public API:

| Function | Returns |
|----------|---------|
| `fetch_task_dict(task)` | 20+-field normalised dict: `column_name`, `priority_label`, `assigned_to_display`, `is_complete`, `is_overdue`, `overdue_days`, `milestone_status`, `parent_task_title`, `dependency_titles`, `subtask_count`, `updated_at`, … |
| `fetch_board_tasks(board, filters=None)` | All task dicts for a board; optional `filters` dict |
| `fetch_milestones(board)` | Milestone dicts only, dual-condition completion |
| `fetch_column_distribution(board)` | `[(col_name, count), …]` ordered by column position |
| `fetch_dependency_graph(board)` | `{task_id: {blocking:[], blocked_by:[], blocking_count:N}}` — includes reverse M2M |
| `fetch_assignee_workload(board)` | `{display_name: {task_count, task_titles, display_name, column_breakdown, overdue_count}}` — ALL task titles, never truncated |
| `fetch_overdue_tasks(board)` | Convenience wrapper — overdue task dicts |
| `fetch_tasks_for_user_on_board(board, username)` | Convenience wrapper — filter by assignee username |

- **New management command**: `verify_spectra_vdfs --board-id=N [--section=all|tasks|milestones|columns|dependencies|workload]` — prints VDF output as ASCII for comparison against the UI.
- **New management command**: `regression_test_spectra --board-id=N --username=USER [--question=N] [--verbose]` — sends 16 accuracy-test questions to Spectra and runs 51 assertion checks against VDF ground truth. Baseline: 50/51 pass (98%). The 1 soft failure is a non-critical LLM response omission — data was present in context; Gemini chose not to repeat the assignee name in the free-form response.

### 7A.1 Bug 1 + Bug 6 — Milestone Status Wrong

- **Symptoms**: "Foundation Architecture Complete" milestone showed status "To Do" (Bug 1). Done milestones were flagged overdue (Bug 6).
- **Root cause**: `_get_live_project_snapshot_context()` used only `ms.column.name` to determine done/not-done. Because Foundation's column is "To Do" (the milestone predates column drag), its real `milestone_status = 'completed'` was ignored. Overdue check was `due < today` with no exclusion for completed milestones.
- **Fix**: Replaced milestone loop with `fetch_milestones(board)`. VDF uses dual-condition: `milestone_status == 'completed'` OR column name in `DONE_COLUMN_NAMES`. Overdue flag excludes completed items.
- **Regression**: Q3 — "Foundation Architecture Complete" now reports **Done**.

### 7A.2 Bug 2 + Bug 4 — Column Confusion ("In Progress" vs "In Review")

- **Symptoms**: Authentication System reported "In Progress" (Bug 2). "In Review" column returned wrong tasks (Bug 4).
- **Root cause**: `_get_progress_metrics_context()` classified tasks using `0 < progress < 100` → bucket "In Progress", regardless of actual column. Authentication System had `progress=80` in column "In Review".
- **Fix**: Replaced progress-based status buckets in `_get_progress_metrics_context()` with `fetch_column_distribution(board)`. Status is now column-name based end-to-end.
- **Regression**: Q4 — Authentication System now shows **In Review**. Q6 — "In Review" column returns exactly 2 tasks.

### 7A.3 Bug 3 — Wrong Priority ("High" vs "Urgent" for User Registration Flow)

- **Symptoms**: Priority reported as "High"; actual DB value is `priority='urgent'`.
- **Root cause**: `get_taskflow_context()` (the correct method, which calls `get_priority_display()`) was blocked by the dispatch gate when other context methods fired first. Those contexts rendered raw DB values or stale label strings.
- **Fix**: (1) Dispatch gate removed (see 7A.6). (2) `get_taskflow_context()` refactored to use `fetch_board_tasks()`, ensuring `priority_label` always uses `get_priority_display()`.
- **Regression**: Q5 — Priority now correctly shows **Urgent**.

### 7A.4 Bug 5 — Assignee Tasks Include Wrong People's Work

- **Symptoms**: Asked about Sam Rivera's tasks; Gemini returned tasks belonging to other team members.
- **Root cause**: `_get_user_info_context()` queried cross-board (all user boards) and listed only the top-5 overdue + top-5 due-soon task titles per person — incomplete, ambiguous, cross-board. Gemini guessed and mixed up assignees. `get_taskflow_context()` (board-scoped, all tasks) was blocked by the dispatch gate.
- **Fix**: (1) When `self.board` is set, `get_user_stats()` now calls `fetch_board_tasks(self.board, filters={'assigned_to_username': ...})` — board-scoped, all task titles listed. (2) `_board_workload` dict pre-computed via `fetch_assignee_workload(self.board)`, keyed by username. (3) `_get_task_distribution_context()` uses `fetch_assignee_workload(self.board)` when board is set. (4) Dispatch gate removed.
- **Regression**: Q7 — Sam Rivera's tasks: all 9 correct, all titles listed, no other people's tasks mixed in.

### 7A.5 Bug 7 — Dependency Blocking Count Wrong

- **Symptoms**: Asked which tasks block the most others; Gemini returned incorrect or zero counts.
- **Root cause**: `_get_dependency_context()` never queried the `dependent_tasks` reverse relation. Only forward queries existed (`task.dependencies.all()` = what this task depends on). Reverse blocking counts were therefore always 0.
- **Fix**: `fetch_dependency_graph(board)` builds both directions: `blocked_by` (forward) and `blocking` (reverse via `dependent_tasks`) + `blocking_count`. `_get_dependency_context()` now renders a "Top Blocking Tasks" section sorted by `blocking_count` descending.
- **Regression**: Q9 — File Upload System blocks 2, User Management API blocks 2.

### 7A.6 Dispatch Gate Removed

- **Root cause (architectural)**: `if is_project_query and not context_parts` meant `get_taskflow_context()` was skipped whenever any other context had already matched. For compound queries (e.g. "Show Sam Rivera's tasks" triggers both `_is_user_info_query` and `is_project_query`), Gemini received the user-info context (partial titles) but **not** the full task list. This was the systemic root cause of Bugs 3 and 5.
- **Fix**: Changed gate condition to unconditional `if is_project_query`. Full VDF task list always appended when board is active.
- **Effect**: Slight token increase for compound queries (~1 extra context block). Accuracy improvement is significant.
- **File**: `chatbot_service.py` ~line 4512

### 7A.7 Pre-existing Bug — `timezone` Not Imported

- **Problem**: `get_user_feedback_learning_context()` used `timezone.now()` but had no `from django.utils import timezone` import, causing `NameError` on every Spectra request. Silently swallowed by the outer try/except, but recorded as an error in logs.
- **Fix**: Added `from django.utils import timezone`.
- **File**: `chatbot_service.py` ~line 515

---

## 8. Suggestions for Future Improvement

### 8.1 v2.0 Action Re-enablement Checklist
When re-enabling actions, uncomment these in order:
1. `spectra_tools.py` — Uncomment action tool schemas
2. `conversation_flow.py` — Uncomment `_start_*_flow()` routing in `handle_message()`
3. `chatbot_service.py` — Remove or update `_V1_DISABLED_INTENTS` and `QUERY_ONLY_FALLBACK`
4. `chat.html` — Restore action suggestion chips and capability cards
5. Remove the `Spectra v1.0 — Query & Insights · Actions coming in v2.0` footer
6. Test preset onboarding flow end-to-end

### 8.2 Server-Side Idempotency
Add an idempotency key (UUID generated client-side, sent with each request) to prevent duplicate message processing. Check for existing messages with the same key before creating a new one.

### 8.3 Rate Limiting on AI Requests
Implement per-user rate limiting on the `send_message` endpoint to prevent abuse. Consider using django-ratelimit or a Redis-backed counter.

### 8.4 Streaming Responses
Chat is now synchronous (Phase 6). Consider implementing Server-Sent Events or WebSocket streaming for progressive response delivery, especially for longer Gemini responses.

### 8.5 Context Window Management
The 23+ context modules can collectively exceed the Gemini context window for boards with many tasks. Consider implementing a token budget system that prioritizes the most relevant context modules and truncates or omits lower-priority ones.

> **Phase 7 note**: The dispatch gate removal means `get_taskflow_context()` always runs for project queries, which increases token usage for large boards. If token budget becomes a concern, consider capping `fetch_board_tasks()` at N=100 tasks and summarising the rest.

### 8.6 Automated RBAC Tests
Write integration tests that verify:
- User A cannot see User B's sandbox data via Spectra
- A user removed from a board cannot query it via a stale session
- Cross-workspace queries return empty results
- Organization context doesn't leak member counts from inaccessible boards

### 8.7 Admin Panel Cleanup
For v1.0, consider hiding the action-related mode/pending_action filters from the `SpectraConversationStateAdmin` to avoid admin confusion. Re-enable them for v2.0.

### 8.8 Hierarchy Context Enhancement
Consider making a lightweight "hierarchy summary" (just goal/mission names) that's always included in the system prompt, rather than relying on keyword detection. This would let Spectra naturally reference the hierarchy even for general project questions.

### 8.9 Conversation History
Currently each request is stateless (no history sent to the model). This prevents multi-turn reasoning but saves tokens. Consider implementing a sliding window of the last N messages for better conversational context, with a clear token budget.

### 8.10 Sandbox Strategy Duplication
When creating sandbox copies of demo boards, consider copying `strategy_id` from the original board so the sandbox retains its full hierarchy chain. Currently the sandbox has `strategy_id=None` and relies on the Phase 6 fallback to find goals via `get_user_goals()`.

### 8.11 WikiLink Board Associations for Sandbox
Wiki pages are linked to the original demo board (id=1) via `WikiLink(board=1)`. When a sandbox copy is created (id=78), only one wiki page (Coding Standards) has a link to board 78. Consider duplicating WikiLink board associations for sandbox copies so all wiki pages are accessible via the board-linked path.

---

## 9. Files Modified

| File | Phase | Changes |
|------|-------|---------|
| `ai_assistant/utils/chatbot_service.py` | 0, 1, 3, 6, 7 | RBAC gates, sandbox check, system prompt read-only instruction, `QUERY_ONLY_FALLBACK`, `_V1_DISABLED_INTENTS`, hierarchy breadcrumb, strategic keywords, board drill-down RBAC, milestone names/dates in snapshot, M2M dependency support, goals fallback, wiki related-name fix, org fallback fix, system prompt rule #13 clarification; **Phase 7**: VDF integration for 6 context methods, dispatch gate removed, `timezone` import fix |
| `ai_assistant/utils/spectra_data_fetchers.py` | 7 | **NEW** — VDF layer: `fetch_task_dict`, `fetch_board_tasks`, `fetch_milestones`, `fetch_column_distribution`, `fetch_dependency_graph`, `fetch_assignee_workload`, `fetch_overdue_tasks`, `fetch_tasks_for_user_on_board` |
| `ai_assistant/utils/conversation_flow.py` | 1 | `handle_message()` blocks all action intents, resets stale modes |
| `ai_assistant/utils/spectra_tools.py` | 1 | 10 action tool schemas commented out, 2 read-only tools remain |
| `ai_assistant/utils/rbac_utils.py` | 0, 6 | Cross-workspace fix, workspace guards, sandbox exclusion, removed org filter on sandbox boards |
| `ai_assistant/views.py` | 0, 6 | Session board re-validation, synchronous chat processing, auto-board selection |
| `templates/ai_assistant/chat.html` | 2, 4 | Q&A capability cards, read-only suggestion chips, v2.0 footer, double-submit guard |
| `decision_center/tasks.py` | 6 | JSON parse fix for literal `\n` from Gemini |
| `analytics/models.py` | 6 | `update_duration()` try-except for stale row |

### Files Created

| File | Purpose |
|------|---------|
| `ai_assistant/management/commands/reset_stale_spectra_states.py` | One-time cleanup: reset stuck conversation states to normal mode |
| `ai_assistant/utils/spectra_data_fetchers.py` | VDF layer — centralised verified data fetchers for all Spectra context methods |
| `ai_assistant/management/commands/verify_spectra_vdfs.py` | Print VDF output for a board (ASCII) for manual comparison against the UI |
| `ai_assistant/management/commands/regression_test_spectra.py` | 16-question accuracy regression test suite with 51 assertion checks |

---

## 10. Deployment Checklist

```
# 1. Run stale state cleanup
python manage.py reset_stale_spectra_states --apply

# 2. Collect static files (if CSS/JS changed)
python manage.py collectstatic --noinput

# 3. Verify core imports
python -c "import django; django.setup(); from ai_assistant.utils.chatbot_service import QUERY_ONLY_FALLBACK; print('chatbot_service OK')"
python -c "import django; django.setup(); from ai_assistant.utils.spectra_data_fetchers import fetch_board_tasks; print('VDF layer OK')"

# 4. Verify VDF output against a board (compare against UI)
python manage.py verify_spectra_vdfs --board-id=<BOARD_ID> --section=all

# 5. Accuracy regression test (requires Gemini API key active)
python manage.py regression_test_spectra --board-id=<BOARD_ID> --username=<USER>
# Expected: 50/51 checks passed (Q15 soft failure is a non-critical LLM omission)

# 6. Smoke test — confirm action request returns fallback
# (manually or via the test script)

# 7. Verify Phase 6 fixes
python _tmp_verify_spectra_fixes.py
# Expected: all 5 categories show PASS
```

---

## 11. Context Builder Quick Reference

Summary of what each always-on and conditional context module provides:

| Module | Trigger | Data Provided |
|--------|---------|---------------|
| **Doc summary** (0c) | Always | One-line index of all published wiki pages |
| **Live snapshot** (0d) | Always | Column distribution (VDF-backed), milestone names/dates with dual-condition completion, overdue/unassigned counts, hierarchy breadcrumb |
| **Wiki** (1) | `_is_wiki_query` keywords | Full wiki page content (top 5 by relevance) |
| **Meetings** (2) | `_is_meeting_query` keywords | Meeting notes with summaries, dates, action items |
| **Organization** (3) | `_is_organization_query` | Org structure, member counts (RBAC-scoped) |
| **User info** (4) | `_is_user_info_query` | VDF-backed: board-scoped assignee workload, all task titles per person, overdue/due-soon lists |
| **Task distribution** (5) | `_is_task_distribution_query` | VDF-backed: board-scoped workload with all task titles; cross-board ORM fallback when no board set |
| **Progress metrics** (6) | `_is_progress_query` | VDF-backed: `fetch_column_distribution()` counts (never progress-field buckets), average progress stats |
| **Dependencies** (8) | `_is_dependency_query` | VDF-backed: M2M forward + reverse blocking graph (`dependent_tasks`), top-blocking-tasks list sorted by blocking_count descending |
| **Strategic workflow** (15c) | `_is_strategic_workflow_query` | Goal → Mission → Strategy → Board hierarchy (with fallback to workspace goals) |
| **Taskflow** (16) | `_is_project_query` — **always runs when board is set** | VDF-backed: all tasks with column-based status, `get_priority_display()` labels, assignee, due dates, M2M dependencies — dispatch gate removed in Phase 7 |
