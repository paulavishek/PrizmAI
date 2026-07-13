# Running a Construction Project in PrizmAI

> **At a glance**
>
> - **Who:** Ray, a project manager at a mid-size general contractor
> - **Project:** Building out a **12,000 sq ft office fit-out** — demolition, framing, MEP
>   (mechanical/electrical/plumbing), drywall, finishes, and final inspection — on a fixed
>   handover date
> - **Team:** A site superintendent, subcontractor leads for each trade, and an architect of
>   record
> - **Features covered:** Smart board setup, Gantt & dependencies, Automations, AI Coach,
>   Pre-Mortem, Scope Autopsy, Stress Test, What-If & Shadow Boards, Decision Center, and
>   Budget & ROI
> - **How it ends:** The fit-out is handed over on schedule and on budget, with a Stress Test
>   and a weather-scenario Shadow Board keeping the critical path protected the whole way

This case study follows one build from mobilization to handover, showing *when* and *why* a
construction PM reaches for PrizmAI's advanced tools — and how sequencing, weather, and
subcontractor risk get managed before they cost days and dollars on site.

---

## 1. Kickoff: setting up the board

Ray starts from the dashboard and clicks **Create Board**, describing the job plainly:

> *"Office fit-out — demo, framing, MEP rough-in, inspections, drywall, finishes, and
> handover — on a fixed completion date, with every trade sequenced against inspection
> sign-offs."*

PrizmAI's **AI board setup** proposes a workflow through **Smart Column Suggestions**, which
Ray shapes into how a jobsite actually runs: **Backlog → Scheduled → In Progress → Inspection
→ Complete**.

He adds two **custom fields** so every task carries jobsite context:

- **Trade** — Demolition, Framing, Electrical, Plumbing, HVAC, Drywall, Finishes
- **Phase** — Pre-construction, Rough-in, Finishes, Closeout

Then Ray builds out the work packages and — because sequencing is everything in
construction — links the **dependencies** that reflect physical reality: MEP rough-in can't
start until framing passes inspection; drywall can't close until MEP is signed off. On the
**Gantt chart**, those links draw the **critical path** through the job, so Ray can see at a
glance which tasks, if they slip, push the handover date. He sets inspection milestones and
**invites** the superintendent and trade leads.

## 2. Running day-to-day: Automations, the AI Coach, and the Gantt

Ray sets up an **Automation** to keep inspections from falling through the cracks. Rules are
plain WHEN / IF / THEN dropdowns — no AI, one action each:

- **WHEN** a task moves to *Inspection*
- **IF** its *Phase* is *Rough-in*
- **THEN** *Assign to a specific person* — the site superintendent who coordinates the
  inspector

The **Gantt chart** is Ray's daily home base — he watches the critical path and drags dates
as reality shifts, with dependent tasks flagged when a move would affect them. A week in, the
**AI Coach** surfaces a pattern:

> **💡 AI Coach:** *"Framing sign-off has slipped two days, and three MEP tasks depend on it.
> On the current sequence that pushes drywall — and the handover — by the same two days.
> Expediting the framing inspection recovers the schedule."*

Ray gets the inspector out a day early and protects the critical path before the slip
compounds down the chain.

## 3. Pre-Mortem: imagining failure before MEP rough-in

Before the high-stakes MEP rough-in phase, Ray opens the board's **More (⋯) menu** and
chooses **Run Pre-Mortem**. PrizmAI plays devil's advocate and generates **five distinct ways
the job could go wrong**, each with a risk level and root cause. Three from Ray's run:

1. **Inspection domino** — *a failed framing inspection cascades into every trade behind it,
   collapsing the rough-in schedule.*
2. **Long-lead delay** — *the switchgear arrives late and electrical rough-in can't complete,
   stalling drywall.*
3. **Trade collision** — *electrical and plumbing are scheduled in the same ceiling space the
   same week and get in each other's way.*

Ray clicks **Acknowledge Scenario** on the long-lead delay and notes: *"Confirmed switchgear
delivery date with the supplier; staged a backup vendor."* Each trade lead can acknowledge
different scenarios independently.

## 4. Scope handling: the TaskScopeReason modal and Scope Autopsy

Mid-build, the client requests changes: additional data drops in every office and an upgraded
finish package in the lobby. Because Ray enabled scope tracking early — which captures a
**baseline snapshot** — PrizmAI shows a short **scope-reason modal** whenever a task is added
after the baseline. He tags each change-order task with a reason from the dropdown:
**Stakeholder Request** for the client's asks (other options include Requirement Change,
Discovered Complexity, and Gold Plating).

