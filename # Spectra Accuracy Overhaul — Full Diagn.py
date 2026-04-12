# Spectra Accuracy Overhaul — Full Diagnostic & Improvement Spec
> PrizmAI v1.0 → v1.1  
> Author: Architecture session with Claude  
> Date: April 12, 2026  
> Status: Ready for VS Code Claude implementation

---

## Executive Summary

A 16-question Spectra testing session on the Software Development demo board exposed a systemic accuracy problem: **Spectra is not fabricating answers** — she is doing her best with incomplete, stale, or incorrectly structured data delivered by the context-building layer. The AI model itself is not broken. The **data pipeline feeding the AI is broken in at least 6 distinct ways**, and one of them (the column-name confusion) is architecturally wrong at the foundation level.

This document diagnoses every confirmed bug, traces each one to its root cause in `chatbot_service.py`, and specifies the exact fix. It also specifies a new architectural pattern — **Verified Data Fetchers (VDFs)** — that will prevent entire categories of these bugs from recurring.

---

## Part 1 — Bug-by-Bug Diagnosis

### Bug 1 — Milestone Status Wrong ("Done" milestone shown as "To Do")

**What the user saw:**  
Spectra listed all 6 milestones as "To Do". The Gantt chart clearly showed the first milestone (Foundation Architecture Complete) as Done.

**Root Cause:**  
In `_get_live_project_snapshot_context()`, the Phase 6 fix (bug 7.4) added milestone listing, but it queries milestones by their `milestone=True` flag on the `Task` model. It reads the task's `status` field — which stores the **column name string**, not a normalized status code. If the "Done" column on that board is named "Completed" or "Done ✓" or has any variation from the literal word the code checks for, the milestone appears as "To Do" in the context. Spectra faithfully reports what the context says.

Additionally: the query almost certainly does `Task.objects.filter(board=self.board, milestone=True)` but doesn't `select_related('column')` — it reads `task.status` which may be a stale cached value from when the task was last saved, not the live column the task is currently sitting in.

**The real fix:**  
Milestone status must be derived from `task.column.name` (the live column object), not from `task.status` (a stored string that can go stale). See Section 3 — VDF for Milestones.

---

### Bug 2 — Column Confusion: "In Progress" vs "In Review"

**What the user saw:**  
Spectra said "Authentication System" is "In Progress". The Kanban board shows it in the "In Review" column.

**Root Cause — This is the most serious architectural bug.**  
Django's `Task` model stores a `status` field as a `CharField`. This field appears to be populated with the **column name at the time the task is moved** — but it is not automatically updated when the column itself is renamed, or when the board uses non-standard column names. More critically: Spectra's context builders query `task.status` for all reporting, but the **ground truth of where a task currently is** is `task.column` (the ForeignKey to the `Column` object). These two can diverge.

There is also a second problem: the `_get_taskflow_context()` method likely groups tasks by `task.status` value. If two columns have names that differ only slightly ("In Progress" vs "In Review"), or if the `status` field was not re-saved when the task was moved to "In Review", they both read as the same status string in Spectra's context.

**The real fix:**  
All task status reporting in Spectra must read `task.column.name` via a `select_related('column')` query, never `task.status` directly. The `status` field should be treated as a legacy/fallback only. See Section 3 — VDF for Tasks.

---

### Bug 3 — Wrong Priority for "User Registration Flow"

**What the user saw:**  
Spectra said User Registration Flow has "high priority". The Kanban board shows it as "Urgent".

**Root Cause:**  
The `Task` model stores priority as an integer or a choice key (e.g., `1`, `2`, `3`, `4`) mapped to labels ("Low", "Medium", "High", "Urgent"). The context builder likely reads `task.priority` as a raw integer and either (a) does not convert it using `task.get_priority_display()`, or (b) uses a hardcoded mapping that is off-by-one compared to the actual model choices.

