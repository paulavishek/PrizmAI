
> **Feature Request: Knowledge Graph Project Memory for PrizmAI**
>
> I want to build a "Knowledge Graph Project Memory" system. This is a multi-part feature that gives PrizmAI organizational memory — automatically capturing decisions, lessons, and outcomes across all projects, and making them queryable in plain English. Implement everything described below.
>
> ---
>
> ### 1. DATABASE MODELS
>
> Create these models in the appropriate models.py:
>
> ```python
> class MemoryNode(models.Model):
>     """A single captured memory — one decision, event, or lesson"""
>     
>     NODE_TYPES = [
>         ('decision', 'Decision Made'),
>         ('lesson', 'Lesson Learned'),
>         ('risk_event', 'Risk Event'),
>         ('outcome', 'Project Outcome'),
>         ('conflict_resolution', 'Conflict Resolution'),
>         ('scope_change', 'Scope Change'),
>         ('milestone', 'Milestone Reached'),
>         ('ai_recommendation', 'AI Recommendation'),
>         ('manual_log', 'Manual Decision Log'),
>     ]
>     
>     board = models.ForeignKey('Board', on_delete=models.SET_NULL, null=True, blank=True, related_name='memory_nodes')
>     mission = models.ForeignKey('Mission', on_delete=models.SET_NULL, null=True, blank=True)
>     node_type = models.CharField(max_length=30, choices=NODE_TYPES)
>     title = models.CharField(max_length=200)
>     content = models.TextField()
>     context_data = models.JSONField(default=dict)  # stores relevant metadata
>     tags = models.JSONField(default=list)  # list of string tags
>     created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
>     created_at = models.DateTimeField(auto_now_add=True)
>     is_auto_captured = models.BooleanField(default=True)  # False = manually added
>     source_object_type = models.CharField(max_length=50, blank=True)  # e.g. 'Task', 'Conflict'
>     source_object_id = models.IntegerField(null=True, blank=True)
>     importance_score = models.FloatField(default=0.5)  # 0.0 to 1.0
>     
>     class Meta:
>         ordering = ['-created_at']
>
>
> class MemoryConnection(models.Model):
>     """Links between memory nodes — the 'graph' part"""
>     
>     CONNECTION_TYPES = [
>         ('caused', 'Caused'),
>         ('similar_to', 'Similar To'),
>         ('led_to', 'Led To'),
>         ('prevented', 'Prevented'),
>         ('repeated_from', 'Repeated From Past Project'),
>     ]
>     
>     from_node = models.ForeignKey(MemoryNode, on_delete=models.CASCADE, related_name='outgoing_connections')
>     to_node = models.ForeignKey(MemoryNode, on_delete=models.CASCADE, related_name='incoming_connections')
>     connection_type = models.CharField(max_length=30, choices=CONNECTION_TYPES)
>     created_at = models.DateTimeField(auto_now_add=True)
>     ai_generated = models.BooleanField(default=True)
>     
>
> class OrganizationalMemoryQuery(models.Model):
>     """Logs all questions asked to the memory search — for improving the system"""
>     
>     asked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
>     query_text = models.TextField()
>     response_json = models.JSONField()
>     nodes_referenced = models.ManyToManyField(MemoryNode, blank=True)
>     asked_at = models.DateTimeField(auto_now_add=True)
>     was_helpful = models.BooleanField(null=True)  # user feedback: thumbs up/down
> ```
>
> Run migrations after creating these models.
>
> ---
>
> ### 2. AUTOMATIC MEMORY CAPTURE (DJANGO SIGNALS)
>
> Create a new file `memory_signals.py`. Use Django signals to automatically create MemoryNode records when important things happen. Wire up signals for these events:
>
> **Signal 1 — Task completed:**
> ```python
> # When a task status changes to 'done' or equivalent
> # Capture: task name, who completed it, how many days it took vs estimate, board name
> # Node type: 'milestone' if it's a high-priority task, else 'outcome'
> # Only capture if task took more than 1 day (filter out trivial tasks)
> ```
>
> **Signal 2 — Deadline missed:**
> ```python
> # When a task's due date passes and status is not complete
> # Capture: task name, how many days overdue, assignee, board name, task priority
> # Node type: 'risk_event'
> # Importance score: 0.8 (high — missed deadlines are important memories)
> ```
>
> **Signal 3 — Board archived/completed:**
> ```python
> # When a board status changes to archived or completed
> # Capture: board name, total tasks, completion percentage, 
> #          actual duration vs planned, final budget vs planned
> # Node type: 'outcome'
> # Importance score: 1.0 (highest — project outcomes are the most valuable memories)
> ```
>
> **Signal 4 — Conflict resolved:**
> ```python
> # When a Conflict record is marked as resolved
> # Capture: conflict type, resolution chosen, boards/people involved
> # Node type: 'conflict_resolution'
> ```
>
> **Signal 5 — AI recommendation accepted or rejected:**
> ```python
> # When a user acts on an AI suggestion (accepts or dismisses)
> # Capture: which feature generated it, what was suggested, what the user did
> # Node type: 'ai_recommendation'
> # Importance score: 0.6
> ```
>
> **Signal 6 — Scope change detected:**
> ```python
> # When scope creep detection fires (if that signal/model exists)
> # Capture: original scope baseline, what changed, by how much
> # Node type: 'scope_change'
> # Importance score: 0.85
> ```
>
> Connect all signals in the app's `apps.py` `ready()` method.
>
> ---
>
> ### 3. MEMORY CONNECTION GENERATOR (BACKGROUND TASK)
>
> Create a Celery task called `generate_memory_connections` that runs once daily (use django-celery-beat to schedule it). This task:
>
> - Fetches all MemoryNodes created in the last 7 days
> - For each new node, asks Gemini to find connections to older nodes
> - Use this Gemini prompt:
>
> **System prompt:**
> ```
> You are an organizational memory analyst. You will be given a new memory node 
> and a list of existing memory nodes from past projects. Your job is to identify 
> meaningful connections between the new node and existing ones.
> 
> Only return connections that are genuinely meaningful — not superficial word matches.
> A connection is meaningful if it would actually help a project manager make a 
> better decision by knowing about it.
> 
> Return ONLY valid JSON. No markdown, no explanation outside JSON.
> ```
>
> **User prompt (built dynamically):**
> ```
> NEW MEMORY NODE:
> Type: {node_type}
> Title: {title}
> Content: {content}
> Project: {board.name}
> Date: {created_at}
>
> EXISTING NODES TO COMPARE (most recent 50, summarized):
> {list of existing nodes as: "ID: {id} | Type: {type} | Title: {title} | Project: {board.name} | Date: {date}"}
>
> Return JSON:
> {
>   "connections": [
>     {
>       "to_node_id": 123,
>       "connection_type": "similar_to" | "caused" | "led_to" | "prevented" | "repeated_from",
>       "reason": "One sentence explaining why this connection is meaningful"
>     }
>   ]
> }
>
> Return maximum 3 connections. Return empty array if no meaningful connections exist.
> ```
>
> - Temperature: **0.3** (we want precise matching, not creative connections)
> - Model: `gemini-2.5-flash-lite`
> - Create `MemoryConnection` records for each valid connection returned
> - Limit: process maximum 20 new nodes per daily run to control API costs
>
> ---
>
> ### 4. BACKEND VIEWS
>
> Create these views:
>
> **View 1: `board_knowledge_tab(request, board_id)`**
> - GET request
> - Returns all MemoryNodes for this board, ordered by importance_score DESC then created_at DESC
> - Also returns count of connections each node has
> - Renders the Knowledge tab partial template
>
> **View 2: `add_manual_memory(request, board_id)`**
> - POST request, login required
> - Accepts: title, content, node_type (limited to 'decision' and 'manual_log' for manual entries), tags (comma-separated string)
> - Creates a MemoryNode with is_auto_captured=False
> - Returns success JSON with the created node data
>
> **View 3: `organizational_memory_search(request)`**
> - POST request, login required
> - Accepts: `query` (plain English question, max 500 chars)
> - Fetches the 100 most important MemoryNodes across ALL boards (ordered by importance_score DESC)
> - Sends query + nodes to Gemini with this prompt:
>
> **System prompt:**
> ```
> You are PrizmAI's organizational memory. You have access to a company's 
> complete project history — decisions made, lessons learned, outcomes achieved, 
> risks encountered. Answer questions by finding relevant memories and synthesizing 
> them into a clear, useful response.
>
> Rules:
> - Only use the memory nodes provided. Do not invent information.
> - Always cite which specific memory nodes your answer draws from (by ID).
> - If no relevant memories exist, say so honestly — do not make up an answer.
> - Speak like a knowledgeable colleague, not a database.
> - Keep answers concise — maximum 4 sentences of synthesis, then list sources.
>
> Return ONLY valid JSON.
> ```
>
> **User prompt:**
> ```
> Question: {query}
>
> Available memories:
> {for each node: "NODE {id}: [{node_type}] {title} | Project: {board.name} | Date: {date}\n{content[:300]}"}
>
> Return JSON:
> {
>   "answer": "Your synthesized answer here",
>   "confidence": "High" | "Medium" | "Low",
>   "source_node_ids": [1, 5, 12],
>   "no_data_found": false
> }
> ```
>
> - Temperature: **0.3**
> - Save the query + response to `OrganizationalMemoryQuery`
> - Return JSON to frontend
>
> **View 4: `memory_feedback(request, query_id)`**
> - POST, login required
> - Accepts: `was_helpful` (boolean)
> - Updates the `OrganizationalMemoryQuery.was_helpful` field
> - Returns success JSON
>
> **View 5: `deja_vu_check(request, board_id)`**
> - GET request, called automatically when a new board is opened for the first time
> - Compares this board's goal/description against existing MemoryNodes using Gemini
> - Returns maximum 3 relevant past memories if similarity is found
> - Returns empty if no meaningful similarity or if no completed boards exist yet
> - Cache result for 24 hours per board (don't re-check every page load)
>
> ---
>
> ### 5. URLS
>
> ```python
> path('boards/<int:board_id>/knowledge/', views.board_knowledge_tab, name='board_knowledge'),
> path('boards/<int:board_id>/knowledge/add/', views.add_manual_memory, name='add_manual_memory'),
> path('boards/<int:board_id>/deja-vu/', views.deja_vu_check, name='deja_vu_check'),
> path('memory/search/', views.organizational_memory_search, name='memory_search'),
> path('memory/feedback/<int:query_id>/', views.memory_feedback, name='memory_feedback'),
> ```
>
> ---
>
> ### 6. FRONTEND — KNOWLEDGE TAB ON BOARD PAGE
>
> Add a **"Knowledge"** tab in the AI tabs section, positioned here:
> ```
> [ Risk & Conflicts ] [ Pre-Mortem ] [ Knowledge ] [ Retrospective ]
> ```
>
> **Inside the Knowledge tab, show three sections:**
>
> **Section A — Decision Log (manual entries)**
> ```
> Decision Log                              [+ Log a Decision]
> ──────────────────────────────────────────────────────────
> [If empty]: "No decisions logged yet. 
>              Document key decisions so your team never loses context."
>
> [Each entry card]:
> 📝 DECISION  |  {date}  |  {user}
> {title}
> {content}
> Tags: {tag1} {tag2}
> ```
>
> Clicking **"+ Log a Decision"** opens a small modal:
> ```
> Log a Decision or Lesson
> ─────────────────────────
> Type: [Decision Made ▾] or [Lesson Learned ▾]
> Title: [___________________________]
> What happened / what was decided:
> [_________________________________]
> [_________________________________]
> Tags (optional, comma-separated):
> [___________________________]
> [Cancel]  [Save to Memory]
> ```
>
> **Section B — Auto-Captured Memories**
> ```
> Auto-Captured Memories ({count})         [Show All / Show Important Only toggle]
> ──────────────────────────────────────────────────────────────────────────────
> [Each memory card — compact, not full size]:
> {icon by type} {title}  |  {date}  |  {importance dot: red/amber/green}
> {content — truncated to 100 chars, expandable}
> {if connections exist}: 🔗 Connected to {n} other memories
> ```
>
> **Section C — Déjà Vu Panel (only shows if deja_vu_check returns results)**
> ```
> 🧠 PrizmAI has seen something like this before
> ──────────────────────────────────────────────
> Based on this board's goals, here are relevant lessons from past projects:
>
> [Card for each past memory]:
> From: {board.name}  |  {date}
> {title}
> {content}
> ```
>
> ---
>
> ### 7. FRONTEND — ORGANIZATIONAL MEMORY PAGE
>
> Create a new standalone page at `/memory/` accessible from the main left sidebar navigation under a section called **"Intelligence"**.
>
> Sidebar addition:
> ```
> INTELLIGENCE
> 📊  Analytics
> 🧠  Organizational Memory    ← add this
> ```
>
> **The Organizational Memory page layout:**
>
> ```
> ╔══════════════════════════════════════════════════════════╗
> ║  🧠 Organizational Memory                                ║
> ║  "Ask anything about your project history"               ║
> ╠══════════════════════════════════════════════════════════╣
> ║                                                          ║
> ║  [Search box — full width]                               ║
> ║  "Ask a question... e.g. Why did the API project         ║
> ║   run over budget? What lessons did we learn about        ║
> ║   scope creep?"                          [Ask Memory]    ║
> ║                                                          ║
> ╠══════════════════════════════════════════════════════════╣
> ║  ANSWER                                    Confidence:   ║
> ║  {synthesized answer text}                 [HIGH badge]  ║
> ║                                                          ║
> ║  Sources used:                                           ║
> ║  • [Node title] — {board.name} — {date}                  ║
> ║  • [Node title] — {board.name} — {date}                  ║
> ║                                                          ║
> ║  Was this helpful?  [👍 Yes]  [👎 No]                    ║
> ╠══════════════════════════════════════════════════════════╣
> ║  RECENT QUESTIONS                                        ║
> ║  {list of last 5 queries this user asked, clickable      ║
> ║   to re-run}                                             ║
> ╠══════════════════════════════════════════════════════════╣
> ║  MEMORY STATS                                            ║
> ║  {total_nodes} memories  |  {boards_count} projects      ║
> ║  {oldest_memory_date} — present                          ║
> ╚══════════════════════════════════════════════════════════╝
> ```
>
> **Empty state (no memories yet):**
> ```
> 🧠 Your organizational memory is empty
>
> Memory grows automatically as your team works. 
> It captures decisions, completed milestones, missed deadlines, 
> and resolved conflicts — so nothing is ever forgotten.
>
> Come back after completing your first project.
>
> Memory nodes captured so far: 0
> ```
>
> ---
>
> ### 8. FRONTEND — DÉJÀ VU ALERT BANNER
>
> On the board detail page, when the board is loaded, make an AJAX call to `deja_vu_check`. If it returns results, show a dismissable banner at the top of the board page (above the tabs):
>
> ```
> ┌─────────────────────────────────────────────────────────┐
> │ 🧠 PrizmAI found 2 similar past projects                │
> │ Lessons learned may apply here. View before starting? → │
> │                                          [View] [Dismiss]│
> └─────────────────────────────────────────────────────────┘
> ```
>
> Clicking **"View"** scrolls to the Knowledge tab and expands the Déjà Vu Panel. Clicking **"Dismiss"** hides the banner and sets a session variable so it doesn't reappear on this visit.
>
> ---
>
> ### 9. NAVIGATION UPDATE
>
> In the main sidebar navigation template, add under an "Intelligence" section heading:
> ```python
> # Add this to the sidebar context or template:
> {'name': 'Organizational Memory', 'url': 'memory_search', 'icon': 'brain'}
> ```
> Use whatever icon system is already in the codebase (FontAwesome, Bootstrap Icons, etc.) — find the closest "brain" or "lightbulb" icon available.
>
> ---
>
> ### 10. AUDIT LOGGING
>
> Using the existing audit logging system, log:
> - When a user runs an Organizational Memory search (query text, user, timestamp)
> - When a manual memory node is created (title, board, user)
> - When a user gives thumbs up/down feedback on a memory answer
>
> ---
>
> ### IMPLEMENTATION ORDER
>
> Implement strictly in this order:
> 1. Database models + migrations
> 2. Django signals for auto-capture (memory_signals.py)
> 3. Backend views + URLs
> 4. Celery task for connection generation
> 5. Knowledge tab on board page (Sections A, B, C)
> 6. Organizational Memory standalone page
> 7. Déjà Vu alert banner
> 8. Sidebar navigation update
> 9. Audit logging hooks
>
