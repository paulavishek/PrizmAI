# kanban/stakeholder_ai.py
"""
AI-powered stakeholder relevance suggestions for a task.

Replaces the old client-side keyword heuristic (which forced any
high-influence/high-interest stakeholder into the results even with zero
textual connection to the task). A deterministic scorer narrows the board's
roster to a shortlist, then an AIRouter call reasons over that shortlist to
produce genuine per-stakeholder relevance and justification tied to the
task's actual content. If the AI call fails, the deterministic scorer's
list is returned on its own (with the same "no forced inclusion" rule) so
the feature degrades gracefully instead of erroring out.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)

MARKETING_KEYWORDS = ['marketing', 'campaign', 'social', 'brand', 'content', 'promotion', 'advertising', 'launch', 'announce']
TECHNICAL_KEYWORDS = ['development', 'api', 'code', 'bug', 'feature', 'technical', 'software', 'database', 'server', 'deploy', 'integration']
DESIGN_KEYWORDS = ['design', 'ui', 'ux', 'interface', 'visual', 'mockup', 'prototype', 'wireframe', 'layout']
MANAGEMENT_KEYWORDS = ['review', 'approve', 'budget', 'timeline', 'schedule', 'milestone', 'strategic', 'planning']
DATA_KEYWORDS = ['data', 'analytics', 'report', 'metrics', 'dashboard', 'analysis', 'insight']

MAX_AI_CANDIDATES = 15


def score_stakeholders_deterministic(task, stakeholders):
    """
    Score stakeholders against a task's content and attributes.

    Returns a list of {"stakeholder", "score", "reason"} dicts, sorted by
    score descending, with score == 0 entries excluded. A stakeholder with
    no genuine textual connection to the task is never force-included just
    for having high influence/interest.
    """
    combined_text = f"{(task.title or '').lower()} {(task.description or '').lower()}"
    priority = (task.priority or '').lower()

    scored = []
    for sh in stakeholders:
        context = ' '.join(filter(None, [
            (sh.role or '').lower(),
            (sh.organization or '').lower(),
            (sh.notes or '').lower(),
        ]))

        score = 0
        reasons = []

        if any(kw in combined_text for kw in MARKETING_KEYWORDS) and any(t in context for t in ('marketing', 'brand', 'content')):
            score += 3
            reasons.append('Marketing-related expertise aligns with task scope')
        if any(kw in combined_text for kw in TECHNICAL_KEYWORDS) and any(t in context for t in ('develop', 'engineer', 'technical', 'software')):
            score += 3
            reasons.append('Technical expertise relevant to task requirements')
        if any(kw in combined_text for kw in DESIGN_KEYWORDS) and any(t in context for t in ('design', 'ux', 'ui')):
            score += 3
            reasons.append('Design expertise matches task needs')
        if any(kw in combined_text for kw in MANAGEMENT_KEYWORDS) and any(t in context for t in ('manager', 'director', 'lead')):
            score += 2
            reasons.append('Management oversight may be required')
        if any(kw in combined_text for kw in DATA_KEYWORDS) and any(t in context for t in ('data', 'analyst', 'analytics')):
            score += 3
            reasons.append('Data/analytics expertise relevant to task')

        if sh.influence_level == 'high' and priority in ('urgent', 'high'):
            score += 2
            reasons.append('High-influence stakeholder for a high-priority task')
        if sh.interest_level == 'high':
            score += 1
            reasons.append('High interest in project outcomes')

        if score > 0:
            scored.append({
                'stakeholder': sh,
                'score': score,
                'reason': reasons[0] if reasons else 'Relevant to project scope',
            })

    scored.sort(key=lambda entry: entry['score'], reverse=True)
    return scored


def _relevance_tier(score):
    if score >= 3:
        return 'high'
    if score >= 2:
        return 'medium'
    return 'low'


def _deterministic_suggestions(scored):
    suggestions = []
    for entry in scored[:5]:
        sh = entry['stakeholder']
        suggestions.append({
            'id': sh.id,
            'name': sh.name,
            'role': sh.role,
            'organization': sh.organization,
            'relevance': _relevance_tier(entry['score']),
            'reason': entry['reason'],
            'quadrant': sh.get_quadrant(),
        })
    return suggestions


def _build_stakeholder_suggestion_prompt(task, candidates):
    board = task.column.board
    task_lines = [
        f"Title: {task.title}",
        f"Description: {task.description or '(none)'}",
        f"Priority: {task.priority or 'medium'}",
        f"Board: {board.name}",
        f"Column/status: {task.column.name}",
    ]
    if task.due_date:
        task_lines.append(f"Due date: {task.due_date.strftime('%Y-%m-%d')}")
    if task.phase:
        task_lines.append(f"Phase: {task.phase}")

    candidate_lines = []
    for entry in candidates:
        sh = entry['stakeholder']
        candidate_lines.append(
            f"- id={sh.id} | name={sh.name} | role={sh.role} | organization={sh.organization or 'n/a'} | "
            f"influence={sh.influence_level} | interest={sh.interest_level} | "
            f"current_engagement={sh.get_current_engagement_display()} | "
            f"desired_engagement={sh.get_desired_engagement_display()} | "
            f"quadrant={sh.get_quadrant()} | notes={sh.notes or '(none)'}"
        )

    return f"""You are a project stakeholder analyst. Given a task and a list of candidate stakeholders, decide which stakeholders are genuinely relevant to THIS SPECIFIC task.

