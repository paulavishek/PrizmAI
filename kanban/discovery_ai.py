"""
PrizmDiscovery AI Scoring Service.

Uses the same AIRouter / Gemini pattern as requirements/ai_analysis.py.
Two public methods:
  - score_idea(idea, organization)   — fills in impact/effort/confidence + reasoning
  - suggest_ideas_for_goal(goal, n)  — called during onboarding to seed inbox
"""
import json
import logging
import re
from typing import Dict, List, Optional

from django.utils import timezone

logger = logging.getLogger(__name__)


def apply_score_to_idea(idea, result: Dict) -> None:
    """
    Persist a DiscoveryAIScorer.score_idea() result onto a DiscoveryIdea.

    Shared by the on-demand scoring view (discovery_views.idea_ai_score) and
    the async form-submission scoring task (forms.tasks.score_form_idea) so
    both save paths can't drift apart.
    """
    idea.ai_score_impact = result['impact']
    idea.ai_score_effort = result['effort']
    idea.ai_score_confidence = result['confidence']
    idea.ai_score_recommendation = result.get('recommendation', '')
    idea.ai_score_reasoning = result.get('reasoning', '')
    idea.ai_scored_at = timezone.now()
    idea.save(update_fields=[
        'ai_score_impact', 'ai_score_effort', 'ai_score_confidence',
        'ai_score_recommendation', 'ai_score_reasoning', 'ai_scored_at', 'updated_at',
    ])