When the finishes phase starts looking tight, Ray opens **Scope Autopsy** from the scope
dashboard. It renders a plain-language **timeline of scope-growth events** that separates the
documented change orders from any undocumented growth — showing exactly how much the client's
additions expanded the finishes workload. That timeline is Ray's paper trail when he submits
the change order for additional time and cost: the growth is documented, dated, and
attributable, not a vague dispute at closeout.

## 5. Stress Test: the adversarial chaos engine

Before the finishes-and-closeout push, Ray runs a **Stress Test** from the ⋯ menu — the tool
that maps most naturally onto a jobsite, where "chaos" means weather, supply delays, and
crews that don't show. PrizmAI simulates those shocks against the schedule and returns a
composite **Immunity Score** across five dimensions: **Schedule, Budget, Team, Dependencies,**
and **Scope Stability**.

> **Immunity Score: 48 / 100 — MODERATE**
>
> - *Schedule: high risk — zero float on the critical path through inspections*
> - *Dependencies: fragile — a single failed inspection cascades to four trades*

The four bands run **FRAGILE → MODERATE → RESILIENT → ANTIFRAGILE**. Beneath the score,
PrizmAI prescribes fixes it calls **Vaccines**. Ray expands the top one:

> *"Add schedule float ahead of the drywall close by pulling finishes prep forward, so a
> single failed inspection doesn't cascade to the handover date."* — **Applying this Vaccine
> raises Schedule from high-risk toward RESILIENT (+15).**

Ray resequences to bank two days of float ahead of the inspection gate and re-runs the test
to confirm the lift.

## 6. Scenario planning: What-If and Shadow Boards

A stretch of bad weather is forecast during the exterior-dependent work. Ray pressure-tests
it before it hits. He opens the **What-If Simulator** and sets the sliders:

- **Deadline:** critical-path tasks pushed 5 days (weather delay)
- **Team size:** −1 (a crew pulled to another site)

The simulator runs the change against the board's real data and returns a before/after
comparison: the handover date slips and the scenario is flagged **high-risk**.

Rather than lose track of that risk, Ray clicks **Promote to Shadow Board**. PrizmAI spins up
a living parallel branch beside the real board that pulls in daily progress and maintains a
**Divergence Log** — a running record of how far the actual job is drifting from the
weather-delay scenario. Through the rainy stretch, Ray watches the divergence: as long as the
real board stays ahead of the shadow, the handover is safe; the moment it falls behind, he
has early warning to add a crew or add a shift.

## 7. The command center: Decision Center

Ray starts each morning in the **Decision Center**, which folds every signal above into one
view. At the top is his **AI Daily Briefing** (the "Focus Today" headline):

> *"Framing inspection is the one gate holding four downstream trades — clear it today.
> Budget is healthy, but the weather Shadow Board's divergence log shows the exterior work
> tightening your float. The switchgear delivery is confirmed for Thursday."*

Below it, his work sorts into three queues:

1. **Action Required** — expedite the framing inspection blocking MEP rough-in.
2. **Awareness** — the finishes crew's load is rising after the lobby upgrade change order.
3. **Quick Win** — release the completed demo phase so the framing crew can mobilize.

## 8. Budget & ROI: holding the number

On the **Budget & ROI** dashboard, Ray tracks committed vs. actual cost across trades —
subcontractor draws, material invoices, and the approved change orders. PrizmAI tracks the
**burn rate** and predicts the **budget-exhaustion date**, flipping status from OK → Warning
→ Critical as spend moves. When the client's change orders come in, Ray logs the added cost
against the change-order line, and the documented Scope Autopsy timeline backs the billing —
so the project stays **on budget** because the growth was captured and charged, not absorbed.

## 9. Closeout: on-time handover

The fit-out passes final inspection and hands over on the committed date. Because the
**Gantt** kept the critical path visible, the **Stress Test** banked float ahead of the
inspection gates, and the **weather Shadow Board** gave early warning through the rainy
stretch, none of the classic construction slips turned into a missed handover. The documented
change orders mean the final number matches what was billed.

> If a project ever has to be wound down instead of completed — a job cancelled, a build
> mothballed — PrizmAI's **Exit Protocol** runs a structured shutdown that salvages the
> reusable templates and checklists and captures the lessons for the next job. See the
> [Marketing Campaign case study](marketing-campaign.md) for a full walkthrough.

---

## What to take from this

Ray delivered a sequencing-heavy job on a fixed date without letting the usual gremlins —
failed inspections, long-lead items, weather — cascade into a slip. The **Gantt and
dependencies** kept the critical path honest, the **AI Coach** and **Stress Test** exposed
where a single failed inspection could domino, the **weather Shadow Board** turned a forecast
into an early-warning system, and **Scope Autopsy** turned client change orders into a
documented, billable paper trail. On a jobsite, that's the difference between managing the
schedule and being managed by it.
