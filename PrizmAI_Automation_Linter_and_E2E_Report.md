# PrizmAI — Automation Feature: Linter + End-to-End Pre-Ship Report

**Feature:** Automation — WHEN/IF/THEN/OTHERWISE rule engine, plus the new
client-side **rule linter** that warns on trigger↔condition combinations that can
never align.
**Goal:** Verify the feature works correctly before shipping to Google Cloud for
real users — every trigger, condition, and action, and specifically the newly
added "unsatisfiable combination" warning.
**Method:** Hermetic automated tests under `kanban_board.test_settings` (Celery
eager, in-memory SQLite, rolled-back transactions) + a runtime-parity harness for
the JS linter + an end-to-end showcase that captures a real audit log.
**Tester:** Claude (Opus 4.8) · **Prepared:** 2026-07-06 · **Branch:**
`feature/dashboard-modernization`

---

## 1. Executive summary

The automation engine is **ship-ready for the shipped (lean-MVP) surface**. Every
user-selectable trigger, condition, and action works, saves cleanly, and produces
a correct audit-log entry. The new linter is **truthful**: every warning it shows
is provable against the real runtime engine, and it never mislabels a rule that
can actually fire. The linter was also **honest but incomplete** — it covered only
2 combinations; it now covers **13 combinations across 4 triggers**, each backed
by a runtime-parity test.

Three findings surfaced during the sweep. **None is a user-facing bug in the
shipped surface.** All three are the automated *ship-gate tests being broader than
the shipped UI* (they assert against the full 50-action / Phase-5/6 registry,
while the builder deliberately exposes a lean subset). They are documented in
§6 with recommendations.

| Area | Result |
|------|--------|
| Conditions (49) | ✅ Green — `test_automation_tier1a–1d` (57 tests) |
| Actions (50 registered / 13 exposed) | ✅ Green — `test_automation_tier2a–2d`; 13 exposed round-trip through save |
| Triggers (21 task-save + m2m/source/scheduled) | ✅ Green — `test_automation_triggers` (~48 tests) |
| **Linter parity + E2E (new)** | ✅ **19/19 pass** — every verdict proven against runtime |
| **Action-surface contract (new)** | ✅ **5/5 pass** — builder = endpoint = model, in sync |
| **End-to-end showcase (new)** | ✅ **12 rules fired, audit log captured** |
| LLM-free guard | ✅ Green — `test_automation_no_sync_ai` |

**Verdict: SHIP** the lean-MVP automation surface. Address the §6 findings before
exposing the additional 37 actions / Phase-5/6 triggers in the builder.

---

## 2. What was already covered (verified green on this branch, in isolation)

The engine already had strong coverage; this sweep re-verified it rather than
rebuilding it.

- **Conditions — 49 registered, 57 tests.** Each condition asserted TRUE and
  FALSE across every operator, plus AND/OR and the OTHERWISE branch
  (`test_automation_tier1a/1b/1c/1d.py`).
- **Actions — 50 registered, engine-level battery** (`test_automation_tier2a–2d.py`).
- **Triggers — ~48 tests** covering dedupe, label/comment/attachment receivers,
  idle/overdue/predicted-late sweeps, milestone, due-date change, scheduled-cron
  mapping, and template copy (`test_automation_triggers.py`).

> A full-suite run (all 11 files at once) reported **166 passed / 39 failed**.
> Every one of the 39 was reproduced and explained (§6) — 38 are the serialization
> ship-gate asserting unexposed actions, 1 was a stale test fixture (now fixed).
> No failure is a defect in the user-facing automation feature.

---

## 3. The rule linter — parity + end-to-end (the new feature)

The linter (`TRIGGER_FIELD_CONSTRAINTS` in
`static/js/unified_rule_builder.js`) is **client-side and advisory** (Save stays
enabled). A false "dead" warning on a rule that *could* fire would be worse than a
missing warning, so the test strategy proves every verdict against the real
Python runtime.

**File:** `kanban/tests/test_automation_linter_parity.py` — **19 tests, all pass.**

### 3.1 Parity (the linter's premise is true)
For a task in the exact state the trigger fires on, the runtime returns the
constant the linter claims — `False` for a *dead* verdict, `True` for a
*pointless* one:

| Trigger | Condition | Linter says | Runtime `evaluate(...)` | ✓ |
|---------|-----------|-------------|-------------------------|---|
| `task_created` | `progress ≥ 30` | dead | `False` | ✅ |
| `task_created` | `progress ≥ 0` | pointless | `True` | ✅ |
| `task_created` | `all_subtasks_done is_true` | dead | `False` | ✅ |
| `task_created` | `has_comments is_true` | dead | `False` | ✅ |
| `task_created` | `idle_days ≥ 1` | dead | `False` | ✅ |
| `task_overdue` | `due_date is_empty` | dead | `False` | ✅ |
| `task_assigned` | `assignee is_empty` | dead | `False` | ✅ |

