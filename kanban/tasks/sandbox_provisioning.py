"""
Celery task for asynchronous sandbox provisioning.

Uses the same WebSocket progressive-disclosure pattern as AI streaming tasks:
Celery worker deep-copies demo template boards → streams progress updates
via Django Channels → frontend redirects on completion.
"""
import logging

from celery import shared_task
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone

logger = logging.getLogger(__name__)


def _send_provision_status(user_id, message, progress=0):
    """Send a provisioning progress update to the user's WebSocket group."""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'sandbox_provision_{user_id}',
            {
                'type': 'provision_status',
                'message': message,
                'progress': progress,
            },
        )
    except Exception as exc:
        logger.warning('Failed to send provision status for user %s: %s', user_id, exc)


def _send_provision_result(user_id, data):
    """Send the provisioning completion result."""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'sandbox_provision_{user_id}',
            {
                'type': 'provision_result',
                'data': data,
            },
        )
    except Exception as exc:
        logger.warning('Failed to send provision result for user %s: %s', user_id, exc)


def _send_provision_error(user_id, message):
    """Send a provisioning error."""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'sandbox_provision_{user_id}',
            {
                'type': 'provision_error',
                'message': message,
            },
        )
    except Exception as exc:
        logger.warning('Failed to send provision error for user %s: %s', user_id, exc)


