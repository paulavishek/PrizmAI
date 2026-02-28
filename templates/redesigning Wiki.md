Phase 1 — The Data Foundation (Do This First)


"In the Knowledge Hub / Wiki app, create a WikiTemplate model in the database with these fields: name (text), description (one-line summary), category_name (suggested category), content (markdown text), icon (emoji or icon name), is_active (yes/no toggle). Then create the 5 templates as fixed data inside the app — not user-created, not editable from the UI. Templates are read-only system data. The 5 templates are: Project Charter, Issue Log, Risk Register, Meeting Minutes, RACI Matrix."

Why this order: Everything else — the library page, the buttons, the pre-filled form — all depends on this data existing first.

Phase 2 — The Template Content
What this means: Writing the actual text that goes inside each template.
This is the content I recommend for each. Share this with Claude verbatim:
Project Charter — fields for Project Name, Objective, Scope, Stakeholders, Budget, Timeline, Success Criteria, Risks
Issue Log — table with columns: Issue ID, Description, Priority, Owner, Status, Due Date, Resolution
Risk Register — table with columns: Risk ID, Description, Probability, Impact, Score, Mitigation, Owner, Status
Meeting Minutes — fields for Date, Attendees, Agenda, Decisions Made, Action Items (with owner + due date), Next Meeting
RACI Matrix — table with tasks as rows, team roles as columns, cells contain R/A/C/I values
Ask Claude to write these as properly formatted Markdown so they render nicely in the existing content area you showed me.

Phase 3 — The Template Library Page
What this means: Build the page at /wiki/templates/ that shows all 5 templates as cards.
Tell Claude:

"Create a Template Library page at /wiki/templates/. Show each template as a card with its name, description, and a 'Use Template' button. This page should be accessible from the Knowledge Hub main page. No login restrictions — any logged-in user can access it."


Phase 4 — The "Use Template" Flow
What this means: When someone clicks "Use Template," open the Create form pre-filled with that template's content.
Tell Claude:

"When a user clicks 'Use Template' on any template card, redirect them to /wiki/create/ with the template data pre-filled. Pre-fill: Title (template name), Category (the template's suggested category — auto-create this category if it doesn't exist for this user), and Content (the full markdown template text). The user can edit everything before saving. Saving always creates a brand new wiki page — it never modifies the template itself."

This is the most important phase — if this feels clunky, the whole feature fails.

Phase 5 — Entry Points on the Main Page
What this means: Make templates discoverable from the Knowledge Hub home screen.
Two things to add, as per your Decision 1:

"On the Knowledge Hub main page, add: (1) A permanent 'Template Library' card in the sidebar or quick actions area with a link to /wiki/templates/. (2) If a user has zero wiki pages, replace the empty list area with a friendly message that says something like 'Start with a template' and shows the 5 template cards directly inline."


Phase 6 — Test It End to End
Before calling it done, verify these specific scenarios:

New user with zero pages → sees template prompt → clicks template → form pre-fills → saves → new page appears in their list
Existing user → finds Template Library via sidebar → uses a template → existing pages unaffected
Category auto-creation → if user has no "Project Management" category, does it get created cleanly?
Template content → does the Markdown render properly in Preview mode before saving?


The Order Matters
Phase 1 (Database) → Phase 2 (Content) → Phase 3 (Library Page) 
→ Phase 4 (Use Template Flow) → Phase 5 (Entry Points) → Phase 6 (Testing)
Do not skip ahead. Phase 4 will break if Phase 1 isn't done. Phase 5 will look broken if Phase 3 doesn't exist yet.