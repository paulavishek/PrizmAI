"""
Migration audit — the "Wow Moment".

Immediately after a project is migrated in, this runs a first-look audit so the
user sees value on day one instead of a static board dump. It:
  1. Collects deterministic signals across the migrated boards (no AI needed) —
     task counts, tasks missing due dates, workload imbalance, high-priority
     backlog, done ratio.
  2. Asks the AI (via AIRouter.complete — never a raw SDK) for a short narrative
     summary + top risks based on those signals.
  3. Stores the result on ``Strategy.ai_summary`` / ``ai_summary_generated_at``
     (existing fields intended for exactly this bubble-up).

Returns a dict: ``{"summary": str, "signals": {...}}``. The AI narrative is
best-effort: if the provider fails, the deterministic signals are still saved.
"""

import logging
from typing import Any, Dict, List

from django.utils import timezone

from kanban.column_semantics import column_type_q

logger = logging.getLogger(__name__)

# An assignee is "overloaded" at or above this many open (not-done) tasks.
_OVERLOAD_THRESHOLD = 8


def collect_signals(strategy) -> Dict[str, Any]:
    """Gather deterministic health signals across all boards under a Strategy."""
    from kanban.models import Task

    boards = list(strategy.boards.all())
    board_ids = [b.id for b in boards]

    tasks = Task.objects.filter(column__board_id__in=board_ids)
    total = tasks.count()

    done = tasks.filter(column_type_q('done', 'column')).count()
    open_tasks = tasks.exclude(column_type_q('done', 'column'))
    missing_due = open_tasks.filter(due_date__isnull=True).count()
    high_priority_open = open_tasks.filter(priority__in=['high', 'urgent']).count()

    # Workload per assignee (open tasks only).
    workload: Dict[str, int] = {}
    for t in open_tasks.select_related('assigned_to'):
        who = t.assigned_to.get_username() if t.assigned_to else 'Unassigned'
        workload[who] = workload.get(who, 0) + 1
    overloaded = sorted(
        [(name, n) for name, n in workload.items()
         if name != 'Unassigned' and n >= _OVERLOAD_THRESHOLD],
        key=lambda x: -x[1],
    )
    unassigned_open = workload.get('Unassigned', 0)

    return {
        'board_count': len(boards),
        'board_names': [b.name for b in boards],
        'total_tasks': total,
        'done_tasks': done,
        'open_tasks': total - done,
        'done_ratio': round(done / total, 2) if total else 0.0,
        'missing_due_dates': missing_due,
        'high_priority_open': high_priority_open,
        'unassigned_open': unassigned_open,
        'overloaded': overloaded,  # [(username, count), ...]
    }


def _build_prompt(strategy, signals: Dict[str, Any]) -> str:
    overloaded = ", ".join(f"{n} ({c} open tasks)" for n, c in signals['overloaded']) or "none"
    return (
        f"A project called '{strategy.name}' was just migrated into PrizmAI from an "
        f"external tool. Here is a first-look snapshot:\n"
        f"- Boards: {signals['board_count']} ({', '.join(signals['board_names'][:10])})\n"
        f"- Tasks: {signals['total_tasks']} total, {signals['open_tasks']} open, "
        f"{signals['done_tasks']} done ({int(signals['done_ratio'] * 100)}% complete)\n"
        f"- Open tasks with no due date: {signals['missing_due_dates']}\n"
        f"- High/urgent open tasks: {signals['high_priority_open']}\n"
        f"- Unassigned open tasks: {signals['unassigned_open']}\n"
        f"- Overloaded people: {overloaded}\n\n"
        f"Write a concise day-one audit (max ~120 words) for the project manager: "
        f"a one-line health read, then the top 3 concrete risks or gaps to address "
        f"first. Be specific and reference the numbers. Plain text, no preamble."
    )


def generate_migration_audit(strategy, user=None) -> Dict[str, Any]:
    """
    Run the audit and persist the narrative onto the Strategy. Best-effort AI.
    """
    signals = collect_signals(strategy)

    summary = ""
    try:
        from ai_assistant.utils.ai_router import AIRouter, AIProviderError
        try:
            resp = AIRouter().complete(
                prompt=_build_prompt(strategy, signals),
                user=user,
                complexity='simple',
                feature='migration_audit',
            )
            summary = (resp.get('text') or '').strip()
        except AIProviderError as exc:
            logger.warning("Migration audit AI call failed: %s", exc)
    except Exception:
        logger.exception("Migration audit could not run the AI narrative")

    if not summary:
        # Deterministic fallback so the user still sees something useful.
        summary = (
            f"Migrated {signals['total_tasks']} tasks across {signals['board_count']} "
            f"board(s). {signals['open_tasks']} open, {signals['missing_due_dates']} "
            f"without a due date, {signals['high_priority_open']} high-priority open."
        )

    try:
        strategy.ai_summary = summary
        strategy.ai_summary_generated_at = timezone.now()
        strategy.save(update_fields=['ai_summary', 'ai_summary_generated_at'])
    except Exception:
        logger.exception("Could not persist migration audit onto strategy %s", strategy.pk)

    return {"summary": summary, "signals": signals}
