"""
Spectra Context Router — decides which context providers to activate.

Replaces the 30+ ``_is_*_query()`` keyword methods with a two-tier system:

Tier 1 (fast, always):  Keyword matching against provider FEATURE_TAGS.
Tier 2 (smart, on-demand):  Gemini Flash classification for ambiguous queries.

The router NEVER blocks the response — if Gemini is down, keyword matching
still works.  If keywords match nothing, ALL providers get their summaries
included anyway (via the registry's get_all_summaries).

Created: April 16, 2026 — Spectra Context Provider Overhaul
"""

import json
import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)

# Maximum providers to include full detail for (prevents token explosion)
MAX_DETAIL_PROVIDERS = 5

# Minimum total keyword-match score before we skip the AI classifier.
# Below this, run the AI classifier as a second opinion even if 2+ providers
# matched on keywords — short queries with weak signal often need the AI to
# resolve ambiguity (e.g. "what's the status?" can mean tasks OR commitments).
AI_FALLBACK_SCORE_THRESHOLD = 8

# Long queries usually span multiple features; always consult the AI classifier
# so we don't miss a provider just because one keyword dominated the score.
LONG_QUERY_WORD_THRESHOLD = 12


def route_query(query, provider_tags, use_ai=True):
    """
    Given a user query and the available provider tag map, return a list
    of provider names that should provide detailed context.

    Args:
        query:          User's natural language question.
        provider_tags:  Dict {provider_name: [tag1, tag2, ...]} from registry.
        use_ai:         Whether to attempt AI-based routing (True by default).

    Returns:
        list of provider names (strings) that should be queried for detail.
    """
    # ── Tier 1: keyword matching (scored) ───────────────────────────────
    keyword_matches, total_score = _keyword_match(query, provider_tags)

    word_count = len(query.split())
    needs_ai_second_opinion = (
        total_score < AI_FALLBACK_SCORE_THRESHOLD
        or word_count >= LONG_QUERY_WORD_THRESHOLD
        or len(keyword_matches) <= 1
    )

    if not needs_ai_second_opinion or not use_ai:
        # Strong, focused keyword signal — trust it.
        return keyword_matches[:MAX_DETAIL_PROVIDERS]

    # ── Tier 2: AI classification (weak signal OR long query) ───────────
    ai_matches = _ai_classify(query, provider_tags)
    if ai_matches:
        # Merge AI picks with any strong keyword matches so we don't lose
        # ground truth when the AI is over-eager. Keyword picks come first.
        merged = list(dict.fromkeys(keyword_matches + ai_matches))
        return merged[:MAX_DETAIL_PROVIDERS]

    # If AI returns nothing, fall back to keyword matches (even if just 1)
    if keyword_matches:
        return keyword_matches[:MAX_DETAIL_PROVIDERS]

    # No match at all — the always-on summaries will still be included
    return []


# ── Tier 1: keyword matching ────────────────────────────────────────────────

def _keyword_match(query, provider_tags):
    """
    Score each provider by how many of its tags appear in the query.
    Returns (ranked_provider_names, total_score_across_all_providers).
    Callers use the total score to decide whether the signal is strong
    enough to skip the AI classifier.
    """
    query_lower = query.lower()
    scores = {}

    for provider_name, tags in provider_tags.items():
        score = 0
        for tag in tags:
            tag_lower = tag.lower()
            # Exact substring match
            if tag_lower in query_lower:
                # Longer tags get more weight (more specific)
                score += len(tag_lower)
            # Word boundary match for short tags (avoid false positives)
            elif len(tag_lower) <= 4 and re.search(r'\b' + re.escape(tag_lower) + r'\b', query_lower):
                score += len(tag_lower)

        if score > 0:
            scores[provider_name] = score

    # Sort by score descending
    ranked = sorted(scores.keys(), key=lambda n: scores[n], reverse=True)
    total_score = sum(scores.values())
    return ranked, total_score


# ── Tier 2: AI-based classification ─────────────────────────────────────────

def _ai_classify(query, provider_tags):
    """
    Use Gemini Flash to classify which providers are relevant.
    Returns list of provider names or empty list on failure.
    """
    try:
        from ai_assistant.utils.ai_router import AIRouter
        router = AIRouter()

        provider_list = '\n'.join(
            f'- {name}: {", ".join(tags[:8])}'
            for name, tags in provider_tags.items()
        )

        system_prompt = (
            'You are a query classifier for a project management AI assistant. '
            'Given a user query and a list of data providers, return a JSON array '
            'of provider names that should be activated to answer the query.\n\n'
            'Rules:\n'
            '- Return 1-5 provider names, most relevant first.\n'
            '- Only include providers whose data is needed to answer the query.\n'
            '- Always include "Board Tasks" for task-related questions.\n'
            '- Always include "Cross-Board Aggregate" for dashboard/overview questions.\n'
            '- Return ONLY valid JSON: ["Provider1", "Provider2"]\n\n'
            f'Available providers:\n{provider_list}'
        )

        response = router.complete(
            query,
            user=None,
            system_prompt=system_prompt,
            complexity='simple',
        )

        if response and response.get('text'):
            content = response['text'].strip()
            # Extract JSON array from response
            match = re.search(r'\[.*?\]', content, re.DOTALL)
            if match:
                names = json.loads(match.group())
                # Validate names against known providers
                valid = [n for n in names if n in provider_tags]
                if valid:
                    logger.debug('AI router selected: %s', valid)
                    return valid

    except Exception as e:
        logger.debug('AI routing failed (falling back to keywords): %s', e)

    return []


# ── Query type classification (for temperature selection) ────────────────────

def classify_query_type(query):
    """
    Classify query for temperature selection. Replaces the old
    classify_spectra_query() function with a simpler, more robust version.

    Returns dict with 'type' and 'temperature'.
    """
    q = query.lower().strip()

    # Data retrieval — needs accuracy
    if any(kw in q for kw in [
        'how many', 'count', 'list', 'who is', 'what is', 'show me',
        'assigned to', 'due', 'overdue', 'status', 'total',
    ]):
        return {'type': 'data_retrieval', 'temperature': 0.3}

    # Analysis — consistent insights
    if any(kw in q for kw in [
        'analyze', 'analysis', 'trend', 'compare', 'risk', 'why',
        'recommend', 'suggest', 'improve', 'bottleneck', 'forecast',
    ]):
        return {'type': 'analysis', 'temperature': 0.4}

    # Action requests — precise
    if any(kw in q for kw in [
        'create', 'update', 'delete', 'move', 'assign', 'change',
        'add', 'remove', 'set', 'mark',
    ]):
        return {'type': 'action', 'temperature': 0.3}

    # Help — clear guidance
    if any(kw in q for kw in [
        'how do', 'how to', 'explain', 'help', 'guide', 'tutorial',
        'what does', 'where is', 'can i',
    ]):
        return {'type': 'help', 'temperature': 0.5}

    # Default — conversational. Kept low (0.4) on purpose: Spectra is a
    # data-grounded assistant, not a brainstorm partner. High temperature
    # encourages Gemini to fill gaps with plausible-sounding training data,
    # which is the exact failure mode this overhaul targets.
    return {'type': 'conversational', 'temperature': 0.4}
