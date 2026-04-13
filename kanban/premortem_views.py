"""
Pre-Mortem AI Analysis Views

Provides a proactive failure-simulation feature: before a project starts,
AI plays devil's advocate and simulates 5 ways the project could fail.
"""

import json
import time
import logging
from datetime import date, timedelta

from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Q
from django.conf import settings

from kanban.models import Board, Task
from kanban.premortem_models import PreMortemAnalysis, PreMortemScenarioAcknowledgment
from kanban.audit_utils import log_audit
from kanban.decorators import demo_write_guard, demo_ai_guard
from api.ai_usage_utils import track_ai_request, require_ai_quota, check_ai_quota

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def board_premortem_ready(board):
    """
    Check whether a board meets the unlock conditions for Pre-Mortem analysis.

    Returns a dict:
        {
            'ready': bool,
            'has_enough_tasks': bool,
            'has_deadline': bool,
            'has_assignee': bool,
            'task_count': int,
        }
    """
    tasks = Task.objects.filter(column__board=board, item_type='task')
    task_count = tasks.count()
    has_enough_tasks = task_count >= 5
    has_deadline = tasks.filter(due_date__isnull=False).exists()
    has_assignee = tasks.filter(assigned_to__isnull=False).exists()

    return {
        'ready': has_enough_tasks and has_deadline and has_assignee,
        'has_enough_tasks': has_enough_tasks,
        'has_deadline': has_deadline,
        'has_assignee': has_assignee,
        'task_count': task_count,
    }


def _collect_board_snapshot(board):
    """
    Gather all relevant board data for the Gemini prompt and for archival.
    """
    tasks = Task.objects.filter(column__board=board, item_type='task')
    now = timezone.now()

    task_count = tasks.count()
    high_priority_count = tasks.filter(priority__in=['high', 'urgent']).count()

    # "Done" columns heuristic
    done_q = Q(column__name__icontains='done') | Q(column__name__icontains='complete')
    overdue_count = tasks.filter(
        due_date__lt=now
    ).exclude(done_q).count()

    unassigned_count = tasks.filter(assigned_to__isnull=True).count()
    no_deadline_count = tasks.filter(due_date__isnull=False).count()
    no_deadline_count = task_count - no_deadline_count  # tasks WITHOUT a due date

    # Team size – union of board members and distinct assignees
    member_ids = set(board.memberships.values_list('user_id', flat=True))
    assignee_ids = set(
        tasks.filter(assigned_to__isnull=False)
        .values_list('assigned_to_id', flat=True)
        .distinct()
    )
    team_size = len(member_ids | assignee_ids)

    # Timeline
    project_deadline = board.project_deadline  # may be None
    earliest_start = (
        tasks.filter(start_date__isnull=False)
        .order_by('start_date')
        .values_list('start_date', flat=True)
        .first()
    )
    start_date = earliest_start or board.created_at.date()

    days_available = None
    days_remaining = None
    if project_deadline:
        days_available = (project_deadline - start_date).days
        days_remaining = (project_deadline - date.today()).days

    # Budget (from ProjectBudget model)
    budget_info = None
    try:
        budget = board.budget  # OneToOneField reverse accessor
        allocated = float(budget.allocated_budget)
        spent = float(budget.get_spent_amount())
        budget_info = f"{budget.currency} {allocated:,.2f} allocated, {budget.currency} {spent:,.2f} spent ({budget.get_budget_utilization_percent():.0f}% used)"
    except Exception:
        budget_info = None

    # Existing active conflicts
    conflict_count = 0
    try:
        from kanban.conflict_models import ConflictDetection
        conflict_count = ConflictDetection.objects.filter(
            board=board, status='active'
        ).count()
    except Exception:
        pass

    snapshot = {
        'board_name': board.name,
        'board_description': board.description or '',
        'task_count': task_count,
        'high_priority_count': high_priority_count,
        'overdue_count': overdue_count,
        'unassigned_count': unassigned_count,
        'no_deadline_count': no_deadline_count,
        'team_size': team_size,
        'start_date': str(start_date),
        'project_deadline': str(project_deadline) if project_deadline else None,
        'days_available': days_available,
        'days_remaining': days_remaining,
        'budget_info': budget_info,
        'conflict_count': conflict_count,
    }
    return snapshot


