> **Feature Request: Cognitive Load Guardian — Decision Center for PrizmAI**
>
> I want to build a "Decision Center" feature — a unified, prioritized dashboard that batches all pending decisions, risks, and alerts across all boards into one focused interface. This eliminates constant context-switching by giving PMs one place to review everything that needs their attention.
>
> ---
>
> ### 1. DATABASE MODELS
>
> ```python
> class DecisionItem(models.Model):
>     """A single item requiring PM attention, collected for batch review"""
>
>     ITEM_TYPES = [
>         ('conflict', 'Unresolved Conflict'),
>         ('premortem_risk', 'Pre-Mortem Risk Unacknowledged'),
>         ('overdue_task', 'Overdue Task'),
>         ('overallocated', 'Team Member Over-Allocated'),
>         ('scope_change', 'Scope Change Detected'),
>         ('budget_threshold', 'Budget Threshold Crossed'),
>         ('deadline_approaching', 'Deadline Approaching'),
>         ('unassigned_task', 'Task Has No Assignee'),
>         ('stale_task', 'Stale Task — No Update'),
>         ('ai_recommendation', 'AI Recommendation Pending'),
>         ('memory_captured', 'New Knowledge Memory Captured'),
>     ]
>
>     PRIORITY_LEVELS = [
>         ('action_required', 'Action Required'),
>         ('awareness', 'Awareness Only'),
>         ('quick_win', 'Quick Win'),
>     ]
>
>     STATUS_CHOICES = [
>         ('pending', 'Pending'),
>         ('resolved', 'Resolved'),
>         ('snoozed', 'Snoozed'),
>         ('dismissed', 'Dismissed'),
>     ]
>
>     created_for = models.ForeignKey(
>         settings.AUTH_USER_MODEL,
>         on_delete=models.CASCADE,
>         related_name='decision_items'
>     )
>     board = models.ForeignKey(
>         'Board', on_delete=models.CASCADE,
>         null=True, blank=True
>     )
>     item_type = models.CharField(max_length=30, choices=ITEM_TYPES)
>     priority_level = models.CharField(max_length=20, choices=PRIORITY_LEVELS)
>     title = models.CharField(max_length=200)
>     description = models.TextField()
>     suggested_action = models.TextField(blank=True)
>     source_object_type = models.CharField(max_length=50, blank=True)
>     source_object_id = models.IntegerField(null=True, blank=True)
>     context_data = models.JSONField(default=dict)
>     status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
>     created_at = models.DateTimeField(auto_now_add=True)
>     resolved_at = models.DateTimeField(null=True, blank=True)
>     resolved_by = models.ForeignKey(
>         settings.AUTH_USER_MODEL,
>         on_delete=models.SET_NULL,
>         null=True, blank=True,
>         related_name='resolved_decisions'
>     )
>     snoozed_until = models.DateTimeField(null=True, blank=True)
>     estimated_minutes = models.IntegerField(default=2)
>
>     class Meta:
>         ordering = [
>             'status',
>             'priority_level',
>             '-created_at'
>         ]
>
>
> class DecisionCenterSettings(models.Model):
>     """Per-user settings for the Decision Center"""
>
>     user = models.OneToOneField(
>         settings.AUTH_USER_MODEL,
>         on_delete=models.CASCADE,
>         related_name='decision_center_settings'
>     )
>     daily_digest_enabled = models.BooleanField(default=True)
>     digest_time = models.TimeField(default='08:00')
>     show_awareness_items = models.BooleanField(default=True)
>     show_quick_wins = models.BooleanField(default=True)
>     min_overdue_days = models.IntegerField(default=2)
>     min_stale_days = models.IntegerField(default=14)
>     budget_alert_threshold = models.IntegerField(default=80)
>     deadline_warning_days = models.IntegerField(default=7)
> ```
>
> Run migrations after creating these models.
>
> ---
>
> ### 2. DECISION ITEM COLLECTOR (CELERY TASK)
>
> Create a Celery task called `collect_decision_items` that runs **once every morning at 7am** (schedule via django-celery-beat). This task scans all active boards and creates `DecisionItem` records for each user who has access.
>
> The task should collect the following, checking each condition:
>
> **Action Required items:**
>
> ```python
> # 1. Unresolved conflicts
> # Query: Conflict.objects.filter(status='active', board__in=user_boards)
> # For each: create DecisionItem(item_type='conflict', priority_level='action_required')
> # title: "Conflict on {board.name}: {conflict.title}"
> # suggested_action: "Review conflict and select a resolution strategy"
> # estimated_minutes: 3
>
> # 2. Unacknowledged Pre-Mortem risks (High probability only)
> # Query: PreMortemAnalysis objects where overall_risk_level='high'
> #        and board has no acknowledgments on high-probability scenarios
> # title: "High-risk Pre-Mortem unreviewed on {board.name}"
> # suggested_action: "Acknowledge or address high-risk scenarios before work continues"
> # estimated_minutes: 5
>
> # 3. Overdue tasks (respect user's min_overdue_days setting)
> # Query: Tasks where due_date < today AND status != done
> #        AND (today - due_date).days >= settings.min_overdue_days
> # Group by board — create ONE DecisionItem per board (not one per task)
> # title: "{count} overdue tasks on {board.name}"
> # context_data: {'task_ids': [...], 'most_overdue_days': N}
> # estimated_minutes: 2 per task, capped at 10
>
> # 4. Over-allocated team members
> # Query: Use existing resource optimization data if available
> #        Or: count tasks assigned to same user due in same week > 5
> # title: "{member.name} is over-allocated on {board.name}"
> # suggested_action: "Review and reassign tasks to balance workload"
> # estimated_minutes: 4
> ```
>
> **Awareness items:**
>
> ```python
> # 5. Deadlines approaching within settings.deadline_warning_days
> # Query: Boards where end_date is within N days AND status != completed
> # title: "{board.name} deadline in {days} days"
> # priority_level: 'awareness'
> # estimated_minutes: 1
>
> # 6. Budget crossing threshold
> # Query: Boards where (spent/total_budget * 100) >= settings.budget_alert_threshold
> # title: "{board.name} budget at {percentage}%"
> # priority_level: 'awareness'
> # estimated_minutes: 1
> ```
>
> **Quick Win items:**
>
> ```python
> # 7. Tasks with no assignee
> # Query: Tasks where assignee is null AND status != done
> #        Group by board, create ONE item per board
> # title: "{count} unassigned tasks on {board.name}"
> # priority_level: 'quick_win'
> # estimated_minutes: 1
>
> # 8. Stale tasks (respect settings.min_stale_days)
> # Query: Tasks where last updated > N days ago AND status not in [done, archived]
> # Group by board
> # title: "{count} stale tasks on {board.name} — no updates in {N}+ days"
> # priority_level: 'quick_win'
> # estimated_minutes: 2
> ```
>
> **Deduplication rule:** Before creating any DecisionItem, check if an identical item (same item_type + same source_object_id + same created_for user) already exists with status='pending'. If yes, skip — don't create duplicates.
>
> ---
>
> ### 3. AI SUMMARY GENERATOR
>
> After the collector runs, trigger a second Celery task called `generate_decision_summary` for each user who has pending items. This calls Gemini to generate a brief natural language morning briefing.
>
> **System prompt:**
> ```
> You are a calm, efficient chief of staff summarizing a project manager's
> morning decision queue. Be concise, prioritized, and practical.
> Speak directly to the PM. No fluff, no filler sentences.
> Return ONLY valid JSON.
> ```
>
> **User prompt:**
> ```
> Generate a morning briefing for this PM's decision queue.
>
> ACTION REQUIRED ({count} items):
> {list each item: "- {title} on {board.name}"}
>
> AWARENESS ({count} items):
> {list each item: "- {title}"}
>
> QUICK WINS ({count} items):
> {list each item: "- {title}"}
>
> Total estimated review time: {sum of estimated_minutes} minutes
>
> Return JSON:
> {
>   "headline": "One sentence — the single most important thing they need to know today",
>   "briefing": "2-3 sentences maximum — prioritized summary of what needs attention",
>   "estimated_minutes": {total},
>   "top_priority_board": "{board name with most urgent items}"
> }
> ```
>
> - Temperature: **0.4**
> - Model: `gemini-2.5-flash-lite`
> - Store the result in a simple `DecisionCenterBriefing` model:
>
> ```python
> class DecisionCenterBriefing(models.Model):
>     user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
>     generated_at = models.DateTimeField(auto_now_add=True)
>     headline = models.CharField(max_length=300)
>     briefing = models.TextField()
>     estimated_minutes = models.IntegerField()
>     top_priority_board = models.CharField(max_length=200, blank=True)
>     item_counts = models.JSONField(default=dict)
>
>     class Meta:
>         ordering = ['-generated_at']
> ```
>
> ---
>
> ### 4. BACKEND VIEWS
>
> **View 1: `decision_center(request)`**
> - GET, login required
> - Fetches all pending DecisionItems for the current user
> - Fetches today's DecisionCenterBriefing if exists
> - Separates items into three groups: action_required, awareness, quick_win
> - Renders the Decision Center page
>
> **View 2: `resolve_decision_item(request, item_id)`**
> - POST, login required
> - Sets item status to 'resolved', sets resolved_at and resolved_by
> - Returns success JSON with updated pending count
>
> **View 3: `snooze_decision_item(request, item_id)`**
> - POST, login required
> - Accepts: `snooze_hours` (default 24, options: 24, 48, 168 for 1 week)
> - Sets status to 'snoozed', sets snoozed_until
> - Returns success JSON
>
> **View 4: `dismiss_decision_item(request, item_id)`**
> - POST, login required
> - Sets status to 'dismissed'
> - Returns success JSON
>
> **View 5: `decision_center_settings(request)`**
> - GET + POST, login required
> - GET: returns current DecisionCenterSettings for user
> - POST: updates settings
> - Auto-creates DecisionCenterSettings with defaults if none exists
>
> **View 6: `decision_center_widget_data(request)`**
> - GET, login required
> - Returns lightweight JSON for the dashboard widget:
> ```json
> {
>   "action_required_count": 3,
>   "awareness_count": 2,
>   "quick_win_count": 4,
>   "headline": "...",
>   "last_cleared_at": "..."
> }
> ```
> - Cache per user for 30 minutes
>
> ---
>
> ### 5. URLS
>
> ```python
> path('decision-center/', views.decision_center, name='decision_center'),
> path('decision-center/settings/', views.decision_center_settings, name='decision_center_settings'),
> path('decision-center/widget/', views.decision_center_widget_data, name='decision_center_widget'),
> path('decision-center/item/<int:item_id>/resolve/', views.resolve_decision_item, name='resolve_decision_item'),
> path('decision-center/item/<int:item_id>/snooze/', views.snooze_decision_item, name='snooze_decision_item'),
> path('decision-center/item/<int:item_id>/dismiss/', views.dismiss_decision_item, name='dismiss_decision_item'),
> ```
>
> ---
>
> ### 6. FRONTEND — DASHBOARD WIDGET
>
> On the main dashboard page, add a prominent widget card near the top of the page:
>
> ```
> ┌─────────────────────────────────────────────────────────┐
> │ ⚡ Decision Center                    [Open Full View →] │
> ├─────────────────────────────────────────────────────────┤
> │ "{headline from today's AI briefing}"                    │
> ├───────────────┬──────────────────┬──────────────────────┤
> │ 🔴 3          │ 🔵 2             │ ⚡ 4                 │
> │ Action        │ Awareness        │ Quick Wins           │
> │ Required      │ Items            │ Available            │
> ├───────────────┴──────────────────┴──────────────────────┤
> │ Est. review time: 8 min   Last cleared: Yesterday 9:14am│
> └─────────────────────────────────────────────────────────┘
> ```
>
> Load widget data via AJAX call to `decision_center_widget` endpoint. Show a loading skeleton while fetching. If zero items across all categories, show:
> ```
> ✅ All clear — no decisions pending
> ```
>
> ---
>
> ### 7. FRONTEND — DECISION CENTER FULL PAGE
>
> Create a standalone page at `/decision-center/` with this layout:
>
> **Header section:**
> ```
> ⚡ Decision Center
> ─────────────────────────────────────────────────────────
> 🧠 AI MORNING BRIEFING                    {today's date}
> "{briefing text — 2-3 sentences}"
> Top priority: {top_priority_board}   Est. time: {N} min
> ```
>
> **Three collapsible sections:**
>
> **Section 1 — Action Required** (expanded by default, red left border):
> ```
> 🔴 ACTION REQUIRED  ({count})
> ─────────────────────────────────────────────────────────
> [Each item card]:
>
> {item_type icon}  {title}                    ~{N} min
> Board: {board.name}
> {description}
>
> 💡 Suggested: {suggested_action}
>
> [Go to Board]  [Mark Resolved]  [Snooze 24h ▾]  [Dismiss]
> ```
>
> **Section 2 — Awareness** (collapsed by default, blue left border):
> ```
> 🔵 AWARENESS  ({count})   [expand ▾]
> ```
> When expanded, same card format but without "Suggested Action" and with only [Mark Resolved] and [Dismiss] buttons.
>
> **Section 3 — Quick Wins** (collapsed by default, green left border):
> ```
> ⚡ QUICK WINS  ({count})   [expand ▾]
> ```
> When expanded, same card format with a "Quick Win" badge. Include a **"Clear All Quick Wins"** button at the top of this section that resolves all quick win items at once.
>
> **Snooze dropdown options:**
> ```
> Snooze for:
> • 24 hours
> • 48 hours
> • 1 week
> ```
>
> **Settings gear icon** in top-right corner of the page opens a settings panel:
> ```
> Decision Center Settings
> ─────────────────────────────────────
> Daily digest email:        [Toggle ON/OFF]
> Digest send time:          [08:00 ▾]
> Show awareness items:      [Toggle ON/OFF]
> Show quick wins:           [Toggle ON/OFF]
> Mark task overdue after:   [2] days
> Mark task stale after:     [14] days
> Budget alert threshold:    [80]%
> Deadline warning window:   [7] days
>
> [Save Settings]
> ```
>
> ---
>
> ### 8. SIDEBAR NAVIGATION UPDATE
>
> Add to the main left sidebar under an **"Intelligence"** section (alongside Organizational Memory):
>
> ```
> INTELLIGENCE
> 📊  Analytics
> 🧠  Organizational Memory
> ⚡  Decision Center         ← add this
> ```
>
> Show a small badge count on the sidebar item showing the number of "Action Required" pending items. Update this count via the same AJAX widget call.
>
> ---
>
> ### 9. NOTIFICATION BELL INTEGRATION
>
> In the existing notification bell in the top navigation bar, add a special entry when Action Required items exist:
>
> ```
> [Bell icon with badge]
>
> In dropdown:
> ─────────────────────────
> ⚡ Decision Center
> {N} items need your attention
> [Open Decision Center →]
> ─────────────────────────
> {existing notifications below}
> ```
>
> This should be the FIRST item in the notification dropdown, above regular notifications, only when action_required_count > 0.
>
> ---
>
> ### 10. AUDIT LOGGING
>
> Using the existing audit logging system, log:
> - When a DecisionItem is resolved (item title, board, user, timestamp)
> - When a DecisionItem is dismissed (item title, type, user)
> - When settings are changed (what changed, user)
>
> ---
>
> ### IMPLEMENTATION ORDER
>
> 1. Database models + migrations
> 2. `collect_decision_items` Celery task
> 3. `generate_decision_summary` Celery task
> 4. Backend views + URLs
> 5. Dashboard widget
> 6. Decision Center full page
> 7. Sidebar navigation + badge count
> 8. Notification bell integration
> 9. Settings panel
> 10. Audit logging
>
