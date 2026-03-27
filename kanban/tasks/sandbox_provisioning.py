"""
Celery task for asynchronous sandbox provisioning.

Uses the same WebSocket progressive-disclosure pattern as AI streaming tasks:
Celery worker deep-copies demo template boards → streams progress updates
via Django Channels → frontend redirects on completion.
"""
import logging
from datetime import timedelta

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
def provision_sandbox_task(self, user_id):
    """
    Deep-copy all demo template boards into a private sandbox for *user_id*.

    Streams progress via WebSocket so the frontend can show a loading state.
    On completion, sends the redirect URL.
    """
    from django.contrib.auth import get_user_model
    from kanban.models import Board, DemoSandbox
    from kanban.sandbox_views import _duplicate_board, _purge_existing_sandbox
    from kanban.utils.demo_protection import allow_demo_writes

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        _send_provision_error(user_id, 'User not found.')
        return {'status': 'error', 'message': 'User not found.'}

    _send_provision_status(user_id, 'Preparing your private workspace…', 5)

    # Purge any expired sandbox
    try:
        existing = user.demo_sandbox
        if existing.expires_at <= timezone.now():
            _purge_existing_sandbox(user)
        else:
            # Active sandbox already exists — just return it
            first_board = Board.objects.filter(
                owner=user,
                is_official_demo_board=False,
                is_seed_demo_data=False,
            ).exclude(pk=existing.saved_board_id).first()
            redirect_url = f'/boards/{first_board.id}/' if first_board else '/dashboard/'
            _send_provision_result(user_id, {
                'status': 'exists',
                'redirect_url': redirect_url,
                'expires_at': existing.expires_at.isoformat(),
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
            expires_at=timezone.now() + timedelta(hours=24),
            is_browsing=True,
        )

    # Set the profile flag
    try:
        profile = user.profile
        profile.is_viewing_demo = True
        profile.save(update_fields=['is_viewing_demo'])
    except Exception:
        pass

    redirect_url = '/dashboard/'
    _send_provision_status(user_id, 'Your workspace is ready!', 100)
    _send_provision_result(user_id, {
        'status': 'created',
        'boards_created': len(new_boards),
        'redirect_url': redirect_url,
        'expires_at': sandbox.expires_at.isoformat(),
    })
    return {
        'status': 'created',
        'boards_created': len(new_boards),
        'redirect_url': redirect_url,
    }
