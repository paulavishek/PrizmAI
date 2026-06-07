# PrizmAI — Automation Feature Test Report

## Tier 2 Action Battery (2a–2d) — Engine-Level Verification

**Feature:** Automation — Actions (what an automation rule actually *does*)
**Scope:** All 50 actions across the 6 builder groups, batteried into Tiers 2a–2d
**Method:** Hermetic, automated engine-level tests (Django `TestCase` + pytest)
**Tester:** Claude (Opus 4.8) · **Prepared:** June 2026
**Branch:** `feature/spectra-accuracy-fixes` · **Commits:** `0cae6a2` → `05c647e`

---

## 1. Executive Summary

Tier 2 verifies every **action** in the Automation feature — the part of a rule that performs work (set a field, post a comment, move a task, create a wiki page, capture a memory node, etc.). The 50 actions were grouped into four batteries (2a–2d) and tested at the **engine level**: each test creates one rule with a single action, fires it through the real automation engine, and asserts (a) the **Audit Log** records exactly **one** entry with the expected outcome (`success`/`skipped`), and (b) the action produced the **correct effect** (the right field value, or the right output artifact with the right content).

Unlike a manual UI pass, this suite is **hermetic and repeatable**: every test builds its own board/task/users in a rolled-back transaction, so it never touches live/demo data and can be re-run any time in CI. It runs under `kanban_board.test_settings` (Celery eager, in-memory broker + SQLite) so it needs no Redis and makes no external calls.

| Metric | Value | | |
|--------|-------|---|---|
| Actions covered | 50 / 50 | Total tests | **58** |
| Tiers complete | 2a, 2b, 2c, 2d | Pass rate | **100%** |
| Real bugs found & fixed | **7** | Behavior notes logged | 2 |
| AI-blocking calls in actions | **0** (guarded) | Demo/live data mutated | None |
| Test type | Automated, hermetic | Verification | Audit Log + artifact inspection |

**Headline:** All 50 actions fire correctly, write the correct value/artifact, and log exactly one Audit entry. Seven latent production bugs were discovered by the battery and fixed. An audit confirmed the automation engine makes **no synchronous LLM calls** — a guard test now enforces this.

---

## 2. Scope & Exclusions

### 2.1 What is being tested
- Whether each action **fires** when its rule is triggered.
- Whether the action writes the **correct value** to the correct field, or creates the **correct artifact with the correct content**.
- Whether the Audit Log records **exactly one** entry per trigger (no duplicates, no trigger loops).
- Whether **no-op / skip** conditions are handled gracefully (logged as `skipped`, not `failed`).

### 2.2 What is NOT tested in Tier 2 (deferred)
- **Conditions (IF logic)** — the 53 condition operators → **Tier 1**.
- **OTHERWISE (fallback) branch** — → **Tier 1 Branch Logic**.
- **Safety isolations** — infinite-loop prevention, RBAC enforcement on rule CRUD, adversarial edge cases → **Tier 4**.
- **Downstream AI generation** — the async sweeps that AI-gateway actions feed (PrizmBrief generation, task AI re-analysis, knowledge-graph gap analysis) are out of scope; Tier 2 verifies the *trigger/queued record*, not the AI output.
- **UI-level behavior** — visual rendering, the rule-builder drawer, screenshots. (Covered separately by the manual UI pass; see §7.)

---

## 3. Test Environment & Method

| Component | Value |
|-----------|-------|
| Test runner | `python -m pytest kanban/tests/test_automation_tier2<x>.py -v` |
| Settings | `kanban_board.test_settings` (Celery eager, in-memory broker/SQLite, no Redis) |
| Isolation | `django.test.TestCase` — each test in a rolled-back transaction |
| Trigger used | `task_assigned` for most actions (controllable: reassign the task to fire); native source triggers where required (`discovery_idea_submitted` for promote-idea) |
| "Fire once" rule | Re-fetch the task as a fresh instance, change `assigned_to` to a *different* user, `save()` |
| Audit assertion | `AutomationLog.filter(rule=…, task_affected=…).count() == 1` and `outcome` as expected |
| Effect assertion | Re-fetch the object and assert the field/artifact content |

**Standard rule template (per test):** WHEN `task_assigned` · IF none · THEN `<the single action under test>` · OTHERWISE none · `is_active=True`.

**Note on run time:** each fire runs the full signal pipeline (predictions, etc.), so a suite of ~15 tests takes ~3–4 minutes. This is expected, not a hang.

---

## 4. Results Tracking

Legend: **A** = field write · **B** = record/comment/notification creation · **C** = platform status update · **D** = deferred AI gateway (no blocking call). Outcome = the Audit Log outcome asserted.

