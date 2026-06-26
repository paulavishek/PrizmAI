# Spectra Test Run — Raw Transcript

_Generated: 2026-06-27 00:28:17_

## Q68 [G] — testuser1 @ Core AI Protocol Development

**Prompt:** Which tasks are stalling on this board, and which one has been sitting in its column the longest?

**query_type:** `conversational`  |  **elapsed:** 5.6s

**Spectra's answer:**

The following tasks are stalling on the **Core AI Protocol Development** board:

**🔴 Critical — past the red threshold:**

*   **Develop proof-of-concept agent interaction module** — 80 days in "To Do" (critical at 14 days) - Assigned to testuser1
*   **Conduct internal review of protocol design** — 80 days in "To Do" (critical at 14 days) - Assigned to testuser1
*   **Urgent task** — 39 days in "To Do" (critical at 14 days) - Assigned to testuser2
*   **Draft initial multi-agent protocol specification (v0.1)** — 39 days in "Unit Testing" (critical at 14 days) - Assigned to testuser1

The tasks that have been sitting in their columns the longest are **"Develop proof-of-concept agent interaction module"** and **"Conduct internal review of protocol design"**, both with 80 days in the "To Do" column.

---

## Q69 [G] — testuser1 @ Core AI Protocol Development

**Prompt:** Are there any tasks past their aging warning or critical threshold? How many days have they been stuck?

**query_type:** `data_retrieval`  |  **elapsed:** 3.3s

**Spectra's answer:**

Yes, there are tasks past their aging warning or critical threshold on the "Core AI Protocol Development" board.

Here are the tasks that are **Critical** (past the red threshold):

*   **Develop proof-of-concept agent interaction module** — 80 days in To Do (critical at 14 days). Assigned to testuser1.
*   **Conduct internal review of protocol design** — 80 days in To Do (critical at 14 days). Assigned to testuser1.
*   **Draft initial multi-agent protocol specification (v0.1)** — 39 days in Unit Testing (critical at 14 days). Assigned to testuser1.
*   **Urgent task** — 39 days in To Do (critical at 14 days). Assigned to testuser2.

These tasks have been stalled in their current columns for a significant amount of time, exceeding the critical threshold for those columns.

---

## Q70 [G] — testuser1 @ Core AI Protocol Development

**Prompt:** How does the Task Aging feature work, and where do I configure its thresholds?

**query_type:** `help`  |  **elapsed:** 3.9s

**Spectra's answer:**

The **Task Aging** feature helps you identify work that has stalled in its current column. A badge on each Kanban card displays the number of days the task has been in that specific column, resetting whenever the task moves. The badge escalates from neutral grey to amber (warning) and then red (critical) as the task remains in place.

You can configure the thresholds for these warnings in two ways:

1.  **Board Settings:** This sets the board-level warning and critical day counts that apply to all columns by default.
2.  **Per Column:** For more granular control, you can adjust the thresholds for individual columns. Access this by clicking the ⋮ menu on a column and selecting *Aging Alerts*. Here, you can choose to inherit the board-level settings, set custom thresholds, or disable aging alerts for that specific column. Aging alerts are off by default for "Done" and "Backlog"-style columns.

Stalled tasks, indicated by the red critical badge, also surface in the **Focus Today** view.

---