def _build_gemini_prompt(snapshot):
    """
    Build the system + user prompt pair for the Pre-Mortem analysis.
    Returns (system_prompt, user_prompt).
    """
    system_prompt = (
        "You are a senior project risk analyst specializing in Pre-Mortem analysis. "
        "Your job is to imagine that this project has already completely failed, "
        "then work backwards to identify the 5 most likely root causes of that failure.\n\n"
        "Rules:\n"
        "- Be specific to THIS project's actual data. Use the real numbers provided.\n"
        "- Do NOT give generic project management advice.\n"
        "- Do NOT be reassuring or diplomatic. Be direct about risks.\n"
        "- Each failure scenario must be distinct — no overlapping causes.\n"
        "- Think like a skeptic, not a cheerleader.\n\n"
        "Return ONLY valid JSON. No markdown, no backticks, no explanation outside the JSON."
    )

    timeline_str = "Not set"
    if snapshot.get('days_available') is not None:
        timeline_str = (
            f"{snapshot['days_available']} days total "
            f"({snapshot['days_remaining']} days remaining)"
        )

    user_prompt = (
        "Analyze this project and generate a Pre-Mortem analysis.\n\n"
        "PROJECT DATA:\n"
        f"- Name: {snapshot['board_name']}\n"
        f"- Description: {snapshot['board_description'] or 'Not specified'}\n"
        f"- Total tasks: {snapshot['task_count']}\n"
        f"- High priority tasks: {snapshot['high_priority_count']}\n"
        f"- Overdue tasks: {snapshot['overdue_count']}\n"
        f"- Tasks with no assignee: {snapshot['unassigned_count']}\n"
        f"- Tasks with no due date: {snapshot['no_deadline_count']}\n"
        f"- Team size: {snapshot['team_size']} people\n"
        f"- Timeline: {timeline_str}\n"
        f"- Budget: {snapshot['budget_info'] or 'Not set'}\n"
        f"- Existing conflicts detected: {snapshot['conflict_count']}\n\n"
        'Return this exact JSON structure:\n'
        '{\n'
        '  "failure_scenarios": [\n'
        '    {\n'
        '      "title": "Short 4-6 word title",\n'
        '      "probability": "High" or "Medium" or "Low",\n'
        '      "description": "2-3 sentences describing exactly how this project fails '
        'in this specific way, referencing the actual project numbers above",\n'
        '      "early_warning_sign": "One specific observable signal that this failure '
        'is beginning — something the PM can actually notice",\n'
        '      "prevention_action": "One concrete action the PM can take RIGHT NOW '
        'to reduce this risk"\n'
        '    }\n'
        '  ],\n'
        '  "overall_risk_level": "High" or "Medium" or "Low",\n'
        '  "confidence_note": "One sentence describing what assumptions you made '
        'due to missing data"\n'
        '}'
    )

    return system_prompt, user_prompt


def _call_gemini(system_prompt, user_prompt):
    """
    Call Gemini and return parsed JSON dict.
    Raises on failure.
    """
    import google.generativeai as genai
    from kanban_board.ai_cache import get_cached_ai_response

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(
        'gemini-2.5-flash-lite',
        system_instruction=system_prompt,
    )

    generation_config = {
        'temperature': 0.4,
        'top_p': 0.8,
        'top_k': 40,
        'max_output_tokens': 4096,
    }

    # Use combined prompt as cache key (system + user)
    full_prompt = f"{system_prompt}\n---\n{user_prompt}"
    raw = get_cached_ai_response(
        prompt=full_prompt,
        model_call=lambda: model.generate_content(user_prompt, generation_config=generation_config),
        operation='premortem',
    )
    if not raw:
        raise RuntimeError('AI pre-mortem analysis returned no response')

    # Strip markdown fences if accidentally returned
    if raw.startswith('```'):
        raw = raw.split('\n', 1)[1] if '\n' in raw else raw[3:]
    if raw.endswith('```'):
        raw = raw[:-3].strip()
    if raw.startswith('json'):
        raw = raw[4:].strip()

    return json.loads(raw)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@login_required
