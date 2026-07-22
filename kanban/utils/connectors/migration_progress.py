"""
Migration progress store.

A tiny cache-backed progress channel so the browser can poll a running
migration (mirrors the board-analytics real-progress pattern). Keyed by the
Celery task id.

Uses the ``ai_cache`` alias (Redis) — NOT the default cache — because it must be
visible across processes (Daphne web + Celery worker). See CACHES in settings:
the default cache has IGNORE_EXCEPTIONS on, so a failed write would be swallowed
silently; ai_cache is the documented cross-process channel.
"""

from django.core.cache import caches

_TTL = 60 * 30  # 30 minutes
_PREFIX = "migration_progress:"


def _cache():
    try:
        return caches["ai_cache"]
    except Exception:
        return caches["default"]


def _key(task_id: str) -> str:
    return f"{_PREFIX}{task_id}"


def set_progress(task_id: str, percent: int, message: str, state: str = "running", extra: dict = None):
    payload = {"percent": int(percent), "message": message, "state": state}
    if extra:
        payload.update(extra)
    _cache().set(_key(task_id), payload, _TTL)


def get_progress(task_id: str) -> dict:
    return _cache().get(_key(task_id)) or {"percent": 0, "message": "Starting…", "state": "pending"}
