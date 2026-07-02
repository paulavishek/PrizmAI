# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Behavioral Guidelines

- **No assumptions.** Never assume a function, model field, URL, template block, or file exists. This codebase has many similarly-named modules (e.g. `commitment_views.py` vs `commitment_views.py.bak`, multiple `*_ai.py` / `*_utils.py` files per app) — guessing wrong wastes tokens fixing it later.
- **Verify first.** Before proposing or editing, `Grep`/`Read` the actual code path involved. Confirm a model field, signal, or helper exists before writing code that calls it.
- **Acknowledge gaps.** If a referenced file/feature can't be found, search for it explicitly (it's likely under a differently-named app or file) or ask — don't invent a plausible-sounding path.
- Check `MANUAL_TEST_PLAN.md`, `FEATURES.md`, and the relevant `docs/` guide before assuming how a feature is *supposed* to work — several major subsystems (Automations, RBAC, demo data, Celery) have dedicated docs described below.

## Development Commands

```bash
# Run dev server
python manage.py runserver

# Tests (pytest is configured via setup.cfg → uses kanban_board.test_settings)
pytest
pytest tests/test_kanban/                 # one test dir
pytest tests/test_kanban/test_foo.py::TestClass::test_method  # single test
python manage.py test kanban              # Django test runner (alt.)

# Migrations
python manage.py makemigrations
python manage.py migrate

# Demo data
python manage.py populate_test_data       # seed full demo org/boards/tasks
python manage.py refresh_demo_dates       # shift demo dates to stay "current"

# Celery (background tasks — Redis broker, required for automations/coach/etc.)
celery -A kanban_board worker --pool=solo -Q celery,summaries,ai_tasks,interactive -l info
celery -A kanban_board beat -l info
```

No frontend build step — JS/CSS are served as static files, Tiptap editor is loaded via CDN.

## Architecture

**Monolithic Django app**, not microservices. `kanban` is the core app and by far the largest — board access enforcement, automations, budgets, coaching, custom fields, invitations, and more all live there as flat `*_views.py` / `*_models.py` / `*_utils.py` files rather than sub-apps. Business logic belongs in the relevant app directory (`kanban`, `ai_assistant`, `analytics`, `accounts`, etc.), not top-level scripts.

**Apps** (see `INSTALLED_APPS` in `kanban_board/settings.py`):
- `accounts` — auth, profiles, workspace/timezone middleware, demo personas
- `kanban` — boards/tasks/columns, RBAC enforcement, automations, budgets, coach, custom fields, demo system (`kanban/utils/demo_*`)
- `ai_assistant` — Spectra chat, AI provider routing (`ai_assistant/utils/ai_router.py`)
- `api` — REST API (DRF) + AI usage tracking/quotas
- `analytics`, `messaging` (WebSocket chat via Channels), `wiki`, `webhooks`, `integrations`
- `knowledge_graph` — project memory graph (decisions/lessons/risk events)
- `decision_center`, `exit_protocol`, `requirements` — decision queue, project wind-down, requirements traceability

**AI calls always go through `AIRouter`** (`ai_assistant/utils/ai_router.py`). Never instantiate a provider SDK (Gemini/OpenAI/Anthropic) directly in feature code — `AIRouter.complete()` handles BYOK vs org vs platform key resolution and returns a normalized `{"text", "model", "tokens_used"}` dict, raising `AIProviderError` on failure. Some older call-sites still read the stale `model_used`/`tokens` keys — check the call-site's contract before trusting it.

**Multi-tenancy**: **Workspace** is the tenant boundary (not `Organization` — that's legacy/nullable and a known source of cross-tenant bleed if used for scoping). Scope queries by `Board.workspace` / the active workspace, resolved per-request by `accounts.middleware.WorkspaceMiddleware`.

**RBAC** is layered (view `has_perm`/`check_access` → django-rules predicates → `simple_access` helpers → demo-protection signals → workspace scoping). Full reference: `RBAC_DOCUMENTATION.md`. Demo Workspace intentionally bypasses RBAC.

**Demo system** is extensive and easy to break silently: seeded data must set `is_seed_demo_data=True`, dates are relative and refreshed via `refresh_demo_dates` / `kanban/utils/demo_date_refresh.py`, and per-user sandbox boards are cloned from official template boards (`sandbox_views.py`). Read `MANUAL_TEST_PLAN.md` and existing `project_*` context before touching demo seeding/cloning — this is the single most common source of "looks fine until reset" bugs.

**Automations** are a WHEN/IF/THEN/OTHERWISE rule engine (`kanban/automation_*.py`) — triggers, conditions, and actions are separate registries; it deliberately makes **no synchronous LLM calls** (see `tests/test_kanban` automation guard test). See `FEATURES.md` for the trigger/condition/action catalog.

**Celery**: local dev runs a single `--pool=solo` worker on Windows (sequential, no true concurrency) — see `CELERY_PRODUCTION_GUIDE.md` for the full task inventory and why sync-safe paths (like Spectra chat) were deliberately moved *off* Celery rather than made to wait on it.

**Settings**: `kanban_board/settings.py` for dev/runtime, `kanban_board/test_settings.py` for pytest/Django test runner (must keep `rules.permissions.ObjectPermissionBackend` in `AUTHENTICATION_BACKENDS` or RBAC-guarded views 403 in tests).

## Conventions

- Don't create temporary diagnostic scripts (`_tmp_*.py`, ad-hoc root-level `.py` files) — use `python manage.py shell` for one-off inspection, and put real tests under `tests/`.
- Existing tests use `client.login()` in a few legacy spots and fail under django-axes — this is pre-existing, not a regression to chase; write *new* tests with `force_login`.
- Don't reintroduce direct provider SDK calls, Organization-based tenant scoping, or Celery dependencies for simple sync request/response flows — these are documented anti-patterns from past incidents, not stylistic preferences.
