# PrizmAI — Roadmap, Strategy & Go-Forward Plan

> **Audience:** Avishek Paul — Project Author  
> **Date:** April 2026  
> **Primary Goal:** Build a compelling open source PM portfolio to support applications for Program/Project Management roles at big tech companies (Google, Amazon, etc.)

---

## 1. Honest Situation Assessment

### Your Unique Strengths
- **6 years PM experience** (PhD research = complex, multi-stakeholder, long-horizon projects)
- **PMP + AWS + Google Digital Cloud Leader** certifications
- **PhD in Bioengineering** — signals rigorous problem-solving, not just credential-stacking
- **You built a 95+ model, full-stack AI PM platform** using LLMs as your tool — this itself is a story about modern PM practice (directing AI to build software is analogous to directing engineers on a team)
- **Architecture is genuinely sophisticated** — strategic hierarchy, knowledge graph, stress testing, explainable AI — features that don't exist in commercial tools

### The Honest Gap You're Closing
Your PM experience is academic, not industry. Big tech recruiters see PMP-certified academics fairly often. What makes you different is that you built a production-grade tool that demonstrates:
1. You understand what practicing PMs actually need (not just theory)
2. You can manage a complex technical project end-to-end
3. You understand AI, cloud infrastructure, and modern software delivery
4. You can build and lead a community (open source = distributed team management)

**This project is the bridge from academic PM to industry PM. Treat it that way.**

---

## 2. Revised Strategy: Job Application vs. Commercial Product

Because your goal is job applications (not revenue), the priorities are **different** from what a startup would do. Here is the reframe:

| Commercial Product Priority | Your Priority |
|---|---|
| Acquire paying users | Demonstrate PM depth to tech recruiters |
| Ship Spectra v2 ASAP | Document WHY v2 is deferred + community strategy |
| Mobile app for retention | GCP deployment to signal cloud competency |
| Jira importer for migration | Well-structured open source repo with good docs |
| Slack integration for viral growth | Public GitHub presence with meaningful commit history |

**The single most important audience for PrizmAI is not end users — it's Google and Amazon hiring managers.** Every decision below is filtered through that lens first.

---

## 3. What to Do Right Now (Pre-Application Priority)

### 3.1 Google Cloud Deployment — HIGHEST PRIORITY

Deploying to GCP Cloud Run + Neon PostgreSQL is the right call for three reasons:
1. Eliminates self-hosting friction for real users who try the demo
2. Directly signals GCP competency to Google recruiters
3. Neon PostgreSQL is serverless and scales to zero — aligns with cost-conscious open source philosophy

**Migration steps in order:**

#### Step 1: Switch from SQLite to PostgreSQL locally first
```
# requirements.txt — add:
psycopg2-binary>=2.9.9
dj-database-url>=2.1.0
```
In `settings.py`, replace the DATABASES block with:
```python
import dj_database_url
DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',
        conn_max_age=600
    )
}
```
This makes your local dev use SQLite by default but production use whatever `DATABASE_URL` env var points to (Neon PostgreSQL).

#### Step 2: Create a Neon PostgreSQL database
- Sign up at neon.tech (free tier is sufficient for demo)
- Create a project → copy the connection string
- Add it as `DATABASE_URL` in your GCP Cloud Run environment variables

#### Step 3: Containerize with Docker
Create a `Dockerfile` in the project root:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python manage.py collectstatic --noinput
EXPOSE 8080
CMD ["gunicorn", "kanban_board.wsgi:application", "--bind", "0.0.0.0:8080", "--workers", "2"]
```

Create `.dockerignore`:
```
venv/
__pycache__/
*.pyc
db.sqlite3
.env
*.bat
_tmp_*.py
```

#### Step 4: Deploy to Cloud Run
```bash
# Build and push to Google Artifact Registry
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/prizmai

