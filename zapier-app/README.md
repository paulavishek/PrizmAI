# PrizmAI Zapier App

A Zapier integration for [PrizmAI](https://github.com/your-org/prizmai) — the open-source AI-powered project management platform.

## Triggers

| Trigger | Description |
|---|---|
| **New Task** | Fires when a task is created in PrizmAI |
| **Task Completed** | Fires when a task reaches 100% progress |
| **Task Assigned to Me** | Fires when a task is assigned to the authenticated user |

## Actions

| Action | Description |
|---|---|
| **Create Task** | Creates a new task in a PrizmAI board |
| **Update Task Status** | Moves a task to a different column (status) |

## Setup

### Prerequisites
- Node.js ≥ 18
- A running PrizmAI instance
- A PrizmAI API token (generate at **Profile → API Tokens → Create Token**)

### Install dependencies

```bash
cd zapier-app
npm install
```

### Configure the base URL

Set the `PRIZMAI_BASE_URL` environment variable to point to your PrizmAI instance:

```bash
# Local dev
export PRIZMAI_BASE_URL=http://localhost:8000

# Production
export PRIZMAI_BASE_URL=https://app.prizmai.com
```

### Run tests

```bash
npx zapier test
```

### Deploy (private use)

```bash
npx zapier login
npx zapier push
```

The app will be available in your Zapier account under **My Apps**.

---

## Authentication

PrizmAI uses **API Token** authentication. Users generate a token at:

```
https://<your-domain>/api/v1/auth/tokens/
```

The token should have at minimum: `tasks.read`, `tasks.write`, `boards.read` scopes.

---

## API Endpoints used

All endpoints live under `/api/v1/zapier/` and are documented in `API_DOCUMENTATION.md`.

| Endpoint | Method | Used by |
|---|---|---|
| `/api/v1/zapier/tasks/` | GET | New Task trigger |
| `/api/v1/zapier/tasks/completed/` | GET | Task Completed trigger |
| `/api/v1/zapier/tasks/assigned/` | GET | Task Assigned trigger |
| `/api/v1/zapier/tasks/create/` | POST | Create Task action |
| `/api/v1/zapier/tasks/<id>/status/` | PATCH | Update Task Status action |
| `/api/v1/zapier/boards/` | GET | Board dropdown |
| `/api/v1/zapier/boards/<id>/columns/` | GET | Column dropdown |

---

## Marketplace Submission (future)

This app is currently **private/internal**. See the comments in `index.js` for the step-by-step marketplace submission checklist.

Key requirement for public apps: Zapier requires **OAuth 2.0** rather than API key auth. When PrizmAI is ready for the marketplace, the `authentication.js` module should be swapped to OAuth 2.0.