@shared_task(
    bind=True,
    name='kanban.sandbox_provisioning.provision_sandbox',
    time_limit=120,
    soft_time_limit=90,
)
def provision_sandbox_task(self, user_id, is_reset=False):
    """
    Deep-copy all demo template boards into a private sandbox for *user_id*.

    Streams progress via WebSocket so the frontend can show a loading state.
    On completion, sends the redirect URL.

    Args:
        is_reset: If True, this is a reset operation and last_reset_at will be set.
    """
    from django.contrib.auth import get_user_model
    from kanban.models import Board, DemoSandbox
    from kanban.sandbox_views import (
        _duplicate_board, _purge_existing_sandbox,
        _join_demo_org, _reassign_demo_tasks_to_user,
    )
    from kanban.utils.demo_protection import allow_demo_writes

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        _send_provision_error(user_id, 'User not found.')
        return {'status': 'error', 'message': 'User not found.'}

    _send_provision_status(user_id, 'Preparing your private workspace…', 5)

    # Check for existing sandbox
    try:
        existing = user.demo_sandbox
        # Active sandbox already exists — just return it
        first_board = Board.objects.filter(
            owner=user,
            is_sandbox_copy=True,
        ).first()
        redirect_url = f'/boards/{first_board.id}/' if first_board else '/dashboard/'
        _send_provision_result(user_id, {
            'status': 'exists',
            'redirect_url': redirect_url,
        })
        return {'status': 'exists', 'redirect_url': redirect_url}
    except DemoSandbox.DoesNotExist:
        pass

    template_boards = list(Board.objects.filter(is_official_demo_board=True).order_by('name'))
    if not template_boards:
        _send_provision_error(user_id, 'No demo template boards found.')
        return {'status': 'error', 'message': 'No demo template boards found.'}

    _send_provision_status(user_id, 'Copying demo boards…', 15)

    new_boards = []
    total = len(template_boards)
    with allow_demo_writes():
        for idx, template in enumerate(template_boards):
            try:
                pct = 15 + int((idx / total) * 70)  # 15% → 85%
                _send_provision_status(
                    user_id,
                    f'Creating board {idx + 1} of {total}: {template.name}…',
                    pct,
                )
                new_board = _duplicate_board(template, user)
                new_boards.append(new_board)
            except Exception as e:
                logger.error(
                    "Error duplicating board '%s' for %s: %s",
                    template.name, user.username, e,
                )

        if not new_boards:
            _send_provision_error(user_id, 'Sandbox creation failed — no boards duplicated.')
            return {'status': 'error', 'message': 'Sandbox creation failed.'}

        _send_provision_status(user_id, 'Finalizing your workspace…', 90)

        sandbox = DemoSandbox.objects.create(
            user=user,
            last_reset_at=timezone.now() if is_reset else None,
        )

        # Join demo org and reassign a few tasks to the real user
        _join_demo_org(user)
        _reassign_demo_tasks_to_user(sandbox, user)

    # Set the profile flag
    try:
        profile = user.profile
        profile.is_viewing_demo = True
        profile.save(update_fields=['is_viewing_demo'])
    except Exception:
        pass

    # Refresh dates on the newly created sandbox boards so they are
    # relative to today (template dates may have been refreshed hours ago).
    try:
        from kanban.utils.demo_date_refresh import refresh_single_board_dates
        for board in new_boards:
            refresh_single_board_dates(board.id)
    except Exception as e:
        logger.warning("Error refreshing sandbox board dates: %s", e)

    # Regenerate Decision Center items so the dashboard/DC page
    # show fresh, accurate counts immediately after provisioning.
    try:
        from decision_center.tasks import collect_for_user, generate_briefing_for_user
        collect_for_user(user)
        generate_briefing_for_user(user)
    except Exception:
        pass

    # Seed Requirements demo data for the new sandbox boards (idempotent).
    try:
        from django.core.management import call_command
        call_command('populate_demo_requirements')
    except Exception as e:
        logger.warning("Could not seed requirements after sandbox provision: %s", e)

    # Seed PrizmDiscovery demo ideas for the demo org (idempotent).
    try:
        from django.core.management import call_command
        call_command('populate_discovery_demo_data')
    except Exception as e:
        logger.warning("Could not seed Discovery demo ideas after sandbox provision: %s", e)

    # Seed automation hierarchy demo data: checklist items, parent/subtask
    # groups, and blocking dependency pair needed for T-22–T-29 test scenarios.
    try:
        from django.core.management import call_command
        call_command('populate_automation_demo_data')
    except Exception as e:
        logger.warning("Could not seed automation hierarchy data after sandbox provision: %s", e)

    # Recalculate shadow branches against the freshly-provisioned board so
    # their feasibility scores reflect THIS sandbox's tasks/deadline/team right
    # away.  Branches are deep-copied from the template carrying the template's
    # last snapshot (often a stale score like 81%); without this the user sees
    # that stale value until they manually click "Refresh Scores", and the
    # first refresh then appears to "jump" the score by 40+ points.  Run
    # synchronously (we're already in a worker) with skip_ai so provisioning
    # isn't blocked on Gemini, then enqueue the AI backfill per new snapshot.
    # Trigger 'Sandbox provisioned' is treated as a baseline correction, so it
    # writes no divergence log and doesn't appear in the Quantum Standup.
    try:
        from django.core.cache import cache as _shadow_cache
        from kanban.tasks.shadow_branch_tasks import (
            run_branch_recalc_sync, generate_ai_for_branch_snapshot,
        )
        from kanban.shadow_models import ShadowBranch
        for board in new_boards:
            if not ShadowBranch.objects.filter(board=board, status='active').exists():
                continue
            # _duplicate_board sets a 120s demo_shadow_lock to suppress recalcs
            # *during* the clone.  Cloning is finished now, so clear the lock for
            # this board before recalculating — otherwise run_branch_recalc_sync
            # early-returns ("demo data populate in progress") and the branches
            # keep their stale cloned scores until a later signal recalc.
            try:
                _shadow_cache.delete(f'demo_shadow_lock_{board.id}')
            except Exception:
                pass
            recalc = run_branch_recalc_sync(
                board.id,
                trigger_event='Sandbox provisioned',
                skip_ai=True,
            )
            for snapshot_id in recalc.get('snapshot_ids', []):
                try:
                    generate_ai_for_branch_snapshot.delay(snapshot_id)
                except Exception:
                    pass
    except Exception as e:
        logger.warning("Could not recalc shadow branches after sandbox provision: %s", e)

    redirect_url = '/dashboard/'
    _send_provision_status(user_id, 'Your workspace is ready!', 100)
    _send_provision_result(user_id, {
        'status': 'created',
        'boards_created': len(new_boards),
        'redirect_url': redirect_url,
    })
    return {
        'status': 'created',
        'boards_created': len(new_boards),
        'redirect_url': redirect_url,
    }
