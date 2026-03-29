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
from kanban.decorators import demo_write_guard, demo_ai_guard

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

    # Resume mid-flow states
    if profile.onboarding_status == 'goal_submitted':
        return redirect('onboarding_generating')
    if profile.onboarding_status == 'workspace_generated':
        return redirect('onboarding_review')

    from_dashboard = request.GET.get('from') == 'dashboard'
    return render(request, 'kanban/onboarding/welcome.html', {'from_dashboard': from_dashboard})


# ---------------------------------------------------------------------------
# Goal Input
# ---------------------------------------------------------------------------

@login_required
@demo_ai_guard
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

    # Dispatch Celery task (with short broker connect timeout so the user
    # isn't left waiting 60+ seconds when Redis is down).
    from kanban.tasks.onboarding_tasks import generate_workspace_from_goal_task
    try:
        result = generate_workspace_from_goal_task.apply_async(
            args=[request.user.id, goal_text],
            retry=False,                          # Don't auto-retry dispatch
            connect_timeout=5,                     # Fail fast if broker is unreachable
        )
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

    # If stuck generating for too long when user (re)loads this page, recover
    from django.utils import timezone
    STALE_THRESHOLD_SECONDS = 120  # 2 minutes
    if preview.status == 'generating':
        age = (timezone.now() - preview.updated_at).total_seconds()
        if age > STALE_THRESHOLD_SECONDS:
            logger.warning(
                f"Stale preview on page load for {request.user.username} "
                f"(age={age:.0f}s) — recovering"
            )
            _recover_stale_preview(preview)
            preview.refresh_from_db()
            if preview.status == 'ready':
                return redirect('onboarding_review')

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

    Includes stale-generation recovery: if the preview has been stuck at
    'generating' for more than STALE_THRESHOLD seconds, re-dispatch the
    Celery task or fall back to a template workspace.
    """
    from django.utils import timezone

    STALE_THRESHOLD_SECONDS = 120  # 2 minutes

    try:
        preview = OnboardingWorkspacePreview.objects.get(user=request.user)
    except OnboardingWorkspacePreview.DoesNotExist:
        return JsonResponse({'status': 'failed', 'error': 'No workspace generation in progress.'})

    # --- Stale-generation recovery ---
    if preview.status == 'generating':
        age = (timezone.now() - preview.updated_at).total_seconds()
        if age > STALE_THRESHOLD_SECONDS:
            logger.warning(
                f"Stale onboarding preview for {request.user.username} "
                f"(age={age:.0f}s) — attempting recovery"
            )
            _recover_stale_preview(preview)
            preview.refresh_from_db()

    resp = {'status': preview.status}
    if preview.status == 'failed' and preview.error_message:
        resp['error'] = preview.error_message
    return JsonResponse(resp)


# ---------------------------------------------------------------------------
# Stale preview recovery helper
# ---------------------------------------------------------------------------

def _recover_stale_preview(preview):
    """
    Attempt to re-dispatch a stuck 'generating' preview.

    Try Celery first; if the broker is unreachable, generate synchronously;
    if even that fails, use the static fallback template so the user is
    never stuck forever.
    """
    from kanban.tasks.onboarding_tasks import generate_workspace_from_goal_task
    from kanban.utils.ai_utils import get_fallback_workspace

    # 1. Try re-dispatching via Celery
    try:
        result = generate_workspace_from_goal_task.delay(
            preview.user_id, preview.goal_text
        )
        preview.celery_task_id = result.id
        # Reset updated_at so the stale check doesn't fire again immediately
        preview.save(update_fields=['celery_task_id', 'updated_at'])
        logger.info(f"Re-dispatched workspace task for user {preview.user.username}")
        return
    except Exception as exc:
        logger.warning(f"Celery re-dispatch failed: {exc}")

    # 2. Try synchronous generation
    try:
        generate_workspace_from_goal_task(preview.user_id, preview.goal_text)
        return
    except Exception as exc:
        logger.warning(f"Synchronous recovery failed: {exc}")

    # 3. Last resort — static fallback template
    try:
        preview.generated_data = get_fallback_workspace(preview.goal_text)
        preview.status = 'ready'
        preview.error_message = (
            'AI generation timed out — using a template workspace. '
            'You can customise everything on the next screen.'
        )
        preview.save(update_fields=[
            'generated_data', 'status', 'error_message', 'updated_at',
        ])
        logger.info(f"Fallback workspace applied for user {preview.user.username}")
    except Exception as inner:
        logger.error(f"Even fallback failed for user {preview.user.username}: {inner}")
        preview.status = 'failed'
        preview.error_message = 'Workspace generation failed. Please try again.'
        preview.save(update_fields=['status', 'error_message', 'updated_at'])


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------

@login_required
def onboarding_review(request):
    """
    GET /onboarding/review/
    Show the review page with the generated hierarchy.
    """
    from django.utils import timezone
    import datetime

    try:
        preview = OnboardingWorkspacePreview.objects.get(user=request.user)
    except OnboardingWorkspacePreview.DoesNotExist:
        return redirect('onboarding_goal')

    if preview.status == 'generating':
        return redirect('onboarding_generating')
    if preview.status == 'committed':
        return redirect('dashboard')

    data = preview.edited_data if preview.edited_data else preview.generated_data

    # Detect stale previews (generated >6 hours ago and never committed)
    age = timezone.now() - preview.created_at
    is_stale = age > datetime.timedelta(hours=6)

    return render(request, 'kanban/onboarding/review.html', {
        'preview': preview,
        'data': data,
        'data_json': json.dumps(data),
        'is_stale': is_stale,
        'preview_age_hours': int(age.total_seconds() // 3600),
    })


# ---------------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------------

@login_required
@require_POST
@demo_write_guard
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

    # Switch out of demo mode so the dashboard shows the user's own workspace
    profile = request.user.profile
    if profile.is_viewing_demo:
        profile.is_viewing_demo = False
        profile.save(update_fields=['is_viewing_demo'])

    # Show a one-time banner on the dashboard reminding the user to assign tasks
    request.session['show_onboarding_assign_banner'] = True

    return redirect('dashboard')


# ---------------------------------------------------------------------------
# Start Over
# ---------------------------------------------------------------------------

@login_required
@require_POST
@demo_write_guard
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
@demo_write_guard
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
@demo_write_guard
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


# ---------------------------------------------------------------------------
# HITL: Validate workspace coherence (Phase 3)
# ---------------------------------------------------------------------------

@login_required
@require_POST
@demo_ai_guard
def onboarding_validate(request):
    """
    POST /onboarding/validate/
    Accept the edited workspace JSON and run an AI coherence check.
    Returns JSON: {status, flags[]}.
    """
    from kanban.utils.ai_utils import validate_workspace_coherence
    from api.ai_usage_utils import track_ai_request
    from kanban.audit_utils import log_audit
    import time

    try:
        workspace_data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    if not workspace_data.get('goal') or not workspace_data.get('missions'):
        return JsonResponse({
            'status': 'structural_issue',
            'flags': [{
                'level': 'goal',
                'item_title': '',
                'message': 'Workspace must have a goal and at least one mission.',
                'suggested_fix': 'Add a goal and missions before validating.'
            }]
        })

    mission_names = [m.get('name', '') for m in workspace_data.get('missions', [])]
    logger.info(f"[validate] user={request.user.username} missions={mission_names}")

    start_time = time.time()
    try:
        result = validate_workspace_coherence(workspace_data)

        response_time_ms = int((time.time() - start_time) * 1000)
        logger.info(f"[validate] result status={result.get('status')} flags={len(result.get('flags', []))}")
        track_ai_request(
            user=request.user,
            feature='onboarding_validation',
            request_type='validate',
            success=True,
            response_time_ms=response_time_ms,
        )
        log_audit(
            'system.warning',
            user=request.user,
            message=f"Onboarding workspace validated: {result.get('status', 'unknown')}",
        )

        return JsonResponse(result)

    except Exception as exc:
        response_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"[validate] Workspace validation error: {exc}", exc_info=True)
        track_ai_request(
            user=request.user,
            feature='onboarding_validation',
            request_type='validate',
            success=False,
            error_message=str(exc),
            response_time_ms=response_time_ms,
        )
        # Return service_error so the frontend shows a warning rather than faking 'clear'
        return JsonResponse({'status': 'service_error', 'flags': []})


# ---------------------------------------------------------------------------
# HITL: Regenerate child titles (Phase 4)
# ---------------------------------------------------------------------------

@login_required
@require_POST
@demo_ai_guard
def onboarding_regenerate_children(request):
    """
    POST /onboarding/regenerate-children/
    Accept a renamed parent's new title and current child titles,
    return updated child titles from Gemini.

    Request body: {
        "parent_title": "string",
        "parent_level": "mission" | "strategy",
        "current_children": ["title1", "title2", ...]
    }

    Response: {
        "success": true,
        "titles": ["new1", "new2", ...]
    }
    """
    from kanban.utils.ai_utils import regenerate_child_titles
    from api.ai_usage_utils import track_ai_request
    from kanban.audit_utils import log_audit
    import time

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    parent_title = (body.get('parent_title') or '').strip()
    parent_level = (body.get('parent_level') or '').strip()
    current_children = body.get('current_children', [])

    if not parent_title or parent_level not in ('mission', 'strategy'):
        return JsonResponse({'success': False, 'error': 'Invalid parent_title or parent_level'}, status=400)
    if not isinstance(current_children, list) or len(current_children) == 0:
        return JsonResponse({'success': False, 'error': 'current_children must be a non-empty list'}, status=400)

    start_time = time.time()
    try:
        titles = regenerate_child_titles(parent_title, parent_level, current_children)

        response_time_ms = int((time.time() - start_time) * 1000)
        if titles:
            track_ai_request(
                user=request.user,
                feature='onboarding_regeneration',
                request_type='regenerate',
                success=True,
                response_time_ms=response_time_ms,
            )
            log_audit(
                'system.warning',
                user=request.user,
                message=f"Onboarding children regenerated: {len(titles)} titles for {parent_level}: {parent_title}",
            )
            return JsonResponse({'success': True, 'titles': titles})
        else:
            track_ai_request(
                user=request.user,
                feature='onboarding_regeneration',
                request_type='regenerate',
                success=False,
                error_message='Regeneration returned None',
                response_time_ms=response_time_ms,
            )
            return JsonResponse({
                'success': False,
                'error': 'Could not generate new titles. Please try again.'
            }, status=500)

    except Exception as exc:
        response_time_ms = int((time.time() - start_time) * 1000)
        track_ai_request(
            user=request.user,
            feature='onboarding_regeneration',
            request_type='regenerate',
            success=False,
            error_message=str(exc),
            response_time_ms=response_time_ms,
        )
        logger.error(f"Child title regeneration error: {exc}")
        return JsonResponse({
            'success': False,
            'error': 'Something went wrong. Please try again.'
        }, status=500)
