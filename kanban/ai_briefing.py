"""
AI-powered daily briefing action plan generator.

Uses Gemini to produce genuinely intelligent `why` explanations and
`next_action` recommendations for each high-risk / overdue task shown in
the "AI Recommended Actions" modal on the dashboard.

Falls back to the rule-based logic if AI is unavailable or returns an
unparseable response.
"""

import json
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rule-based fallback (original deterministic logic preserved here)
# ---------------------------------------------------------------------------

def _rule_based_action_plan(tasks, action_type, overdue_count, now):
    """
    Build action plan entries using deterministic rules.  Used when Gemini
    is unavailable or returns an invalid response.
    """
    plan = []
    for _t in tasks[:3]:
        _is_critical = _t.risk_level == 'critical'
        _is_overdue  = bool(_t.due_date and _t.due_date < now)
        _progress    = _t.progress or 0
        _unassigned  = _t.assigned_to is None
        _assignee    = (
            (_t.assigned_to.get_full_name() or _t.assigned_to.username)
            if _t.assigned_to else None
        )
        _days = int((_t.due_date - now).days) if _t.due_date else None

        # WHY
        if _is_critical and _progress == 0 and _unassigned:
            _why = "Critical risk with no owner and zero progress — a hard blocker with no one driving it forward."
        elif _is_critical and _progress == 0:
            _why = "Critical risk and not yet started — needs immediate kick-off to avoid cascading delays."
        elif _is_critical and _is_overdue:
            _days_late = abs(_days) if _days is not None else '?'
            _why = f"Critical risk and already {_days_late} day{'s' if _days_late != 1 else ''} overdue — every day of further delay compounds delivery impact."
        elif _is_critical and _days is not None and _days <= 7:
            _why = f"Critical risk with only {_days} day{'s' if _days != 1 else ''} remaining and {_progress}% complete — needs urgent escalation."
        elif _is_critical:
            _why = f"Flagged critical risk at {_progress}% progress — requires close monitoring and active mitigation."
        elif _progress == 0 and _unassigned:
            _why = "High-risk and unassigned with no progress — without an owner this will continue to slip."
        elif _is_overdue:
            _days_late = abs(_days) if _days is not None else '?'
            _why = f"High-risk and {_days_late} day{'s' if _days_late != 1 else ''} overdue — remaining work needs to be replanned immediately."
        elif _days is not None and _days <= 7 and _progress < 50:
            _why = f"High-risk, due in {_days} day{'s' if _days != 1 else ''}, and only {_progress}% done — not enough time at the current pace."
        else:
            _why = f"High-risk at {_progress}% progress — needs active oversight to prevent escalation."

        # NEXT ACTION
        if _unassigned:
            _next = "Assign to an available team member immediately."
        elif _progress == 0 and _is_critical:
            _next = f"Schedule an unblock session with {_assignee} — this must start today."
        elif _is_overdue and _progress == 0:
            _next = f"Escalate to {_assignee} or reassign — overdue and not yet started."
        elif _is_overdue:
            _next = f"Replan the due date with {_assignee} and confirm they are unblocked."
        elif _days is not None and _days <= 3 and _progress < 70:
            _next = f"Review blockers with {_assignee} today — insufficient time at current pace."
        elif _days is not None and _days <= 7 and _progress < 30:
            _next = f"Fast-track or scope-reduce with {_assignee} and flag risk to stakeholders."
        elif _progress == 0:
            _next = f"Confirm {_assignee} has started this task and identify any blockers."
        else:
            _next = f"Check in with {_assignee} on blockers and update progress status."

        plan.append({'task': _t, 'why': _why, 'next_action': _next})

    return plan