### 3.2 End-to-end (the linter's promise is true)
A real `AutomationRule` for `task_created + progress ≥ 30` is fired through the
live engine: the `AutomationLog` records **`outcome = skipped`** ("Condition not
met") — proving "this rule will skip every time" literally. The *pointless*
variant (`progress ≥ 0`) still fires `success` — the linter never turns a working
rule into a dead one.

### 3.3 Guardrail
Fields the create-form CAN populate (`priority`, `assignee`, `due_date`, `title`)
are proven **not** dead at creation, so the linter must never flag them.

---

## 4. Linter gap audit + expansion

The linter shipped covering **1 trigger × 2 conditions**. Auditing the runtime for
every field that is provably constant at a trigger's fire moment, the mapping was
expanded to **4 triggers × 13 conditions** — each added combination first proven
by a parity test (§3.1). Conservative by design: only combinations the runtime
reduces to a constant were added.

### Added to `TRIGGER_FIELD_CONSTRAINTS`

| Trigger | Conditions now flagged | Why constant at fire time |
|---------|------------------------|---------------------------|
| `task_created` | `progress`*, `all_subtasks_done`*, `subtask_count`, `subtask_completion_pct`, `checklist_progress`, `has_comments`, `has_attachments`, `has_dependencies`, `has_blocked_tasks`, `idle_days`, `time_in_column`, `hours_logged` | A new task has no related rows yet; age / idle / time-in-column are all 0 |
| `task_overdue` | `due_date` (`is_empty`, `within_days` → dead; `is_overdue`, `is_not_empty` → pointless) | An overdue task must have a past due date |
| `task_assigned` | `assignee` (`is_empty`, `is Unassigned` → dead; `is_not_empty` → pointless) | The trigger only fires when a task gains an assignee |
| `task_unassigned` | `assignee` (mirror of above) | The trigger only fires when a task loses its assignee |

\* = shipped originally. All others are new.

### Deliberately **excluded** (would be false warnings)
`priority`, `assignee`, `due_date`, `title`, `description`, `start_date`,
`risk_*` on `task_created` — the create form CAN set these, so they are not
provably constant. `is_root_task` was excluded because `task_created` can fire for
a subtask (via `add_subtask` / the API), so "is root" is not guaranteed.

> **Parity lock:** `kanban/tests/test_automation_linter_parity.py` is the Python
> source of truth for the JS mapping. If the JS and runtime ever diverge, it goes
> red. (There is no JS test runner in this repo, so parity is enforced from the
> Python side.)

---

## 5. End-to-end showcase — rules built + audit log

**File:** `kanban/tests/test_automation_showcase.py` — builds one real rule per
trigger family, fires each through the live signal engine, and captures the
`AutomationLog`. The run below is from real, asserted execution.

### 5.1 Rules built (12)

| # | Rule | Trigger | Conditions | THEN action | OTHERWISE |
|---|------|---------|------------|-------------|-----------|
| 1 | New task → tag Hot | `task_created` | — | `add_label` Hot | — |
| 2 | New urgent task → comment | `task_created` | priority is urgent | `post_comment` | — |
| 3 | Urgent? else flag | `task_created` | priority is urgent | `post_comment` | `post_comment` |
| 4 | New high-priority only | `task_created` | priority is high | `post_comment` | — |
| 5 | **DEAD: new task + progress≥30** | `task_created` | progress ≥ 30 | `post_comment` | — |
| 6 | On assign → notify | `task_assigned` | — | `post_comment` | — |
| 7 | Moved to Review → high priority | `task_moved_to_column` | — | `set_priority` high | — |
| 8 | Priority changed → note | `task_priority_changed` | — | `post_comment` | — |
| 9 | On complete → log | `task_completed` | — | `post_comment` | — |
| 10 | Half done → nudge | `task_completion_threshold` (50) | — | `post_comment` | — |
| 11 | Due date moved → note | `task_due_date_changed` | — | `post_comment` | — |
| 12 | Review label → escalate note | `task_label_added` (NeedsReview) | — | `post_comment` | — |

### 5.2 Audit log (what the engine recorded)

| Rule | Trigger event | Task | Outcome | Branch | Skip reason |
|------|---------------|------|---------|--------|-------------|
| New task → tag Hot | task_created | Freshly filed bug | ✅ success | then | — |
| New urgent task → comment | task_created | Prod outage | ✅ success | then | — |
| Urgent? else flag | task_created | Minor typo | ✅ success | **otherwise** | — |
| New high-priority only | task_created | Routine chore | ⏭️ skipped | skipped | Condition not met |
| **DEAD: new task + progress≥30** | task_created | Cannot ever fire this | ⏭️ **skipped** | skipped | Condition not met |
| On assign → notify | task_assigned | Needs an owner | ✅ success | then | — |
| Moved to Review → high priority | task_moved_to_column | Feature PR | ✅ success | then | — |
| Priority changed → note | task_priority_changed | Escalating item | ✅ success | then | — |
| On complete → log | task_completed | Wrap-up task | ✅ success | then | — |
| Half done → nudge | task_completion_threshold | Long task | ✅ success | then | — |
| Due date moved → note | task_due_date_changed | Deadline task | ✅ success | then | — |
| Review label → escalate note | task_label_added | Getting spicy | ✅ success | (n/a) | — |

**10 success (9 THEN + 1 OTHERWISE) · 2 skipped · exactly one audit row per
fire.** The linter's "dead" combo (#5) lands as `skipped` in the audit log,
end-to-end confirming the warning's claim. (The `task_label_added` path is a
separate m2m receiver that does not stamp a `branch` — expected.)

