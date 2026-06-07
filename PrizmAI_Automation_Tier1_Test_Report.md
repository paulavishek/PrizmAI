# PrizmAI — Automation Feature Test Report
## Tier 1 — Condition Batteries + Branch Logic (OTHERWISE)

**Feature:** Automation — Conditions (the IF logic that gates *whether* a rule's actions run) + Branch Logic (THEN / OTHERWISE)
**Scope:** All 49 condition attributes across the 6 builder batteries, plus AND/OR combination and the OTHERWISE fallback branch
**Method:** Hermetic, automated tests (Django `TestCase` + pytest) — a fast condition-evaluation matrix layered with end-to-end engine firing
**Tester:** Claude (Opus 4.8) · **Prepared:** June 2026
**Branch:** `feature/spectra-accuracy-fixes`

---

## 1. Executive Summary

Tier 1 verifies every **condition** in the Automation feature — the part of a rule
that decides *whether* its actions fire — and the **branch logic** that routes a
fired rule to its THEN or OTHERWISE actions. Where Tier 2 proved the 50 actions
*do the right thing*, Tier 1 proves the 49 conditions *decide the right thing*.

The 49 conditions are grouped into the 6 builder batteries and tested in two
layers:

1. **Condition matrix (fast):** each condition is driven directly through the
   registry entry point `automation_conditions.evaluate(attribute, operator, value,
   target)` against real DB fixtures, asserting both a **TRUE** and a **FALSE**
   outcome for every operator. No signal pipeline runs, so hundreds of assertions
   complete in seconds.
2. **Branch integration (end-to-end):** real `AutomationRule`s with conditions are
   fired through the live engine via `task_assigned`, asserting the `AutomationLog`
   outcome (`success` / `skipped`) and proving which branch (THEN vs OTHERWISE)
   actually executed via the value it wrote.

This mirrors the "decoupled engine layers" philosophy of the compact test plan: the
matrix exhaustively covers operator logic cheaply, while a smaller integration set
exercises the engine's AND/OR + OTHERWISE + audit-logging path.

| Metric | Value | | |
|--------|-------|---|---|
| Conditions covered | 49 / 49 | Total tests | **57** |
| Batteries complete | 1a, 1b, 2, 3, 4, 5 + Branch | Pass rate | **100%** |
| Real bugs found & fixed | **4** | Behavior notes open | 0 |
| Demo/live data mutated | None | Test type | Automated, hermetic |
| Verification | True+False matrix + Audit Log (engine) | | |

**Headline:** All 49 conditions evaluate correctly for both their true and false
cases across every operator; AND/OR combination and the OTHERWISE fallback branch
all behave correctly and log exactly one Audit entry. **Four latent production
bugs** were discovered by the battery and fixed: three are field/attribute-name
mismatches between a condition handler and its model — each had made its condition
silently un-satisfiable (always `False`) — and the fourth mislabeled a fired
OTHERWISE branch as `'then'` in the audit log. All four are fixed and re-verified.

---

## 2. Scope & Exclusions

### 2.1 What is being tested
- Whether each condition returns the **correct boolean** for its TRUE case and its
  FALSE case, across **every operator** it supports.
- Whether **AND** logic requires all conditions and **OR** logic requires any.
- Whether the **OTHERWISE** branch runs when conditions are not met (and is skipped
  when they are).
- Whether the engine logs the correct **outcome** (`success` when a branch runs,
  `skipped` when no branch applies) — exactly one entry per fire.
- Whether **graceful-False** holds: a condition against missing data / an absent
  related row returns `False` (or its documented default) instead of crashing.

### 2.2 What is NOT tested in Tier 1 (deferred)
- **Actions (THEN effects)** — the 50 action handlers → **Tier 2** (complete).
- **Triggers (WHEN)** — the synchronous/scheduled trigger firing → **Tier 3a/3b**
  (complete).
- **Safety isolations** — infinite-loop / re-entrancy prevention, RBAC on rule CRUD,
  cross-board IDOR, adversarial condition inputs → **Tier 4**.
- **Server-side condition validation** (rejecting an operator that needs a value
  when value is blank) is already covered by
  `test_automation_triggers.py::ConditionValueValidationTest` and is not duplicated
  here.
- **UI-level behavior** — the rule-builder dropdown, condition rows, screenshots.

---

## 3. Test Environment & Method

| Component | Value |
|-----------|-------|
| Test runner | `python -m pytest kanban/tests/test_automation_tier1<x>.py -v` |
| Settings | `kanban_board.test_settings` (Celery eager, in-memory broker/SQLite, no Redis) |
| Isolation | `django.test.TestCase` — each test in a rolled-back transaction |
| Matrix entry point | `kanban.automation_conditions.evaluate(attribute, operator, value, TriggerTarget(...))` |
| Branch trigger | `task_assigned` (reassign to a different user, re-fetch first) — same controllable trigger as Tier 2 |
| Matrix assertion | `evaluate(...) == expected` for a TRUE fixture and a FALSE fixture per operator |
| Branch assertion | `AutomationLog.filter(rule=…, task_affected=…).count() == 1`, `outcome` as expected, and the task field written by the branch that ran |
| Demo/live data | Never touched — every test builds its own board/columns/users/tasks |

**Note on run time:** the matrix tests still create real `Task` rows (each `save()`
runs the full signal pipeline — predictions, etc.), so a matrix battery of ~17
tests takes ~3–4 minutes. This is expected, not a hang.

---

## 4. Results Tracking

Legend: each condition is asserted **True** (condition holds → expected `True`) and
**False** (condition does not hold → expected `False`) across every operator it
supports. All passed.

### Battery 1a — Task State (8 conditions) · file `test_automation_tier1a.py`

| Condition | Operators tested | T/F | Result |
|-----------|------------------|-----|--------|
| `priority` | is, is_not, is_empty, is_not_empty (+ case-insensitive) | ✓/✓ | ✅ |
| `assignee` | is, is_not, is_empty, is_not_empty, "none" sentinel | ✓/✓ | ✅ |
| `column` | is, is_not (+ case-insensitive) | ✓/✓ | ✅ |
| `label` | has, does_not_have, is_empty, is_not_empty | ✓/✓ | ✅ |
| `progress` | gte, lte, equals | ✓/✓ | ✅ |
| `all_subtasks_done` | is_true, is_false (+ no-subtasks default) | ✓/✓ | ✅ |
| `due_date` | is_empty, is_not_empty, is_overdue, within_days | ✓/✓ | ✅ |
| `stale_high_priority` | is_true, is_false (priority + 7-day staleness) | ✓/✓ | ✅ |

### Battery 1b — Core Task Fields (10 conditions) · file `test_automation_tier1a.py`

| Condition | Operators tested | T/F | Result |
|-----------|------------------|-----|--------|
| `status` | is, is_not (alias of `column`) | ✓/✓ | ✅ |
| `created_by` | is, is_not, is_empty, is_not_empty | ✓/✓ | ✅ |
| `start_date` | is_empty, is_not_empty, is_past, is_today, within_days | ✓/✓ | ✅ |
| `description` | contains, does_not_contain, is_empty, is_not_empty | ✓/✓ | ✅ |
| `title` | contains, does_not_contain | ✓/✓ | ✅ |
| `checklist_progress` | gte, lte (+ no-checklist default) | ✓/✓ | ✅ |
| `has_comments` | is_true, is_false, count_gte, count_lte | ✓/✓ | ✅ |
| `has_attachments` | is_true, is_false | ✓/✓ | ✅ **(BUG-1B-01 fixed)** |
| `idle_days` | gte, lte | ✓/✓ | ✅ |
| `time_in_column` | gte, lte | ✓/✓ | ✅ |

### Battery 2 — Risk & AI Prediction (8 conditions) · file `test_automation_tier1b.py`

| Condition | Operators tested | T/F | Result |
|-----------|------------------|-----|--------|
| `risk_level` | is, is_not, is_at_least (ordinal) | ✓/✓ | ✅ |
| `risk_score` | gte, lte, equals | ✓/✓ | ✅ |
| `predicted_completion` | before_due, after_due, within_days_of_due | ✓/✓ | ✅ |
| `prediction_confidence` | gte, lte (fraction **and** percentage forms) | ✓/✓ | ✅ |
| `complexity_score` | gte, lte, equals | ✓/✓ | ✅ |
| `schedule_status` | is (late / on_track computed) | ✓/✓ | ✅ |
| `lss_classification` | is, is_not | ✓/✓ | ✅ |
| `ai_risk_score` | gte, lte | ✓/✓ | ✅ |

### Battery 3 — Hierarchy & Dependencies (9 conditions) · file `test_automation_tier1b.py`

| Condition | Operators tested | T/F | Result |
|-----------|------------------|-----|--------|
| `parent_status` | is, is_not (+ no-parent default) | ✓/✓ | ✅ |
| `subtask_count` | gte, lte, equals | ✓/✓ | ✅ |
| `subtask_completion_pct` | gte, lte | ✓/✓ | ✅ |
| `has_dependencies` | is_true, is_false | ✓/✓ | ✅ |
| `has_blocked_tasks` | is_true, is_false | ✓/✓ | ✅ |
| `dependency_status` | all_complete, any_overdue, any_blocked (+ no-deps default) | ✓/✓ | ✅ |
| `item_type` | is | ✓/✓ | ✅ |
| `phase` | is, is_not (+ case-insensitive) | ✓/✓ | ✅ |
| `is_root_task` | is_true, is_false | ✓/✓ | ✅ |

### Battery 4 — Resource, Cost & Workload (9 conditions) · file `test_automation_tier1c.py`

| Condition | Operators tested | T/F | Result |
|-----------|------------------|-----|--------|
| `workload_impact` | is, is_at_least (ordinal) | ✓/✓ | ✅ |
| `skill_match_score` | gte, lte | ✓/✓ | ✅ |
| `required_skills` | is_empty, is_not_empty, contains, count_gte (dict skills) | ✓/✓ | ✅ |
| `collaboration_required` | is_true, is_false | ✓/✓ | ✅ |
| `estimated_cost` | gte, lte (+ no-TaskCost default) | ✓/✓ | ✅ |
| `estimated_hours` | gte, lte | ✓/✓ | ✅ |
| `hours_logged` | gte, lte (summed TimeEntry hours) | ✓/✓ | ✅ |
| `cost_variance_pct` | gte, lte (+ zero-estimate guard) | ✓/✓ | ✅ |
| `assignee_workload` | gte, lte (+ unassigned default) | ✓/✓ | ✅ |

### Battery 5 — Board-Scoped (5 conditions, `requires='board'`) · file `test_automation_tier1c.py`

| Condition | Operators tested | T/F | Result |
|-----------|------------------|-----|--------|
| `board_has_active_conflicts` | is_true, is_false, count_gte (only `active` counted) | ✓/✓ | ✅ |
| `board_immunity_score` | gte, lte | ✓/✓ | ✅ **(BUG-1C-02 fixed)** |
| `board_scope_creep_pct` | gte, lte (baseline vs current task count) | ✓/✓ | ✅ |
| `board_velocity_trend` | is (improving / declining) | ✓/✓ | ✅ **(BUG-1C-03 fixed)** |
| `board_predicted_overrun_days` | gte (predicted vs project deadline) | ✓/✓ | ✅ |

### Branch Logic (THEN / OTHERWISE / AND / OR) · file `test_automation_tier1d.py` · **9 passed**

End-to-end: a real rule is fired via `task_assigned`; THEN writes `progress=90`,
OTHERWISE writes `progress=10`, so the branch that ran is unambiguous.

Branch is proven two ways: by the value the branch wrote, and (for T1D-02/03/04) by
the audit log's `execution_detail['branch']` after the BUG-1D-01 fix.

| ID | Scenario | Outcome | Branch proven | Result |
|----|----------|---------|---------------|--------|
| T1D-01 | Condition met → THEN | success | progress=90 (THEN) | ✅ |
| T1D-02 | Not met, no OTHERWISE → skipped | **skipped** ("Condition not met") | unchanged; branch='skipped' | ✅ |
| T1D-03 | Not met + OTHERWISE → fallback | success | progress=10; branch='otherwise' | ✅ |
| T1D-04 | Met, OTHERWISE present but unused | success | progress=90; branch='then' | ✅ |
| T1D-05 | AND, all true | success | progress=90 | ✅ |
| T1D-06 | AND, one false → skipped | **skipped** | unchanged | ✅ |
| T1D-07 | OR, one true | success | progress=90 | ✅ |
| T1D-08 | OR, all false → skipped | **skipped** | unchanged | ✅ |
| T1D-09 | Empty conditions → always runs | success | progress=90 | ✅ |

**Totals:** 17 (1a) + 17 (1b) + 14 (1c) + 9 (1d) = **57 tests, all passing.**
(Battery counts by condition: 1a 8 + 1b 10 + 2 8 + 3 9 + 4 9 + 5 5 = **49 conditions**.)

---

## 5. Bug Log

Four real bugs were found by the battery and fixed. The first three are
**attribute/field-name mismatches** between a condition handler and its model — each
silently made the condition un-satisfiable (it could only ever return `False`), so
any automation rule relying on it would never fire. None crashed (the registry
dispatcher swallows handler exceptions and returns `False`), which is exactly why
they had gone unnoticed: the conditions "worked" — they just never matched. The
fourth is an audit-log correctness bug in the OTHERWISE branch path.

| Bug ID | Condition / Area | Severity | Description | Fix |
|--------|------------------|----------|-------------|-----|
| BUG-1B-01 | `has_attachments` | Medium | Read `task.taskfile_set` / `task.files`; `TaskFile` is attached via `related_name='file_attachments'`, so the reverse accessor never existed → attachment count was always 0 → `is_true` could never match | Read `task.file_attachments.count()` |
| BUG-1C-02 | `board_immunity_score` | Medium | Read `latest.overall_score`; the `ImmunityScore` composite field is named `overall` → `getattr(..., 'overall_score', 0)` always returned 0 → every threshold compared against 0 | Read `getattr(latest, 'overall', 0)` |
| BUG-1C-03 | `board_velocity_trend` | Medium | Ordered by `snapshot_date` and read `velocity_value`; `TeamVelocitySnapshot` has neither field (it has `period_end` and `story_points_completed`) → FieldError/AttributeError swallowed by the dispatcher → always `False` | Order by `period_end`, measure velocity as `story_points_completed` |
| BUG-1D-01 | OTHERWISE branch audit label | Low | `AutomationLog.execution_detail['branch']` was hardcoded `'then' if outcome != 'skipped' else 'skipped'` in `kanban/signals.py`, so a fired OTHERWISE branch was logged as `'then'` (the action effect was correct; only the label was wrong) | `_execute_flat_rule` now returns the real branch (`then`/`otherwise`/`skipped`); the main receiver records it. All 7 call sites updated |

BUG-1B-01/1C-02/1C-03 are in `kanban/automation_conditions.py`; BUG-1D-01 is in
`kanban/signals.py` (with `kanban/tasks/automation_tasks.py` call sites updated to
the new 3-tuple return). All fixes were re-verified green, and the full automation
regression (Tier 2 actions + triggers + LLM-free guard + serialization) was re-run
with no regressions.

---

## 6. The "49 vs 53" Reconciliation

Earlier plans referenced "53 conditions across 6 batteries." The engine registers
**49 distinct condition attributes** (`@register_condition` in
`kanban/automation_conditions.py`). The difference is presentation, not coverage:

- `column` and `status` are two registered attributes over one underlying field
  (the UI labels them separately); both are tested.
- A few attributes expose several operators that the builder surfaces as distinct
  dropdown rows (e.g. `risk_level` is / is_not / is_at_least), which can inflate a
  UI-level count.

Tier 1 covers **all 49 registered attributes** and **every operator** each one
implements. If the builder dropdown advertises a condition that is not in the
registry, that is a builder/engine mismatch and belongs in Tier 4 (it would
silently evaluate to `False` today).

---

## 7. Definition of Done — Tier 1 Complete

- ☑ All 49 conditions tested across batteries 1a/1b/2/3/4/5 — no skips.
- ☑ Each condition asserted **True and False** across every operator it supports.
- ☑ Graceful-False paths verified (no parent, no subtasks, no deps, no TaskCost,
  zero estimate, unassigned, missing board-side rows).
- ☑ Branch logic verified end-to-end: THEN, skipped, OTHERWISE, AND, OR, empty.
- ☑ Exactly one Audit Log entry per fire with the correct outcome.
- ☑ All discovered bugs fixed and re-verified green (**4 fixed**).
- ☑ Full automation regression green after the fixes (Tier 2 + triggers + guard +
  serialization).

### Deliverables

| File | Purpose |
|------|---------|
| `kanban/tests/test_automation_tier1a.py` | 17 tests — Battery 1a + 1b condition matrix |
| `kanban/tests/test_automation_tier1b.py` | 17 tests — Battery 2 + 3 condition matrix |
| `kanban/tests/test_automation_tier1c.py` | 14 tests — Battery 4 + 5 condition matrix |
| `kanban/tests/test_automation_tier1d.py` | 9 tests — branch logic (THEN/OTHERWISE/AND/OR), incl. branch-label assertions |
| `kanban/automation_conditions.py` | Bug fixes BUG-1B-01, BUG-1C-02, BUG-1C-03 |
| `kanban/signals.py` + `kanban/tasks/automation_tasks.py` | Bug fix BUG-1D-01 (`_execute_flat_rule` returns the real branch; 7 call sites updated) |

---

## 8. After Tier 1 — What Comes Next

| Tier | Focus | Status |
|------|-------|--------|
| 3a / 3b / 3c | Triggers (synchronous, scheduled, deferred) | ✅ Complete |
| 2a–2d | Actions (50) | ✅ Complete |
| 1 | Conditions (49) + Branch Logic | ✅ **Complete (this report)** |
| 4 | Safety isolations — infinite loops, RBAC on rule CRUD, cross-board IDOR, adversarial inputs | ⏳ Not started |

**Recommended next:** Tier 4 (safety). With triggers, actions, and conditions all
verified, the remaining risk is *misuse and abuse*: a rule whose action re-triggers
its own trigger (loop), a user editing rules on a board they don't own (RBAC/IDOR),
and adversarial condition values. These must be run individually and last.

**Optional follow-ups:**
- Consider promoting the matrix's graceful-False assertions into explicit Tier 4
  adversarial cases (malformed operators, wrong value types).

---

*PrizmAI Automation Tier 1 Test Report · 49 conditions · 57 tests · 4 bugs fixed · Prepared June 2026 · Branch `feature/spectra-accuracy-fixes`*