### Tier 2a — Task State (13 actions) · file `test_automation_tier2a.py` · **13 passed**

| ID | Action | Type | Fires? | Effect verified | Audit |
|----|--------|------|--------|-----------------|-------|
| A-01 | Set priority | A | YES | `priority='urgent'` | 1 ✓ Success |
| A-02 | Set progress % | A | YES | `progress=75` | 1 ✓ Success |
| A-03 | Set description | A | YES | replaced (original gone) | 1 ✓ Success |
| A-04 | Append to description | A | YES | original preserved + appended | 1 ✓ Success |
| A-05 | Add label | A | YES | `{Bug, Feature}` (Bug kept) | 1 ✓ Success |
| A-06 | Remove label | A | YES | label removed | 1 ✓ Success |
| A-07 | Assign to user | A | YES | overwrote trigger assignee; **no loop** | 1 ✓ Success |
| A-08 | Clear assignee | A | YES | unassigned; **no loop** | 1 ✓ Success |
| A-09 | Move to column | A | YES | moved to In Review | 1 ✓ Success |
| A-10 | Set due date | A | YES | ~+14 days | 1 ✓ Success |
| A-11 | Set start date | A | YES | today | 1 ✓ Success |
| A-12 | Clear due date | A | YES | cleared | 1 ✓ Success |
| A-13 | Close task | A | YES | `progress=100` (column unchanged) | 1 ✓ Success |

### Tier 2b — Hierarchy & Dependencies (8) + Resources & Workload (7) · file `test_automation_tier2b.py` · **19 passed**

| ID | Action | Type | Fires? | Effect verified | Audit |
|----|--------|------|--------|-----------------|-------|
| B-01a | Cascade due date (match parent) | A | YES | subtasks ← parent due | 1 ✓ Success |
| B-01b | Cascade due date (+N days) | A | YES | dated subtasks shifted +7d | 1 ✓ Success |
| B-01c | Cascade due date (no parent due) | A | YES | no change | 1 ✓ **Skipped** |
| B-02 | Cascade priority | A | YES | subtasks ← parent priority | 1 ✓ Success |
| B-03 | Assign all subtasks | A | YES | all subtasks → user | 1 ✓ Success |
| B-04a | Complete parent if all subtasks done | A | YES | parent → 100% | 1 ✓ Success |
| B-04b | …sibling incomplete | A | YES | parent unchanged | 1 ✓ **Skipped** |
| B-05 | Notify blocked tasks | B | YES | Notification to blocked assignee | 1 ✓ Success |
| B-06 | Auto-check checklist item | A | YES | item → completed | 1 ✓ Success |
| B-06b | …no matching item | A | YES | no change | 1 ✓ **Skipped** |
| B-07 | Add checklist item | B | YES | item created | 1 ✓ Success |
| B-08 | Add subtask | B | YES | child task created (+offset due) | 1 ✓ Success |
| B-09 | Set workload impact | A | YES | `workload_impact='high'` | 1 ✓ Success |
| B-10 | Set estimated hours | A | YES | `TaskCost.estimated_hours=12` | 1 ✓ Success |
| B-11 | Set estimated cost | A | YES | `TaskCost.estimated_cost=5000` | 1 ✓ Success |
| B-12 | Assign to best skill match | A | YES | → highest-overlap member | 1 ✓ Success |
| B-13 | Assign to lightest workload | A | YES | → fewest-incomplete member | 1 ✓ Success |
| B-14 | Add required skill | A | YES | skill appended | 1 ✓ Success |
| B-15 | Escalate to board owner | B | YES | Notification to owner | 1 ✓ Success |

### Tier 2c — AI & Risk (5) + AI Tools & Platform (7) · file `test_automation_tier2c.py` · **14 passed**

| ID | Action | Type | Fires? | Effect verified | Audit |
|----|--------|------|--------|-----------------|-------|
| C-01 | Set risk level | A | YES | `risk_level='high'` | 1 ✓ Success |
| C-02 | Request AI analysis | D | YES | `last_ai_analysis=None` (flag for sweep) | 1 ✓ Success |
| C-03 | Flag for review | B | YES | 'Needs Review' label + Comment | 1 ✓ Success |
| C-04 | Add risk indicator | A | YES | indicator appended | 1 ✓ Success |
| C-05 | Add mitigation strategy | B | YES | `mitigation:` Comment | 1 ✓ Success |
| C-06 | Acknowledge coach suggestion | C | YES | all active → acknowledged | 1 ✓ Success |
| C-06b | …none active | C | YES | no change | 1 ✓ **Skipped** |
| C-07 | Resolve conflict | C | YES | conflict → resolved | 1 ✓ Success |
| C-08 | Promote discovery idea | C | YES | idea → approved (native trigger) | 1 ✓ Success |
| C-09 | Apply stress-test vaccine | C | YES | vaccine → applied | 1 ✓ Success |
| C-09b | …no vaccine | C | YES | no change | 1 ✓ **Skipped** |
| C-10 | Create memory node | D | YES | `MemoryNode(decision)` created | 1 ✓ Success |
| C-11 | Generate status report | D | YES | queued `SavedBrief` created | 1 ✓ Success |
| C-12 | Add stakeholder engagement | B | YES | engagement record created | 1 ✓ Success |

