"""
Project Stress Test Views

Provides the Red Team AI adversarial simulation feature:
runs simulated attacks on a board, produces Immunity Score,
and prescribes structural Vaccine fixes.
"""

import json
import re
import time
import logging

import google.generativeai as genai
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.conf import settings

from kanban.models import Board
from kanban.stress_test_models import (
    StressTestSession, ImmunityScore, StressTestScenario, Vaccine,
)
from kanban.stress_test_prompt import (
    STRESS_TEST_SYSTEM_PROMPT, build_stress_test_user_prompt,
)
from kanban.stress_test_data import build_board_stress_test_data
from kanban.audit_utils import log_audit
from kanban.decorators import demo_write_guard, demo_ai_guard
from api.ai_usage_utils import track_ai_request, require_ai_quota, check_ai_quota

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON repair helper
# ---------------------------------------------------------------------------

def _parse_gemini_json(raw: str) -> dict:
    """
    Parse JSON from Gemini output, repairing common issues:
    - Markdown fences
    - Trailing commas
    - Truncated responses (close open braces/brackets)
    - Newlines inside string values
    """
    # Strip markdown fences
    text = raw.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1] if '\n' in text else text[3:]
    if text.endswith('```'):
        text = text[:-3].strip()
    if text.startswith('json'):
        text = text[4:].strip()

    # Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # Try straightforward parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fix truncated response — close any unclosed structures
    repaired = _repair_truncated_json(text)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # Last resort — try to extract the largest valid JSON object
    # by finding the first { and trying progressively shorter substrings
    start = text.find('{')
    if start == -1:
        raise ValueError("No JSON object found in AI response")

    # Binary-style: try closing off from the end
    for end_pos in range(len(repaired), start, -1):
        chunk = repaired[:end_pos]
        # Close any remaining open structures
        chunk = _repair_truncated_json(chunk)
        try:
            return json.loads(chunk)
        except json.JSONDecodeError:
            continue

    raise ValueError("Could not parse AI response as JSON after repair attempts")


def _repair_truncated_json(text: str) -> str:
    """Close unclosed strings, arrays, and objects in truncated JSON."""
    result = text

    # If we're inside an unclosed string (odd number of unescaped quotes),
    # close it and truncate the last value
    in_string = False
    i = 0
    while i < len(result):
        c = result[i]
        if c == '\\' and in_string:
            i += 2
            continue
        if c == '"':
            in_string = not in_string
        i += 1

    if in_string:
        result += '"'

    # Remove trailing commas
    result = re.sub(r',\s*$', '', result)

    # Count and close unclosed brackets/braces
    opens = 0
    closes_needed_bracket = 0
    closes_needed_brace = 0
    in_str = False
    i = 0
    while i < len(result):
        c = result[i]
        if c == '\\' and in_str:
            i += 2
            continue
        if c == '"':
            in_str = not in_str
        if not in_str:
            if c == '{':
                closes_needed_brace += 1
            elif c == '}':
                closes_needed_brace -= 1
            elif c == '[':
                closes_needed_bracket += 1
            elif c == ']':
                closes_needed_bracket -= 1
        i += 1

    result += ']' * max(0, closes_needed_bracket)
    result += '}' * max(0, closes_needed_brace)

    return result


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@login_required
def stress_test_dashboard(request, board_id):
    """Main Stress Test page — shows latest session or empty state."""
    board = get_object_or_404(Board, id=board_id)

    sessions = StressTestSession.objects.filter(board=board).select_related(
        'immunity_score'
    ).prefetch_related('scenarios', 'vaccines')

    latest_session = sessions.first()

    # Build immunity score history for trend chart (chronological)
    immunity_history = list(
        ImmunityScore.objects.filter(session__board=board)
        .order_by('session__created_at')
        .values_list('overall', flat=True)[:10]
    )

    # Stats
    total_scenarios = 0
    scenarios_addressed = 0
    vaccines_applied_session = 0
    if latest_session:
        total_scenarios = latest_session.scenarios.count()
        scenarios_addressed = latest_session.scenarios.filter(is_addressed=True).count()
        vaccines_applied_session = latest_session.vaccines.filter(is_applied=True).count()

    vaccines_applied_total = Vaccine.objects.filter(board=board, is_applied=True).count()
    vaccines_total = Vaccine.objects.filter(board=board).count()

    # Pre-mortem count for cross-link
    premortem_count = 0
    try:
        latest_premortem = board.pre_mortems.first()
        if latest_premortem and latest_premortem.analysis_json:
            premortem_count = len(
                latest_premortem.analysis_json.get('failure_scenarios', [])
            )
    except Exception:
        pass

    # AI quota availability for the "Run" button
    has_quota = True
    if request.user.is_authenticated:
        has_quota, _, _ = check_ai_quota(request.user)

    context = {
        'board': board,
        'session': latest_session,
        'all_sessions': sessions,
        'immunity_history': json.dumps(immunity_history),
        'total_scenarios': total_scenarios,
        'scenarios_addressed': scenarios_addressed,
        'vaccines_applied': vaccines_applied_total,
        'vaccines_applied_session': vaccines_applied_session,
        'vaccines_total': vaccines_total,
        'premortem_count': premortem_count,
        'has_quota': has_quota,
        'session_count': sessions.count(),
    }
    return render(request, 'kanban/stress_test.html', context)


