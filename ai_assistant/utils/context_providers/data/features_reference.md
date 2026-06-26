# PrizmAI Feature Guide

Authoritative reference for Spectra to explain PrizmAI features and recommend the
right tool for a user's goal. Every feature entry has three fields:
**What it does**, **Use it when**, and **Where to find it**.

Locations: top-level features live in the **left sidebar**. Board-level AI tools
live in the **AI Tools panel** on an open board (open a board, then click the
**AI Tools** button to slide out the panel; tools are grouped into the sections
named below).

---

## Core navigation (left sidebar)

### Dashboard
- **What it does:** Landing view summarizing your workspace — boards, tasks, and at-a-glance status.
- **Use it when:** You want a quick overview of everything after logging in.
- **Where to find it:** Sidebar → Dashboard.

### Goals
- **What it does:** Top of the strategic hierarchy (Goals → Missions → Strategies → Boards → Tasks); defines organizational objectives.
- **Use it when:** You want to set high-level objectives and connect day-to-day work to them.
- **Where to find it:** Sidebar → Goals.

### Missions
- **What it does:** Strategic missions that sit under Goals and group the Strategies/Boards that deliver them.
- **Use it when:** You're breaking a Goal into concrete strategic initiatives.
- **Where to find it:** Sidebar → Missions.

### Boards
- **What it does:** Kanban boards with columns, tasks, labels, assignees, due dates, and progress — the core workspace for execution.
- **Use it when:** You're planning and tracking the actual work.
- **Where to find it:** Sidebar → Boards.

### Task Aging Alerts
- **What it does:** Every kanban card shows an adaptive badge counting how many days the task has sat in its **current column** (the count resets whenever the task moves). The badge stays hidden while a task is fresh, then escalates through a neutral grey pill, an amber **warning**, and a red **critical** as it stalls. Spectra reads the same signal, so you can ask "which tasks are stalling?" and stalled tasks also surface in Focus Today.
- **Use it when:** You want to spot work that has stopped moving and may be blocked.
- **Where to find it:** It's automatic on board cards. Tune thresholds in Board Settings (board-level Warning/Critical day counts) or per column via the column's ⋮ menu → *Aging Alerts* (inherit, custom, or disable). Done/Backlog-style columns have it off by default.

### Discovery
- **What it does:** Ideas inbox with AI scoring and an impact/effort matrix to triage what to build next.
- **Use it when:** You have a backlog of raw ideas and need to decide which are worth pursuing.
- **Where to find it:** Sidebar → Discovery (also Board → AI Tools → Plan → Discovery).

### Calendar
- **What it does:** Unified calendar of tasks and events across all your boards.
- **Use it when:** You want a time-based view of deadlines and events in one place.
- **Where to find it:** Sidebar → Calendar.

### Wiki (Knowledge Hub)
- **What it does:** Documentation hub for wiki pages; Spectra can search and cite these pages.
- **Use it when:** You're capturing or looking up project documentation, standards, or notes.
- **Where to find it:** Sidebar → Wiki.

### Messages
- **What it does:** Team chat rooms, task threads, file sharing, and notifications.
- **Use it when:** You need to discuss work with your team or share files.
- **Where to find it:** Sidebar → Messages.

### Conflicts
- **What it does:** Detects and surfaces project conflicts (e.g. scheduling/resource clashes) with a resolution dashboard.
- **Use it when:** You suspect overlapping commitments or want to review/resolve detected conflicts.
- **Where to find it:** Sidebar → Conflicts.

### Project Cemetery
- **What it does:** Archive and post-mortem repository for completed or discontinued projects, preserving lessons.
- **Use it when:** You want to look back at finished/failed projects and what was learned.
- **Where to find it:** Sidebar → Project Cemetery.

---

## Tools (sidebar — pinned below navigation)

### Automations
- **What it does:** Rule-based workflow engine — trigger and scheduled rules that act when conditions are met (assign, notify, move, etc.).
- **Use it when:** You're repeating manual steps and want them to happen automatically.
- **Where to find it:** Sidebar → Tools → Automations.

### Time Tracking
- **What it does:** Log hours against tasks and view timesheets for resource and effort analysis.
- **Use it when:** You need to record time spent or analyze where effort is going.
- **Where to find it:** Sidebar → Tools → Time.

### Focus Today (Decision Center)
- **What it does:** A morning decision queue batching what needs your attention — conflicts, risks, overdue tasks, and scope alerts.
- **Use it when:** You want a single prioritized list of decisions to clear each day.
- **Where to find it:** Sidebar → Tools → Focus Today.

### Organizational Memory
- **What it does:** Workspace-wide knowledge capture and AI-powered search across decisions, lessons, and patterns.
- **Use it when:** You're looking for institutional knowledge that spans boards/projects.
- **Where to find it:** Sidebar → Tools → Memory.

### Ask Spectra
- **What it does:** The AI project assistant (this assistant) — answers questions about your boards, tasks, risks, and the strategic hierarchy, and explains features.
- **Use it when:** You want a fast, data-grounded answer or guidance on what to do next.
- **Where to find it:** Sidebar → Ask Spectra.

---

## Board AI tools — Analyze

### Analytics
- **What it does:** Board dashboard with completion, velocity, and health metrics plus AI insights.
- **Use it when:** You want to understand how the board is performing.
- **Where to find it:** Board → AI Tools → Analyze → Analytics.

### Burndown
- **What it does:** AI burndown/velocity prediction with a completion forecast.
- **Use it when:** You want to know whether you're on track to finish on time.
- **Where to find it:** Board → AI Tools → Analyze → Burndown.