### Tier 2d — Communications & Memory (10 actions) · file `test_automation_tier2d.py` · **12 passed**

| ID | Action | Type | Fires? | Artifact content verified | Audit |
|----|--------|------|--------|---------------------------|-------|
| D-01 | Send notification | B | YES | `Notification` to assignee, text | 1 ✓ Success |
| D-02 | Post comment | B | YES | `Comment.content` (substituted) | 1 ✓ Success |
| D-03 | Log time entry | B | YES | `TimeEntry` hours + `work_date` | 1 ✓ Success |
| D-04 | Mention users in comment | B | YES | `Comment` contains `@mention` | 1 ✓ Success |
| D-05 | Start task thread | B | YES | `TaskThreadComment` content | 1 ✓ Success |
| D-06 | Link wiki page | B | YES | `Comment` linking page title/slug | 1 ✓ Success |
| D-06b | …slug not found | B | YES | no change | 1 ✓ **Skipped** |
| D-07 | Create wiki page | B | YES | `WikiPage` title/content/category | 1 ✓ Success |
| D-08 | Capture decision | D | YES | `MemoryNode(decision)` content | 1 ✓ Success |
| D-09 | Capture lesson | D | YES | `MemoryNode(lesson)` content | 1 ✓ Success |
| D-10 | Notify stakeholders | B | YES | `Notification` to email-linked user | 1 ✓ Success |
| D-10b | …no linked user | B | YES | no change | 1 ✓ **Skipped** |

**Totals:** 13 + 19 + 14 + 12 = **58 tests, all passing.**

---

## 5. Bug Log

Seven real bugs were found by the battery and fixed. All but the skill-match dict bug were **field/name mismatches** between an action handler and its model, which made the action crash (`failed`) or silently no-op (`skipped`) on real data.

