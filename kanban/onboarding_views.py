"""
Views for the AI-powered onboarding flow (v2).

URL prefix: /onboarding/
All views require @login_required.
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from kanban.onboarding_models import OnboardingWorkspacePreview
from kanban.onboarding_utils import commit_onboarding_workspace

logger = logging.getLogger(__name__)

MIN_GOAL_CHARS = 30


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_profile(request):
    """Return the UserProfile, creating one if somehow missing."""
    from accounts.models import UserProfile
    try:
        return request.user.profile
    except UserProfile.DoesNotExist:
        return UserProfile.objects.create(
            user=request.user,
            is_admin=False,
            completed_wizard=True,
            onboarding_version=2,
            onboarding_status='pending',
        )


def _is_v2(profile):
    return profile.onboarding_version >= 2


# ---------------------------------------------------------------------------
# Welcome
# ---------------------------------------------------------------------------

@login_required
def onboarding_welcome(request):
    """
    GET /onboarding/
    Show the welcome screen with three choices:
      - Set up my workspace
      - Show me a demo first
      - Skip
    Redirect to dashboard if already past onboarding.
    """
    profile = _get_profile(request)

    if profile.onboarding_status in ('completed', 'skipped'):
        return redirect('dashboard')

    # Resume mid-flow states
    if profile.onboarding_status == 'goal_submitted':
        return redirect('onboarding_generating')
    if profile.onboarding_status == 'workspace_generated':
        return redirect('onboarding_review')

    return render(request, 'kanban/onboarding/welcome.html')


# ---------------------------------------------------------------------------
# Goal Input
# ---------------------------------------------------------------------------

@login_required
def onboarding_goal_input(request):
    """
    GET  /onboarding/goal/ — render goal input form
    POST /onboarding/goal/ — validate, create preview, dispatch Celery task
    """
    profile = _get_profile(request)

    if not _is_v2(profile):
        return redirect('dashboard')

    if request.method == 'GET':
        # Pre-fill with previous goal text if resuming
        prefill = request.GET.get('goal', '') or (profile.onboarding_goal_text or '')
        return render(request, 'kanban/onboarding/goal_input.html', {
            'prefill_goal': prefill,
        })

    # POST — submit goal
    goal_text = (request.POST.get('goal_text', '') or '').strip()
    if len(goal_text) < MIN_GOAL_CHARS:
        return render(request, 'kanban/onboarding/goal_input.html', {
            'prefill_goal': goal_text,
            'error': f'Please enter at least {MIN_GOAL_CHARS} characters.',
        })

    # Save goal text on profile
    profile.onboarding_goal_text = goal_text
    profile.onboarding_status = 'goal_submitted'
    profile.save(update_fields=['onboarding_goal_text', 'onboarding_status'])

    # Create or replace preview
    preview, _created = OnboardingWorkspacePreview.objects.update_or_create(
        user=request.user,
        defaults={
            'goal_text': goal_text,
            'generated_data': {},
            'edited_data': None,
            'status': 'generating',
            'error_message': None,
        },
    )

    # Dispatch Celery task
    from kanban.tasks.onboarding_tasks import generate_workspace_from_goal_task
    try:
        result = generate_workspace_from_goal_task.delay(request.user.id, goal_text)
        preview.celery_task_id = result.id
        preview.save(update_fields=['celery_task_id'])
    except Exception as exc:
        # Celery broker down — run synchronously as fallback
        logger.warning(f"Celery dispatch failed, running synchronously: {exc}")
        try:
            generate_workspace_from_goal_task(request.user.id, goal_text)
        except Exception as sync_exc:
            logger.error(f"Synchronous workspace generation failed: {sync_exc}")
            # The task itself handles fallback, so preview should be 'ready'
            # If even that fails, mark failed
            preview.refresh_from_db()
            if preview.status == 'generating':
                from kanban.utils.ai_utils import get_fallback_workspace
                preview.generated_data = get_fallback_workspace(goal_text)
                preview.status = 'ready'
                preview.error_message = 'Could not reach AI service — using template workspace.'
                preview.save(update_fields=['generated_data', 'status', 'error_message', 'updated_at'])

    return redirect('onboarding_generating')


# ---------------------------------------------------------------------------
# Generating (loading screen)
# ---------------------------------------------------------------------------

@login_required
def onboarding_generating(request):
    """
    GET /onboarding/generating/
    Show the animated loading page. If preview is already ready, redirect.
    """
    try:
        preview = OnboardingWorkspacePreview.objects.get(user=request.user)
    except OnboardingWorkspacePreview.DoesNotExist:
        return redirect('onboarding_goal')

    if preview.status == 'ready':
        return redirect('onboarding_review')
    if preview.status == 'committed':
        return redirect('dashboard')

    profile = _get_profile(request)
    return render(request, 'kanban/onboarding/generating.html', {
        'goal_text': preview.goal_text,
    })


# ---------------------------------------------------------------------------
# Status (AJAX polling)
# ---------------------------------------------------------------------------

@login_required
@require_GET
def onboarding_status(request):
    """
    GET /onboarding/status/
    Returns JSON: {"status": "generating|ready|failed", "error": "..."}
    """
    try:
        preview = OnboardingWorkspacePreview.objects.get(user=request.user)
    except OnboardingWorkspacePreview.DoesNotExist:
        return JsonResponse({'status': 'failed', 'error': 'No workspace generation in progress.'})

    resp = {'status': preview.status}
    if preview.status == 'failed' and preview.error_message:
        resp['error'] = preview.error_message
    return JsonResponse(resp)


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------

@login_required
def onboarding_review(request):
    """
    GET /onboarding/review/
    Show the review page with the generated hierarchy.
    """
    try:
        preview = OnboardingWorkspacePreview.objects.get(user=request.user)
    except OnboardingWorkspacePreview.DoesNotExist:
        return redirect('onboarding_goal')

    if preview.status == 'generating':
        return redirect('onboarding_generating')
    if preview.status == 'committed':
        return redirect('dashboard')

    data = preview.edited_data if preview.edited_data else preview.generated_data

    return render(request, 'kanban/onboarding/review.html', {
        'preview': preview,
        'data': data,
        'data_json': json.dumps(data),
    })


# ---------------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------------

@login_required
@require_POST
def onboarding_commit(request):
    """
    POST /onboarding/commit/
    Materialise the workspace hierarchy into real DB objects.
    """
    try:
        preview = OnboardingWorkspacePreview.objects.get(user=request.user)
    except OnboardingWorkspacePreview.DoesNotExist:
        return redirect('onboarding_goal')

    if preview.status == 'committed':
        return redirect('dashboard')

    # Capture edits from the review form
    edited_json = request.POST.get('edited_data', '').strip()
    if edited_json:
        try:
            preview.edited_data = json.loads(edited_json)
            preview.save(update_fields=['edited_data', 'updated_at'])
        except json.JSONDecodeError:
            logger.warning("Could not parse edited_data JSON — using generated_data")

    try:
        commit_onboarding_workspace(request.user, preview)
    except Exception as exc:
        logger.error(f"Failed to commit onboarding workspace: {exc}")
        return render(request, 'kanban/onboarding/review.html', {
            'preview': preview,
            'data': preview.edited_data or preview.generated_data,
            'data_json': json.dumps(preview.edited_data or preview.generated_data),
            'commit_error': 'Something went wrong while creating your workspace. Please try again.',
        })

    return redirect('dashboard')


# ---------------------------------------------------------------------------
# Start Over
# ---------------------------------------------------------------------------

@login_required
@require_POST
def onboarding_start_over(request):
    """
    POST /onboarding/start-over/
    Delete current preview and redirect to goal input with previous text.
    """
    profile = _get_profile(request)

    if not _is_v2(profile):
        return redirect('dashboard')

    previous_goal = profile.onboarding_goal_text or ''

    OnboardingWorkspacePreview.objects.filter(user=request.user).delete()

    profile.onboarding_status = 'pending'
    profile.save(update_fields=['onboarding_status'])

    return redirect(f'/onboarding/goal/?goal={previous_goal[:500]}')


# ---------------------------------------------------------------------------
# Skip
# ---------------------------------------------------------------------------

@login_required
@require_POST
def onboarding_skip(request):
    """
    POST /onboarding/skip/
    Skip the onboarding flow entirely — land on a clean dashboard.
    """
    profile = _get_profile(request)

    if not _is_v2(profile):
        return redirect('dashboard')

    profile.onboarding_status = 'skipped'
    profile.save(update_fields=['onboarding_status'])
    return redirect('dashboard')


# ---------------------------------------------------------------------------
# Explore Demo
# ---------------------------------------------------------------------------

@login_required
@require_POST
def onboarding_explore_demo(request):
    """
    POST /onboarding/demo/
    Toggle into demo-viewing mode and redirect to dashboard.
    """
    profile = _get_profile(request)

    if not _is_v2(profile):
        return redirect('dashboard')

    profile.is_viewing_demo = True
    if profile.onboarding_status == 'pending':
        profile.onboarding_status = 'demo_exploring'
    profile.save(update_fields=['is_viewing_demo', 'onboarding_status'])
    return redirect('dashboard')