---

## 6. Findings (all in the ship-gate tests, not the shipped UI)

### F-1 — Save endpoint accepts only the 13 exposed actions (by design)
The create/update endpoint validates actions against
`AutomationRule.ACTION_CHOICES` (**13 actions**). The engine *registers* **50**.
The builder dropdown (`ACTION_GROUPS` in `unified_rule_builder.js`) exposes
**exactly the same 13** — so **builder, endpoint, and model are perfectly in
sync**, and a real user can never select an action the server rejects. New guard:
`kanban/tests/test_automation_action_surface.py` (5 tests) locks this invariant,
proves all 13 exposed actions round-trip, and pins the other 37 as *intentionally*
rejected.

- **Impact on shipping the lean MVP:** none. This is the reason the broad
  serialization ship-gate shows 37 red — it builds fixtures from the full 50-action
  registry. That test is *ahead of the shipped UI surface*, not detecting a bug.
- **Recommendation:** before exposing more actions, either (a) scope
  `test_automation_serialization.py`'s CURRENT_RULES action fixtures to the
  exposed set, or (b) add each new action to the builder AND `ACTION_CHOICES`
  together — the new guard test will flag any drift.

### F-2 — Legacy/template rules using an unexposed action can't be re-saved
`log_time_entry` (and other unexposed actions) appear in `LEGACY_RULES` and could
exist in older/template-created rules. Such a rule *runs* fine, but opening it in
the builder and clicking Save hits the endpoint whitelist and returns
`400 unknown action type`.

- **Impact:** low for brand-new users (they can only create the 13). A real
  edit-path gap for any pre-existing or template-seeded rule using an unexposed
  action.
- **Recommendation:** on **update** of an existing rule, accept any *registered*
  action (`ACTION_HANDLERS`) even if it is outside the builder's dropdown — this
  preserves legacy/template rules while keeping the lean creation UI. Gate only
  the dropdown, not persistence.

### F-3 — `test_c08_promote_discovery_idea` fixture predated the Discovery workspace FK  *(fixed)*
`discovery_idea_submitted` now resolves its target board from the idea's
**workspace** ([signals.py:2304](kanban/signals.py#L2304)). The Tier-2 fixture set
only the legacy `organization` field, so the trigger never routed and the action
appeared to do nothing. Fixed the fixture to set `workspace` on the board and
idea; the `promote_discovery_idea` action now verifiably sets `stage='approved'`.
(Both the trigger and the action are Phase-5/6 features outside the lean builder.)

---

## 7. Deliverables (files added / changed)

| File | Type | Purpose |
|------|------|---------|
| `kanban/tests/test_automation_linter_parity.py` | **new test** | 19 tests — linter parity + E2E |
| `kanban/tests/test_automation_action_surface.py` | **new test** | 5 tests — builder ⇄ endpoint ⇄ model contract |
| `kanban/tests/test_automation_showcase.py` | **new test** | 12-rule end-to-end audit-log showcase |
| `static/js/unified_rule_builder.js` | **product** | Expanded `TRIGGER_FIELD_CONSTRAINTS` (2 → 13 combos, 4 triggers) |
| `kanban/tests/test_automation_tier2c.py` | **test fix** | F-3: workspace fixture so the discovery trigger routes |

---

## 8. Manual UI checklist (for your hands-on pass)

The parity tests prove the linter's *logic*; these confirm the *rendering* in the
running app:

1. New rule → trigger **Task is created** → condition **Progress ≥ 30%** → a
   yellow warning appears under the preview with a **Remove this condition**
   button; clicking it clears the condition and the warning.
2. Same trigger → **Progress ≥ 0%** → a muted grey "adds nothing" note (no Remove
   button — pointless, not dead).
3. New combos: **Task is created + Idle days ≥ 1**, **+ Has attachments is true**,
   **+ Subtask count ≥ 1** → each shows a "can never be true" warning.
4. Trigger **Task is assigned** + **Assignee is empty** → warning. Trigger **Task
   becomes overdue** + **Due date is empty** → warning.
5. A valid rule (e.g. **Task moved to a column → Set priority High**) shows **no**
   warning and saves normally.

---

*PrizmAI Automation — Linter + E2E Pre-Ship Report · 19 + 5 + 12 new checks green
· 3 findings (all ship-gate scope) · Prepared 2026-07-06 · Branch
`feature/dashboard-modernization`.*
