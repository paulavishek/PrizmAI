"""
PrizmBrief — AI Presentation Content Generator

Generates structured slide-by-slide presentation content from live board data,
tailored to the selected audience and detail level.
No external paid API — uses the existing Gemini integration.
"""

import logging
import re
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from kanban.models import Board, Column, Task

logger = logging.getLogger(__name__)

# ── Audience options ──────────────────────────────────────────────────────────
AUDIENCE_CHOICES = [
    ("client",      "👔 Client / External Stakeholder"),
    ("executive",   "🏢 Senior Management / Executive"),
    ("team",        "👥 Internal Team"),
    ("technical",   "🧑‍💻 Technical Team / Developers"),
]

# ── Purpose options ───────────────────────────────────────────────────────────
PURPOSE_CHOICES = [
    ("status",      "📊 Project Status Update"),
    ("sprint",      "🏁 Sprint Review"),
    ("risk",        "⚠️ Risk & Issues Briefing"),
    ("kickoff",     "🚀 Project Kickoff Summary"),
    ("completion",  "✅ Project Completion / Handoff"),
]

# ── Mode options ──────────────────────────────────────────────────────────────
MODE_CHOICES = [
    ("executive_summary", "Executive Summary",
     "5–6 slides, key numbers only, no deep detail. Good for busy stakeholders."),
    ("full_briefing",     "Full Briefing",
     "8–10 slides, complete data, context, and recommended actions. Good for team reviews."),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _label(choices, value):
    """Return the display label for a choice value."""
    return next((label for key, label in choices if key == value), value)


def _gather_board_data(board):
    """
    Pull all metrics needed for brief generation from live DB data.
    Returns a dict of metrics and a list of data-richness warnings.
    """
    today = timezone.now()
    all_tasks = Task.objects.filter(column__board=board, item_type='task')

    total_tasks      = all_tasks.count()
    completed_tasks  = all_tasks.filter(progress=100)
    completed        = completed_tasks.count()
    in_progress      = all_tasks.filter(progress__gt=0, progress__lt=100).count()
    not_started      = all_tasks.filter(progress=0).count()
    completion_pct   = round((completed / total_tasks * 100), 1) if total_tasks else 0

    # Overdue = has a due date in the past and not completed
    overdue = all_tasks.filter(
        due_date__lt=today, progress__lt=100
    ).count()

    # Blocked = in a column whose name contains "block" (case-insensitive)
    blocked_col_ids = Column.objects.filter(
        board=board, name__icontains='block'
    ).values_list('id', flat=True)
    blocked_tasks = all_tasks.filter(column_id__in=blocked_col_ids)
    blocked_count = blocked_tasks.count()
    blocked_list  = list(
        blocked_tasks.select_related('assigned_to')[:5]
        .values('title', 'assigned_to__username')
    )

    # Velocity: tasks completed in last 7 days
    week_ago  = today - timedelta(days=7)
    two_weeks = today - timedelta(days=14)
    velocity_now  = all_tasks.filter(completed_at__gte=week_ago, progress=100).count()
    velocity_prev = all_tasks.filter(
        completed_at__gte=two_weeks, completed_at__lt=week_ago, progress=100
    ).count()
    velocity_change_pct = 0
    if velocity_prev > 0:
        velocity_change_pct = round(((velocity_now - velocity_prev) / velocity_prev) * 100, 1)

    # Risk
    high_risk_count = all_tasks.filter(risk_level__in=['high', 'critical']).count()

    # Column breakdown
    columns = Column.objects.filter(board=board).order_by('position')
    tasks_by_column = [
        {'name': col.name, 'count': all_tasks.filter(column=col).count()}
        for col in columns
    ]

    # Team workload
    from django.db.models import Count
    workload_qs = (
        all_tasks.filter(assigned_to__isnull=False, progress__lt=100)
        .values('assigned_to__username')
        .annotate(open_tasks=Count('id'))
        .order_by('-open_tasks')
    )
    total_open = all_tasks.filter(progress__lt=100).count()
    workload = []
    for row in workload_qs[:8]:
        capacity_pct = round((row['open_tasks'] / total_tasks * 100), 1) if total_tasks else 0
        workload.append({
            'name':       row['assigned_to__username'],
            'open_tasks': row['open_tasks'],
            'capacity':   capacity_pct,
        })

    # Budget
    budget_info = {}
    try:
        from kanban.budget_models import ProjectBudget
        budget = ProjectBudget.objects.filter(board=board).first()
        if budget:
            spent      = getattr(budget, 'actual_cost', None) or 0
            allocated  = float(budget.allocated_budget)
            spent_f    = float(spent)
            remaining  = allocated - spent_f
            pct_spent  = round((spent_f / allocated * 100), 1) if allocated else 0
            budget_info = {
                'allocated':  allocated,
                'spent':      spent_f,
                'remaining':  remaining,
                'pct_spent':  pct_spent,
                'currency':   budget.currency,
            }
    except Exception:
        pass

    # Milestones (Gantt items) — next upcoming ones
    milestones = Task.objects.filter(
        column__board=board, item_type='milestone', due_date__gte=today
    ).order_by('due_date')[:4]
    milestone_list = [
        {
            'title':    m.title,
            'due_date': m.due_date.strftime('%B %d, %Y') if m.due_date else 'TBD',
        }
        for m in milestones
    ]

    # Scope: tasks added after baseline (tasks created in the last sprint – rough proxy)
    sprint_start   = today - timedelta(days=14)
    new_tasks_count = all_tasks.filter(created_at__gte=sprint_start).count()

    # ── Data-richness warnings ────────────────────────────────────────────────
    warnings = []
    if total_tasks < 5:
        warnings.append("Your board has very few tasks. The brief may be limited.")
    due_date_count = all_tasks.filter(due_date__isnull=False).count()
    if due_date_count == 0:
        warnings.append("No tasks have due dates set. Timeline slides will be generic.")
    if not budget_info:
        warnings.append("No budget data found. Budget slides will be omitted.")
    if not milestone_list:
        warnings.append("No upcoming milestones found. The roadmap slide will be limited.")

    return {
        'board_name':       board.name,
        'report_date':      today.strftime('%B %d, %Y'),
        'report_time':      today.strftime('%H:%M'),
        'total_tasks':      total_tasks,
        'completed':        completed,
        'in_progress':      in_progress,
        'not_started':      not_started,
        'completion_pct':   completion_pct,
        'overdue':          overdue,
        'blocked_count':    blocked_count,
        'blocked_list':     blocked_list,
        'velocity_now':     velocity_now,
        'velocity_change':  velocity_change_pct,
        'high_risk_count':  high_risk_count,
        'tasks_by_column':  tasks_by_column,
        'workload':         workload,
        'total_open':       total_open,
        'budget':           budget_info,
        'milestones':       milestone_list,
        'new_tasks_count':  new_tasks_count,
    }, warnings


def _parse_slides(raw_text):
    """
    Parse the AI response into a list of slide dicts.
    Expects delimiters like:  --- SLIDE 1: Title ---
    Returns: [{'number': 1, 'title': '...', 'body': '...'}, ...]
    """
    slides   = []
    pattern  = re.compile(r'---\s*SLIDE\s*(\d+)\s*[:\-–—]\s*(.+?)\s*---', re.IGNORECASE)
    parts    = pattern.split(raw_text)

    # parts[0] is any preamble before the first slide marker (discard)
    # then groups of (number, title, body)
    i = 1
    while i + 2 <= len(parts):
        number = parts[i].strip()
        title  = parts[i + 1].strip()
        body   = parts[i + 2].strip()
        slides.append({'number': int(number), 'title': title, 'body': body})
        i += 3

    # Fallback: if the AI didn't use the delimiter, return as one block
    if not slides:
        slides.append({'number': 1, 'title': 'Presentation Brief', 'body': raw_text.strip()})

    return slides


# ── Main view ─────────────────────────────────────────────────────────────────

@login_required
def prizmbrief_setup(request, board_id):
    """
    GET  → Renders the 3-question setup form.
    POST → Gathers board data, generates the brief, renders the results page.
    """
    import time as _time
    from api.ai_usage_utils import check_ai_quota, track_ai_request
    from kanban.utils.ai_utils import generate_prizmbrief

    board = get_object_or_404(Board, id=board_id)

    # ── Shared context bits for the form ──────────────────────────────────────
    form_context = {
        'board':            board,
        'audience_choices': AUDIENCE_CHOICES,
        'purpose_choices':  PURPOSE_CHOICES,
        'mode_choices':     MODE_CHOICES,
    }

    if request.method == 'GET':
        return render(request, 'kanban/prizmbrief_setup.html', form_context)

    # ── POST: validate inputs ─────────────────────────────────────────────────
    audience = request.POST.get('audience', '').strip()
    purpose  = request.POST.get('purpose', '').strip()
    mode     = request.POST.get('mode', 'executive_summary').strip()

    valid_audiences = [k for k, _ in AUDIENCE_CHOICES]
    valid_purposes  = [k for k, _ in PURPOSE_CHOICES]
    valid_modes     = [k for k, _, _ in MODE_CHOICES]

    if audience not in valid_audiences or purpose not in valid_purposes or mode not in valid_modes:
        return render(request, 'kanban/prizmbrief_setup.html', {
            **form_context,
            'error': 'Please answer all three questions before generating.',
        })

    # ── Quota check ───────────────────────────────────────────────────────────
    has_quota, quota, remaining = check_ai_quota(request.user)
    if not has_quota:
        return render(request, 'kanban/prizmbrief_setup.html', {
            **form_context,
            'error': 'AI usage quota exceeded. Please wait for your quota to reset.',
        })

    # ── Gather live data ──────────────────────────────────────────────────────
    metrics, data_warnings = _gather_board_data(board)

    # ── Call AI ───────────────────────────────────────────────────────────────
    start = _time.time()
    brief_data = {
        **metrics,
        'audience':      audience,
        'audience_label': _label(AUDIENCE_CHOICES, audience),
        'purpose':       purpose,
        'purpose_label': _label(PURPOSE_CHOICES, purpose),
        'mode':          mode,
        'user_name':     request.user.get_full_name() or request.user.username,
    }

    raw_text = generate_prizmbrief(brief_data)
    elapsed  = int((_time.time() - start) * 1000)

    track_ai_request(
        user=request.user,
        feature='prizmbrief',
        request_type='generate',
        board_id=board.id,
        success=bool(raw_text),
        response_time_ms=elapsed,
    )

    if not raw_text:
        return render(request, 'kanban/prizmbrief_setup.html', {
            **form_context,
            'error': 'AI could not generate the brief right now. Please try again shortly.',
        })

    # ── Parse slides ──────────────────────────────────────────────────────────
    slides = _parse_slides(raw_text)

    # ── Full-text for Copy All / Download .txt ────────────────────────────────
    full_text_lines = [
        f"PrizmBrief — AI Presentation Content",
        f"Board: {board.name}",
        f"Generated: {metrics['report_date']} at {metrics['report_time']}",
        f"Audience: {_label(AUDIENCE_CHOICES, audience)}",
        f"Purpose:  {_label(PURPOSE_CHOICES, purpose)}",
        f"Mode:     {next((lbl for k, lbl, _ in MODE_CHOICES if k == mode), mode)}",
        "",
        "=" * 60,
        "",
        raw_text.strip(),
    ]
    full_text = "\n".join(full_text_lines)

    # Safe filename component
    import re as _re
    safe_name = _re.sub(r'[^A-Za-z0-9_-]', '_', board.name)

    return render(request, 'kanban/prizmbrief_result.html', {
        'board':          board,
        'slides':         slides,
        'full_text':      full_text,
        'download_name':  f"{safe_name}_AI_Presentation_Brief.txt",
        'audience_label': _label(AUDIENCE_CHOICES, audience),
        'purpose_label':  _label(PURPOSE_CHOICES, purpose),
        'mode_label':     next((lbl for k, lbl, _ in MODE_CHOICES if k == mode), mode),
        'report_date':    metrics['report_date'],
        'report_time':    metrics['report_time'],
        'data_warnings':  data_warnings,
        # Pass back so Regenerate can pre-fill
        'last_audience':  audience,
        'last_purpose':   purpose,
        'last_mode':      mode,
    })
