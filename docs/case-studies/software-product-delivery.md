# Running a Software Product Delivery in PrizmAI

> **At a glance**
>
> - **Who:** Sofia, a product delivery lead at a growing SaaS company
> - **Project:** Shipping **v3.0** — a new analytics dashboard, a public REST API, and a
>   billing revamp — on a fixed 12-week release train
> - **Team:** Two backend engineers, a frontend engineer, a designer, and a QA engineer
> - **Features covered:** Smart board setup, Automations, AI Coach, Explainable AI,
>   Pre-Mortem, Scope Autopsy, Stress Test, What-If & Shadow Boards, Decision Center,
>   Budget & ROI, and **Requirements traceability**
> - **How it ends:** v3.0 ships on time; every delivered story traces back to an approved
>   requirement, and the release closes with a clean audit trail

This case study follows one release from kickoff to launch, showing *when* and *why* a
delivery lead reaches for PrizmAI's advanced tools — and how the platform keeps a fast
release train honest about scope, risk, and what was actually promised.

---

## 1. Kickoff: setting up the board

Sofia starts from the dashboard and clicks **Create Board**, describing the work plainly:

> *"Deliver the v3.0 release — analytics dashboard, public REST API, and billing revamp —
> in a 12-week train, with QA sign-off before each merge to the release branch."*

PrizmAI's **AI board setup** proposes a workflow through **Smart Column Suggestions**, which
Sofia shapes into her team's real flow: **Backlog → Ready → In Progress → In Review → QA →
Done**.

She adds two **custom fields** so every task carries engineering context:

- **Component** — Frontend, Backend, API, Infra
- **Work Type** — Feature, Bug, Tech Debt

Then she breaks v3.0 into epics and stories, links the dependencies (the API has to land
before the dashboard can consume it), sets a milestone per release checkpoint, and
**invites the team**.

## 2. Running day-to-day: Automations, the AI Coach, and Explainable AI

Sofia sets up an **Automation** to remove a recurring bit of manual bookkeeping. Rules are
plain WHEN / IF / THEN dropdowns — no AI, one action each:

- **WHEN** a task moves to *QA*
- **IF** its *Work Type* is *Bug*
- **THEN** *Assign to a specific person* — the QA engineer

Now every bug fix routes to QA automatically instead of waiting to be noticed.

A few days in, the **AI Coach** flags a pattern:

> **💡 AI Coach:** *"Three of next week's highest-risk tasks — API auth, billing webhooks,
> and the migration — are due in the same two-day window. Converging risk like this usually
> precedes a slip. Consider staggering one."*

This is where **Explainable AI** earns its keep. When PrizmAI marks the billing-webhook task
as high-risk, Sofia clicks the **"Why?"** button and sees the reasoning broken down — task
complexity, an external dependency (the payment processor), a skill gap, and timeline
pressure — along with the AI's confidence level and the assumptions behind it. She doesn't
have to trust a black box; she can see the drivers and challenge them. When she assigns the
task, the same **"Why?"** explains the assignee recommendation as a skill-and-availability
match, not a guess. Sofia staggers the migration by two days and moves on.

## 3. Pre-Mortem: imagining failure before the mid-release checkpoint

Before the week-6 checkpoint, Sofia opens the board's **More (⋯) menu** and chooses **Run
Pre-Mortem**. PrizmAI plays devil's advocate and generates **five distinct ways the release
could fail**, each with a risk level and root cause. Three from Sofia's run:

1. **Integration crunch** — *the dashboard can't be finished on time because the API
   contract keeps changing under it.*
2. **QA bottleneck** — *everything lands in the final week and QA can't clear the backlog
   before the freeze.*
3. **Migration risk** — *the billing migration runs long in staging and there's no rollback
   rehearsal.*

Sofia clicks **Acknowledge Scenario** on the migration risk and notes: *"Scheduled a
rollback rehearsal in week 9; froze the API contract at end of week 5."* Each engineer can
acknowledge different scenarios independently.

## 4. Scope handling: the TaskScopeReason modal and Scope Autopsy

Halfway through, sales asks for two "small" additions: SSO for the new dashboard and an extra
billing report. Because Sofia enabled scope tracking early — which captures a **baseline
snapshot** — PrizmAI shows a short **scope-reason modal** whenever a task is added after the
baseline. She tags the new stories with a reason from the dropdown: **Stakeholder Request**
for the sales asks (other options include Requirement Change, Discovered Complexity, and Gold
Plating).

When the frontend engineer starts looking overloaded, Sofia opens **Scope Autopsy** from the
scope dashboard. Instead of a vague "we added stuff" feeling, she gets a plain-language
**timeline of scope-growth events** that cleanly separates documented additions (the SSO and
report requests) from undocumented growth — and shows exactly how much the late asks pushed
the frontend workload. That timeline becomes her evidence when she negotiates the SSO story
out of v3.0 and into v3.1.

