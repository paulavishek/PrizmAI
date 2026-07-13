# Running a Marketing Campaign in PrizmAI

> **At a glance**
>
> - **Who:** Dana, a campaign director at a mid-size B2B SaaS company
> - **Project:** A 90-day multi-channel product launch — landing pages, an automated
>   email nurture sequence, high-spend paid acquisition, a live webinar, and launch-week PR
> - **Team:** A copywriter, a brand designer, a paid-media specialist, and a freelance
>   video editor
> - **Features covered:** Smart board setup, Automations, AI Coach, Pre-Mortem, Scope
>   Autopsy, Stress Test, What-If & Shadow Boards, Decision Center, Budget & ROI, and the
>   full **Exit Protocol**
> - **How it ends:** Mid-flight conversion volatility plus an executive budget freeze halts
>   the campaign. Instead of a dead dashboard, Dana runs an orderly wind-down, salvages the
>   reusable parts, and relaunches a sharper, context-aware version next quarter

This case study walks a new user through one campaign from kickoff to closeout, showing
*when* and *why* to reach for PrizmAI's advanced risk and simulation tools — not just that
they exist.

---

## 1. Kickoff: setting up the board

Dana starts from the dashboard and clicks **Create Board**. When prompted to describe the
project, she gives it a concrete objective:

> *"Multi-channel acquisition campaign for the V2 platform launch by Q3 — optimize paid
> spend to hold Customer Acquisition Cost (CAC) under $150 while coordinating creative
> asset handoffs across the team."*

PrizmAI's **AI board setup** reads the objective and proposes a starting workflow via
**Smart Column Suggestions**. Dana fine-tunes the columns to match how her team actually
works: **Backlog → Briefed → In Production → Review & Sign-Off → Scheduled → Live**.

Because a campaign produces many kinds of deliverables, she adds two **custom fields** so
every task carries the context she'll want to filter and report on later:

- **Channel** — Email, Paid Social, Web, PR, Webinar
- **Asset Type** — Copy, Design, Video, Landing Page

She breaks the campaign into its first ~30 tasks, links the obvious dependencies, sets due
dates leading up to launch week, and **invites her team** by email. Each person sees only
the boards and tasks they've been added to.

## 2. Running day-to-day: Automations and the AI Coach

To kill repetitive follow-ups, Dana sets up an **Automation** from the board's Automations
panel. PrizmAI's rules use plain WHEN / IF / THEN dropdowns — no AI, so they fire instantly
and predictably. Each rule runs a single action:

- **WHEN** a task moves to *Review & Sign-Off*
- **IF** its *Channel* is *Paid Social*
- **THEN** *Assign to a specific person* — the paid-media specialist

Now every paid asset lands with the right reviewer automatically.

A week in, an insight indicator appears in Dana's sidebar. It's her **AI Coach**:

> **💡 AI Coach:** *"Rolling 7-day velocity is down 40%. Likely bottleneck: four video ad
> assets are stalled in 'Review & Sign-Off' waiting on the same reviewer. Clearing this
> should restore your projected launch timeline."*

Dana redistributes the secondary sign-offs and unblocks the creative pipeline before a
single deadline slips — exactly the kind of early signal that's easy to miss heads-down.

## 3. Pre-Mortem: imagining failure before it happens

Two weeks before paid spend goes live, Dana opens the board's **More (⋯) menu** and chooses
**Run Pre-Mortem**. PrizmAI plays devil's advocate and generates **five distinct ways the
campaign could fail**, each with a risk level and the root cause behind it. Three from
Dana's run:

1. **Asset bottleneck** — *the interactive landing page misses the launch window because
   the freelance editor's embed assets slip in production.*
2. **Budget bleed** — *paid social overspends in week one because conversion tracking tags
   are misconfigured, burning budget on unverified audiences.*
3. **Audience drop-off** — *webinar registrations stall because the invite sequence went out
   without A/B-tested subject lines.*

Dana can't pre-empt all five, but she clicks **Acknowledge Scenario** on the first and adds
a note: *"Decoupled the landing page from the final video — a placeholder graphic ships as a
fallback."* Each teammate can acknowledge different scenarios independently.

## 4. Scope handling: the TaskScopeReason modal and Scope Autopsy

Mid-campaign, executives request a sudden expansion — localized creative variants for
several international micro-segments.

Because Dana turned on scope tracking early (which captures a **baseline snapshot** of the
project), PrizmAI now shows a short **scope-reason modal** whenever a task is added after the
baseline. She tags each of the eight new localization tasks with a reason from the dropdown
— here, **Stakeholder Request** (other options include Requirement Change, Discovered
Complexity, and Gold Plating).

A week later, sensing strain on her design resources, Dana opens **Scope Autopsy** from the
scope dashboard. Instead of a vague task list, PrizmAI renders a plain-language **timeline of
scope-growth events**, showing that the mid-flight stakeholder additions grew the creative
backlog sharply — and mapping exactly why the design team hit a capacity wall. Every
documented addition is separated from undocumented growth, so the story is honest.

## 5. Stress Test: the adversarial chaos engine

With launch week approaching, Dana runs a **Stress Test** from the board's ⋯ menu. PrizmAI
subjects the campaign to simulated "chaos" — sudden resource loss, compressed timelines,
dependency shocks — and returns a composite **Immunity Score** across five dimensions:
**Schedule, Budget, Team, Dependencies,** and **Scope Stability**.

> **Immunity Score: 42 / 100 — FRAGILE**
>
> - *Team: critical risk (single point of failure on the designer)*
> - *Schedule: thin buffer heading into launch week*