### Skill Gaps
- **What it does:** Identifies gaps between team skills and task requirements and supports development plans.
- **Use it when:** Work needs skills your team may not have, and you want to plan for it.
- **Where to find it:** Board → AI Tools → Analyze → Skill Gaps.

### Status Report
- **What it does:** Generates a stakeholder-ready project status report (with RAG status).
- **Use it when:** You need to communicate project status to stakeholders.
- **Where to find it:** Board → AI Tools → Analyze → Status Report.

### Resource Optimization
- **What it does:** AI-powered team workload balancing and task reassignment suggestions.
- **Use it when:** Some people are overloaded and others have capacity.
- **Where to find it:** Board → AI Tools → Analyze → Resource Optimization.

---

## Board AI tools — Plan

### Budget & ROI
- **What it does:** Tracks budget, costs, and return on investment for the project.
- **Use it when:** You need to monitor spend against budget or justify ROI.
- **Where to find it:** Board → AI Tools → Plan → Budget & ROI.

### Scope
- **What it does:** Monitors scope changes against a baseline with snapshots and constraint tracking.
- **Use it when:** You're worried about scope creep and want to see how scope has moved.
- **Where to find it:** Board → AI Tools → Plan → Scope.

### Requirements
- **What it does:** AI requirement analysis — quality scoring, gap detection, and traceability to tasks.
- **Use it when:** You're managing formal requirements and want to trace them through to delivery.
- **Where to find it:** Board → AI Tools → Plan → Requirements.

### Gantt
- **What it does:** Timeline view with task dependencies, milestones, and drag-to-reschedule.
- **Use it when:** You want a date-driven view of the plan and dependencies.
- **Where to find it:** Board → tab bar → Gantt.

---

## Board AI tools — AI Insights

### AI Coach
- **What it does:** Proactive coaching suggestions on workload, deadlines, and risks, plus PM metrics.
- **Use it when:** You want ongoing nudges on how to run the project better.
- **Where to find it:** Board → AI Tools → AI Insights → AI Coach.

### PrizmBrief
- **What it does:** Generates audience-aware AI presentation slides from board data.
- **Use it when:** You need to turn project data into a presentation quickly.
- **Where to find it:** Board → AI Tools → AI Insights → PrizmBrief.

### Knowledge Base
- **What it does:** Your project's interconnected memory — decisions, lessons, risks, and milestones (Knowledge Graph).
- **Use it when:** You want to capture or revisit why decisions were made and what was learned.
- **Where to find it:** Board → AI Tools → AI Insights → Knowledge Base.

---

## Board AI tools — Scenarios & Risk

### What-If
- **What it does:** Simulates board/scenario changes and analyzes the predicted impact.
- **Use it when:** You want to test a change before committing to it.
- **Where to find it:** Board → AI Tools → Scenarios & Risk → What-If.

### Shadow Board
- **What it does:** Parallel-universe branches from snapshots — test changes and commit them with merge/feasibility scoring.
- **Use it when:** You want to explore an alternative plan in isolation without touching the live board.
- **Where to find it:** Board → AI Tools → Scenarios & Risk → Shadow Board.

### Pre-Mortem
- **What it does:** AI failure simulation — generates likely failure scenarios before execution so you can pre-empt them.
- **Use it when:** You're starting something risky and want to know what could go wrong in advance.
- **Where to find it:** Board → AI Tools → Scenarios & Risk → Pre-Mortem.

### Stress Test
- **What it does:** Red-teams the project plan with AI attack scenarios and an immunity score.
- **Use it when:** You want to pressure-test how resilient the plan is.
- **Where to find it:** Board → AI Tools → Scenarios & Risk → Stress Test.

---

## Board AI tools — Project Review

### Retrospectives
- **What it does:** AI-powered retrospectives with action items and improvement tracking.
- **Use it when:** A sprint/project phase ended and you want to capture what to improve.
- **Where to find it:** Board → AI Tools → Project Review → Retrospectives.

### Scope Autopsy
- **What it does:** Forensic post-mortem of how scope grew over time.
- **Use it when:** Scope ballooned and you want to understand exactly how and why.
- **Where to find it:** Board → AI Tools → Project Review → Scope Autopsy.

### Exit Protocol
- **What it does:** Structured project wind-down — assessment, knowledge preservation, and archival.
- **Use it when:** A project is ending and you want to close it down cleanly and keep the learnings.
- **Where to find it:** Board → AI Tools → Project Review → Exit Protocol.

---

## Cross-cutting capabilities

### Déjà Vu Check
- **What it does:** Flags when a new task or pattern resembles past projects, surfacing relevant prior knowledge.
- **Use it when:** You want to avoid repeating past mistakes on similar work.
- **Where to find it:** Surfaced via Organizational Memory / Knowledge Graph.

### Triple Constraint
- **What it does:** Tracks a project confidence score across Scope, Cost, and Time.
- **Use it when:** You want a single balanced read on project health across the three constraints.
- **Where to find it:** Board analytics / Gantt context.

### Custom Fields
- **What it does:** User-defined task attributes (text, dropdowns, dates) per workspace.
- **Use it when:** The built-in task fields don't capture something you need to track.
- **Where to find it:** User menu → Custom Fields (admins).

### Stakeholders & RACI
- **What it does:** Stakeholder management with RACI roles and involvement tracking.
- **Use it when:** You need to map who is Responsible/Accountable/Consulted/Informed.
- **Where to find it:** Board-level stakeholder management.

### BYOK (Bring Your Own Key)
- **What it does:** Use your own AI provider key (Gemini, OpenAI, or Anthropic) for AI features.
- **Use it when:** You want to run AI on your own provider account/keys.
- **Where to find it:** Profile / AI provider settings.
