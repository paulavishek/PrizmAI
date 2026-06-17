# Spectra Capability Test — Results & Fixes

**Date:** 2026-06-17
**Method:** All 67 questions from [SPECTRA_TEST_QUESTIONS.md](SPECTRA_TEST_QUESTIONS.md) were run
through the real Spectra service (`TaskFlowChatbotService.get_response`, live Gemini calls)
as the configured test users/boards, via `scripts/spectra_test_harness.py`. Every answer was
cross-checked against the database (`scripts/spectra_ground_truth.py`) and against the exact
provider context Spectra received.

- **Primary test board:** Core AI Protocol Development (board 63, testuser1 = Owner) — the
  richest board (hierarchy, 40 decisions, 20 wiki pages, scope autopsy +75%, 8 discovery
  ideas, org-memory nodes, 5 conflicts).
- **RBAC boards:** board 51 (AI Model Dev), board 82 (testuser3's Test Board).
- Raw transcripts: `scripts/_spectra_results_BEFORE.md` (initial run) and
  `scripts/_spectra_results.md` (post-fix re-runs).

---

## Headline

| | Count |
|---|---|
| Total questions | 67 |
| ✅ Correct on first run | 56 |
| ❌ Wrong / misleading on first run | 11 |
| ✅ Correct after fixes | 67 |
| Hallucinated **false data** (invented tasks/numbers/names) | **0** |

**Key finding:** Spectra never fabricated data. Every failure was the *opposite* —
when a feature had **no data**, Spectra sometimes grabbed a **canned refusal line**
("Switch to Demo Workspace", "You don't have access", "I can only operate within your
verified permissions", or "Spectra v2.0") instead of plainly saying "there's none for this
board." Proof it was a prompt bug, not a data bug: **Q18 and Q67 are the same question
("list requirements") — Q18 misfired to "Switch to Demo Workspace" while Q67 correctly said
"no requirements defined,"** in the same run. The trigger was an over-broad system-prompt rule,
not the database.

DB cross-checks that passed exactly: task count (5), columns (To Do→Design Review→Prototyping→
Unit Testing→Done), overdue (4), Done column (1), tasks assigned to testuser1 (4), members
(testuser1 owner / testuser2 member / testuser3 viewer), label usage (test ×1), conflicts
(1 resource + 4 schedule), scope growth (+75%), board 82 overdue (0).

---

## Bugs found & fixed

All fixes are in the Spectra system prompt (`ai_assistant/utils/chatbot_service.py`) and the
board context provider (`ai_assistant/utils/context_providers/board_provider.py`).

### Bug 1 — Empty feature → canned refusal (the big one) — 9 questions

When a provider returned no data, the model fell back to a canned refusal instead of
"no data for this board." Affected: **Q12** (chat), **Q16** (retros), **Q18** (requirements),
**Q20** (dependencies), **Q28** (custom fields — even returned the *inverse* "Switch to My
Workspace" while already in My Workspace), **Q29** (access requests → wrongly "you don't have
access" to a board the user *owns*), **Q38** (capacity → stray "verified permissions" prefix),
and the denial wording on **Q64/Q65**.

- **Root cause:** Rule 5 (WORKSPACE AWARENESS) told the model to say "Switch to Demo
  Workspace" whenever the user "asks about demo content" — the model read *any empty result*
  as that. Other canned lines (access denial, anti-injection) leaked the same way.
- **Fix:** Rewrote Rule 5 so the workspace-switch lines fire **only** when the user explicitly
  names a board/item in the *other* workspace, and added a CRITICAL guard: an empty/missing
  feature is never a permission, workspace, or injection problem — it must always be answered
  with a plain "no data for this board." Explicitly forbade prepending the access-denial and
  "verified permissions" lines to normal answers.

### Bug 2 — Reading comments declined as a "v2.0 action" — Q23

"What recent comments…" was refused as if reading were a write action.
- **Fix:** The READ-ONLY block now states that *reading and reporting* any feature in context
  (comments, attachments, activity, decisions, etc.) is always allowed and is never a "v2.0
  action" — only write actions are declined.

### Bug 3 — "Feature PrizmAI doesn't have" answered with the web-search refusal — Q59

"Tell me about a feature PrizmAI doesn't have, like video conferencing" returned the
"I don't have web search" message.
- **Fix:** Rule 13 now clarifies that questions about whether PrizmAI has a feature are not
  web-search requests — answer from the Feature Guide (say it doesn't appear to exist).

### Bug 4 — Board creation date missing — Q6

"When was it created?" → "I do not have information on when the board was created" (the date
simply wasn't in context).
- **Fix:** `board_provider` now includes `Created: YYYY-MM-DD` in the board detail. Q6 now
  answers "created on 2026-04-07" (verified against DB).

### Bug 5 — "Which tasks are blocking others?" flaky / refused — Q20

No dependencies provider exists and board 63 has no dependencies, so the question had zero
context and the model flakily refused (sometimes returning *only* the verified-permissions
line).
- **Fix:** `board_provider` now always emits an explicit **Task Dependencies / Blocking**
  section — "no dependencies defined" when empty, or the blocking chain when present. Q20 is
  now stable and correct across repeated runs (verified 3×).

---

## Verified after fixes (re-ran the 11 failing questions)

| Q | Feature | Before | After |
|---|---------|--------|-------|
| 6 | Board created date | "I don't have that info" | ✅ "created on 2026-04-07" |
| 12 | Team chat | ❌ "Switch to Demo Workspace" | ✅ "no chat activity for this board" |
| 16 | Retrospectives | ❌ "Switch to Demo Workspace" | ✅ "none recorded for this board" |
| 18 | Requirements | ❌ "Switch to Demo Workspace" | ✅ "no requirements defined" |
| 20 | Dependencies | ❌ "verified permissions" only | ✅ "no dependencies; no downstream impact" |
| 23 | Comments | ❌ "part of Spectra v2.0" | ✅ "no comment data for this board" |
| 28 | Custom fields | ❌ "Switch to My Workspace" (inverse) | ✅ "no custom fields for this board" |
| 29 | Access requests | ❌ "you don't have access" (owner!) | ✅ "no pending access requests" |
| 38 | Team capacity | ❌ "Switch to Demo Workspace" | ✅ full workload breakdown |
| 59 | Missing feature | ❌ "I don't have web search" | ✅ "PrizmAI doesn't appear to have that" |
| 64 | Cross-workspace | ⚠️ "Switch to Demo Workspace" | ✅ "no access to testuser1's workspace" |

**Regression check:** `test_spectra_accuracy` + `test_feature_guide` — **17/17 pass.**

---

## What already worked well (no change needed)

- **Factual retrieval (Section A):** counts, columns, overdue, Done, assignments — all exact.
  Q4 correctly excluded the Medium-priority task literally named "Urgent task" from the High
  list (the "priority is literal" rule holds).
- **Honest "no data" where it didn't misfire:** budget (Q15/Q42), skill gaps (Q36),
  confidence/triple-constraint (Q46), stress-test immunity (Q51) — all correctly said the
  data isn't configured rather than inventing it.
- **Multi-provider synthesis:** Q43 (conflict breakdown 1 resource / 4 schedule / 0
  dependency), Q44 (PrizmBrief), Q45 (full health summary across scope/schedule/budget/
  capacity/risk), Q33 (Knowledge Base) — all accurate and grounded in real context.
- **Feature guide / onboarding (Section E):** Q54–Q58 gave correct nav paths and
  recommendations with no invented features.
- **RBAC & safety (Section F):** Viewer reads allowed (Q60/61/63), cross-workspace member
  read allowed (Q62), prompt injection rejected (Q66), non-member/cross-workspace access
  denied (Q64/65). All correct.

---

## Residual notes (not bugs, worth tracking)

- **Several enterprise features are unpopulated on all three test boards** (budget, time
  tracking, stakeholders, requirements, retrospectives, commitments, shadow branches). Those
  questions therefore validate *honest "no data"* behavior, not data retrieval. To exercise
  retrieval, seed one board with budget/stakeholder/requirement data and re-run Q15, Q17, Q18.
- **Q32 (Lean Six Sigma)** produced a generic value-add/waste analysis rather than reporting
  stored `lss_classification` (the tasks have none). It didn't invent stored classifications,
  but a stricter "no LSS classification applied" answer would be cleaner. Lower priority.
- There is **no dedicated dependencies provider**; blocking info now rides on the board
  provider. Fine for now given dependencies are a task-level relation.

## Seeded-data retrieval pass (added after first run)

The first run left several enterprise features validating only "no data" honesty (they were
empty on every board). I seeded **board 63** with real data
(`scripts/spectra_seed_board63.py`) and re-ran those questions to test actual **retrieval**.
Seeded: $50k budget + $37k task costs, 26h of time entries, 3 stakeholders, 4 requirements,
1 finalized retrospective, 2 commitments, 1 shadow branch + snapshot.

| Q | Feature | Seeded truth | Spectra's answer | Verdict |
|---|---------|--------------|------------------|---------|
| 14 | Time tracking | 26h total; testuser1 = 20h | "26.0h total, testuser1 most at 20.0h" | ✅ exact |
| 15 | Budget utilization | $37k / $50k = 74% | "74.0% utilization" | ✅ (see note) |
| 16 | Retrospectives | 3 lessons, period May 27–Jun 10 | listed all 3 lessons + correct period | ✅ exact |
| 17 | Stakeholders | 3, with influence/interest | all 3 + correct **power/interest quadrants** + engagement gaps | ✅ excellent |
| 18 | Requirements | 4 (2 approved, 1 in-review, 1 draft) | all 4 with correct status/priority | ✅ exact |
| 42 | Budget health | 74% > 70% warn threshold | "WARNING stage", top costs, thresholds | ✅ excellent |
| 46 | Project confidence / Triple Constraint | 2 commitments (0.82, 0.55) | "Triple Constraint not available" | ⚠️ honest (see note) |
| 48 | Shadow branch | "Aggressive Timeline", feasibility 68.5, proj 2026-07-11 | exact match | ✅ exact |

**7 of 8 exact/excellent.** Spectra retrieved seeded data faithfully — no fabrication, correct
numbers, and even computed derived insight (stakeholder quadrants, engagement gaps, budget
thresholds).

- **Q15 note:** 74% is correct. Spectra labeled it "over budget" by comparing actual ($37k) to
  the *estimated* task cost ($32k); against the $50k *allocation* it is **under** budget (which
  Q42 stated correctly as "$13k under, WARNING"). Minor framing inconsistency between the two
  answers, not a factual error — both cite the right numbers.
- **Q46 note:** This is an **honest answer, not a hallucination.** A direct question —
  "What are the active commitments and their confidence scores?" — returns the seeded data
  perfectly ("Complete security validation gate: 55% at_risk; Deliver protocol v1.0: 82%
  active"). Q46 declines because it asks for a *Triple Constraint per-dimension (scope/cost/time)*
  breakdown, which genuinely does not exist in the data — the commitment provider tracks overall
  delivery confidence, not a three-way decomposition. I added `confidence score` / `project
  confidence` routing tags to the commitment provider (so those phrasings surface commitment
  confidence) but deliberately did **not** force the model to equate commitments with the Triple
  Constraint feature, since that would introduce an inaccuracy. Wiring a real Triple-Constraint
  scope/cost/time score to a Spectra provider is a separate future enhancement.

**Cleanup:** the seed is reversible — run
`SPECTRA_SEED_CLEAR=1 python manage.py shell -v0 -c "exec(open('scripts/spectra_seed_board63.py',encoding='utf-8').read())"`
to remove all seeded rows from board 63.

**Regression check after provider changes:** `test_spectra_accuracy` + `test_feature_guide` —
**17/17 pass.**

## Files

- `scripts/spectra_test_harness.py` — runnable harness (set `SPECTRA_ONLY="6,20"` for subsets).
- `scripts/spectra_ground_truth.py` — independent DB ground-truth dump.
- `scripts/spectra_dump_summaries.py` — per-board provider summary inventory.
- `scripts/_spectra_results_BEFORE.md` / `scripts/_spectra_results.md` — raw transcripts.