## 5. Stress Test: the adversarial chaos engine

Two weeks before the freeze, Sofia runs a **Stress Test** from the ⋯ menu. PrizmAI throws
simulated "chaos" at the release — a lost engineer, a compressed timeline, a dependency shock
— and returns a composite **Immunity Score** across five dimensions: **Schedule, Budget,
Team, Dependencies,** and **Scope Stability**.

> **Immunity Score: 61 / 100 — MODERATE**
>
> - *Dependencies: high risk — the dashboard, billing UI, and reports all sit behind the
>   one API engineer*
> - *Schedule: thin buffer before the freeze*

The four bands run **FRAGILE → MODERATE → RESILIENT → ANTIFRAGILE**. Beneath the score,
PrizmAI prescribes fixes it calls **Vaccines**. Sofia expands the top one:

> *"Pair a second engineer onto the API surface and split the contract work so no single
> person blocks three downstream tasks."* — **Applying this Vaccine raises Dependencies from
> high-risk toward RESILIENT (+16).**

She pairs her second backend engineer onto the API and re-runs the test to confirm the lift.

## 6. Scenario planning: What-If and Shadow Boards

With the freeze approaching, Sofia pressure-tests a real worry — one engineer has a
pre-booked vacation in week 10. She opens the **What-If Simulator** and sets the sliders:

- **Team size:** −1 (engineer out for a week)
- **Deadline:** unchanged (the release date is fixed)

The simulator runs the change against the board's real data and returns a before/after
comparison: several tasks on the critical path slip past the freeze and the scenario is
flagged **high-risk**.

Rather than lose track of that risk, Sofia clicks **Promote to Shadow Board**. PrizmAI spins
up a living parallel branch beside the real board that pulls in daily progress and maintains
a **Divergence Log** — a running record of how far reality is drifting from the
short-staffed scenario. If the team stays ahead of the shadow, Sofia knows the vacation is
absorbable; if it falls behind, she has early warning to pull the SSO story or add help.

## 7. The command center: Decision Center

Sofia starts each morning in the **Decision Center**, which folds every signal above into one
view. At the top is her **AI Daily Briefing** (the "Focus Today" headline):

> *"The migration rollback rehearsal is the one thing gating your week-9 checkpoint. QA
> throughput is holding, but the Shadow Board's divergence log shows the vacation week
> tightening your critical path. Clear the API contract review today."*

Below it, her work sorts into three queues:

1. **Action Required** — approve the frozen API contract so downstream work can start.
2. **Awareness** — the frontend engineer's load is near its limit after the SSO request.
3. **Quick Win** — merge the finished analytics-export story, already through QA.

## 8. Budget & ROI: keeping the release honest on cost

On the **Budget & ROI** dashboard, Sofia tracks the release's engineering cost — logged hours
roll up into labor cost per task, and she watches the **burn rate** against the release
budget. Because v3.0 is tracking cleanly, PrizmAI rates budget health as **Good** and flags
no overrun risk — the useful signal here is the *absence* of alarms, confirming the fixed
train is affordable at the current pace.

## 9. Closeout: Requirements traceability and a clean launch

v3.0 ships on the release date. What makes the launch defensible — not just done — is
**Requirements traceability**.

From the start, Sofia captured the release's promises as **Requirements** (each with an
identifier, a type like *Functional* or *Business*, and a priority), and **linked** each one
to the goals, strategies, and **tasks** that deliver it. As work progressed, every
requirement moved through its lifecycle — **Draft → In Review → Approved → Implemented →
Verified** — with a full status history behind it.

At launch, Sofia opens the requirements view and sees the whole map at a glance: every
Approved requirement is linked to delivered, QA'd tasks and marked **Verified**; the SSO
requirement that got deferred is clearly parked for v3.1 rather than silently dropped. When
an executive asks "did we actually ship what we committed to?", the answer isn't a
recollection — it's a traceable chain from each goal to the requirement to the task that
implemented it, with the audit trail to prove it.

> If a project ever needs to be wound down instead of shipped — a release cancelled, a
> product sunset — PrizmAI's **Exit Protocol** runs a structured, dignified shutdown that
> salvages the reusable parts and captures the lessons. See the
> [Marketing Campaign case study](marketing-campaign.md) for a full walkthrough.

---

## What to take from this

Sofia ran a fast, fixed release train without flying blind. **Explainable AI** let her trust
(and challenge) the risk and assignment calls, the **AI Coach** and **Stress Test** caught
converging and dependency risk before the freeze, **Scope Autopsy** turned "we added stuff"
into evidence she could negotiate with, and **What-If + Shadow Boards** told her whether a
vacation week was survivable. At the end, **Requirements traceability** meant "we shipped what
we promised" was a provable fact — the difference between a release that's finished and one
that's accountable.