| Bug ID | Action / Area | Severity | Description | Fix | Commit |
|--------|---------------|----------|-------------|-----|--------|
| BUG-2B-01 | `assign_to_best_skill_match` | Medium | Compared **stringified skill dicts** (`str({'name','level'})`), so it only matched if name AND level were identical → silently no-opped on all real `UserProfile.skills` data | Added `_skill_names()` to compare by **name only** (dict or string) | `4b7fec4` |
| BUG-2C-01 | `apply_stress_test_vaccine` | Medium | Imported `StressTestVaccine`; the model class is `Vaccine` → ImportError swallowed → action **always skipped** | Import `Vaccine as StressTestVaccine` | `d893ced` |
| BUG-2C-02 | `generate_status_report` | High | `SavedBrief.create(created_by=…)`; the field is `user` and `name` is required → **crashed (failed)** | Use `user=`, add `name=` | `d893ced` |
| BUG-2C-03 | `add_stakeholder_engagement` | Medium | Passed `interaction_type`/`logged_by` (don't exist); model needs `description`/`created_by`; a bare `except` hid the error → false "no stakeholders" skip | Use real fields; let errors surface | `d893ced` |
| BUG-2D-01 | `log_time_entry` | High | Omitted `work_date` (required `DateField`, no default) → **crashed (failed)** | Set `work_date=timezone.now().date()` | `05c647e` |
| BUG-2D-02 | `create_wiki_page` | High | Omitted `category` + `updated_by` (required FKs) and `slug` → **crashed (failed)** | get_or_create a default "Automation" `WikiCategory`; pass `category`/`slug`/`updated_by` | `05c647e` |
| BUG-CFG-01 | `test_settings` (test harness) | Medium | Overrode `AUTHENTICATION_BACKENDS` and dropped `rules.permissions.ObjectPermissionBackend` → every rules-guarded view returned **403** in tests; also missing cache aliases | Restore the django-rules backend; define all cache aliases; add `BoardMembership` in affected tests | `9e492fb` |

### Behavior notes (not bugs — documented for Tier 4 / product review)
- **NOTE-2A-01 (Close task):** `close_task` only sets `progress=100`. It does **not** move the card to Done or set `completed_at` (writes via `.update()`, bypassing `Task.save()`). Decide if "closed" should imply Done-column/completion timestamp.
- **NOTE-2A/2B-02 (date offsets):** `set_due_date` / `add_subtask` write a **naive local-midnight** value into a `DateTimeField`; under `USE_TZ` the stored UTC value can land ±1 day. Consider making these timezone-aware.

---

## 6. Architecture Finding — Automation is LLM-free (guarded)

A full audit classified all ~50 actions by AI involvement. **No automation action makes a synchronous LLM call or queues async AI directly.** The "AI" actions are deferred **gateways**: they write a flag/placeholder that a *separate scheduled sweep* later enriches with AI.

| AI-gateway action | Writes (cheap, deterministic) | AI happens later in |
|-------------------|-------------------------------|---------------------|
| `request_ai_analysis` | `task.last_ai_analysis = None` | next task-AI sweep |
| `generate_status_report` | queued `SavedBrief` placeholder | PrizmBrief async generation |
| `create_memory_node` / `capture_decision` / `capture_lesson` | `MemoryNode(gaps_analyzed=False)` | `analyze_memory_gaps` Celery sweep |

This property is now **locked in by a guard test** — `test_automation_no_sync_ai.py` reads `automation_actions.py` and fails if it ever references the AI layer or async dispatch (`gemini`, `AIRouter`, `.complete(`, `ai_utils`, `apply_async`, `.delay(`, …). Decision (recorded): **keep all actions**; route any future AI need through a deferred flag/record, not an inline call.

---

## 7. Definition of Done — Tier 2 (a–d) Complete

Tier 2 is complete when ALL of the following are true — **all met:**

- ☑ All 50 actions tested across 2a–2d — no skips.
- ☑ Each action shows exactly **1** Audit Log entry (`success`, or `skipped` for deliberate no-ops) per fire.
- ☑ Each action verified to produce the **correct field value / artifact content**.
- ☑ No-op / skip paths verified (cascade with no parent due, complete-parent with incomplete sibling, missing checklist item, missing wiki slug, unlinked stakeholder).
- ☑ Trigger-loop safety confirmed (assign/clear-assignee fire exactly once).
- ☑ All discovered bugs fixed and re-verified green (**7 fixed**).
- ☑ Full regression green: 2a (13) + 2b (19) + 2c (14) + 2d (12) + triggers (47) + guard (1).
- ☑ LLM-free property enforced by a guard test.
- ☑ All work committed and pushed (`0cae6a2` → `05c647e`).

### Deliverables
| File | Purpose |
|------|---------|
| `kanban/tests/test_automation_tier2a.py` | 13 Task State tests |
| `kanban/tests/test_automation_tier2b.py` | 19 Hierarchy + Resources/Workload tests |
| `kanban/tests/test_automation_tier2c.py` | 14 AI & Risk + AI Tools/Platform tests |
| `kanban/tests/test_automation_tier2d.py` | 12 Communications & Memory tests |
| `kanban/tests/test_automation_no_sync_ai.py` | LLM-free guard |
| `kanban/management/commands/setup_tier2a_test.py` | Seed command for the **manual UI** pass (live demo board) |

---

## 8. After Tier 2 — What Comes Next

| Tier | Focus | Count | Status |
|------|-------|-------|--------|
| 2a | Task State actions | 13 | ✅ Complete |
| 2b | Hierarchy & Dependencies + Resources & Workload | 15 | ✅ Complete |
| 2c | AI & Risk + AI Tools & Platform | 12 | ✅ Complete |
| 2d | Communications & Memory | 10 | ✅ Complete |
| 1 | Condition batteries (53 conditions) + Branch Logic (OTHERWISE) | 53 + ~5 | ⏳ Not started |
| 4 | Safety isolations — infinite loops, RBAC on rule CRUD, edge cases | TBD | ⏳ Not started |

**Recommended next:** Tier 1 (conditions) — these gate *whether* actions run, and pair naturally with the action coverage now in place. Tier 4 (safety) should follow, focusing on loop prevention and RBAC on rule create/edit/delete.

**Still open (optional follow-ups):**
- Address the 2 behavior notes (timezone-aware dates; define "Close task" semantics).
- The **manual UI pass** remains valuable for catching UI-level issues the engine tests can't see — use `python manage.py setup_tier2a_test` to seed the live demo board with the test task + 13 paused rules.

---

*PrizmAI Automation Tier 2 Test Report · 50 actions · 58 tests · 7 bugs fixed · Prepared June 2026 · Branch `feature/spectra-accuracy-fixes`*
