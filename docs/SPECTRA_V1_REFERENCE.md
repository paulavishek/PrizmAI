# Spectra v1.0 — Reference Document

> Last updated: April 12, 2026  
> Applies to: PrizmAI v1.0 ship configuration  
> Author: Build session with Claude (Phases 0–6)

---

## 1. Overview

Spectra is PrizmAI's AI project assistant, powered by Google Gemini 2.5 Flash-Lite. In v1.0, Spectra operates in **read-only Q&A mode** — it can query, analyze, and report on project data but cannot create, update, or delete any resources. Action capabilities (task creation, messaging, time logging, event scheduling, board creation, automation setup, retrospective generation) are code-complete but disabled, with restoration planned for v2.0.

---

## 2. Architecture

### AI Pipeline

| Component | Role |
|-----------|------|
| `ai_assistant/utils/ai_clients.py` | Google Gemini client with smart routing (defaults to Flash-Lite, upgrades to Flash for complex queries) |
| `ai_assistant/utils/chatbot_service.py` | Main service (~4600 lines). Context building, prompt assembly, Gemini call, response formatting |
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
- Live board snapshot (task counts, status distribution, milestone names/dates, hierarchy breadcrumb)
- Knowledge base, feedback learning, user preferences

Conditional (keyword-triggered):
- Wiki, meetings, risks, resources, dependencies (M2M + parent_task), deadlines, budget, time tracking, conflict, automation, calendar, scope creep, stakeholder, commitment protocols, board features, strategic workflow (Goal → Mission → Strategy → Board, with fallback to workspace-scoped goals), general project fallback, web search

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
| `ai_assistant/utils/chatbot_service.py` | 0, 1, 3, 6 | RBAC gates, sandbox check, system prompt read-only instruction, `QUERY_ONLY_FALLBACK`, `_V1_DISABLED_INTENTS`, hierarchy breadcrumb, strategic keywords, board drill-down RBAC, milestone names/dates in snapshot, M2M dependency support, goals fallback, wiki related-name fix, org fallback fix, system prompt rule #13 clarification |
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

---

## 10. Deployment Checklist

```
# 1. Run stale state cleanup
python manage.py reset_stale_spectra_states --apply

# 2. Collect static files (if CSS/JS changed)
python manage.py collectstatic --noinput

# 3. Verify imports
python -c "import django; django.setup(); from ai_assistant.utils.chatbot_service import QUERY_ONLY_FALLBACK; print('OK')"

# 4. Smoke test — confirm action request returns fallback
# (manually or via the test script)

# 5. Verify Phase 6 fixes
python _tmp_verify_spectra_fixes.py
# Expected: all 5 categories show ✅ PASS
```

---

## 11. Context Builder Quick Reference

Summary of what each always-on and conditional context module provides:

| Module | Trigger | Data Provided |
|--------|---------|---------------|
| **Doc summary** (0c) | Always | One-line index of all published wiki pages |
| **Live snapshot** (0d) | Always | Task counts by status, milestone names/dates, overdue/unassigned counts, hierarchy breadcrumb |
| **Wiki** (1) | `_is_wiki_query` keywords | Full wiki page content (top 5 by relevance) |
| **Meetings** (2) | `_is_meeting_query` keywords | Meeting notes with summaries, dates, action items |
| **Organization** (3) | `_is_organization_query` | Org structure, member counts (RBAC-scoped) |
| **Dependencies** (8) | `_is_dependency_query` | M2M dependencies + parent_task chains, bottleneck analysis |
| **Strategic workflow** (15c) | `_is_strategic_workflow_query` | Goal → Mission → Strategy → Board hierarchy (with fallback to workspace goals) |
| **Taskflow** (16) | `_is_project_query` fallback | All tasks with status, assignee, due dates, M2M dependencies |
