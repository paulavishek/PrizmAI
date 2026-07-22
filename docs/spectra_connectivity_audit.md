# Spectra Connectivity & Correctness Audit

_Last updated: 2026-06-03 — Spectra Accuracy Pass (branch `feature/spectra-accuracy-fixes`)._

## Why this audit exists

Spectra intermittently failed simple factual questions and contradicted itself
(e.g. the same "who has how many tasks" question answered two different ways in one
session, "due in the next 7 days" returning tasks due months out, commitment confidence
shown as "0.3778%"). This document maps Spectra A–Z to every AI and non‑AI feature,
records what was wrong, and what was fixed.

**Headline finding:** Spectra is **already connected to essentially every feature** through
a 38‑provider registry (`ai_assistant/utils/context_providers/`) backed by a single‑source
"Verified Data Fetchers" (VDF) layer (`ai_assistant/utils/spectra_data_fetchers.py`). The
failures were **correctness / consistency bugs**, not missing connections.

## Architecture (how a question is answered)

```
send_message (views.py)
  └─ TaskFlowChatbotService.get_response (chatbot_service.py)
       1. RBAC gate (board read access)
       2. Always-on feature SUMMARIES from ALL providers (60s cache)   ← baseline awareness
       3. Smart router (context_router.py) picks ≤5 providers for DETAIL
          + force-include 'Cross-Board Aggregate'/'Hierarchy' (no board)
          + force-include 'Board Tasks' for task-signal queries  ← NEW (fixes starvation)
       4. Legacy builders — ONLY Meetings + Lean (no provider equivalent)
       5. KB / feedback / preference / session memory / web search
       6. generate_system_prompt → AIRouter.complete → Gemini
```

Providers return **summaries** (every query) and **detail** (router‑selected). Every
provider that touches task status/priority/overdue routes through VDF so the numbers are
computed one way only.

## AI Tools → provider → data source

| AI Tool (AI Tools panel) | Provider (`PROVIDER_NAME`) | Backing fetch | Status |
|---|---|---|---|
| AI Coach | AI Coach | `fetch_coach_*` (VDF) | ✅ |
| Burndown / Velocity / Analytics | Analytics + AI Coach PM metrics | `fetch_assignee_workload`, `fetch_column_distribution` (VDF) | ✅ |
| Skill Gaps | Skill Development | `fetch_skill_dev_*` (VDF) | ✅ |
| Status Report | Status Report | `fetch_status_report_*` (VDF) | ✅ |
| Resource Optimization / Leveling | Resource Leveling | `fetch_resource_leveling_*` (VDF) | ✅ |
| Budget & ROI | Budget & ROI | inline ORM on `ProjectBudget`/`TaskCost`/`TimeEntry` | ✅ (own models) |
| Scope / Scope Creep / Scope Autopsy | Scope | `fetch_scope_*` (VDF) | ✅ |
| Requirements | Requirements | `fetch_requirements_*` (VDF) | ✅ |
| Discovery | Discovery Ideas | `fetch_discovery_*` (VDF) | ✅ |
| PrizmBrief | Briefs | `fetch_briefs_*` (VDF) | ✅ |
| What‑If | Risk Scenarios | `fetch_risk_scenarios_*` (VDF) | ✅ (shared w/ pre‑mortem & stress test) |
| Pre‑Mortem | Risk Scenarios | `fetch_risk_scenarios_*` (VDF) | ✅ |
| Stress Test (immunity) | Risk Scenarios | `fetch_risk_scenarios_*` (VDF) | ✅ |
| Shadow Board | Shadow Board Branches | inline ORM on `ShadowBranch` | ✅ |
| Retrospectives | Retrospectives | inline ORM on `ProjectRetrospective` | ✅ (own models) |
| Exit Protocol / Cemetery | Project Cemetery | inline ORM on cemetery models | ✅ (own models) |
| Commitment Protocol | Commitments | inline ORM on `CommitmentProtocol` | ✅ **(confidence bug FIXED)** |
| Conflicts | Conflicts | inline ORM on conflict models | ✅ (own models) |
| Knowledge Graph / Org Memory | Organizational Memory | `fetch_memory_*` (VDF) | ✅ |

## Non‑AI features (left sidebar) → provider → data source

