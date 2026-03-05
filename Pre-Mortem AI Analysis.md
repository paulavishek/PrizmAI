
> **Feature Request: Pre-Mortem AI Analysis for PrizmAI**
>
> I want to build a "Pre-Mortem AI Analysis" feature. Please implement everything described below end-to-end: the database model, the backend view, the Gemini API call, and the frontend UI.
>
> ---
>
> ### 1. DATABASE MODEL
>
> Create a new model called `PreMortemAnalysis` in the appropriate models.py file:
>
> ```python
> class PreMortemAnalysis(models.Model):
>     RISK_LEVELS = [('high', 'High'), ('medium', 'Medium'), ('low', 'Low')]
>     
>     board = models.ForeignKey('Board', on_delete=models.CASCADE, related_name='pre_mortems')
>     created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
>     created_at = models.DateTimeField(auto_now_add=True)
>     overall_risk_level = models.CharField(max_length=10, choices=RISK_LEVELS)
>     analysis_json = models.JSONField()  # stores the full 5-scenario output
>     board_snapshot = models.JSONField()  # stores the project data used for analysis
>     
>     class Meta:
>         ordering = ['-created_at']
> ```
>
> Also create a model for tracking which scenarios the PM has acknowledged:
>
> ```python
> class PreMortemScenarioAcknowledgment(models.Model):
>     pre_mortem = models.ForeignKey(PreMortemAnalysis, on_delete=models.CASCADE, related_name='acknowledgments')
>     scenario_index = models.IntegerField()  # 0-4, which of the 5 scenarios
>     acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
>     acknowledged_at = models.DateTimeField(auto_now_add=True)
>     notes = models.TextField(blank=True)
> ```
>
> Run migrations after creating these models.
>
> ---
>
> ### 2. UNLOCK CONDITION (BACKEND)
>
> The Pre-Mortem feature should only be available when ALL three conditions are met for a board:
> - At least 5 tasks exist on the board
> - At least one task has a deadline/due date set
> - At least one team member is assigned to any task
>
> Create a helper function `board_premortem_ready(board)` that returns `True` or `False` based on these conditions. Use this in both the view and the template.
>
> ---
>
> ### 3. BACKEND VIEW
>
> Create two views:
>
> **View 1: `run_premortem(request, board_id)`**
> - POST only, login required
> - Collect this data from the board:
>   - board.name, board.description, board.goal (if set)
>   - Total task count, high-priority task count, overdue task count
>   - Project start date and deadline (calculate total days available)
>   - Number of unique team members assigned across all tasks
>   - Budget total vs. budget spent (if budget is set, otherwise omit)
>   - Count of tasks with no assignee
>   - Count of tasks with no due date
>   - Any existing active conflicts (from the Conflict model if it exists)
>   - Any existing risk flags
> - Save this collected data as `board_snapshot` in the model
> - Send to Gemini with this exact prompt:
>
> **System prompt for Gemini:**
> ```
> You are a senior project risk analyst specializing in Pre-Mortem analysis. 
> Your job is to imagine that this project has already completely failed, 
> then work backwards to identify the 5 most likely root causes of that failure.
> 
> Rules:
> - Be specific to THIS project's actual data. Use the real numbers provided.
> - Do NOT give generic project management advice.
> - Do NOT be reassuring or diplomatic. Be direct about risks.
> - Each failure scenario must be distinct — no overlapping causes.
> - Think like a skeptic, not a cheerleader.
> 
> Return ONLY valid JSON. No markdown, no backticks, no explanation outside the JSON.
> ```
>
> **User prompt for Gemini (dynamically built from board data):**
> ```
> Analyze this project and generate a Pre-Mortem analysis.
>
> PROJECT DATA:
> - Name: {board.name}
> - Goal: {board.goal or 'Not specified'}
> - Total tasks: {task_count}
> - High priority tasks: {high_priority_count}
> - Overdue tasks: {overdue_count}
> - Tasks with no assignee: {unassigned_count}
> - Tasks with no due date: {no_deadline_count}
> - Team size: {team_size} people
> - Timeline: {days_available} days total ({days_remaining} days remaining)
> - Budget: {budget_info or 'Not set'}
> - Existing conflicts detected: {conflict_count}
>
> Return this exact JSON structure:
> {
>   "failure_scenarios": [
>     {
>       "title": "Short 4-6 word title",
>       "probability": "High" or "Medium" or "Low",
>       "description": "2-3 sentences describing exactly how this project fails in this specific way, referencing the actual project numbers above",
>       "early_warning_sign": "One specific observable signal that this failure is beginning — something the PM can actually notice",
>       "prevention_action": "One concrete action the PM can take RIGHT NOW to reduce this risk"
>     }
>   ],
>   "overall_risk_level": "High" or "Medium" or "Low",
>   "confidence_note": "One sentence describing what assumptions you made due to missing data"
> }
> ```
>
> - Use Gemini temperature: **0.4**
> - Use model: `gemini-2.5-flash-lite`
> - Parse the JSON response and save to `PreMortemAnalysis` model
> - Return the saved analysis as JSON response to the frontend
>
> **View 2: `acknowledge_scenario(request, premortem_id, scenario_index)`**
> - POST only, login required
> - Creates a `PreMortemScenarioAcknowledgment` record
> - Accepts optional `notes` field from request body
> - Returns success JSON
>
> ---
>
> ### 4. URLS
>
> Add these to the appropriate urls.py:
> ```python
> path('boards/<int:board_id>/premortem/run/', views.run_premortem, name='run_premortem'),
> path('boards/<int:board_id>/premortem/latest/', views.get_latest_premortem, name='get_latest_premortem'),
> path('premortem/<int:premortem_id>/acknowledge/<int:scenario_index>/', views.acknowledge_scenario, name='acknowledge_scenario'),
> ```
>
> Also add a view `get_latest_premortem` that retrieves the most recent PreMortemAnalysis for a board (for displaying existing results without re-running).
>
> ---
>
> ### 5. FRONTEND — BOARD PAGE TAB
>
> In the existing AI tabs section on the board detail page, add a new tab called **"Pre-Mortem"** positioned between the "Risk & Conflicts" tab and the "Retrospective" tab (if it exists), like this:
>
> ```
> [ ... existing tabs ... ] [ Risk & Conflicts ] [ Pre-Mortem ] [ Retrospective ] [ ... ]
> ```
>
> **Inside the Pre-Mortem tab, show TWO states:**
>
> **State A — Feature Locked (conditions not met):**
> ```
> [Shield icon — grayed out]
> Pre-Mortem Analysis
> "Complete these steps to unlock:"
> ✓ or ✗  At least 5 tasks on this board
> ✓ or ✗  At least one deadline set
> ✓ or ✗  At least one team member assigned
> ```
> Show each condition with a green checkmark if met, red X if not. This teaches the user what's needed.
>
> **State B — Feature Unlocked (conditions met, no analysis run yet):**
> ```
> [Shield icon — colored, active]
> Pre-Mortem Analysis
> "Simulate failure before it happens. Identify your project's biggest risks 
>  before work begins."
>
> [Button: "Run Pre-Mortem Analysis"]
> 
> Note: "Analysis takes 10-15 seconds"
> ```
>
> **State C — Analysis Results (after running):**
>
> Show at the top:
> ```
> Overall Risk Level: [RED badge: HIGH / AMBER badge: MEDIUM / GREEN badge: LOW]
> Analyzed on: {date}    Run by: {user}
> [Button: "Re-run Analysis"]    [small text: "Re-running uses updated board data"]
> ```
>
> Then show 5 scenario cards. Each card:
> ```
> [Colored left border: red=High, amber=Medium, green=Low]
>
> Scenario 1                           [HIGH RISK badge]
> ─────────────────────────────────────
> {title}
>
> {description}
>
> ⚠ Early Warning Sign:
> {early_warning_sign}
>
> ✅ Prevention Action:
> {prevention_action}
>
> [Button: "Mark as Addressed" if not acknowledged]
> [Green checkmark + "Addressed by {name} on {date}" if acknowledged]
> ```
>
> ---
>
> ### 6. DASHBOARD RISK BADGE
>
> On the board cards shown in the main dashboard/boards list page, add a small shield icon badge in the top-right corner of each board card IF that board has a Pre-Mortem analysis saved:
> - 🔴 Red shield = overall_risk_level is "high"
> - 🟡 Amber shield = overall_risk_level is "medium"  
> - 🟢 Green shield = overall_risk_level is "low"
> - No badge = Pre-Mortem has never been run for this board
>
> Add a tooltip on hover: "Pre-Mortem Risk: High/Medium/Low — click board to view analysis"
>
> ---
>
> ### 7. MISSION PAGE ROLLUP WIDGET
>
> On the Mission detail page, add a small read-only widget called **"Board Risk Overview"** that shows a summary table:
>
> ```
> Board Risk Overview (Pre-Mortem Summary)
> ─────────────────────────────────────────
> Board Name          Risk Level    Last Analyzed
> ──────────────────  ──────────    ─────────────
> Website Redesign    🔴 High       2 days ago
> API Integration     🟡 Medium     1 week ago  
> Marketing Launch    ─ Not run     ─
>
> ⚠ 1 of 3 boards is High Risk. Consider reviewing before proceeding.
> ```
>
> This widget does NOT call Gemini — it only reads existing `PreMortemAnalysis` records. Keep it lightweight.
>
> ---
>
> ### 8. AUDIT LOGGING
>
> Since PrizmAI already has audit logging, make sure to log:
> - When a Pre-Mortem analysis is run (who, which board, timestamp, overall risk result)
> - When a scenario is acknowledged (who, which scenario, timestamp)
>
> Use whatever audit logging pattern is already in the codebase — don't create a new system.
>
> 