# Deploy to Cloud Run
gcloud run deploy prizmai \
  --image gcr.io/YOUR_PROJECT_ID/prizmai \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL=YOUR_NEON_URL,GEMINI_API_KEY=YOUR_KEY
```

#### Step 5: Handle static files
Cloud Run containers are stateless. Use Google Cloud Storage for static files:
```
# requirements.txt — add:
django-storages[google]>=1.14
```
Add to `settings.py`:
```python
if not DEBUG:
    DEFAULT_FILE_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
    STATICFILES_STORAGE = 'storages.backends.gcloud.GoogleCloudStorage'
    GS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME')
```

#### Step 6: Handle Celery on GCP
Celery + Redis on Cloud Run is complex. For the demo/portfolio version:
- Use **Cloud Tasks** (GCP-native) instead of Celery for background jobs, OR
- Deploy a separate **Cloud Run service** for the Celery worker
- Use **Redis via Upstash** (free tier, compatible with your existing Celery config)
- Simplest path: disable non-critical background tasks in production and document this as "Cloud Run deployment uses polling mode; full async requires Celery worker deployment — see SETUP.md"

**Why this matters for Google recruiters:** Being able to talk about Cloud Run, Neon, GCS, Cloud Tasks, and the architectural decisions you made (stateless containers, serverless DB) in an interview is extremely valuable. Document every decision.

---

### 3.2 Fix the GitHub Repository for Recruiter Consumption

Your GitHub repo is what a recruiter or hiring engineer will actually look at. It needs to tell a clear story in under 2 minutes.

**README.md improvements needed:**
- Add a live demo link (once GCP is deployed) — this is the single highest-impact thing
- Add an architecture diagram (even a simple one showing Django → Celery → Redis → Gemini → PostgreSQL)
- Add a "Why PrizmAI?" section that explicitly mentions the problem with expensive commercial AI PM tools
- Add a "Feature Highlights" section with screenshots (recruiters are visual)
- Add a "Tech Stack" badge row (Python, Django, PostgreSQL, Redis, GCP, Gemini)

**Repository hygiene:**
- Clean up all the `_tmp_*.py` files from the root — they signal messy project management
- Move debug/check scripts to a `scripts/` or `dev_tools/` subdirectory
- Ensure `CONTRIBUTING.md` is polished (this signals you expect collaborators)
- Add `CHANGELOG.md` with version history — shows product thinking

**GitHub Actions CI:**
- Your CI badge is already in the README — make sure it's green and stays green
- Add a deployment workflow that auto-deploys to Cloud Run on merge to main

---

### 3.3 Document the Spectra v2 Decision Professionally

The fact that Spectra v2 agentic actions aren't shipped is not a weakness — **how you communicate that decision is what matters.** This is a real PM skill: deciding what NOT to build and why.

Add a `SPECTRA_V2_ROADMAP.md` or a GitHub Issue milestone with this framing:

> **Spectra v2: Agentic Actions — Open for Community Contributions**
>
> Spectra v1 (Q&A + RAG) is stable and in production. Spectra v2 introduces direct action execution from natural language: creating tasks, sending messages, logging time, and scheduling events. The conversation flow architecture is code-complete in `ai_assistant/utils/conversation_flow.py`.
>
> **Why deferred:** Multi-step agentic flows require extensive error recovery, edge case handling, and integration testing that benefits from community collaboration rather than solo development. The architecture is intentionally designed to be extensible.
>
> **How to contribute:** See `CONTRIBUTING.md` for setup instructions. The action framework is in `ai_assistant/utils/action_service.py`. Open issues are labeled `spectra-v2`.

This turns a limitation into a community engagement strategy. It also demonstrates mature product judgment.

---

## 4. Feature Roadmap — Prioritized for Your Goals

The features are organized into three tracks: **Do it yourself**, **Defer to community**, and **Don't build for this goal.**

### Track A: Do It Yourself (High Resume Impact, Achievable Alone)

These are things where the effort is manageable with LLM assistance and the resume signal is strong.

#### A1. PostgreSQL + GCP Deployment
- **Why:** Directly demonstrates cloud infrastructure skills. Essential for Google recruiter conversations.
- **When:** Before submitting any applications.

#### A2. Task List/Table View
- **Why:** The most requested PM tool feature. Shows product instinct. Relatively self-contained Django view + template.
- **What to build:** A filterable, sortable table view of all tasks across a board. Columns: Title, Assignee, Status, Priority, Due Date, Estimate. Filters: assignee, status, priority, due date range.
- **When:** After GCP deployment.

#### A3. Project Template Library (10-15 templates)
- **Why:** Templates are how PM tools demonstrate domain knowledge. Having "Software Sprint," "Marketing Campaign," "Research Project," and "PhD Research Plan" templates shows breadth. A "Research Project" or "Academic-to-Industry Transition" template would be uniquely authentic to your background.
- **What to build:** A management command that seeds template boards + columns + sample tasks. A "Create from Template" option on the new board form.
- **When:** After List view.

#### A4. Recurring Tasks
- **Why:** Basic PM utility. Users expect it. Celery beat already handles scheduling — this is a small addition to the existing automation framework.
- **What to build:** A "Recurrence" field on tasks (daily/weekly/monthly/custom). A Celery task that clones the task on schedule.
- **When:** After template library.

#### A5. CSV Export for Tasks and Time Entries
- **Why:** Required for reporting. Django makes this easy. Shows you understand PM workflows beyond software.
- **What to build:** A "Export to CSV" button on the board task list and time tracking pages.
- **When:** Any time, this is 1-2 hours of work.

#### A6. Sprint / Scrum Module (Basic)
- **Why:** Most of the teams at Google/Amazon use Scrum. Showing you understand sprint planning is important.
- **What to build:**
  - Sprint model: name, start date, end date, goal, status (planning/active/completed)
  - "Add to Sprint" on tasks
  - Sprint board view (filter kanban by active sprint)
  - Story points field on tasks
  - Sprint velocity tracking (builds on existing burndown infrastructure)
- **When:** Medium-term, after the above items.

#### A7. Docker Compose for Local Development
- **Why:** Every serious open source project has a `docker-compose.yml`. Makes contribution friction near zero.
- **What to build:** A single `docker-compose.yml` that starts Django + PostgreSQL + Redis + Celery worker in one command.
- **When:** Before publicizing the open source project.

---

### Track B: Defer to Community (Document as Issues/Milestones)

Create well-written GitHub Issues for these. A rich issue backlog demonstrates roadmap thinking and invites collaboration.

#### B1. Spectra v2 Agentic Actions
- Already discussed above. The architecture exists, document the extension points.

#### B2. Slack / Microsoft Teams Integration
- Create a detailed issue describing the architecture (webhooks + slash commands)
- Label: `integration`, `good-first-issue` (the webhook receiver is straightforward)

#### B3. GitHub / GitLab Integration
- Commits linked to tasks, PR status on task cards
- Label: `integration`, `enhancement`

#### B4. Jira / Linear / Asana Importer
- CSV and API-based import
- Label: `migration`, `enhancement`

#### B5. Mobile PWA
- Progressive Web App manifest + service worker for offline-capable mobile access
- Surprisingly achievable — label: `frontend`, `pwa`

#### B6. Multi-Language / i18n Support
- Django has built-in i18n — the architecture supports it
- Label: `i18n`, `good-first-issue`

#### B7. Custom Fields
- Flexible schema (text, number, dropdown, date, user)
- Complex to get right — good community contribution project
- Label: `architecture`, `enhancement`

#### B8. OpenAI + Anthropic Claude Integration
- BYOK multi-provider support (your planned feature)
- The AI abstraction layer should be documented for contributors
- Label: `ai`, `enhancement`

#### B9. Portfolio / Program Dashboard
- Multi-project health overview for directors/VPs
- Label: `analytics`, `enterprise`

#### B10. Native iOS/Android App
- Beyond the scope of solo development for a portfolio project
- Label: `mobile`, `long-term`

---

### Track C: Don't Build (Wrong Priority for Your Goal)

- **Billing / subscription management** — You're not building a SaaS, BYOK is the model
- **SSO / SAML enterprise auth** — Overkill for portfolio
- **Helm chart / Kubernetes** — GCP Cloud Run is sufficient and more relevant to your Google target
- **Advanced ML model training** — Gemini/OpenAI API abstracts this; custom training is not the story you're telling

---

## 5. How to Tell This Story to Google/Amazon Recruiters

### On Your Resume

**Do not describe PrizmAI as "a side project." Describe it as what it is:**

> **PrizmAI — Open Source AI-Powered Project Management Platform** | *Author & Maintainer* | 2025–Present  
> Designed and built a full-stack PM platform with 95+ data models, real-time WebSocket collaboration, and deep AI integration (Google Gemini). Features include a Goal→Mission→Strategy→Board hierarchy, AI-driven Pre-Mortem and Stress Test simulations, organizational knowledge graph memory, and explainable AI recommendations. Deployed on Google Cloud Run with Neon PostgreSQL. Published as open source (MIT license) with public contribution roadmap and community documentation. Technologies: Python/Django, PostgreSQL, Redis, Celery, GCP Cloud Run, Google Gemini API, WebSockets, REST API.

**Key bullets to include:**
- "Designed strategic hierarchy (Goal → Mission → Strategy → Board) that enforces alignment between individual tasks and organizational objectives — modeling real-world OKR/V2MOM frameworks used at Google and Amazon"
- "Implemented AI Stress Test and Pre-Mortem features that simulate project failure scenarios before execution — applied PM risk frameworks in software"
- "Led open source release: authored CONTRIBUTING.md, structured GitHub issues as a public backlog, and established community governance"
- "Migrated from SQLite to PostgreSQL on Google Cloud Run, implementing stateless container architecture with GCS for static assets and Neon for serverless database"

### In PM Interviews

**The story to tell about PrizmAI:**
> "I realized that commercial PM tools charge $20-50/user/month for basic AI features that cost pennies via API. I wanted to understand the full PM tool space deeply — so instead of just using Jira, I built one. Building PrizmAI forced me to make every product decision a real PM makes: what goes in MVP, what to defer, how to handle scope creep, how to prioritize competing features. The Spectra v2 decision — deferring agentic actions to the open source community — is a real example of building a community around a technical backlog I created."

**For Google specifically:** Emphasize the GCP deployment, Gemini API integration, and the strategic hierarchy (which mirrors Google's OKR system). Google PMs are expected to understand cloud architecture. Being able to say "I deployed this on Cloud Run and can explain the stateless container design trade-offs" is rare for a PM candidate.

**For Amazon specifically:** Frame it around the Leadership Principles:
- *Customer Obsession*: "I talked to PMs frustrated with expensive Jira AI add-ons and built the tool they described"
- *Bias for Action*: "Rather than waiting for a team, I used LLMs as my engineering team and shipped"
- *Invent and Simplify*: "The Shadow Board feature — parallel-universe project simulation — doesn't exist in any commercial tool"
- *Dive Deep*: "I designed the data model for the Knowledge Graph knowing that organizational memory is the hardest part of PM at scale"

### LinkedIn Post Strategy

Post about PrizmAI at these milestones:
1. **GCP deployment** — "Deployed an open source PM tool to Google Cloud Run. Here's the architecture and what I learned about stateless containers..."
2. **First external contributor** — "Someone I've never met just contributed to PrizmAI. Here's what building an open source community taught me about distributed team management..."
3. **100 GitHub stars** — Frame as a community milestone, not vanity metric
4. **Template library launch** — "I built 15 project templates for PrizmAI. The 'PhD Research Plan' template is for researchers transitioning to industry — it's the template I wish I had"

---

## 6. Open Source Community Strategy

### Immediate Actions (Repository Setup)

1. **Clean the repo root** — Move all `_tmp_*.py`, debug scripts, and `.bat` files out of root into `scripts/dev/`
2. **Create `CONTRIBUTING.md`** (you have one — polish it)
3. **Create GitHub Issue templates** — Bug report, Feature request, Good first issue
4. **Label your issues** — `good-first-issue`, `help-wanted`, `spectra-v2`, `integration`, `bug`, `enhancement`
5. **Create a `ROADMAP.md`** (or link to this document) in the repo
6. **Add a live demo link** to README — this is #1 for attracting contributors

### Milestone Structure (GitHub Milestones)

Create these milestones in GitHub to signal roadmap maturity:

| Milestone | Description | Issues |
|---|---|---|
| v1.1 — Production Ready | GCP, PostgreSQL, Docker Compose | 5-8 issues |
| v1.2 — Core UX | List view, CSV export, recurring tasks | 6-10 issues |
| v1.3 — Templates & Sprints | Template library, basic Scrum support | 8-12 issues |
| v2.0 — Spectra Actions | Agentic task/message/event creation | 15-20 issues |
| v2.1 — Integrations | Slack, GitHub, Jira importer | 10-15 issues |

### Attracting Contributors

- **Post on Hacker News "Show HN"** after GCP deployment: "Show HN: PrizmAI – Open Source AI PM tool (Gemini, BYOK, 50 free AI uses)"
- **Post on r/projectmanagement** and **r/django** and **r/opensource**
- **Product Hunt launch** (after GCP, with demo link and screenshots)
- **Tag it properly on GitHub**: topics = `project-management`, `django`, `ai`, `gemini`, `kanban`, `open-source`, `python`
- **Write a dev.to or Medium post**: "I built a full-stack PM tool as a non-developer. Here's what I learned." — This is a compelling story that will go viral in tech circles

---

## 7. Technical Debt to Address Before Open Source Launch

These are not new features — they're issues that will make contributors frustrated or make the codebase look unprofessional.

### High Priority (Fix Before Launch)

1. **Remove hardcoded secrets** — Audit `settings.py` and all files for any hardcoded API keys, `SECRET_KEY`, or credentials. Use `python-dotenv` or environment variables exclusively.

2. **Add `env.example` file** — A template `.env` file with all required variables and comments explaining each. New contributors can't run the project without this.

3. **Ensure `requirements.txt` is pinned** — Run `pip freeze > requirements.txt` and commit exact versions. Or better, use `pip-tools` with a `requirements.in` for maintainability.

4. **Add basic test coverage for critical paths** — At minimum: user auth, board creation, task CRUD, API token auth. GitHub Actions CI should run these. A project with zero tests will not attract serious contributors.

5. **Fix the Spectra board dropdown misleading UI** — The chat says "select from dropdown above" but no dropdown exists. This confuses new users and will generate noise issues. Either add the dropdown or update the prompt text.

6. **Database: PostgreSQL migration** — Run `python manage.py migrate` against Neon and verify all 95+ models migrate cleanly. Fix any SQLite-specific queries before open source launch.

### Medium Priority (Before v1.1 Milestone)

7. **Add `SETUP.md`** (you have one — verify it works end-to-end on a clean machine with Docker Compose)

8. **Document Celery task inventory** — List every periodic task, its schedule, and what it does. New contributors need this to understand background processing.

9. **API documentation** — You have `API_DOCUMENTATION.md`. Verify it matches current endpoints. Consider adding OpenAPI/Swagger auto-generation (`drf-spectacular` if using DRF).

10. **Remove orphaned `_tmp_*.py` scripts** — These are debug artifacts, not part of the codebase. They make the project look untidy and will confuse contributors.

---

## 8. The Spectra v2 Architecture (For Future Contributors)

This section documents what was built, what works, and what needs community help — so future contributors have a clear starting point.

### What's Complete and Working
- `ai_assistant/utils/conversation_flow.py` — Full multi-step conversation state machine
- `ai_assistant/utils/action_service.py` — Action execution framework
- `ai_assistant/utils/rbac_utils.py` — Permission checking before any action
- All conversation state models (`SpectraConversationState`)
- Board selection via natural language (fuzzy matching)
- RBAC pre-checks before entering action flows

### What Needs Work (Community Opportunity)
- **Error recovery in multi-step flows** — When Gemini returns unexpected formats, the conversation breaks
- **Confirmation step reliability** — The "awaiting_confirmation" state sometimes doesn't resolve correctly
- **Message delivery action** — Sends to board chat but doesn't handle edge cases (no chat room, user offline)
- **Calendar event creation** — Timezone handling in the action service has edge cases
- **Integration tests** — The conversation flow has no automated tests; this makes regression hard to detect

### Architecture Reference for Contributors
```
User Message
    ↓