## Task
{chr(10).join(task_lines)}

## Candidate stakeholders
{chr(10).join(candidate_lines)}

## Instructions
- Only include a stakeholder if there is a genuine, specific connection between the task's content and that stakeholder's role, organization, or notes.
- Do NOT include a stakeholder solely because they have high influence or high interest with no substantive connection to this task's content — that is the exact mistake to avoid.
- It is correct and expected to return fewer than 5 results, or zero, if few or no candidates are truly relevant.
- Each "reason" must cite at least one concrete detail from the task AND one concrete detail (role/organization/notes) from the stakeholder — no generic language like "key stakeholder should be kept informed".

Return ONLY a JSON array, one object per relevant stakeholder, in this exact shape:
[
  {{
    "stakeholder_id": 12,
    "relevance": "high|medium|low",
    "reason": "One or two sentences citing specific task content and specific stakeholder attributes."
  }}
]
"""


def _extract_json_array(text):
    """Extract a JSON array from an AI response, tolerating markdown fences."""
    if not text:
        raise ValueError('Empty response')
    fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    candidate = fence_match.group(1).strip() if fence_match else text.strip()
    arr_match = re.search(r'(\[.*\])', candidate, re.DOTALL)
    if arr_match:
        candidate = arr_match.group(1)
    return json.loads(candidate)


def suggest_stakeholders_for_task(task, stakeholders):
    """
    Return AI-driven stakeholder suggestions for a task.

    Returns {"suggestions": [...], "degraded": bool, "from_cache": bool}.
    Falls back to the deterministic scorer alone (never the old "force
    relevant regardless of content" behavior) if the AI call or response
    parsing fails. ``from_cache`` tells the caller whether a live AI call
    was actually made, so quota is only consumed on genuine calls.
    """
    stakeholders = list(stakeholders)
    scored = score_stakeholders_deterministic(task, stakeholders)
    if not scored:
        # No keyword/attribute signal at all — still give the AI a look at
        # the active roster in case it spots a connection the deterministic
        # pass missed, bounded to keep the prompt small.
        scored = [
            {'stakeholder': sh, 'score': 0, 'reason': 'Relevant to project scope'}
            for sh in stakeholders[:MAX_AI_CANDIDATES]
        ]

    candidates = scored[:MAX_AI_CANDIDATES]
    if not candidates:
        return {'suggestions': [], 'degraded': False, 'from_cache': False}

    from kanban_board.ai_cache import ai_cache_manager
    from ai_assistant.utils.ai_router import AIRouter, AIProviderError

    prompt = _build_stakeholder_suggestion_prompt(task, candidates)
    context_id = f"task_{task.id}"
    by_id = {entry['stakeholder'].id: entry for entry in candidates}

    cached = ai_cache_manager.get(prompt, 'stakeholder_suggestion', context_id)
    if cached:
        try:
            return {'suggestions': json.loads(cached), 'degraded': False, 'from_cache': True}
        except (json.JSONDecodeError, TypeError):
            pass

    try:
        router = AIRouter()
        result = router.complete(prompt=prompt, user=None, complexity='simple')['text']
        parsed = _extract_json_array(result)

        suggestions = []
        for item in parsed:
            entry = by_id.get(item.get('stakeholder_id'))
            if not entry:
                continue
            sh = entry['stakeholder']
            suggestions.append({
                'id': sh.id,
                'name': sh.name,
                'role': sh.role,
                'organization': sh.organization,
                'relevance': item.get('relevance', 'low'),
                'reason': item.get('reason', ''),
                'quadrant': sh.get_quadrant(),
            })

        ai_cache_manager.set(prompt, json.dumps(suggestions), 'stakeholder_suggestion', context_id)
        return {'suggestions': suggestions, 'degraded': False, 'from_cache': False}
    except (AIProviderError, ValueError, json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"Stakeholder AI suggestion failed, using deterministic fallback: {e}")
        return {'suggestions': _deterministic_suggestions(scored), 'degraded': True, 'from_cache': False}