def _rule_based_summary(plan, action_type, overdue_count, briefing_action):
    """Deterministic intro summary used as fallback."""
    _critical_zeros = [
        x for x in plan
        if x['task'].risk_level == 'critical' and x['task'].progress == 0
    ]
    if _critical_zeros:
        _cnames = ' and '.join(f'"{x["task"].title}"' for x in _critical_zeros[:2])
        _pl = 's' if len(_critical_zeros) > 1 else ''
        return (
            f"Your critical blocker{_pl} — {_cnames} — {'are' if _pl else 'is'} at 0% progress "
            "and blocking team momentum. Here\u2019s your recommended sequence:"
        )
    elif any(x['task'].risk_level == 'critical' for x in plan):
        return (
            "Critical-risk items are your highest delivery threat. "
            "Address them in this order to protect your timeline:"
        )
    elif action_type == 'overdue':
        return (
            f"{overdue_count} task{'s are' if overdue_count != 1 else ' is'} past the due date. "
            "Here\u2019s the recommended sequence to get back on track:"
        )
    elif plan:
        return (
            "These high-risk items need your attention before they escalate. "
            "Here\u2019s the recommended order of action:"
        )
    return briefing_action


# ---------------------------------------------------------------------------
# Gemini-powered generation
# ---------------------------------------------------------------------------

def _build_ai_prompt(tasks, action_type, overdue_count, total_high_risk, now):
    """
    Build a structured prompt asking Gemini to produce per-task explanations
    and an overall intro summary, all grounded in the real task data.
    """
    today_str = now.strftime('%B %d, %Y')

    task_lines = []
    for i, t in enumerate(tasks, 1):
        due_str = t.due_date.strftime('%b %d, %Y') if t.due_date else 'No due date'
        days_val = int((t.due_date - now).days) if t.due_date else None
        if days_val is None:
            timing = 'no due date set'
        elif days_val < 0:
            timing = f"{abs(days_val)} day{'s' if abs(days_val) != 1 else ''} overdue"
        elif days_val == 0:
            timing = 'due today'
        else:
            timing = f"due in {days_val} day{'s' if days_val != 1 else ''}"

        assignee = (
            (t.assigned_to.get_full_name() or t.assigned_to.username)
            if t.assigned_to else 'Unassigned'
        )
        board_name = t.column.board.name if t.column and t.column.board else 'Unknown board'

        task_lines.append(
            f"Task {i}:\n"
            f"  Title: {t.title}\n"
            f"  Board: {board_name}\n"
            f"  Risk level: {t.risk_level}\n"
            f"  Priority: {t.priority}\n"
            f"  Progress: {t.progress or 0}%\n"
            f"  Due date: {due_str} ({timing})\n"
            f"  Assigned to: {assignee}"
        )

    context_line = []
    if overdue_count:
        context_line.append(f"{overdue_count} overdue task{'s' if overdue_count != 1 else ''}")
    if total_high_risk:
        context_line.append(f"{total_high_risk} high-risk item{'s' if total_high_risk != 1 else ''}")
    context_summary = ' and '.join(context_line) if context_line else 'several at-risk items'

    tasks_block = '\n\n'.join(task_lines)

    prompt = f"""You are Spectra, an intelligent AI project management assistant inside PrizmAI.
Today is {today_str}. The project currently has {context_summary}.

A project manager is viewing a priority action panel. For the tasks below, provide:
1. A `why` explanation (1-2 sentences) — explain the specific risk this task poses to delivery, 
   grounded in its actual data (progress, timing, assignment status). Be direct and concrete.
2. A `next_action` (1 sentence) — a precise, actionable step the PM should take TODAY for this task.
3. An `action_summary` (2-3 sentences) — an intelligent intro paragraph for the full panel,
   synthesising the cross-task risk pattern and why acting now matters. Do NOT just repeat the task titles.

Tasks:
{tasks_block}

Respond ONLY with valid JSON in this exact schema (no markdown, no extra text):
{{
  "action_summary": "<intro paragraph>",
  "tasks": [
    {{"why": "<why for task 1>", "next_action": "<next action for task 1>"}},
    {{"why": "<why for task 2>", "next_action": "<next action for task 2>"}},
    {{"why": "<why for task 3>", "next_action": "<next action for task 3>"}}
  ]
}}

Rules:
- tasks array must have exactly {len(tasks)} item(s), in the same order as the tasks above.
- If a task is unassigned, the next_action must include assigning it as the first step.
- Be specific: reference actual progress percentages, timing, and assignee names.
- Never use generic advice like "monitor closely" alone — pair it with a concrete action.
- Keep each field under 200 characters.
"""
    return prompt