ai_assistant/views.py → send_message()
    ↓
ConversationFlowManager.handle_message()
    ├── Is state.mode == 'normal'?
    │   └── Check intent → start flow OR pass to Q&A
    └── Is state.mode == 'collecting_*'?
        └── Continue multi-step flow → execute action on completion
            ↓
        ActionService.execute() → Django model operations
```

---

## 9. Success Metrics (How to Know It's Working)

Since the goal is job applications, track these:

| Metric | Target | Why It Matters |
|---|---|---|
| GitHub Stars | 100+ | Social proof for recruiters |
| Live Demo accessible | Yes | Removes "show me it works" barrier in interviews |
| GCP deployment | Done | Directly answerable in Google interviews |
| CI/CD pipeline green | Always | Shows engineering discipline |
| First external contributor | 1+ | Proves community building capability |
| README has screenshots | Yes | Visual credibility |
| CONTRIBUTING.md complete | Yes | Shows you can onboard people |
| Google/Amazon application | Submitted | The actual goal |

---

## 10. Realistic Timeline

| Timeframe | Focus |
|---|---|
| **Week 1-2** | Switch to PostgreSQL + create Neon DB + Docker Compose + local testing |
| **Week 3-4** | GCP Cloud Run deployment + CI/CD GitHub Actions + live demo URL |
| **Week 5** | Repository cleanup (remove _tmp files, add env.example, polish README with screenshots) |
| **Week 6-7** | Task List/Table view + CSV export |
| **Week 8** | Template library (10-15 templates) |
| **Week 9-10** | Create all GitHub issues/milestones as public backlog |
| **Week 11** | Hacker News + Product Hunt launch post |
| **Week 12** | Begin job applications with live demo link + polished GitHub |
| **Month 4-6** | Recurring tasks + basic Sprint module (can do in parallel with applications) |
| **Ongoing** | Respond to community issues, review PRs — this is the "open source community management" story |

---

## 11. One Last Honest Note

You asked whether PrizmAI can compete with commercial tools. The honest answer is: **eventually yes on AI depth, currently no on ecosystem breadth.** But that's not your goal.

Your goal is to walk into a Google or Amazon program management interview and demonstrate that you:
1. Understand what PMs actually need (you built a 95-model PM platform)
2. Can manage a complex technical product from idea to deployment
3. Know how to use modern tools (GCP, Gemini, PostgreSQL, WebSockets)
4. Can lead a distributed community (open source governance)
5. Have product judgment (Spectra v2 deferral decision, BYOK model, open source vs. SaaS choice)

PrizmAI already does all of that. The remaining work is **presentation** — making it easy for a recruiter to see that story in 2 minutes.

Deploy it. Clean it up. Write the story. Then apply.

---

*Document generated April 2026. Revisit after GCP deployment to update timelines and status.*
