"""
Celery task for AI-powered onboarding workspace generation.

Dispatched when a new user submits their organization goal.  Calls Gemini
to produce the full Goal → Missions → Strategies → Boards → Tasks hierarchy,
then stores the result in OnboardingWorkspacePreview for user review.

Routed to the 'summaries' queue alongside other AI tasks.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name='kanban.tasks.generate_workspace_from_goal_task',
    queue='summaries',
    max_retries=1,
    soft_time_limit=90,
    time_limit=120,
)
def generate_workspace_from_goal_task(self, user_id: int, goal_text: str):
    """
    Generate a complete workspace hierarchy from an organization goal.

    1. Calls Gemini via generate_workspace_from_goal()
    2. On success → stores JSON in OnboardingWorkspacePreview (status='ready')
    3. On failure → stores fallback workspace + error message (status='ready')
    4. Updates UserProfile.onboarding_status to 'workspace_generated'

    The user never gets stuck — if AI fails, the fallback template kicks in.
    """
    from django.contrib.auth.models import User
    from kanban.onboarding_models import OnboardingWorkspacePreview
    from kanban.utils.ai_utils import generate_workspace_from_goal, get_fallback_workspace

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error(f"Onboarding task: User {user_id} not found")
        return

    try:
        preview = OnboardingWorkspacePreview.objects.get(user=user)
    except OnboardingWorkspacePreview.DoesNotExist:
        logger.error(f"Onboarding task: No preview record for user {user_id}")
        return

    try:
        data = generate_workspace_from_goal(goal_text)

        if data:
            preview.generated_data = data
            preview.status = 'ready'
            preview.error_message = None
            preview.save(update_fields=['generated_data', 'status', 'error_message', 'updated_at'])
            logger.info(f"Workspace generated successfully for user {user.username}")
        else:
            # AI returned nothing — use fallback template
            logger.warning(f"AI returned empty result for user {user.username}, using fallback")
            preview.generated_data = get_fallback_workspace(goal_text)
            preview.status = 'ready'
            preview.error_message = 'AI generation returned empty — using template workspace.'
            preview.save(update_fields=['generated_data', 'status', 'error_message', 'updated_at'])

    except Exception as exc:
        logger.error(f"Workspace generation failed for user {user.username}: {exc}")
        # Use fallback so the user is never stuck
        try:
            preview.generated_data = get_fallback_workspace(goal_text)
            preview.status = 'ready'
            preview.error_message = f'AI generation failed — using template workspace. ({str(exc)[:200]})'
            preview.save(update_fields=['generated_data', 'status', 'error_message', 'updated_at'])
        except Exception as inner:
            logger.error(f"Even fallback save failed for user {user.username}: {inner}")
            preview.status = 'failed'
            preview.error_message = str(exc)[:500]
            preview.save(update_fields=['status', 'error_message', 'updated_at'])

    # Update profile status regardless of AI/fallback path
    try:
        profile = user.profile
        if profile.onboarding_status in ('goal_submitted', 'pending'):
            profile.onboarding_status = 'workspace_generated'
            profile.save(update_fields=['onboarding_status'])
    except Exception as e:
        logger.error(f"Failed to update profile onboarding_status: {e}")