@login_required
@require_POST
@require_ai_quota('stress_test')
@demo_ai_guard
def run_stress_test(request, board_id):
    """Run a new Red Team AI stress test session."""
    board = get_object_or_404(Board, id=board_id)
    board_data = build_board_stress_test_data(board, request.user)

    start_time = time.time()

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            'gemini-2.5-flash',
            system_instruction=STRESS_TEST_SYSTEM_PROMPT,
        )
        response = model.generate_content(
            build_stress_test_user_prompt(board_data),
            generation_config=genai.GenerationConfig(
                temperature=0.4,
                max_output_tokens=16384,
                response_mime_type="application/json",
            ),
        )

        raw = response.text.strip()
        logger.info("Stress Test raw response length: %d chars", len(raw))
        result = _parse_gemini_json(raw)

    except Exception as e:
        logger.error("Stress Test Gemini call failed for board %s: %s", board_id, e)
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='stress_test',
            request_type='stress_test_run',
            board_id=board.id,
            success=False,
            error_message=str(e)[:500],
            response_time_ms=response_time_ms,
        )
        return JsonResponse({
            'success': False,
            'error': 'AI stress test failed. Please try again in a moment.',
        }, status=500)

    # --- Save session ---
    session = StressTestSession.objects.create(
        board=board,
        run_by=request.user,
        assumptions_made=result.get('assumptions_made', []),
        score_rationale=result.get('score_rationale', ''),
    )

    # Save immunity score — coerce None → safe defaults
    dim_scores = result.get('dimension_scores') or {}
    dim_rationale = result.get('dimension_rationale') or {}
    ImmunityScore.objects.create(
        session=session,
        overall=result.get('overall_immunity_score') or 50,
        schedule=dim_scores.get('schedule') or 50,
        budget=dim_scores.get('budget') or 50,
        team=dim_scores.get('team') or 50,
        dependencies=dim_scores.get('dependencies') or 50,
        scope_stability=dim_scores.get('scope_stability') or 50,
        schedule_rationale=dim_rationale.get('schedule') or '',
        budget_rationale=dim_rationale.get('budget') or '',
        team_rationale=dim_rationale.get('team') or '',
        dependencies_rationale=dim_rationale.get('dependencies') or '',
        scope_stability_rationale=dim_rationale.get('scope_stability') or '',
    )

    # Save scenarios — coerce None → safe defaults (Gemini may return null)
    # Each save is isolated: one bad field won't abort the rest.
    scenarios_saved = 0
    for s in result.get('chaos_scenarios', []):
        try:
            outcome_raw = s.get('outcome') or 'SURVIVED'
            if outcome_raw not in ('FAIL', 'SURVIVED', 'SURVIVED_BARELY'):
                outcome_raw = 'SURVIVED'
            StressTestScenario.objects.create(
                session=session,
                scenario_number=s.get('id') or 0,
                attack_type=s.get('attack_type') or '',
                title=s.get('title') or '',
                attack_description=s.get('attack_description') or '',
                cascade_effect=s.get('cascade_effect') or '',
                outcome=outcome_raw,
                severity=min(max(int(s.get('severity') or 5), 1), 10),
                tasks_blocked=max(int(s.get('tasks_blocked') or 0), 0),
                estimated_delay_weeks=s.get('estimated_delay_weeks'),
                has_recovery_path=bool(s.get('has_recovery_path', False)),
                early_warning_sign=s.get('early_warning_sign') or '',
                tags=s.get('tags') or [],
            )
            scenarios_saved += 1
        except Exception as exc:
            logger.error(
                "Stress Test: failed to save scenario %s for session %s: %s",
                s.get('id'), session.id, exc,
            )

    # Save vaccines — coerce None → safe defaults
    # Each save is isolated: one bad field won't abort the rest.
    vaccines_saved = 0
    for v in result.get('vaccines', []):
        try:
            effort_raw = v.get('effort_level') or 'MEDIUM'
            if effort_raw not in ('LOW', 'MEDIUM', 'HIGH'):
                effort_raw = 'MEDIUM'
            Vaccine.objects.create(
                session=session,
                board=board,
                vaccine_number=v.get('id') or 0,
                targets_scenario_number=v.get('targets_scenario') or 1,
                name=v.get('name') or '',
                description=v.get('description') or '',
                effort_level=effort_raw,
                effort_rationale=v.get('effort_rationale') or '',
                projected_score_improvement=max(int(v.get('projected_score_improvement') or 0), 0),
                implementation_hint=v.get('implementation_hint') or '',
                is_applied=False,
            )
            vaccines_saved += 1
        except Exception as exc:
            logger.error(
                "Stress Test: failed to save vaccine %s for session %s: %s",
                v.get('id'), session.id, exc,
            )

    logger.info(
        "Stress Test session %s: saved %d/%d scenarios, %d/%d vaccines",
        session.id,
        scenarios_saved, len(result.get('chaos_scenarios', [])),
        vaccines_saved, len(result.get('vaccines', [])),
    )

    response_time_ms = int((time.time() - start_time) * 1000)
    track_ai_request(
        user=request.user,
        feature='stress_test',
        request_type='stress_test_run',
        board_id=board.id,
        success=True,
        response_time_ms=response_time_ms,
    )

    try:
        log_audit(
            'stress_test.created',
            user=request.user,
            request=request,
            object_type='stresstestsession',
            object_id=session.id,
            object_repr=str(session),
            board_id=board.id,
            changes={
                'immunity_score': {'old': None, 'new': result.get('overall_immunity_score')},
            },
        )
    except Exception:
        logger.warning("Audit log for stress_test.created failed", exc_info=True)

    return JsonResponse({
        'success': True,
        'session_id': session.id,
        'immunity_score': result.get('overall_immunity_score', 50),
        'redirect': f'/board/{board_id}/stress-test/',
    })