| Feature | Provider | Backing fetch | Status |
|---|---|---|---|
| Tasks / Board / Columns / Labels | Board Tasks | `fetch_board_tasks`, `fetch_column_distribution` (VDF) | ✅ |
| Milestones | Board Tasks | `fetch_milestones` (VDF) | ✅ |
| Hierarchy Navigator (Goals/Missions/Strategies) | Hierarchy | inline ORM on `OrganizationGoal`/`Mission`/`Strategy` | ✅ (data‑dependent, see Notes) |
| Wiki | Wiki | inline ORM on `WikiPage` | ✅ |
| Messages / Team Chat | Communication | inline ORM on `ChatRoom`/`ChatMessage` | ✅ |
| Calendar | Calendar | inline ORM on `CalendarEvent` | ✅ |
| Stakeholders | Stakeholders | `fetch_stakeholders_*` (VDF) | ✅ |
| Time Tracking | Time Tracking | inline ORM on `TimeEntry` | ✅ |
| Automations | Automations | inline ORM on automation models | ✅ |
| Comments | Comments | `fetch_comments_*` (VDF) | ✅ |
| Files & Attachments | Files & Attachments | `fetch_files_*` (VDF) | ✅ |
| Activity feed | Activity | `fetch_activity_*` (VDF) | ✅ |
| Custom Fields | Custom Fields | `fetch_custom_fields_*` (VDF) | ✅ |
| Decisions / Focus Today | Decisions | inline ORM on decision models | ✅ |
| Access Requests | Access Requests | `fetch_access_*` (VDF) | ✅ |
| Integrations | Integrations | `fetch_integrations_*` (VDF) | ✅ |
| Knowledge Base | Knowledge Base Inventory | inline ORM on `ProjectKnowledgeBase` | ✅ |
| Meetings (MeetingNotes) | _legacy builder_ `_get_meeting_context` | inline ORM on `MeetingNotes` | ⚠️ no provider — see Gaps |
| Lean Six Sigma | _legacy builder_ `_get_lean_context` | inline ORM on `Task.lss_classification` | ⚠️ no provider — see Gaps |

> "Inline ORM (own models)" is acceptable: VDF centralizes **task** semantics (status =
> column name, overdue, priority display, milestone completion). Providers that query their
> own feature models (budget, calendar, wiki…) don't need VDF as long as they don't
> recompute task status. None of the inline‑ORM providers recompute task completion in a way
> that conflicts with VDF (the one cross‑board task counter, `aggregate_provider`, reuses
> `DONE_COLUMN_NAMES`).

## Confirmed bugs & fixes (this pass)

1. **Double‑sourcing (primary cause of contradictions).** Legacy keyword builders ran
   alongside the providers in `get_response` and recomputed workload/user‑info/org/resource
   numbers differently from VDF. The LLM saw two tables and picked inconsistently.
   **Fix:** removed `_get_user_info_context`, `_get_resource_context`,
   `_get_user_tasks_context`, `_get_organization_context` (+ their `_is_*` gates and call
   sites). Providers (`Board Tasks`, `Analytics`, `Resource Leveling`, `Cross‑Board
   Aggregate`) are now the single source of truth. `_get_user_info_context` was also keyed to
   the **retired** demo personas ('alex'/'sam'/'jordan').

2. **Commitment confidence scale.** `CommitmentProtocol.current_confidence` is a 0.0–1.0
   fraction (model validators 0.1–1.0), but `commitment_provider` printed it as `{value}%`
   ("0.85%") and filtered `< 70` (everything "at risk"). The transcript's "project confidence
   0.39%" was the **average of the three commitment fractions** mislabeled.
   **Fix:** `commitment_provider._pct()` helper + fractional thresholds (`0.70`/`0.50`).

3. **Routing starvation.** `board_provider` already builds a correct "Due in next 7 days"
   pre‑filter and the full task roster, but detail was only injected when it landed in the
   router's top‑5. When it didn't, the LLM scanned the raw list and dumped far‑future tasks
   ("due soon" → July–October) or mixed Done into "high priority".
   **Fix:** force‑include `Board Tasks` for task‑signal queries; system‑prompt rules now (a)
   require the pre‑filtered due‑soon list, (b) forbid Done in priority/at‑risk/upcoming lists,
   (c) make "high priority" literal (no silent High↔Urgent folding).

## Known gaps & non‑bugs

- **Meetings & Lean have no provider** — still served by the two retained legacy builders.
  They don't emit competing task numbers, so they cause no contradictions. _Follow‑up
  (optional): migrate to `meeting_provider.py` / `lean_provider.py` for symmetry._
- **`action_service.py:1091,1133`** render `current_confidence:.0f%` with the same
  fraction‑as‑percent bug, but that is the **disabled v2 action layer**, not the Q&A path.
  _Flagged for the v2 work; not fixed here to keep scope tight._
- **"No goals/missions linked" / "no shadow board branches"** in the old transcript were
  **data‑dependent**, not connectivity bugs: the demo board had no linked strategy and no
  shadow branches. The Hierarchy and Shadow Board providers are wired and return data when it
  exists.
- Several `_is_*`/`_get_*` legacy builders (overdue, deadline‑projection, distribution, etc.)
  remain defined but are **no longer dispatched** by `get_response`; they are harmless dead
  code superseded by providers. Left in place to keep this pass surgical.

## Regression coverage

`ai_assistant/tests/test_spectra_accuracy.py` locks in: workload single‑source determinism,
confidence percent formatting + threshold, due‑soon window excludes far‑future, high‑priority
excludes Done, and overdue parity with the dashboard's `due_date < now` logic.