class DiscoveryAIScorer:
    """AI-powered scoring for PrizmDiscovery ideas."""

    # ── Public API ──────────────────────────────────────────────────

    def score_idea(self, idea, organization) -> Dict:
        """
        Score a DiscoveryIdea on impact, effort, and confidence (0–100 each).

        Returns a dict with keys:
            impact, effort, confidence, recommendation, reasoning, success
        Does NOT write to the model — the caller is responsible for saving.
        Falls back to rule-based estimates on Gemini failure.
        """
        prompt = self._build_score_prompt(idea, organization)
        response = self._call_gemini(prompt, cache_operation='discovery_score',
                                     context_id=f'idea_{idea.pk}')
        if response:
            parsed = self._parse_score_response(response)
            if parsed:
                return {**parsed, 'success': True}

        return self._fallback_score(idea)

    def suggest_ideas_for_goal(self, goal_text: str, n: int = 4) -> List[Dict]:
        """
        Generate n seed idea dicts for the PrizmDiscovery inbox, based on
        the goal text entered during onboarding.

        Returns a list of dicts with keys: title, description, source.
        Returns an empty list on failure — never raises.
        """
        if not goal_text or not goal_text.strip():
            return []
        prompt = self._build_seeding_prompt(goal_text, n)
        response = self._call_gemini(prompt, cache_operation='discovery_seed',
                                     context_id=None)
        if response:
            ideas = self._parse_seeding_response(response)
            if ideas:
                return ideas[:n]
        return []

    # ── Prompt Builders ─────────────────────────────────────────────

    def _build_score_prompt(self, idea, organization) -> str:
        org_name = getattr(organization, 'name', 'this organisation')
        return f"""You are an expert product strategist. Evaluate the following product idea for {org_name}.

IDEA TITLE: {idea.title}
IDEA DESCRIPTION: {idea.description or '(no description provided)'}
SOURCE: {idea.get_source_display()}

Score the idea on three dimensions (0–100 each):
1. Impact (0=no value, 100=transformative value): How much value would this deliver if built?
2. Effort (0=trivial, 100=enormous effort): How much implementation effort is required?
3. Confidence (0=very uncertain, 100=highly certain): How confident are you in these scores given the available information?

Then provide:
- A one-sentence recommendation (max 120 chars).
- A 2–4 sentence reasoning that explains your scores (shown to the user as Explainable AI).

Return ONLY valid JSON (no markdown fences):
{{
  "impact": <0-100>,
  "effort": <0-100>,
  "confidence": <0-100>,
  "recommendation": "<one sentence>",
  "reasoning": "<2-4 sentences>"
}}"""

    def _build_seeding_prompt(self, goal_text: str, n: int) -> str:
        return f"""You are a product strategist helping a team seed their product discovery inbox.

ORGANISATIONAL GOAL: {goal_text}

Generate exactly {n} product idea suggestions that this team should evaluate before committing to development.
Each idea should be a distinct opportunity — not a task, but a strategic direction worth investigating.
Use varied sources (customer feedback, market research, internal brainstorm, etc.).

Return ONLY valid JSON array (no markdown fences):
[
  {{
    "title": "<short idea title, max 80 chars>",
    "description": "<1-2 sentence description of what this idea is and why it matters>",
    "source": "<one of: customer_feedback | internal_brainstorm | market_research | user_feedback | sales_team | finance_team | other>"
  }}
]"""

    # ── Gemini Caller ───────────────────────────────────────────────

    def _call_gemini(self, prompt: str, cache_operation: str,
                     context_id: Optional[str]) -> Optional[str]:
        ai_cache = self._get_ai_cache()
        if ai_cache:
            cached = ai_cache.get(prompt, cache_operation, context_id)
            if cached:
                logger.debug("Discovery AI cache HIT for %s", cache_operation)
                return cached

        try:
            from django.conf import settings
            if (not getattr(settings, 'GEMINI_API_KEY', None)
                    and not getattr(settings, 'OPENAI_API_KEY', None)
                    and not getattr(settings, 'ANTHROPIC_API_KEY', None)):
                logger.error("No AI API key configured")
                return None

            from ai_assistant.utils.ai_router import AIRouter
            router = AIRouter()
            result = router.complete(
                prompt=prompt,
                user=None,
                complexity='complex',
            )['text']

            if result:
                if ai_cache:
                    ai_cache.set(prompt, result, cache_operation, context_id)
                return result
            return None
        except Exception as exc:
            logger.error("Discovery AI call failed: %s", exc)
            return None

    @staticmethod
    def _get_ai_cache():
        try:
            from kanban_board.ai_cache import AIResponseCache
            return AIResponseCache()
        except Exception:
            return None

    # ── Response Parsers ────────────────────────────────────────────

    def _extract_json(self, text: str):
        """Extract JSON object or array from AI response, handling fences."""
        if not text:
            return None
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            # Try to find the first JSON structure in the text
            match = re.search(r'(\{[\s\S]*\}|\[[\s\S]*\])', text)
            if match:
                try:
                    return json.loads(match.group())
                except (json.JSONDecodeError, ValueError):
                    pass
        return None

    def _parse_score_response(self, response: str) -> Optional[Dict]:
        data = self._extract_json(response)
        if not isinstance(data, dict):
            return None
        impact = data.get('impact')
        effort = data.get('effort')
        confidence = data.get('confidence')
        if not all(isinstance(v, (int, float)) and 0 <= v <= 100
                   for v in [impact, effort, confidence]):
            return None
        return {
            'impact': int(impact),
            'effort': int(effort),
            'confidence': int(confidence),
            'recommendation': str(data.get('recommendation', ''))[:500],
            'reasoning': str(data.get('reasoning', '')),
        }

    def _parse_seeding_response(self, response: str) -> Optional[List[Dict]]:
        data = self._extract_json(response)
        if not isinstance(data, list):
            return None
        valid_sources = {
            'customer_feedback', 'internal_brainstorm', 'market_research',
            'user_feedback', 'sales_team', 'finance_team', 'other',
        }
        result = []
        for item in data:
            if not isinstance(item, dict):
                continue
            title = str(item.get('title', '')).strip()[:255]
            description = str(item.get('description', '')).strip()
            source = str(item.get('source', 'other')).strip()
            if source not in valid_sources:
                source = 'other'
            if title:
                result.append({'title': title, 'description': description, 'source': source})
        return result if result else None

    # ── Fallback ────────────────────────────────────────────────────

    @staticmethod
    def _fallback_score(idea) -> Dict:
        """
        Rule-based fallback when Gemini is unavailable.
        Produces conservative mid-range scores with a clear caveat.
        """
        return {
            'impact': 50,
            'effort': 50,
            'confidence': 30,
            'recommendation': 'AI scoring unavailable — please review manually.',
            'reasoning': (
                'Spectra could not connect to the AI engine when this idea was scored. '
                'The placeholder scores above (50/50/30) are defaults, not real estimates. '
                'Re-run scoring once connectivity is restored.'
            ),
            'success': False,
        }