@login_required
@require_POST
@demo_write_guard
def apply_vaccine(request, board_id, vaccine_id):
    """Toggle a vaccine's is_applied state."""
    vaccine = get_object_or_404(Vaccine, pk=vaccine_id, board_id=board_id)

    vaccine.is_applied = not vaccine.is_applied
    vaccine.applied_at = timezone.now() if vaccine.is_applied else None
    vaccine.applied_by = request.user if vaccine.is_applied else None
    vaccine.save()

    try:
        log_audit(
            'stress_test.vaccine_toggled',
            user=request.user,
            request=request,
            object_type='vaccine',
            object_id=vaccine.id,
            object_repr=str(vaccine),
            board_id=board_id,
            changes={'is_applied': {'old': not vaccine.is_applied, 'new': vaccine.is_applied}},
        )
    except Exception:
        logger.warning("Audit log for vaccine toggle failed", exc_info=True)

    return JsonResponse({'success': True, 'is_applied': vaccine.is_applied})


@login_required
@require_POST
@demo_write_guard
def reset_stress_test_history(request, board_id):
    """Delete all stress test sessions (and cascaded data) for this board.
    Only the board creator may do this.
    """
    board = get_object_or_404(Board, id=board_id)

    if board.created_by != request.user and not request.user.is_staff:
        return JsonResponse(
            {'success': False, 'error': 'Only the board owner can reset stress test history.'},
            status=403,
        )

    deleted_count, _ = StressTestSession.objects.filter(board=board).delete()

    try:
        log_audit(
            'stress_test.history_reset',
            user=request.user,
            request=request,
            object_type='board',
            object_id=board.id,
            object_repr=str(board),
            board_id=board.id,
            changes={'sessions_deleted': {'old': deleted_count, 'new': 0}},
        )
    except Exception:
        logger.warning("Audit log for stress_test.history_reset failed", exc_info=True)

    return JsonResponse({'success': True, 'deleted': deleted_count})


@login_required
@require_POST
@demo_write_guard
def mark_scenario_addressed(request, board_id, scenario_id):
    """Toggle a scenario's is_addressed state."""
    scenario = get_object_or_404(
        StressTestScenario, pk=scenario_id, session__board_id=board_id
    )

    scenario.is_addressed = not scenario.is_addressed
    scenario.addressed_at = timezone.now() if scenario.is_addressed else None
    scenario.addressed_by = request.user if scenario.is_addressed else None
    scenario.save()

    try:
        log_audit(
            'stress_test.scenario_addressed',
            user=request.user,
            request=request,
            object_type='stresstestscenario',
            object_id=scenario.id,
            object_repr=str(scenario),
            board_id=board_id,
            changes={'is_addressed': {'old': not scenario.is_addressed, 'new': scenario.is_addressed}},
        )
    except Exception:
        logger.warning("Audit log for scenario address failed", exc_info=True)

    return JsonResponse({'success': True, 'is_addressed': scenario.is_addressed})