Looking at the chat log: Spectra correctly identified priority for some tasks (e.g., Sam Rivera's tasks show "Urgent" correctly for "Core Features Code Review") but got it wrong for "User Registration Flow" specifically. This points to a conditional path in the task detail rendering — tasks fetched via `get_taskflow_context()` for the general listing may use a different priority rendering path than tasks fetched via `_is_task_specific_query()` for detailed task lookup.

**The real fix:**  
All priority rendering must use `task.get_priority_display()` — the Django ORM's built-in method for converting a choice field to its human-readable label. This must be enforced in the VDF, not left to individual context methods.

---

### Bug 4 — "In Review" Column Query Returns Wrong Tasks

**What the user saw:**  
User asked "Which tasks are in the 'In Review' column?" and got a wrong answer.

**Root Cause:**  
This is a direct consequence of Bug 2. When the context builder tries to find tasks "In Review", it likely filters by `task.status = "In Review"`. But if tasks were moved to the In Review column without their `status` field being updated (or if `status` was saved with a slightly different string), those tasks are invisible to this filter. Meanwhile, tasks whose stale `status` string happens to say "In Review" show up even if they've since been moved elsewhere.

**The real fix:**  
Filter by `task.column__name` (via the ForeignKey), never by `task.status` string. Query: `Task.objects.filter(board=board, column__name__iexact="in review").select_related('column', 'assigned_to')`.

---

### Bug 5 — Sam Rivera's Task List Contains Wrong Assignees

**What the user saw:**  
When asked for Sam Rivera's tasks, Spectra returned tasks assigned to other people (notably "Core Features Code Review" which the detailed view shows is assigned to Alex Chen, not Sam Rivera).

**Root Cause:**  
Two likely causes working together:

**Cause A — Assignee query ambiguity:** The context builder queries `Task.objects.filter(board=board, assigned_to__username='sam_rivera_demo')` or similar. But if `assigned_to` is a ForeignKey to `User`, and the demo sandbox has copied tasks but **not correctly transferred the assigned_to ForeignKey to the actual sandbox user copies**, some tasks may have a `null` assigned_to that falls through, or may have mismatched user IDs between the demo template and the sandbox copy.

**Cause B — Aggregate cross-board leakage:** The `_get_aggregate_context()` or `_get_taskflow_context()` may be pulling tasks from multiple boards (the original demo board AND the sandbox copy) when building the "tasks for person X" query, returning duplicates with conflicting data.

The Spectra reference doc (Section 5.3 / bug 7.2) notes that sandbox board detection had an org filter problem that was fixed. But if that fix is incomplete, cross-board task leakage could still occur specifically for assignee-based queries.

**The real fix:**  
Assignee queries must always be scoped to `board=self.board` explicitly (not relying on org scoping), and must `select_related('assigned_to')` to get the live FK value, not any cached string. See VDF specification.

---

### Bug 6 — Overdue Milestones Includes a "Done" Milestone

**What the user saw:**  
Spectra listed "Foundation Architecture Complete" as overdue. It's already marked Done on the Gantt chart.

**Root Cause:**  
The overdue detection logic reads `task.due_date < today AND task.status != 'Done'`. The string comparison for `'Done'` fails for the same reason as Bug 1 — the column may not be literally named "Done", or `task.status` is stale. So a task that is sitting in the Done column still has a stale `status` field value of something else, and the overdue filter catches it incorrectly.

**The real fix:**  
Overdue = `task.due_date < today AND task.column.is_done_column == False`. If the Column model has no `is_done_column` flag, derive it from column position (the last column) or from a `column__name__iexact='done'` check — but this must be based on the live column FK, never the stale status string.

---

### Bug 7 — Dependency Chain Doesn't Match Gantt Chart

**What the user saw:**  
"Which tasks are blocking the most other tasks?" — Spectra's answer didn't match the Gantt chart dependency lines.

**Root Cause:**  
Phase 6 (bug 7.5) fixed the M2M dependency query, but the fix was specifically for `_get_dependency_context()` and `_get_full_dependency_chain()`. The **blocking count query** — "how many tasks does X block?" — is a separate aggregation that wasn't part of the Phase 6 fix. It likely still queries `parent_task` only (which had 0 records on the demo board) and completely ignores the M2M `dependencies` field.

Additionally: the Gantt chart may display dependencies in the **reverse direction** of how the M2M field is defined. Django M2M fields have a `from` and `to` side. If "Task A blocks Task B" is stored as `taskB.dependencies.add(taskA)` (meaning B depends on A), then "find what A blocks" requires a reverse query: `Task.objects.filter(dependencies=taskA)`. If the context builder does the forward query instead, it gets the wrong direction entirely.

**The real fix:**  
The blocking-count query must use `Task.objects.filter(dependencies=task_id).count()` (the reverse M2M lookup) and must be applied consistently across all dependency-related context methods.

---

## Part 2 — Your Architectural Idea: Verified Data Fetchers (VDFs)

You suggested: *"introduce functions into each feature that would fetch info from the corresponding feature and deliver to Spectra. We shouldn't let Spectra fetch the info all by herself."*

This is exactly right, and it has a proper name in software architecture: **a data access layer with a single source of truth**. Here is how to implement it for PrizmAI.

### The Core Problem with the Current Design

Right now, `chatbot_service.py` (~4600 lines) contains 23+ context-building methods, each of which writes its own Django ORM query from scratch. This means:

- The same data (e.g., task status) is fetched 6 different ways across 6 different methods
- When one method gets the query wrong, only that method is fixed — the other 5 are left with the same bug
- There is no enforced contract on what a "task" looks like when Spectra receives it
- Bugs introduced by column renames, model changes, or field additions can silently break 15 methods at once

### The VDF Pattern

A **Verified Data Fetcher** is a dedicated Python function (or class) that:
1. Owns the single canonical ORM query for a given data type
2. Always returns a normalized, standardized Python dict (not a raw ORM object)
3. Is the **only** place allowed to query that data type for Spectra
4. Explicitly handles the known failure modes (stale status, wrong priority label, etc.)

```
chatbot_service.py context methods
         ↓ call
    VDF functions  (new file: ai_assistant/utils/spectra_data_fetchers.py)
         ↓ call
    Django ORM  (Task, Column, Board, User models)
         ↓
    Database (ground truth)
```

### What Each VDF Returns (the "Spectra Task Dict" contract)

Every place in Spectra that reports on a task must receive a dict in this exact shape:

```python
{
    "id": task.id,
    "title": task.title,
    "column_name": task.column.name,          # LIVE from FK — NEVER task.status
    "is_complete": task.column.name.lower() in DONE_COLUMN_NAMES,
    "priority_label": task.get_priority_display(),   # "Urgent", "High", "Medium", "Low"
    "priority_value": task.priority,                 # raw int for sorting
    "assigned_to_username": task.assigned_to.username if task.assigned_to else None,
    "assigned_to_display": task.assigned_to.get_full_name() if task.assigned_to else "Unassigned",
    "due_date": task.due_date,
    "is_overdue": task.due_date and task.due_date.date() < today and not is_complete,
    "is_milestone": task.milestone,
    "description": task.description,
    "dependencies_blocking": [t.id for t in Task.objects.filter(dependencies=task)],  # what THIS task blocks
    "dependencies_blocked_by": [t.id for t in task.dependencies.all()],               # what blocks THIS task
    "parent_task_id": task.parent_task_id,
    "labels": [label.name for label in task.labels.all()],
    "story_points": task.story_points,
    "estimated_hours": task.estimated_hours,
}
```

This contract means: **if the ORM query is correct in the VDF, it is correct everywhere**. You fix it once, all 23 context methods get the fix automatically.

---

## Part 3 — Full Implementation Specification

### New File: `ai_assistant/utils/spectra_data_fetchers.py`

This file must be created from scratch. It contains all VDFs.

---

#### 3.1 Constants

```python
# These are the column name strings that mean "this task is complete"
# Lowercase comparison always used
DONE_COLUMN_NAMES = {"done", "completed", "complete", "closed", "finished", "resolved"}

# Priority display map (fallback if get_priority_display() is unavailable)
PRIORITY_DISPLAY = {1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}
```

**Important:** If your `Task.PRIORITY_CHOICES` uses different integers, update these constants to match exactly. Do not guess — read the model definition before writing these.

---

#### 3.2 `fetch_task_dict(task)` — Core Normalizer

```python
from datetime import date

def fetch_task_dict(task) -> dict:
    """
    Convert a Task ORM object into a normalized Spectra-safe dict.
    ALWAYS call .select_related('column', 'assigned_to') before passing task in.
    """
    from kanban.models import Task  # avoid circular import
    today = date.today()
    
    col_name = task.column.name if task.column_id else (task.status or "Unknown")
    is_complete = col_name.lower().strip() in DONE_COLUMN_NAMES
    
    # Priority: try Django's built-in display method first, fallback to map
    try:
        priority_label = task.get_priority_display()
    except Exception:
        priority_label = PRIORITY_DISPLAY.get(task.priority, str(task.priority))
    
    is_overdue = bool(
        task.due_date and
        task.due_date.date() < today and
        not is_complete
    )
    
    # Blocking: tasks that list THIS task as a dependency (reverse M2M)
    blocking_ids = list(
        Task.objects.filter(dependencies=task.pk).values_list('id', flat=True)
    )
    # Blocked by: tasks that THIS task depends on (forward M2M)
    blocked_by_ids = list(task.dependencies.values_list('id', flat=True))
    
    return {
        "id": task.id,
        "title": task.title,
        "column_name": col_name,
        "is_complete": is_complete,
        "priority_label": priority_label,
        "priority_value": task.priority,
        "assigned_to_username": task.assigned_to.username if task.assigned_to_id else None,
        "assigned_to_display": (
            task.assigned_to.get_full_name() or task.assigned_to.username
        ) if task.assigned_to_id else "Unassigned",
        "due_date": task.due_date,
        "is_overdue": is_overdue,
        "is_milestone": bool(task.milestone),
        "description": task.description or "",
        "blocking_task_ids": blocking_ids,
        "blocked_by_task_ids": blocked_by_ids,
        "parent_task_id": task.parent_task_id,
        "labels": [label.name for label in task.labels.all()],
        "story_points": getattr(task, 'story_points', None),
        "estimated_hours": getattr(task, 'estimated_hours', None),
    }
```

**Implementation note for VS Code Claude:** Read the actual `Task` model fields in `kanban/models.py` before writing this function. Verify field names: `milestone`, `due_date`, `priority`, `column` (FK name), `assigned_to` (FK name), `dependencies` (M2M name), `parent_task` (FK name). Adjust the function to match exactly.

---

#### 3.3 `fetch_board_tasks(board, filters=None)` — Board Task Fetcher

```python
def fetch_board_tasks(board, filters: dict = None) -> list[dict]:
    """
    Fetch ALL tasks for a board as normalized Spectra dicts.
    Optional filters: {'column_name': 'In Review', 'assigned_to_username': 'sam_rivera_demo',
                       'is_milestone': True, 'is_overdue': True, 'priority_value': 4}
    """
    from kanban.models import Task
    
    qs = (
        Task.objects
        .filter(board=board)
        .select_related('column', 'assigned_to')
        .prefetch_related('dependencies', 'labels')
        .order_by('column__order', 'order')
    )
    
    task_dicts = [fetch_task_dict(t) for t in qs]
    
    if filters:
        if 'column_name' in filters:
            target = filters['column_name'].lower().strip()
            task_dicts = [t for t in task_dicts if t['column_name'].lower().strip() == target]
        if 'assigned_to_username' in filters:
            task_dicts = [t for t in task_dicts if t['assigned_to_username'] == filters['assigned_to_username']]
        if 'is_milestone' in filters:
            task_dicts = [t for t in task_dicts if t['is_milestone'] == filters['is_milestone']]
        if 'is_overdue' in filters:
            task_dicts = [t for t in task_dicts if t['is_overdue'] == filters['is_overdue']]
        if 'priority_value' in filters:
            task_dicts = [t for t in task_dicts if t['priority_value'] >= filters['priority_value']]
    
    return task_dicts
```

---

#### 3.4 `fetch_milestones(board)` — Milestone Fetcher

```python
def fetch_milestones(board) -> list[dict]:
    """
    Fetch all milestone tasks for a board with correct live status.
    Returns only tasks with milestone=True, ordered by due_date.
    """
    all_tasks = fetch_board_tasks(board, filters={'is_milestone': True})
    return sorted(
        all_tasks,
        key=lambda t: (t['due_date'] is None, t['due_date'])
    )
```

---

#### 3.5 `fetch_column_distribution(board)` — Status Breakdown

```python
def fetch_column_distribution(board) -> dict:
    """
    Returns task count per column, using live column names from the Column FK.
    Example: {"To Do": 15, "In Progress": 6, "In Review": 2, "Done": 7}
    """
    from kanban.models import Task
    from django.db.models import Count
    
    results = (
        Task.objects
        .filter(board=board)
        .select_related('column')
        .values('column__name')
        .annotate(count=Count('id'))
        .order_by('column__order')
    )
    return {row['column__name']: row['count'] for row in results}
```

---

#### 3.6 `fetch_dependency_graph(board)` — Full Dependency Map

```python
def fetch_dependency_graph(board) -> dict:
    """
    Returns a complete dependency map for a board.
    
    Structure:
    {
        task_id: {
            "title": str,
            "column_name": str,
            "is_complete": bool,
            "blocking": [{"id": int, "title": str}, ...],   # tasks THIS task blocks
            "blocked_by": [{"id": int, "title": str}, ...], # tasks blocking THIS task
            "blocking_count": int,
        }
    }
    
    'blocking' = tasks that have listed this task as a dependency (reverse M2M)
    'blocked_by' = tasks this task lists as dependencies (forward M2M)
    """
    from kanban.models import Task
    
    tasks = (
        Task.objects
        .filter(board=board)
        .select_related('column')
        .prefetch_related('dependencies')
    )
    
    task_lookup = {t.id: t for t in tasks}
    col_name = lambda t: t.column.name if t.column_id else (t.status or "Unknown")
    is_done = lambda name: name.lower().strip() in DONE_COLUMN_NAMES
    
    graph = {}
    for task in tasks:
        blocked_by = list(task.dependencies.all())
        blocking = list(Task.objects.filter(dependencies=task.pk))
        
        graph[task.id] = {
            "title": task.title,
            "column_name": col_name(task),
            "is_complete": is_done(col_name(task)),
            "blocking": [{"id": t.id, "title": t.title} for t in blocking],
            "blocked_by": [{"id": t.id, "title": t.title} for t in blocked_by],
            "blocking_count": len(blocking),
        }
    
    return graph
```

---

#### 3.7 `fetch_assignee_workload(board)` — Workload Summary

```python
def fetch_assignee_workload(board) -> dict:
    """
    Returns task distribution by assignee.
    {
        "display_name": {"username": str, "tasks": [task_dict, ...], "count": int, "overdue_count": int}
    }
    """
    all_tasks = fetch_board_tasks(board)
    workload = {}
    
    for task in all_tasks:
        key = task['assigned_to_display']
        if key not in workload:
            workload[key] = {
                "username": task['assigned_to_username'],
                "tasks": [],
                "count": 0,
                "overdue_count": 0,
            }
        workload[key]["tasks"].append(task)
        workload[key]["count"] += 1
        if task["is_overdue"]:
            workload[key]["overdue_count"] += 1
    
    return dict(sorted(workload.items(), key=lambda x: -x[1]["count"]))
```

---

### Changes to `chatbot_service.py`

Every method listed below must be **refactored** to call the relevant VDF instead of writing its own ORM query. This is not a full rewrite — it is a surgical replacement of the query sections inside each method. The prompt assembly and formatting logic stays the same.

| Method | VDF to use | Key change |
|---|---|---|
| `_get_live_project_snapshot_context()` | `fetch_milestones()`, `fetch_column_distribution()` | Replace task.status with column_name; replace milestone status check |
| `_get_taskflow_context()` | `fetch_board_tasks()` | Replace all direct ORM queries; use task_dict fields |
| `_get_dependency_context()` | `fetch_dependency_graph()` | Full replacement; use blocking_count from graph |
| `_get_full_dependency_chain()` | `fetch_dependency_graph()` | Walk graph dict instead of recursive ORM |
| `get_taskflow_context()` (per-task) | `fetch_board_tasks()` with title filter | Replace direct task query |
| `_build_overdue_context()` (if exists) | `fetch_board_tasks(filters={'is_overdue': True})` | Derived from VDF, not direct ORM |
| `_get_organization_context()` | `fetch_assignee_workload()` | Use for member task counts |

**Critical instruction for VS Code Claude:** When refactoring each method, do not change the string formatting / prompt text. Only replace the data-fetching section (ORM queries, field access) with calls to the VDF. This keeps the diff minimal and reviewable.

---

### Specific Fix for Each of the 6 Reported Bugs

#### Fix 1 & 6 — Milestone Status & Overdue Detection

In `_get_live_project_snapshot_context()`, replace the milestone block with:

```python
from ai_assistant.utils.spectra_data_fetchers import fetch_milestones

milestones = fetch_milestones(self.board)
milestone_lines = []
for m in milestones:
    status_str = "✅ Done" if m['is_complete'] else m['column_name']
    overdue_str = " ⚠️ OVERDUE" if m['is_overdue'] else ""
    due_str = m['due_date'].strftime('%Y-%m-%d') if m['due_date'] else "No date"
    milestone_lines.append(f"  - {m['title']} [{status_str}] Due: {due_str}{overdue_str}")
```

This ensures: (a) a Done milestone is never flagged overdue, (b) status reflects the live column, not a stale string.

---

#### Fix 2 & 4 — Column Name Confusion

In `_get_taskflow_context()` and all task listing code, replace `task.status` with `task_dict['column_name']` from `fetch_board_tasks()`.

For column-specific queries like "which tasks are In Review?", the context builder must detect column-name queries in the prompt and call:
```python
tasks = fetch_board_tasks(self.board, filters={'column_name': detected_column_name})
```

The column name must be extracted from the user's query using simple string matching, not hardcoded to "In Progress" / "Done".

---

#### Fix 3 — Priority Label

In `fetch_task_dict()` (the VDF itself), `task.get_priority_display()` is already the correct call. Once all context methods use task dicts from VDFs, this is automatically fixed everywhere.

For VS Code Claude: verify that `Task.priority` is a choice field. If it uses integer choices, `get_priority_display()` works natively. If it uses string choices (`'urgent'`, `'high'`), the display method also works. Read `kanban/models.py` to confirm.

---

#### Fix 5 — Assignee Query Scoped to Board

In `_get_taskflow_context()` or wherever "tasks for person X" is assembled, use:

```python
tasks_for_person = fetch_board_tasks(
    self.board,  # ← ALWAYS scope to self.board, never use org-level query
    filters={'assigned_to_username': target_username}
)
```

The `fetch_board_tasks()` VDF always starts from `Task.objects.filter(board=board)`, making cross-board leakage structurally impossible.

---

#### Fix 7 — Dependency Direction and Blocking Count

In `_get_dependency_context()`, replace with:

```python
graph = fetch_dependency_graph(self.board)

# Sort by blocking count descending to find bottlenecks
bottlenecks = sorted(
    graph.values(),
    key=lambda n: -n['blocking_count']
)

for node in bottlenecks[:10]:
    if node['blocking_count'] > 0:
        blocked_titles = [b['title'] for b in node['blocking']]
        context_lines.append(
            f"  - '{node['title']}' blocks {node['blocking_count']} task(s): "
            f"{', '.join(blocked_titles)}"
        )
```

This uses `Task.objects.filter(dependencies=task.pk)` — the reverse M2M lookup — which is the correct direction: "find tasks that have listed this task as something they depend on."

---

## Part 4 — Implementation Order

Build and test these in strict order. Do not start the next phase until the previous one passes browser verification.

### Phase A — Create `spectra_data_fetchers.py`

1. Create `ai_assistant/utils/spectra_data_fetchers.py` with all VDFs from Section 3
2. Read `kanban/models.py` to verify all field names before writing any query
3. Write a management command `python manage.py test_spectra_vdfs --board-id=<id>` that calls each VDF and prints its output in a readable format — this is your verification tool
4. Run the command against the Software Development demo board and verify the output matches what you see on screen

**Checkpoint:** Before moving to Phase B, ask Spectra "What are the milestones?" and "What is the status breakdown?" — answers should now be correct.

---

### Phase B — Migrate Snapshot and Taskflow Contexts

1. Refactor `_get_live_project_snapshot_context()` to use `fetch_milestones()` and `fetch_column_distribution()`
2. Refactor `_get_taskflow_context()` to use `fetch_board_tasks()`
3. Ensure `get_taskflow_context()` (per-task detail) also uses `fetch_board_tasks()`

**Checkpoint questions to ask Spectra:**
- "What are all the milestones?" → verify statuses and overdue flags
- "What's the status breakdown?" → verify column counts
- "Tell me about the User Registration Flow task" → verify priority is "Urgent"
- "Show me tasks assigned to Sam Rivera" → verify list is correct and scoped to this board

---

### Phase C — Migrate Dependency Context

1. Refactor `_get_dependency_context()` to use `fetch_dependency_graph()`
2. Refactor `_get_full_dependency_chain()` to walk the graph dict

**Checkpoint questions:**
- "Which tasks are blocking the most other tasks?" → compare to Gantt chart
- "What dependencies might cause delays?" → verify chain directions

---

### Phase D — Column-Specific Query Detection

This is the most careful phase. It requires detecting when the user is asking about a specific column by name.

1. In `_is_project_query()` (or the intent detection layer), add column-name extraction:
   - Scan the user's prompt for known column names on the current board
   - If a column name is detected, tag the query with `{'filter_column': detected_name}`
2. Pass this tag into `_get_taskflow_context()` which then calls `fetch_board_tasks(filters={'column_name': detected_name})`

**Alternative simpler approach:** Rather than intent detection, always include the full column-grouped task list in `_get_taskflow_context()` and let Gemini filter by column name from the context. The VDF ensures the column names in the context are accurate (from the live FK), so Gemini can correctly answer "which tasks are in In Review?" without needing explicit filter logic.

**Checkpoint question:**
- "Which tasks are in the In Review column?" → must match Kanban board exactly

---

### Phase E — Regression Test Pass

Ask Spectra all 16 original questions from the test session and verify each answer is now correct. Document any remaining discrepancies and open new targeted bugs.

---

## Part 5 — Longer-Term Improvements (Post v1.1)

These are not bugs — they are architectural improvements that will prevent the next category of Spectra accuracy problems.

### 5.1 — Spectra Context Validator

Add a lightweight validation layer that runs after every context assembly and before the Gemini call:

```python
def validate_spectra_context(context: str, board) -> list[str]:
    """Returns a list of warnings about potentially incorrect context data."""
    warnings = []
    # Check: are task counts in context consistent with DB counts?
    # Check: are column names in context valid columns on this board?
    # Check: are all mentioned usernames valid members of this board?
    return warnings
```

If warnings are non-empty, log them. This creates a drift-detection system that catches data inconsistencies before they reach the AI.

### 5.2 — Structured Context Format

Currently, context is assembled as a large string of English prose. This makes it easy for the AI to misread. Consider switching the task list section to a structured format:

```
=== TASK LIST ===
[FORMAT: ID | Title | Column | Priority | Assignee | Due | Overdue | Milestone]
001 | User Registration Flow | In Progress | Urgent | Alex Chen | 2026-04-02 | YES | No
002 | Authentication System  | In Review   | High   | Sam Rivera| 2026-03-26 | YES | No
```

This structured format is much harder for the AI to confuse than paragraph-style descriptions.

### 5.3 — Context Freshness Timestamps

Add a timestamp to each context section header:

```
=== TASKS (fetched: 2026-04-12 10:45:02 UTC) ===
```

This helps distinguish "I fetched this 5 seconds ago from the live DB" from "this is cached data from 2 hours ago." It also helps with debugging when Spectra gives a stale answer.

### 5.4 — Board-Specific Column Name Registry

Maintain a `done_columns` list per board (settable in board settings, defaulting to the last column). Use this in all VDF `is_complete` checks instead of the string-matching fallback. This is the architecturally correct solution and removes the dependency on column naming conventions entirely.

---

## Part 6 — Claude Build Prompt for VS Code Claude

Paste the following prompt into VS Code Claude to begin implementation:

---

**START OF BUILD PROMPT**

We are implementing a Spectra accuracy overhaul for PrizmAI. The problem: Spectra's `chatbot_service.py` (~4600 lines) contains 23+ context methods that each write their own ORM queries from scratch. This has caused 7+ confirmed data accuracy bugs. The fix is to introduce a Verified Data Fetcher (VDF) layer.

**Your task today: Phase A — Create `spectra_data_fetchers.py`**

**Step 1 — Read these files before writing any code:**
- `kanban/models.py` — read the full Task, Column, Board models to verify: field name for milestone flag, field name for priority (and its choices), field name for the column FK, field name for the assigned_to FK, name of the M2M dependencies field, field name for parent_task FK
- `ai_assistant/utils/chatbot_service.py` — read lines 280-500 (the context assembly area) and lines 3900-3970 (`_get_live_project_snapshot_context`) to understand the current data flow

**Step 2 — Create `ai_assistant/utils/spectra_data_fetchers.py`** with the following functions (exact signatures specified in the spec doc):
- `fetch_task_dict(task)` — normalizes a single Task ORM object into a safe dict
- `fetch_board_tasks(board, filters=None)` — fetches all tasks for a board as dicts
- `fetch_milestones(board)` — returns only milestone tasks, sorted by due_date
- `fetch_column_distribution(board)` — returns task count per column using live column FK
- `fetch_dependency_graph(board)` — returns full dependency map using M2M reverse lookups
- `fetch_assignee_workload(board)` — returns task distribution grouped by assignee

**Step 3 — Create a management command** `ai_assistant/management/commands/verify_spectra_vdfs.py` that:
- Accepts `--board-id` argument
- Calls each VDF with that board
- Prints results in a readable format for manual verification

**Critical rules:**
- NEVER use `task.status` for reporting column/status — always use `task.column.name` via select_related
- NEVER use hardcoded priority strings — always use `task.get_priority_display()`  
- Blocking direction: `Task.objects.filter(dependencies=task.pk)` = tasks that THIS task blocks (reverse M2M)
- Blocked-by direction: `task.dependencies.all()` = tasks THIS task depends on (forward M2M)
- Always scope queries to `board=board` — never org-level queries in VDFs
- `select_related('column', 'assigned_to')` and `prefetch_related('dependencies', 'labels')` on every task queryset
- Use `kanban/` app name and `OrganizationGoal` model name (not `boards/` or `Goal`)

Do not modify `chatbot_service.py` yet. Phase A is only about creating the VDF file and the verification command. Phase B (wiring VDFs into chatbot_service.py) comes next session.

**END OF BUILD PROMPT**

---

## Appendix — Bug Summary Table

| # | Question Asked | Wrong Answer | Root Cause | VDF Fix |
|---|---|---|---|---|
| 1 | Milestone statuses | "Done" milestone shown as "To Do" | `task.status` stale string vs live column FK | `fetch_milestones()` uses `column.name` |
| 2 | Authentication System status | "In Progress" instead of "In Review" | `task.status` stale vs live column FK | `fetch_board_tasks()` uses `column.name` |
| 3 | User Registration Flow priority | "High" instead of "Urgent" | Priority int not converted via `get_priority_display()` | `fetch_task_dict()` uses `get_priority_display()` |
| 4 | Tasks in "In Review" column | Wrong task list | Filter on `task.status` string instead of column FK | `fetch_board_tasks(filters={'column_name': ...})` |
| 5 | Sam Rivera's tasks | Includes tasks from other people | Org-level query leaking cross-board tasks | `fetch_board_tasks()` always scoped to board |
| 6 | Overdue milestones | Includes a "Done" milestone | Overdue check uses stale `task.status` not column | `fetch_milestones()` derives overdue from live column |
| 7 | Blocking dependency count | Doesn't match Gantt chart | Blocking count used parent_task only, not M2M reverse | `fetch_dependency_graph()` uses M2M reverse lookup |

---

*End of spec. Total bugs diagnosed: 7. Root causes: 3 (stale status field, wrong priority rendering, incomplete M2M query direction). All three are fixed by the VDF pattern.*