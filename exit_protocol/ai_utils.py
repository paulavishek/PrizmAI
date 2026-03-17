"""
AI utility wrappers for Exit Protocol.
All Gemini calls go through here — handles quota checking, request tracking, and error handling.
"""

import json
import logging
import time

from ai_assistant.utils.ai_clients import GeminiClient
from api.ai_usage_utils import track_ai_request, check_ai_quota

from .prompts import (
    HOSPICE_ASSESSMENT_PROMPT, ORGAN_REUSABILITY_PROMPT,
    ORGAN_COMPATIBILITY_PROMPT, CAUSE_OF_DEATH_PROMPT,
    LESSONS_PROMPT, TAGS_PROMPT, TRANSITION_MEMO_PROMPT,
)

logger = logging.getLogger(__name__)


def _safe_context(context, keys):
    """Ensure all expected keys exist with safe fallback values."""
    safe = {}
    for key in keys:
        val = context.get(key)
        if val is None or val == '':
            safe[key] = 'Not available'
        else:
            safe[key] = val
    return safe


def _call_gemini(user, prompt, task_complexity, feature_name, board_id=None, temperature=None):
    """
    Central wrapper: checks quota, calls Gemini, tracks usage.
    Returns the raw text content from Gemini.
    """
    has_quota, quota, remaining = check_ai_quota(user)
    if not has_quota:
        raise ValueError(f"AI quota exceeded for user {user.id}")

    client = GeminiClient()
    start_time = time.time()

    try:
        response = client.get_response(
            prompt=prompt,
            task_complexity=task_complexity,
            temperature=temperature or (0.4 if task_complexity == 'complex' else 0.3),
        )

        elapsed_ms = int((time.time() - start_time) * 1000)
        tokens = response.get('tokens', 0) if isinstance(response, dict) else 0
        content = response.get('content', '') if isinstance(response, dict) else str(response)

        track_ai_request(
            user=user,
            feature=feature_name,
            request_type='exit_protocol',
            board_id=board_id,
            ai_model='gemini',
            success=True,
            tokens_used=tokens,
            response_time_ms=elapsed_ms,
        )

        return content

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=user,
            feature=feature_name,
            request_type='exit_protocol',
            board_id=board_id,
            ai_model='gemini',
            success=False,
            error_message=str(e)[:500],
            response_time_ms=elapsed_ms,
        )
        logger.error(f"Gemini call failed for {feature_name}: {e}")
        raise


def _safe_json(text):
    """Strip markdown fences and parse JSON. Returns dict or raises ValueError."""
    if not text:
        raise ValueError("Empty response from Gemini")
    clean = text.strip()
    # Strip markdown code fences
    if clean.startswith('```'):
        # Remove opening fence (with optional language tag)
        first_newline = clean.index('\n')
        clean = clean[first_newline + 1:]
    if clean.endswith('```'):
        clean = clean[:-3]
    clean = clean.strip()
    return json.loads(clean)


def generate_assessment(user, context, board_id=None):
    """Generate a compassionate hospice assessment. Uses gemini-2.5-flash (complex)."""
    expected_keys = [
        'project_name', 'start_date', 'days_active', 'completed_tasks',
        'total_tasks', 'completion_pct', 'budget_spent_pct', 'velocity_trend',
        'deadlines_missed', 'days_inactive', 'materialized_risks', 'stress_score',
    ]
    safe = _safe_context(context, expected_keys)
    prompt = HOSPICE_ASSESSMENT_PROMPT.format(**safe)
    return _call_gemini(user, prompt, 'complex', 'hospice_assessment', board_id)


def score_organ_reusability(user, context, board_id=None):
    """Score an organ's reusability. Uses gemini-2.5-flash-lite."""
    expected_keys = [
        'organ_type', 'name', 'description', 'payload_summary', 'source_project_context',
    ]
    safe = _safe_context(context, expected_keys)
    prompt = ORGAN_REUSABILITY_PROMPT.format(**safe)
    raw = _call_gemini(user, prompt, 'simple', 'organ_reusability', board_id)
    return _safe_json(raw)


def score_organ_compatibility(user, context, board_id=None):
    """
    Score compatibility of an organ with a target board.
    Called lazily — results cached in Redis by the calling view.
    Uses gemini-2.5-flash-lite.
    """
    expected_keys = [
        'organ_type', 'name', 'description', 'source_context',
        'target_name', 'target_description', 'target_phase',
        'target_team_size', 'target_domain',
    ]
    safe = _safe_context(context, expected_keys)
    prompt = ORGAN_COMPATIBILITY_PROMPT.format(**safe)
    raw = _call_gemini(user, prompt, 'simple', 'organ_compatibility', board_id)
    return _safe_json(raw)


def classify_cause_of_death(user, context, board_id=None):
    """Classify project cause of death. Uses gemini-2.5-flash-lite."""
    expected_keys = [
        'velocity_ratio', 'budget_pct', 'total_budget', 'completion_pct',
        'planned_duration', 'actual_duration', 'scope_change_count',
        'scope_change_pct', 'team_turnover_count', 'strategic_notes',
        'kg_events_summary',
    ]
    safe = _safe_context(context, expected_keys)
    prompt = CAUSE_OF_DEATH_PROMPT.format(**safe)
    raw = _call_gemini(user, prompt, 'simple', 'cause_of_death', board_id)
    return _safe_json(raw)


def extract_lessons(user, context, board_id=None):
    """Extract lessons learned. Uses gemini-2.5-flash (complex)."""
    expected_keys = [
        'project_name', 'cause_of_death', 'knowledge_graph_summary',
        'premortem_hits', 'scope_changes', 'positive_signals',
    ]
    safe = _safe_context(context, expected_keys)
    prompt = LESSONS_PROMPT.format(**safe)
    raw = _call_gemini(user, prompt, 'complex', 'lessons_extraction', board_id)
    return _safe_json(raw)


def generate_tags(user, context, board_id=None):
    """Generate search tags for a cemetery entry. Uses gemini-2.5-flash-lite."""
    expected_keys = ['project_name', 'project_description', 'cause_of_death', 'key_lessons']
    safe = _safe_context(context, expected_keys)
    prompt = TAGS_PROMPT.format(**safe)
    raw = _call_gemini(user, prompt, 'simple', 'cemetery_tags', board_id)
    return _safe_json(raw)


def generate_transition_memo(user, context, board_id=None):
    """Generate a transition memo for one team member. Uses gemini-2.5-flash-lite."""
    expected_keys = ['member_name', 'tasks_summary', 'role_name', 'project_name']
    safe = _safe_context(context, expected_keys)
    prompt = TRANSITION_MEMO_PROMPT.format(**safe)
    return _call_gemini(user, prompt, 'simple', 'transition_memo', board_id)
