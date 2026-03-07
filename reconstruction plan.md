Recommended Dashboard Reconstruction Plan:

Redesign PrizmAI's layout to use a persistent left sidebar instead of the current top navbar, following Monday.com's navigation pattern. Here are the exact requirements:
Left Sidebar (fixed, always visible, ~220px wide):

PrizmAI logo at top
Primary nav items with icons (vertically stacked): Dashboard, Boards, Goals, Missions, Calendar, Wiki, Messages
Secondary/advanced items collapsed under "More": Time, Decisions, Memory, Conflicts, Notifications
"Ask Spectra" as a prominent button near the bottom of sidebar (this is a key differentiator, give it visibility)
User avatar + username at very bottom
Sidebar should be collapsible to icon-only mode

Top Bar (slim, ~48px):

Page title (e.g., "Dashboard", "Boards") on the left
Right side only: Search icon, Notifications bell, Share button
Remove everything else from the top bar

Boards Page Cards — add these to each board card:

A thin colored progress bar at the bottom of each card showing % completion
Task count (e.g., "24 tasks")
Small colored dot indicating board health (green/yellow/red)
Remove the gear icon — merge its settings into the three-dot menu

Dashboard Empty State Fix:

When a chart widget has no data, show a styled empty state with a brief explanation and a CTA button (e.g., "Open a board to start tracking"), not just blank axes

Keep all existing functionality — this is purely a layout and navigation restructure.





Board UI Reconstruction Plan:

Redesign the Kanban board page with the following changes:
Board Header (slim, ~60px):

Left: Board title (single line, not oversized) + breadcrumb above it
Right: Only 4 primary action buttons: "+ Add Task", "Filter", "Sort", and a "⚡ AI Tools" dropdown button

"AI Tools" dropdown contains all AI features grouped:

Analyze: Analytics, Burndown, Skill Gaps, Status Report
Plan: Gantt Chart, Calendar, Budget & ROI, Scope
AI Actions: Coach, PrizmBrief, What-If, Pre-Mortem, Retrospectives, Scope Autopsy
Board Settings: Automations, Knowledge, Export

Board Body:

Kanban columns start immediately below the header — no expanded panels between header and columns
Collapse "Search Tasks" and "Quick Column Reorder" into a single collapsed "Board Tools" accordion, hidden by default
"AI Resource Optimization" panel should be collapsed by default, with a subtle banner: "✨ AI has 4 resource suggestions — Review" that expands it on click

Task Cards — clean up:

Remove eye + trash icons from default card view; show only on hover, and move delete into a three-dot menu to prevent accidental deletion
Rename "0d in column" to "Added today" or simply remove if under 1 day

Keep all existing functionality — this is purely visual reorganization and grouping.





Task Detail Page Reconstruction Plan:

Redesign the task detail page using a two-column layout with tabbed sections instead of a single long scrolling form:
Left column (main content, ~65% width) — tabbed:

Tab 1 "Overview" (default): Title, Description, Status, Assignee, Due Date, Priority, Progress — everything a PM needs in one view
Tab 2 "AI Insights": AI Task Analysis & Summary, AI Complexity Analysis, LSS Classification, AI Risk Assessment
Tab 3 "Details": Constraints, Task Complexity slider, Resource & Workload, Budget & Cost
Tab 4 "Relationships": Parent Task, Dependencies, Related Tasks, Required Skills
Tab 5 "Activity": Comments, Attachments, Linked Wiki, Activity Log

Right sidebar (fixed, ~35% width):

Task metadata at a glance: Status pill, Priority badge, Assignee, Due date, Created by, Created on
Time Tracking widget (collapsed by default, expandable)
Quick AI actions: "Assess Risk", "Suggest Assignee", "Predict Deadline" as small icon buttons

Other fixes:

Fix "Required Skills" field: replace the raw JSON textarea with a tag-input UI where users type a skill name and press Enter to add it as a chip/badge
Move "Delete Task" into a three-dot menu in the top-right header — remove it from the main form footer
Make "Save Changes" a sticky button that stays visible at the top-right regardless of scroll position