def premortem_dashboard(request, board_id):
    """
    Main Pre-Mortem page. Shows locked / unlocked / results state.
    """
    board = get_object_or_404(Board, id=board_id)
    readiness = board_premortem_ready(board)
    latest = board.pre_mortems.first()  # ordered by -created_at

    # Flag stale analyses (older than 7 days)
    if latest:
        latest.is_stale = (timezone.now() - latest.created_at) > timedelta(days=7)

    # Gather acknowledgments and enrich scenario data for the template
    enriched_scenarios = []
    if latest and latest.analysis_json and latest.analysis_json.get('failure_scenarios'):
        ack_map = {}
        for ack in latest.acknowledgments.select_related('acknowledged_by').all():
            ack_map[ack.scenario_index] = ack

        for idx, scenario in enumerate(latest.analysis_json['failure_scenarios']):
            ack = ack_map.get(idx)
            enriched_scenarios.append({
                'index': idx,
                'number': idx + 1,
                'title': scenario.get('title', ''),
                'description': scenario.get('description', ''),
                'probability': scenario.get('probability', 'Medium'),
                'early_warning_sign': scenario.get('early_warning_sign', ''),
                'prevention_action': scenario.get('prevention_action', ''),
                'acknowledged': ack is not None,
                'acknowledged_by': ack.acknowledged_by.get_full_name() or ack.acknowledged_by.username if ack else '',
                'acknowledged_at': ack.acknowledged_at if ack else None,
            })

    # Check AI quota for the "Run" button availability
    has_quota = True
    if request.user.is_authenticated:
        has_quota, _, _ = check_ai_quota(request.user)

    acknowledged_count = sum(1 for s in enriched_scenarios if s['acknowledged'])
    total_scenarios = len(enriched_scenarios)

    context = {
        'board': board,
        'readiness': readiness,
        'latest': latest,
        'enriched_scenarios': enriched_scenarios,
        'has_quota': has_quota,
        'acknowledged_count': acknowledged_count,
        'total_scenarios': total_scenarios,
    }
    return render(request, 'kanban/premortem_dashboard.html', context)


@login_required
@require_POST
@require_ai_quota('premortem')
@demo_ai_guard
def run_premortem(request, board_id):
    """
    Run a new Pre-Mortem AI analysis for the board.
    """
    board = get_object_or_404(Board, id=board_id)

    # RBAC: verify user has access to this board
    if not request.user.has_perm('prizmai.view_board', board):
        return JsonResponse({'error': 'Permission denied'}, status=403)

    # Verify readiness
    readiness = board_premortem_ready(board)
    if not readiness['ready']:
        return JsonResponse({
            'success': False,
            'error': 'Board does not meet the Pre-Mortem unlock conditions.',
        }, status=400)

    # Async mode: enqueue Celery task and return task_id for WebSocket streaming
    if request.headers.get('X-Request-Async'):
        from kanban.tasks.ai_streaming_tasks import run_premortem_task
        result = run_premortem_task.delay(board_id, request.user.id)
        return JsonResponse({'task_id': result.id, 'status': 'queued'})

    start_time = time.time()
    snapshot = _collect_board_snapshot(board)
    system_prompt, user_prompt = _build_gemini_prompt(snapshot)

    try:
        analysis_data = _call_gemini(system_prompt, user_prompt)
    except Exception as e:
        logger.error("Pre-Mortem Gemini call failed for board %s: %s", board_id, e)
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='premortem',
            request_type='pre_mortem_analysis',
            board_id=board.id,
            success=False,
            error_message=str(e)[:500],
            response_time_ms=response_time_ms,
        )
        return JsonResponse({
            'success': False,
            'error': 'AI analysis failed. Please try again in a moment.',
        }, status=500)

    # Normalise risk level
    overall_risk = analysis_data.get('overall_risk_level', 'medium').lower()
    if overall_risk not in ('high', 'medium', 'low'):
        overall_risk = 'medium'

    analysis = PreMortemAnalysis.objects.create(
        board=board,
        created_by=request.user,
        overall_risk_level=overall_risk,
        analysis_json=analysis_data,
        board_snapshot=snapshot,
    )

    response_time_ms = int((time.time() - start_time) * 1000)
    track_ai_request(
        user=request.user,
        feature='premortem',
        request_type='pre_mortem_analysis',
        board_id=board.id,
        success=True,
        response_time_ms=response_time_ms,
    )

    # Audit log
    try:
        log_audit(
            'premortem.created',
            user=request.user,
            request=request,
            object_type='premortemanalysis',
            object_id=analysis.id,
            object_repr=str(analysis),
            board_id=board.id,
            changes={
                'overall_risk_level': {'old': None, 'new': overall_risk},
            },
        )
    except Exception:
        logger.warning("Audit log for premortem.created failed", exc_info=True)

    return JsonResponse({
        'success': True,
        'analysis': {
            'id': analysis.id,
            'overall_risk_level': analysis.overall_risk_level,
            'created_at': analysis.created_at.isoformat(),
            'created_by': request.user.get_full_name() or request.user.username,
            'failure_scenarios': analysis_data.get('failure_scenarios', []),
            'confidence_note': analysis_data.get('confidence_note', ''),
        },
    })


