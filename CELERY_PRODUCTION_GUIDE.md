# PrizmAI — Celery Architecture: Production Readiness Guide

**Prepared:** April 12, 2026  
**Status:** Pre-production planning document  
**Purpose:** Reference guide for migrating the Celery task infrastructure from local development to cloud production.

---

## Table of Contents

1. [What Happened — Root Cause Explained](#1-what-happened--root-cause-explained)
2. [Current Architecture Audit](#2-current-architecture-audit)
3. [What Is Already Correct — Keep As-Is](#3-what-is-already-correct--keep-as-is)
4. [Problems That Must Be Fixed Before Production](#4-problems-that-must-be-fixed-before-production)
5. [Production Plan — 5 Phases](#5-production-plan--5-phases)
   - [Phase 1: Worker Separation (Critical)](#phase-1-worker-separation-critical)
   - [Phase 2: Morning Burst Mitigation (Critical)](#phase-2-morning-burst-mitigation-critical)
   - [Phase 3: Monitoring & Observability (Important)](#phase-3-monitoring--observability-important)
   - [Phase 4: Cloud Infrastructure (Essential)](#phase-4-cloud-infrastructure-essential)
   - [Phase 5: Resilience (Nice-to-Have)](#phase-5-resilience-nice-to-have)
6. [Complete Task Inventory](#6-complete-task-inventory)
7. [File Reference Map](#7-file-reference-map)
8. [Verification Checklist](#8-verification-checklist)

---

## 1. What Happened — Root Cause Explained

### The Problem (Plain English)

Spectra (the AI assistant) was taking 2+ minutes to respond, and eventually timing out. The root cause:

> The single Celery worker uses `--pool=solo`, which means it processes **one task at a time, sequentially**. Every morning at startup, 10+ scheduled background tasks (AI summaries, coaching suggestions, decision briefings, etc.) flood the queue at once. Because the worker can only do one thing at a time, a user asking Spectra a question had to wait behind all those background tasks. The WebSocket timed out after 150 seconds.

### The Fix That Was Applied

The `send_message` view in `ai_assistant/views.py` was changed to process chat messages **directly**, without going through Celery at all. Spectra now calls the Gemini API directly in the web request (takes 2-5 seconds) and returns the answer immediately. The frontend (`ai_progressive.js`) checks for `sync: true` in the response and renders the answer right away without opening a WebSocket.

**This fix is correct and permanent.** Simple question-answer interactions do not need a task queue. Task queues are for long-running work that would otherwise block a web request.

### Why Did This Problem Appear Recently?

The project has grown to **80+ Celery tasks** and **23 periodic scheduled entries**. As more background features were added (commitment protocol decay, knowledge graph connections, exit protocol health scoring, etc.), the queue got longer. The single sequential worker that was fine for 10 tasks became a bottleneck at 80+.

---

## 2. Current Architecture Audit

### Infrastructure Components

| Component | Current Setup |
|-----------|--------------|
| **Task broker** | Redis `redis://127.0.0.1:6379/0` (local) |
| **Result backend** | Redis `redis://127.0.0.1:6379/0` (same instance) |
| **Django cache** | Redis (same instance) |
| **WebSocket channel layer** | Redis (same instance) |
| **Worker pool** | `--pool=solo` (Windows limitation — single sequential process) |
| **Worker concurrency** | 1 (effectively — solo pool) |
| **Queues consumed** | `celery`, `summaries`, `ai_tasks` (all by one worker) |
| **Beat scheduler** | `django_celery_beat.schedulers:DatabaseScheduler` (hybrid: hardcoded + DB entries) |
| **Task timezone** | Asia/Kolkata (IST) |
| **Global task hard limit** | 30 minutes |
| **Process supervision** | Windows `.bat` files with `start cmd /k` |

### Queue Routing Rules (Settings)

```python
CELERY_TASK_ROUTES = {
    'kanban.ai_summary.*': {'queue': 'summaries'},
    'kanban.ai_streaming.*': {'queue': 'ai_tasks'},
}
# Everything else → 'celery' (default queue)
```

### Daily Scheduled Task Timeline (IST)

```
12:00 AM  →  Reset commitment tokens (Monday only)
 1:00 AM  →  Knowledge graph: check missed deadlines
 1:30 AM  →  Knowledge graph: check budget thresholds
 2:00 AM  →  Conflict cleanup (delete resolved >90 days)
 2:15 AM  →  Board health monitoring (exit protocol)
 3:00 AM  →  Demo data date refresh
 4:00 AM  →  Commitment confidence decay (every 4 hours)
 6:00 AM  →  *** Org learning aggregation (AI/ML)
 6:30 AM  →  *** PM metrics refresh (ML prerequisite)
 7:00 AM  →  *** Coaching suggestions generation (AI)
 7:15 AM  →  *** Decision items collection
 7:30 AM  →  *** Decision briefing generation (AI)
 8:00 AM  →  *** Executive briefing generation (AI — HEAVIEST)
 9:00 AM  →  Time anomaly detection (AI)
17:00     →  Time tracking reminders (weekdays)
Every 30m →  Digest email delivery
Every 1h  →  Conflict detection scan
Every 4h  →  Commitment confidence decay

Weekly (Sunday):
 2:00 AM  →  ML model retraining (priority prediction)
 4:00 AM  →  A/B experiment analysis
 5:00 AM  →  Knowledge graph connection discovery (AI)
```

**The 6:00–8:00 AM window is the critical bottleneck.** Six heavy AI tasks fire within 2 hours. On a solo worker, they run one after another — potentially 30-60 minutes of queue saturation.

---

## 3. What Is Already Correct — Keep As-Is

These architectural decisions are sound and should **not** be changed:

### ✅ Spectra Chat Is Now Synchronous
`ai_assistant/views.py` → `send_message` calls Gemini directly and returns `{"sync": true, ...}`. The frontend renders the answer immediately without a WebSocket. This is the right approach for fast (2-5s) interactive calls.

### ✅ Three-Queue Separation
The `summaries`, `ai_tasks`, and `celery` queues correctly separate concerns. AI summary generation doesn't compete with webhook delivery. This foundation is correct — we just need separate workers per queue (see Phase 1).

### ✅ Redis Debounce Locks
Board summary tasks use `cache.add()` (Redis SET NX) as atomic locks to prevent duplicate Gemini calls when rapid saves occur. The 600-second debounce window is appropriate.

### ✅ Data Pruning in Board Summaries
Board summary tasks only send "exception" tasks (blocked, overdue, high-risk) to the LLM in full detail; all others contribute aggregate counts only. This prevents token limit issues on large boards and controls AI costs.

### ✅ Catchup Mechanism on Worker Restart
The `worker_ready` signal handler in `kanban_board/celery.py` re-enqueues missed daily tasks (executive briefing, decision items) if the worker was down during their scheduled time. This is robust behaviour.

### ✅ WebSocket Streaming for Heavy AI Features
Pre-mortem analysis, risk assessment, scope review, etc. use WebSocket progress streaming (10% → 50% → 100%). Users see live progress instead of a blank wait. This is correct UX for operations taking 30-120 seconds.

### ✅ Resilience Patterns
- Fallback template workspaces if onboarding AI fails
- Chunk-based processing (50 records at a time) for commitment decay
- `max_retries=2-3` on most tasks
- Per-task `soft_time_limit` for graceful shutdown before hard kill

---

## 4. Problems That Must Be Fixed Before Production

### Problem 1 — `--pool=solo` (SEVERITY: CRITICAL)

**What it means:** The worker runs as a single Python process executing one task at a time. There is no parallelism at all.

**Impact:** Any long-running task (even a 5-minute board summary) blocks every other task in every queue.

**Fix:** See Phase 1. On Linux (cloud), use `--pool=prefork` or `--pool=gevent`. The `pool=solo` limitation exists only because Windows does not support `prefork`.

---

### Problem 2 — One Worker for All Queues (SEVERITY: CRITICAL)

**What it means:** A single worker process consumes `celery`, `summaries`, and `ai_tasks`. The 10-minute daily executive briefing task blocks webhook delivery, conflict detection, and every user-triggered action — all running on the same worker.

**Fix:** Run three separate workers, one per queue. See Phase 1.

---

### Problem 3 — Morning Task Burst (SEVERITY: CRITICAL)

**What it means:** Six heavy AI tasks fire within 6:00–8:00 AM IST. On a solo worker, a user triggering anything during this window waits in a queue behind up to an hour of AI processing.

**Fix:** Dedicated workers per queue (Phase 1) + spreading out schedule (Phase 2).

---

### Problem 4 — No Process Supervisor (SEVERITY: CRITICAL)

**What it means:** Workers are started with `start cmd /k` in a Windows `.bat` file. If a worker crashes, it is gone. There is no automatic restart, health check, or alerting.

**Fix:** Use systemd (Linux), supervisord, or Docker Compose with health checks. See Phase 4.

---

### Problem 5 — Redis Is a Single Point of Failure (SEVERITY: HIGH)

**What it means:** The same Redis instance handles the task broker, result backend, Django cache, and WebSocket channel layer. If Redis goes down, the entire application — web requests, WebSockets, background tasks — fails simultaneously.

**Fix:** Use managed cloud Redis (e.g., AWS ElastiCache, GCP Memorystore) with replication. Optionally separate databases (db 0 for broker, db 1 for results, db 2 for cache, db 3 for channels). See Phase 4.

---

### Problem 6 — No Monitoring (SEVERITY: HIGH)

**What it means:** There is no visibility into queue depths, task failure rates, worker health, or how long tasks are taking. Problems are discovered only when users complain.

**Fix:** Install Flower for real-time dashboards. See Phase 3.

---

### Problem 7 — No Gemini API Rate Limiting at Task Level (SEVERITY: MEDIUM)

**What it means:** Multiple workers running simultaneously can fire many Gemini API calls at once. Large-scale Gemini throttling or quota exhaustion would cause many tasks to fail simultaneously.

**Fix:** Add `rate_limit` parameters to AI tasks. See Phase 2.

---

### Problem 8 — Global 30-Minute Task Timeout (SEVERITY: LOW)

**What it means:** Every task has a 30-minute hard kill limit. Most tasks should complete in under 2 minutes. A stuck task will hold a worker slot for 30 minutes before being killed.

**Fix:** Set per-task `time_limit` / `soft_time_limit` values. Already partially done — standardise across all tasks. See Phase 5.

---

## 5. Production Plan — 5 Phases

---

### Phase 1: Worker Separation (Critical)

**Implement before any production deployment.**

#### Step 1.1 — Replace `pool=solo` with `pool=gevent`

On Linux (cloud), `pool=prefork` is the default and works well for CPU-bound tasks. For Gemini AI calls (which are I/O-bound — you're mostly waiting for the API to respond), `pool=gevent` is superior: it runs many concurrent calls in a single process with green threads, using far less memory than forking.

Install gevent:
```bash
pip install gevent
```

Add to `requirements.txt`:
```
gevent>=23.9.0
```

#### Step 1.2 — Run Four Separate Workers

Replace the single worker command in your startup scripts with four dedicated workers:

```bash
# Worker 1: Default queue — lightweight operational tasks
# (conflict detection, automations, webhooks, analytics, time tracking)
celery -A kanban_board worker \
  --pool=prefork \
  --concurrency=4 \
  -Q celery \
  -n worker-default@%h \
  --loglevel=info

# Worker 2: AI summaries — heavy Gemini calls (board/mission/goal/briefing)
celery -A kanban_board worker \
  --pool=gevent \
  --concurrency=10 \
  -Q summaries \
  -n worker-summaries@%h \
  --loglevel=info

# Worker 3: AI streaming — WebSocket progress tasks (pre-mortem, risk, scope)
celery -A kanban_board worker \
  --pool=gevent \
  --concurrency=5 \
  -Q ai_tasks \
  -n worker-streaming@%h \
  --loglevel=info

# Worker 4: Interactive — user-triggered on-demand tasks (fast response required)
celery -A kanban_board worker \
  --pool=gevent \
  --concurrency=5 \
  -Q interactive \
  -n worker-interactive@%h \
  --loglevel=info
```

#### Step 1.3 — Add the `interactive` Queue

In `kanban_board/settings.py`, update task routing to add the new `interactive` queue for user-triggered tasks that should respond quickly:

```python
CELERY_TASK_ROUTES = {
    # Existing routes
    'kanban.ai_summary.*': {'queue': 'summaries'},
    'kanban.ai_streaming.*': {'queue': 'ai_tasks'},

    # New: user-triggered tasks that need fast response
    'kanban.tasks.classify_board_on_creation': {'queue': 'interactive'},
    'kanban.detect_board_conflicts': {'queue': 'interactive'},
    'kanban.provision_sandbox_task': {'queue': 'interactive'},
    'kanban.generate_workspace_from_goal_task': {'queue': 'interactive'},
    'kanban.generate_scope_autopsy': {'queue': 'interactive'},
    'exit_protocol.tasks.generate_hospice_assessment': {'queue': 'interactive'},
    'exit_protocol.tasks.generate_knowledge_checklist': {'queue': 'interactive'},
    'exit_protocol.tasks.generate_team_transition_memos': {'queue': 'interactive'},
    'webhooks.tasks.deliver_webhook': {'queue': 'interactive'},
}
```

**Why this matters:** The `interactive` queue is consumed only by `worker-interactive`. Scheduled morning tasks (which use `celery` and `summaries` queues) cannot affect it. A user triggering a pre-mortem at 7:30 AM gets a response regardless of the morning processing load.

#### Step 1.4 — Update Beat Worker to Only Run Beat

Celery Beat should run as a standalone process, not alongside a worker:

```bash
# Beat scheduler (dedicated process — no worker duties)
celery -A kanban_board beat \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler \
  --loglevel=info
```

---

### Phase 2: Morning Burst Mitigation (Critical)

**Implement alongside Phase 1.**

#### Step 2.1 — Stagger the Beat Schedule

In `kanban_board/celery.py`, spread the 6:00–8:00 AM window across 5:00–9:00 AM with 25+ minute gaps. The dependency order must be maintained (PM metrics must run before coaching suggestions):

**Proposed schedule (no dependency violations):**

| Task | Current | Proposed |
|------|---------|----------|
| `aggregate-org-learning-daily` | 6:00 AM | 5:00 AM |
| `refresh-pm-metrics-daily` | 6:30 AM | 5:30 AM |
| `generate-coaching-suggestions-daily` | 7:00 AM | 6:00 AM |
| `dc-collect-decision-items-daily` | 7:15 AM | 6:30 AM |
| `dc-generate-briefing-daily` | 7:30 AM | 7:00 AM |
| `daily-executive-briefing` | 8:00 AM | 7:30 AM |
| `time-anomaly-detection` | 9:00 AM | 8:00 AM |

This spreads 7 heavy tasks across 3 hours with 30-minute gaps instead of 2 hours with 15-minute gaps. With separate workers, these tasks also run concurrently (summaries worker handles briefings while default worker handles other operations).

#### Step 2.2 — Add Rate Limits to AI Tasks

In each AI task file, add a `rate_limit` parameter to cap Gemini calls per minute per worker. This prevents simultaneous workers from hammering the Gemini API quota.

Example (`kanban/tasks/ai_summary_tasks.py`):
```python
@shared_task(
    bind=True,
    name='kanban.ai_summary.generate_board_summary_task',
    queue='summaries',
    time_limit=90,
    soft_time_limit=75,
    max_retries=2,
    rate_limit='6/m'  # Max 6 Gemini calls per minute per worker
)
def generate_board_summary_task(self, board_id):
    ...
```

Apply `rate_limit='6/m'` to all tasks in:
- `kanban/tasks/ai_summary_tasks.py`
- `decision_center/tasks.py` (`generate_decision_briefing`)
- `knowledge_graph/tasks.py` (`generate_memory_connections`)
- `exit_protocol/tasks.py` (all 5 AI tasks)

---

### Phase 3: Monitoring & Observability (Important)

**Implement before or immediately after go-live.**

#### Step 3.1 — Install and Run Flower

Flower is a real-time web dashboard for Celery. It shows queue depths, active tasks, completed/failed tasks, and worker health.

```bash
pip install flower
```

Add to `requirements.txt`:
```
flower>=2.0.0
```

Run:
```bash
celery -A kanban_board flower \
  --port=5555 \
  --basic_auth=admin:your_secure_password
```

Access at: `http://your-domain:5555`

**What to monitor:**
- Queue depths — if `summaries` queue grows past 20 tasks, investigate
- Task failure rate — any task failing repeatedly needs attention
- Worker heartbeats — if a worker stops sending heartbeats, it has crashed
- Task runtime — if a task that normally takes 30s starts taking 10 minutes, something is wrong

**In production:** Put Flower behind your authentication proxy; do not expose it publicly without authentication.

#### Step 3.2 — Add Task Failure Alerting

Add a failure signal handler to `kanban_board/celery.py` to log persistent failures:

```python
from celery.signals import task_failure
import logging

logger = logging.getLogger('celery.failure')

@task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None, 
                         traceback=None, args=None, kwargs=None, **kw):
    logger.error(
        f"Task failed: {sender.name} | ID: {task_id} | "
        f"Error: {type(exception).__name__}: {exception}"
    )
    # Optional: send to Sentry, Slack webhook, or email alert
```

If you use Sentry for error tracking, the Celery integration captures task failures automatically:
```python
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[CeleryIntegration()],
)
```

---

### Phase 4: Cloud Infrastructure (Essential)

**Required for production deployment.**

#### Step 4.1 — Process Supervisor

Replace Windows `.bat` files with a proper process supervisor on the cloud server.

**Option A — Docker Compose (Recommended)**

Create a `docker-compose.yml` that runs each component as a separate container with restart policies and health checks:

```yaml
version: '3.9'

services:
  web:
    build: .
    command: daphne -b 0.0.0.0 -p 8000 kanban_board.asgi:application
    depends_on:
      - redis
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]
      interval: 30s
      timeout: 10s
      retries: 3

  worker-default:
    build: .
    command: celery -A kanban_board worker --pool=prefork --concurrency=4 -Q celery -n worker-default@%h --loglevel=info
    depends_on:
      - redis
    restart: always

  worker-summaries:
    build: .
    command: celery -A kanban_board worker --pool=gevent --concurrency=10 -Q summaries -n worker-summaries@%h --loglevel=info
    depends_on:
      - redis
    restart: always

  worker-streaming:
    build: .
    command: celery -A kanban_board worker --pool=gevent --concurrency=5 -Q ai_tasks -n worker-streaming@%h --loglevel=info
    depends_on:
      - redis
    restart: always

  worker-interactive:
    build: .
    command: celery -A kanban_board worker --pool=gevent --concurrency=5 -Q interactive -n worker-interactive@%h --loglevel=info
    depends_on:
      - redis
    restart: always

  beat:
    build: .
    command: celery -A kanban_board beat --scheduler django_celery_beat.schedulers:DatabaseScheduler --loglevel=info
    depends_on:
      - redis
    restart: always

  flower:
    build: .
    command: celery -A kanban_board flower --port=5555 --basic_auth=admin:${FLOWER_PASSWORD}
    ports:
      - "5555:5555"
    depends_on:
      - redis
    restart: always

  redis:
    image: redis:7-alpine
    restart: always
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
```

**Option B — Systemd (Linux VM without Docker)**

Create unit files for each service in `/etc/systemd/system/`:

```ini
# /etc/systemd/system/prizmai-worker-default.service
[Unit]
Description=PrizmAI Celery Default Worker
After=network.target redis.service

[Service]
User=www-data
WorkingDirectory=/opt/prizmai
EnvironmentFile=/opt/prizmai/.env
ExecStart=/opt/prizmai/venv/bin/celery -A kanban_board worker \
  --pool=prefork --concurrency=4 -Q celery \
  -n worker-default@%%h --loglevel=info \
  --logfile=/var/log/prizmai/worker-default.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Create one unit file per worker (`worker-summaries`, `worker-streaming`, `worker-interactive`, `beat`, `flower`), then enable all:

```bash
systemctl enable prizmai-worker-default
systemctl start prizmai-worker-default
# repeat for each service
```

#### Step 4.2 — Managed Redis

Replace `redis://127.0.0.1:6379/0` with a managed Redis service.

In `kanban_board/settings.py`, use environment variables:

```python
import os

REDIS_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379')

# Separate Redis databases for each concern
CELERY_BROKER_URL = f'{REDIS_URL}/0'
CELERY_RESULT_BACKEND = f'{REDIS_URL}/1'

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'{REDIS_URL}/2',
    }
}

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [f'{REDIS_URL}/3'],
        },
    },
}
```

**Cloud Redis options:**
| Provider | Service | Notes |
|----------|---------|-------|
| AWS | ElastiCache for Redis | 99.9% SLA, Multi-AZ replication |
| GCP | Memorystore for Redis | Fully managed, Redis 7 compatible |
| Azure | Azure Cache for Redis | Integrated with other Azure services |
| DigitalOcean | Managed Redis | Cheapest option, good for smaller deployments |
| Upstash | Redis Serverless | Pay-per-use, good for low-traffic MVPs |

#### Step 4.3 — Environment-Based Configuration

Move all infrastructure settings to a `.env` file (never commit this to version control):

```bash
# .env (production values — kept in secrets manager, not in git)
DJANGO_SECRET_KEY=your-long-random-secret-key
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
DATABASE_URL=postgresql://user:pass@host:5432/prizmai_prod
REDIS_URL=redis://:password@your-redis-host:6379
GEMINI_API_KEY=your-gemini-api-key
GOOGLE_CLIENT_ID=your-oauth-client-id
GOOGLE_CLIENT_SECRET=your-oauth-client-secret
FLOWER_PASSWORD=your-flower-dashboard-password

# Celery tuning (can change without code deploy)
CELERY_WORKER_CONCURRENCY_DEFAULT=4
CELERY_WORKER_CONCURRENCY_SUMMARIES=10
CELERY_WORKER_CONCURRENCY_STREAMING=5
CELERY_WORKER_CONCURRENCY_INTERACTIVE=5
```

---

### Phase 5: Resilience (Nice-to-Have)

**Implement after stable production is running.**

#### Step 5.1 — Circuit Breaker for Gemini API

Add a circuit breaker to the `GeminiClient` so that if multiple consecutive calls fail (API down or quota exhausted), AI tasks gracefully skip processing instead of retrying repeatedly and building up queue depth.

Pattern (using Redis as the failure counter):
```python
# ai_assistant/utils/gemini_client.py (or wherever GeminiClient is)

CIRCUIT_BREAKER_KEY = 'gemini_circuit_breaker'
CIRCUIT_BREAKER_THRESHOLD = 3   # consecutive failures to open circuit
CIRCUIT_BREAKER_TIMEOUT = 900   # 15 minutes before retrying

def is_circuit_open():
    from django.core.cache import cache
    return cache.get(CIRCUIT_BREAKER_KEY) == 'open'

def record_failure():
    from django.core.cache import cache
    failures = cache.get('gemini_failure_count', 0) + 1
    cache.set('gemini_failure_count', failures, timeout=CIRCUIT_BREAKER_TIMEOUT)
    if failures >= CIRCUIT_BREAKER_THRESHOLD:
        cache.set(CIRCUIT_BREAKER_KEY, 'open', timeout=CIRCUIT_BREAKER_TIMEOUT)

def record_success():
    from django.core.cache import cache
    cache.delete('gemini_failure_count')
    cache.delete(CIRCUIT_BREAKER_KEY)
```

In AI tasks, check before calling:
```python
from ai_assistant.utils.gemini_client import is_circuit_open

@shared_task(...)
def generate_board_summary_task(self, board_id):
    if is_circuit_open():
        logger.warning(f"Skipping board summary {board_id} — Gemini circuit open")
        return {'skipped': True, 'reason': 'circuit_breaker'}
    # ... proceed with Gemini call
```

#### Step 5.2 — Standardise Per-Task Timeouts

Replace the global 30-minute `CELERY_TASK_TIME_LIMIT` with consistent per-task values that reflect actual expected runtimes:

| Task Category | `time_limit` | `soft_time_limit` |
|--------------|-------------|------------------|
| Light (cleanup, email, notifications) | 60s | 50s |
| Medium (board summary, coaching, conflict) | 120s | 100s |
| Heavy (executive briefing, pre-mortem, risk) | 300s | 270s |
| Very heavy (onboarding generation, scope autopsy) | 600s | 540s |

The `soft_time_limit` triggers a `SoftTimeLimitExceeded` exception, allowing the task to save partial results before the hard `time_limit` kills the process.

---

## 6. Complete Task Inventory

### Tasks by Queue

#### `celery` (Default Queue)

| Task | Schedule | Purpose |
|------|----------|---------|
| `kanban.detect_conflicts` | Hourly :00 | Scan all boards for resource/dependency conflicts |
| `kanban.generate_resolution_suggestions` | On conflict found | AI resolution suggestions (Gemini) |
| `kanban.notify_conflict_users` | On conflict found | Notify affected users |
| `kanban.cleanup_resolved_conflicts` | Daily 2:00 AM | Archive old conflicts |
| `kanban.run_commitment_decay_all` | Every 4 hours | Bayesian confidence decay (chunks of 50) |
| `kanban.reset_weekly_tokens` | Monday midnight | Refill credibility tokens |
| `kanban.auto_detect_signals_for_board` | On task save | Detect commitment signal events |
| `kanban.generate_ai_reasoning_task` | After decay | Gemini explanation of confidence trend |
| `kanban.run_due_date_approaching_automations` | Hourly :30 | Trigger due-date automation rules |
| `kanban.refresh_pm_metrics` | Daily 6:30 AM | Refresh PM performance profiles |
| `kanban.generate_coaching_suggestions` | Daily 7:00 AM | AI coaching suggestions |
| `kanban.train_priority_models_periodic` | Sunday 2:00 AM | Retrain ML priority models |
| `kanban.analyze_feedback_text` | Wednesday 3:00 AM | NLP feedback analysis |
| `kanban.aggregate_org_learning` | Daily 6:00 AM | Aggregate org-level learning |
| `kanban.run_ab_experiments` | Sunday 4:00 AM | A/B coaching experiments |
| `kanban.send_time_tracking_reminders` | Weekdays 5:00 PM | Time entry reminder |
| `kanban.detect_time_anomalies` | Daily 9:00 AM | Unusual time pattern detection |
| `kanban.weekly_time_summary` | Monday 8:00 AM | Weekly time summary email |
| `kanban.refresh_demo_dates` | Daily 3:00 AM | Keep demo data current |
| `decision_center.collect_decision_items` | Daily 7:15 AM | Collect decision queue items |
| `decision_center.send_daily_digest_emails` | Every 30 min | Email decision briefings |
| `exit_protocol.tasks.monitor_all_boards_health` | Daily 2:15 AM | Dispatch board health scoring |
| `exit_protocol.tasks.compute_board_health_score` | After dispatch | Score individual board health |
| `exit_protocol.tasks.trigger_hospice_notification` | On risk detection | Send health warning |
| `knowledge_graph.check_missed_deadlines` | Daily 1:00 AM | Capture deadline events |
| `knowledge_graph.check_budget_thresholds` | Daily 1:30 AM | Capture budget events |
| `analytics.cleanup_old_sessions` | (periodic) | Archive old sessions |
| `analytics.generate_daily_analytics_report` | (periodic) | Daily analytics summary |

#### `summaries` Queue

| Task | Trigger | Purpose |
|------|---------|---------|
| `kanban.ai_summary.classify_board_on_creation` | Board created | Classify board project type |
| `kanban.ai_summary.generate_board_summary_task` | Signal (debounced 600s) | Level 1: Board-level AI summary |
| `kanban.ai_summary.generate_strategy_summary_task` | API call / creation | Level 2: Strategy summary |
| `kanban.ai_summary.generate_mission_summary_task` | API call / creation | Level 3: Mission summary |
| `kanban.ai_summary.generate_goal_summary_task` | API call / creation | Goal summary |
| `kanban.ai_summary.generate_daily_executive_briefing` | Daily 8:00 AM | **Heaviest**: Full org briefing (Gemini) |
| `kanban.ai_summary.generate_proxy_metrics_on_goal_creation` | Goal created | Generate measurable goal proxies |
| `kanban.generate_workspace_from_goal_task` | Onboarding | AI workspace generation (onboarding) |
| `decision_center.generate_decision_briefing` | Daily 7:30 AM | AI briefing from decision items |
| `knowledge_graph.generate_memory_connections` | Sunday 5:00 AM | Discover AI connections between memories |

#### `ai_tasks` Queue

| Task | Trigger | Purpose |
|------|---------|---------|
| `kanban.ai_streaming.run_premortem` | User action | Pre-mortem failure analysis (streaming) |
| `kanban.ai_streaming.run_vulnerability_assessment` | User action | Vulnerability discovery (streaming) |
| `kanban.ai_streaming.run_hindcast_analysis` | User action | Historical pattern extraction (streaming) |
| `kanban.ai_streaming.run_future_case_analysis` | User action | Scenario forecasting (streaming) |
| `kanban.ai_streaming.run_comprehensive_risk_assessment` | User action | Full multi-dimensional risk (streaming) |
| `kanban.generate_scope_autopsy` | User action | Scope creep forensic analysis (Gemini) |
| `kanban.provision_sandbox_task` | User action | Sandbox workspace deep-copy (streaming) |
| `exit_protocol.tasks.generate_hospice_assessment` | User/auto | AI board decline analysis |
| `exit_protocol.tasks.generate_knowledge_checklist` | Board hospice | AI pre-archival checklist |
| `exit_protocol.tasks.generate_team_transition_memos` | Board hospice | AI team transition memos |
| `exit_protocol.tasks.scan_and_extract_organs` | Board hospice | Extract reusable patterns |
| `exit_protocol.tasks.perform_burial` | Board hospice | Final archival |
| `webhooks.tasks.deliver_webhook` | Event triggered | HMAC-signed webhook delivery (max_retries=3) |

#### `interactive` Queue (New — to be added)

| Task | Trigger | Purpose |
|------|---------|---------|
| `kanban.tasks.classify_board_on_creation` | Board created | Fast classification response |
| `kanban.detect_board_conflicts` | Data change | Per-board on-demand conflict scan |
| `kanban.provision_sandbox_task` | User action | Sandbox setup with live progress |
| `kanban.generate_workspace_from_goal_task` | Onboarding | User-facing workspace generation |

---

## 7. File Reference Map

| File | What to Change | Phase |
|------|---------------|-------|
| `kanban_board/settings.py` | `CELERY_TASK_ROUTES` (add `interactive` queue), `REDIS_URL` env var, separate Redis DBs | 1, 4 |
| `kanban_board/celery.py` | Beat schedule timing (stagger morning tasks), `task_failure` signal handler | 2, 3 |
| `start_prizmAI.bat` | Add 4 separate worker commands (for local Windows dev only) | 1 |
| `start_prizmAI_dev.bat` | Same as above for dev | 1 |
| `docker-compose.yml` | **New file** — defines all services with restart policies | 4 |
| `Dockerfile` | **New file** — Django app container | 4 |
| `.env.example` | **New file** — document all required env vars | 4 |
| `requirements.txt` | Add `gevent>=23.9.0`, `flower>=2.0.0`, optionally `sentry-sdk` | 1, 3 |
| `kanban/tasks/ai_summary_tasks.py` | Add `rate_limit='6/m'`, tighten per-task timeouts | 2, 5 |
| `kanban/tasks/ai_streaming_tasks.py` | Add `rate_limit='6/m'`, tighten per-task timeouts | 2, 5 |
| `decision_center/tasks.py` | Add `rate_limit='6/m'` to briefing task | 2 |
| `knowledge_graph/tasks.py` | Add `rate_limit='6/m'` to connection task | 2 |
| `exit_protocol/tasks.py` | Add `rate_limit='6/m'` to 5 AI tasks | 2 |
| `ai_assistant/views.py` | **No change needed** — sync chat is correct | — |

---

## 8. Verification Checklist

Use this checklist when validating the production deployment:

### Phase 1 Verification
- [ ] Run `celery inspect active_queues` — should show 4 separate workers, each consuming only their assigned queue
- [ ] Trigger a board summary and a Spectra chat simultaneously — chat should respond in <5 seconds
- [ ] Check that pre-mortem WebSocket streaming still works end-to-end
- [ ] Verify conflict detection still fires hourly

### Phase 2 Verification
- [ ] Check `celery inspect scheduled` at 6:00 AM — tasks should be staggered, not all firing at once
- [ ] Monitor Spectra response time during the 6:00–8:00 AM window — should stay <5 seconds
- [ ] Confirm executive briefing still generates by ~8:00 AM with the new schedule

### Phase 3 Verification
- [ ] Access Flower at `http://your-domain:5555` — all 4 workers visible with green heartbeat
- [ ] Trigger a deliberate task failure — confirm it appears in Flower's failure list
- [ ] Confirm failure log entries appear in the application log

### Phase 4 Verification
- [ ] Kill a worker process manually — confirm it restarts automatically within 10 seconds
- [ ] Restart Redis — confirm all workers reconnect automatically
- [ ] Confirm all environment variables are loaded (no hardcoded `127.0.0.1` in configs)
- [ ] Run Django check: `python manage.py check --deploy`

### Phase 5 Verification
- [ ] Disable Gemini API key temporarily — confirm tasks skip gracefully and log "circuit open"
- [ ] Confirm no task runs longer than its declared `time_limit` value

### Load Test (Final Sign-Off)
- [ ] Run 10 concurrent Spectra chat sessions while the morning task burst is occurring
- [ ] All chats respond in <5 seconds
- [ ] No WebSocket timeouts
- [ ] All scheduled tasks complete by their expected deadline
- [ ] Queue depths return to 0 within 10 minutes of the morning burst

---

## Summary Decision Table

| Decision | What to Do | Reason |
|----------|-----------|--------|
| Spectra sync chat | **Keep as-is** | Correct design; fast interactive calls don't need a queue |
| `pool=solo` locally | **Keep for local dev** | Windows limitation; acceptable for single-developer use |
| `pool=solo` in production | **Replace with gevent/prefork** | Single sequential process cannot support concurrent tasks |
| One worker for all queues | **Split into 4 workers** | Prevents scheduled tasks from starving user-triggered operations |
| 80+ task definitions | **Keep as-is** | Task logic is correct; issue is infrastructure, not task design |
| Redis single instance | **Replace with managed Redis** | Single point of failure; prod needs replication |
| `.bat` startup scripts | **Replace with Docker/systemd** | No auto-restart, no health monitoring |
| Task monitoring | **Add Flower** | Blind operation is not acceptable in production |

---

*This document was generated from a full audit of the PrizmAI codebase conducted on April 12, 2026.*  
*Last updated: April 12, 2026*
