"""
Async Spectra scoring for Discovery ideas created via a Forms submission.

Auto-scoring on submit is the payoff of the Forms -> Discovery pipeline (the
PM "wakes up to a pre-evaluated matrix" instead of a raw list). This task
runs the exact same DiscoveryAIScorer used by the on-demand
kanban.discovery_views.idea_ai_score view, just off the request thread.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def score_form_idea(idea_id):
    from kanban.discovery_ai import DiscoveryAIScorer, apply_score_to_idea
    from kanban.discovery_models import DiscoveryIdea

    try:
        idea = DiscoveryIdea.objects.select_related('organization').get(pk=idea_id)
    except DiscoveryIdea.DoesNotExist:
        logger.warning('score_form_idea: idea %s no longer exists', idea_id)
        return

    if idea.is_scored:
        return  # already scored — avoid clobbering a manual score with a race

    scorer = DiscoveryAIScorer()
    result = scorer.score_idea(idea, idea.organization)
    apply_score_to_idea(idea, result)