def _call_gemini(tasks, action_type, overdue_count, total_high_risk, now):
    """
    Call Gemini and return (action_summary, per_task_list) or raise on failure.
    per_task_list is a list of dicts with keys 'why' and 'next_action'.
    """
    try:
        from ai_assistant.utils.ai_clients import GeminiClient
    except ImportError:
        raise RuntimeError("GeminiClient not available")

    client = GeminiClient(default_model='gemini-2.5-flash-lite')
    if client.models is None:
        raise RuntimeError("Gemini API not initialised (missing API key?)")

    prompt = _build_ai_prompt(tasks, action_type, overdue_count, total_high_risk, now)

    result = client.get_response(
        prompt=prompt,
        task_complexity='simple',
        temperature=0.35,          # Analytical, focused
        use_cache=True,
        cache_operation='analysis',
        context_id=f"briefing_{action_type}_{','.join(str(t.id) for t in tasks)}",
    )

    raw = result.get('content', '')
    if not raw:
        raise ValueError("Empty response from Gemini")

    # Strip optional markdown fences
    cleaned = raw.strip()
    if cleaned.startswith('```'):
        cleaned = '\n'.join(cleaned.split('\n')[1:])
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3].rstrip()

    data = json.loads(cleaned)

    ai_summary = data.get('action_summary', '').strip()
    ai_tasks   = data.get('tasks', [])

    if len(ai_tasks) < len(tasks):
        raise ValueError(
            f"Gemini returned {len(ai_tasks)} task entries but expected {len(tasks)}"
        )

    # Validate required keys in all entries
    for entry in ai_tasks[:len(tasks)]:
        if 'why' not in entry or 'next_action' not in entry:
            raise ValueError("Gemini task entry missing 'why' or 'next_action'")

    return ai_summary, ai_tasks[:len(tasks)]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_action_plan(tasks, action_type, overdue_count, total_high_risk, briefing_action, now=None):
    """
    Build the daily briefing action plan.

    Attempts to use Gemini for genuinely intelligent per-task explanations and
    an overall intro summary.  Falls back to the rule-based logic silently if
    AI is unavailable or returns an invalid response, so the dashboard is never
    broken by an AI failure.

    Returns:
        (action_plan, action_summary, ai_powered)
        action_plan    – list of dicts: {task, why, next_action}
        action_summary – intro text for the modal header card
        ai_powered     – True if content was generated by Gemini
    """
    if now is None:
        now = timezone.now()

    if not tasks:
        plan    = []
        summary = briefing_action
        return plan, summary, False

    # --- Try AI ---
    try:
        ai_summary, ai_entries = _call_gemini(
            tasks[:3], action_type, overdue_count, total_high_risk, now
        )
        plan = [
            {
                'task':        t,
                'why':         ai_entries[i]['why'],
                'next_action': ai_entries[i]['next_action'],
            }
            for i, t in enumerate(tasks[:3])
        ]
        summary = ai_summary or _rule_based_summary(plan, action_type, overdue_count, briefing_action)
        logger.info("Daily briefing action plan generated by Spectra AI (Gemini).")
        return plan, summary, True

    except Exception as exc:
        logger.warning(f"Spectra AI briefing generation failed, using rule-based fallback: {exc}")

    # --- Fallback ---
    plan    = _rule_based_action_plan(tasks[:3], action_type, overdue_count, now)
    summary = _rule_based_summary(plan, action_type, overdue_count, briefing_action)
    return plan, summary, False