The four bands run **FRAGILE → MODERATE → RESILIENT → ANTIFRAGILE**. Beneath the score,
PrizmAI prescribes targeted fixes it calls **Vaccines**. Dana expands the first:

> *"Add a backup design resource, or stand up a pre-approved brand-template library for ad
> production."* — **Applying this Vaccine raises Team from FRAGILE toward RESILIENT (+18).**

She stands up the template library immediately and re-runs the test to confirm the lift,
insulating her active sprints against a single-person bottleneck.

## 6. Scenario planning: What-If and Shadow Boards

When rumors of a corporate budget squeeze start circulating, Dana pressure-tests her
readiness *before* anything changes. She opens the **What-If Simulator** and sets the
sliders to model the most likely fallout of a budget cut:

- **Team size:** −1 (lose the freelance video editor)
- **Deadline:** pulled in 10 days

The simulator runs the change against the board's real data and returns a before/after
comparison: the projected completion date slips well past launch week and the scenario is
flagged **high-risk**.

Rather than let that risk fade from view, Dana clicks **Promote to Shadow Board**. PrizmAI
spins up a living parallel branch beside the real board. As the team completes work day to
day, the Shadow Board pulls that progress into its own model and maintains a **Divergence
Log** — a running record of exactly how far reality is drifting from the constrained
scenario. Dana can watch the gap without touching production.

## 7. The command center: Decision Center

Dana starts each morning in the **Decision Center**, PrizmAI's prioritization hub that
folds every signal above into one view. At the top sits her **AI Daily Briefing** (the
"Focus Today" headline):

> *"Paid channels are converting ~15% below projection, pulling your budget-exhaustion date
> in to about three weeks out. Your Shadow Board's divergence log shows a widening variance.
> Prioritize the pending ad-performance mitigations today."*

Below it, her work is sorted into three queues:

1. **Action Required** — acknowledge the high-risk Pre-Mortem scenario on conversion-tag
   validation.
2. **Awareness** — review the design team's capacity chart, now near its limit after the
   scope additions.
3. **Quick Win** — approve the finished email-nurture brief so it moves straight into
   production.

## 8. Budget reality: the numbers that decide everything

On the **Budget & ROI** dashboard, every task card carries estimated vs. actual cost —
vendor invoices, contractor fees, daily media spend. PrizmAI tracks the **burn rate** and
predicts the **budget-exhaustion date**, flipping status from OK → Warning → Critical as
spend climbs.

With paid conversions stalling, the AI budget analysis rates campaign health as
**Concerning**: at the current efficiency, the CAC target is mathematically out of reach.
Then the decisive constraint lands from above — a corporate reallocation **freezes the
remaining budget** for unlaunched Q3 initiatives. The campaign, as scoped, is over.

## 9. Exit Protocol: an orderly wind-down

This is where most tools leave you with a board that just goes quiet. PrizmAI instead runs
**Exit Protocol** — a structured, dignified shutdown Dana starts from the board header (it
can also trigger automatically when health signals like velocity decline, budget-vs-progress,
and missed deadlines cross a threshold).

**Hospice.** PrizmAI produces an **assessment** of where things stand and a custom
**Knowledge-Extraction Checklist** so nothing important is lost:

- *Document the final paid-channel conversion baselines.*
- *Log contractor hours completed to date.*
- *Archive finished visual assets to the organizational asset bank.*

Dana's team works through it while the context is fresh.

**Organ Transplant.** PrizmAI scans the project for reusable components — it calls them
**organs** — scores each for reusability, and files them in a searchable **Organ Library**.
From Dana's campaign it salvages:

- The **email nurture sequence** → a reusable task template
- The *"notify on paid review"* **Automation rule** → an execution template
- The **audience-research findings** → an entry in organizational memory

Each organ is fully self-contained and ready to **transplant** into a future board, with an
AI note on how well it fits and what to adapt.

## 10. Cemetery and Resurrection: compounding the knowledge

**Cemetery.** Dana buries the project. PrizmAI records a permanent gravestone with the
**cause of death** — here, *💸 Budget Exhaustion* (a *🔀 Strategic Pivot* is the alternative,
since the money moved to another priority) — and generates an **AI Autopsy Report**: a
plain-language summary, a timeline of the decline, and two candid lists:

- **Lessons to repeat** — *automated review triggers cut creative cycle time noticeably.*
- **Lessons to avoid** — *scaling top-of-funnel paid spend before locking conversion
  tracking correlates with budget bleed.*

It's the honest retrospective teams usually skip when a project dies.

**Resurrection.** Next quarter, a leaner version of the launch is greenlit. Instead of a
blank board, Dana opens the cemetery entry and clicks **Resurrect**. The new board arrives
pre-seeded with the surviving lessons and the salvaged organs — and PrizmAI **auto-generates
a fresh Pre-Mortem** informed by how the last attempt failed. Its very first risk scenario?
*Validate conversion tracking 48 hours before launch to prevent unmonitored budget bleed.*
Dana learned that the expensive way once; this time it's built into the plan from day one.

---

## What to take from this

Dana never had to guess. The **AI Coach** and **Decision Center** caught velocity and
efficiency problems early, **Scope Autopsy** and **Stress Test** exposed exactly where the
campaign was fragile, **What-If and Shadow Boards** mapped the budget-cut risk without
disrupting live work, and **Budget & ROI tracking** made the hard call visible before it
became a crisis.

Most projects don't end in a wind-down — **Software** and **Construction** teams typically
ship on time (see those case studies). But when a project *does* have to be shut down,
**Exit Protocol** turns a cancelled campaign into a stocked toolkit and a smarter relaunch —
a graduation, not a grave.