@login_required
@require_POST
@demo_write_guard
def acknowledge_scenario(request, premortem_id, scenario_index):
    """
    Mark a Pre-Mortem scenario as addressed / acknowledged.
    """
    analysis = get_object_or_404(PreMortemAnalysis, id=premortem_id)

    if scenario_index < 0 or scenario_index > 4:
        return JsonResponse({'success': False, 'error': 'Invalid scenario index.'}, status=400)

    # Prevent duplicate acknowledgments
    if PreMortemScenarioAcknowledgment.objects.filter(
        pre_mortem=analysis,
        scenario_index=scenario_index,
        acknowledged_by=request.user,
    ).exists():
        return JsonResponse({'success': False, 'error': 'Already acknowledged.'}, status=400)

    body = {}
    try:
        body = json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        pass

    ack = PreMortemScenarioAcknowledgment.objects.create(
        pre_mortem=analysis,
        scenario_index=scenario_index,
        acknowledged_by=request.user,
        notes=body.get('notes', ''),
    )

    # Audit log
    try:
        log_audit(
            'premortem.scenario_acknowledged',
            user=request.user,
            request=request,
            object_type='premortemaacknowledgment',
            object_id=ack.id,
            board_id=analysis.board_id,
            changes={
                'scenario_index': {'old': None, 'new': scenario_index},
            },
        )
    except Exception:
        logger.warning("Audit log for premortem acknowledgment failed", exc_info=True)

    return JsonResponse({
        'success': True,
        'acknowledged_by': request.user.get_full_name() or request.user.username,
        'acknowledged_at': ack.acknowledged_at.isoformat(),
    })


@login_required
def get_latest_premortem(request, board_id):
    """
    Return the most recent Pre-Mortem analysis for a board as JSON.
    """
    board = get_object_or_404(Board, id=board_id)
    latest = board.pre_mortems.first()

    if not latest:
        return JsonResponse({'success': True, 'analysis': None})

    acknowledged = list(
        latest.acknowledgments.values_list('scenario_index', flat=True)
    )

    return JsonResponse({
        'success': True,
        'analysis': {
            'id': latest.id,
            'overall_risk_level': latest.overall_risk_level,
            'created_at': latest.created_at.isoformat(),
            'created_by': (
                latest.created_by.get_full_name() or latest.created_by.username
            ) if latest.created_by else 'Unknown',
            'failure_scenarios': latest.analysis_json.get('failure_scenarios', []),
            'confidence_note': latest.analysis_json.get('confidence_note', ''),
            'acknowledged_scenarios': acknowledged,
        },
    })
