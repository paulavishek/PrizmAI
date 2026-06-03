"""
Celery Tasks for Webhook Delivery
Uses existing Celery infrastructure for async webhook processing
"""
import requests
import time
import hmac
import hashlib
import json
from datetime import timedelta
from urllib.parse import urlparse
from django.core.exceptions import ValidationError
from django.utils import timezone
from celery import shared_task
from webhooks.models import Webhook, WebhookDelivery
from webhooks.security import validate_webhook_target


# Host substring -> provider name, used when a webhook has no explicit provider set.
_HOST_PROVIDER_MAP = (
    ('hooks.slack.com', 'slack'),
    ('discord.com', 'discord'),
    ('discordapp.com', 'discord'),
    ('chat.googleapis.com', 'googlechat'),
    ('webhook.office.com', 'teams'),
    ('api.github.com', 'github'),
    ('events.pagerduty.com', 'pagerduty'),
)


def _resolve_provider(webhook):
    """Explicit webhook.provider wins; otherwise sniff the URL host; else 'generic'."""
    provider = (getattr(webhook, 'provider', '') or '').strip().lower()
    if provider:
        return provider
    host = (urlparse(webhook.url).hostname or '').lower()
    for needle, name in _HOST_PROVIDER_MAP:
        if needle in host:
            return name
    return 'generic'


def _build_message_text(event_type, data, bold='*'):
    """
    Build a human-readable one-line message for chat providers.
    `bold` is the markdown emphasis marker for the target platform
    ('*' for Slack/Google Chat, '**' for Discord/Teams, '' for plain text).
    """
    def b(s):
        return f'{bold}{s}{bold}' if s else ''

    title = data.get('title', '')
    board_name = ''
    if isinstance(data.get('board'), dict):
        board_name = data['board'].get('name', '')
    on_board = f' on board {b(board_name)}' if board_name else ''
    in_board = f' in board {b(board_name)}' if board_name else ''
    to_col = ''
    if isinstance(data.get('to_column'), dict):
        to_col = f' → {b(data["to_column"].get("name", ""))}'

    messages = {
        'test.event': '🔔 PrizmAI test — your integration is working!',
        'task.created': f'📋 Task created: {b(title)}{on_board}',
        'task.updated': f'✏️ Task updated: {b(title)}{on_board}',
        'task.deleted': f'🗑️ Task deleted: {b(title)}{on_board}',
        'task.completed': f'✅ Task completed: {b(title)}{on_board}',
        'task.assigned': f'👤 Task assigned: {b(title)}{on_board}',
        'task.moved': f'🔀 Task moved: {b(title)}{to_col}{on_board}',
        'comment.added': f'💬 Comment added on: {b(title)}{in_board}',
        'board.updated': f'📌 Board updated: {b(board_name)}' if board_name else '📌 Board updated',
    }
    return messages.get(event_type, f'🔔 PrizmAI event: {event_type}')


def _build_provider_payload(provider, event_type, data, cfg=None):
    """
    Return the provider-specific JSON body for a webhook, or None to fall back to
    the standard PrizmAI envelope ({event, timestamp, delivery_id, data}).

    cfg is webhook.provider_config (dict) for providers whose body needs extra
    fields the URL/headers can't carry.
    """
    cfg = cfg or {}

    if provider in ('slack', 'googlechat'):
        # Both require a top-level "text" key; both use *single-asterisk* emphasis.
        return {'text': _build_message_text(event_type, data, bold='*')}

    if provider == 'discord':
        # Discord requires "content" (or embeds); rejects a body with neither.
        return {'content': _build_message_text(event_type, data, bold='**')}

    if provider == 'teams':
        # Classic Office 365 connector MessageCard.
        return {
            '@type': 'MessageCard',
            '@context': 'http://schema.org/extensions',
            'summary': 'PrizmAI notification',
            'themeColor': '0076D7',
            'text': _build_message_text(event_type, data, bold='**'),
        }

    if provider == 'github':
        # repository_dispatch: PAT supplied via custom_headers (Authorization).
        return {
            'event_type': cfg.get('event_type') or 'prizmai_event',
            'client_payload': {'event': event_type, 'data': data},
        }

    if provider == 'pagerduty':
        # Events API v2 — routing_key comes from provider_config.
        return {
            'routing_key': cfg.get('routing_key', ''),
            'event_action': 'trigger',
            'payload': {
                'summary': _build_message_text(event_type, data, bold=''),
                'source': 'PrizmAI',
                'severity': 'warning',
            },
        }

    # zapier / make / n8n / powerautomate / gitlab / custom / generic -> standard envelope.
    return None


@shared_task(bind=True, max_retries=3)
def deliver_webhook(self, delivery_id, is_retry=False):
    """
    Deliver a webhook to the target URL

    Args:
        delivery_id: ID of the WebhookDelivery to process
        is_retry: True when called by retry_delivery; skips double-counting stats
    """
    try:
        delivery = WebhookDelivery.objects.select_related('webhook').get(id=delivery_id)
    except WebhookDelivery.DoesNotExist:
        return {'error': 'Delivery not found'}

    webhook = delivery.webhook

    # Check if webhook is still active
    if not webhook.is_active or webhook.status == 'disabled':
        delivery.status = 'failed'
        delivery.error_message = 'Webhook is inactive or disabled'
        delivery.save()
        return {'error': 'Webhook inactive'}

    try:
        # Prepare payload — format it for the target provider when we have a
        # dedicated builder; otherwise send the standard PrizmAI envelope.
        provider = _resolve_provider(webhook)
        formatted = _build_provider_payload(
            provider, delivery.event_type, delivery.payload, webhook.provider_config
        )
        if formatted is not None:
            payload = formatted
        else:
            payload = {
                'event': delivery.event_type,
                'timestamp': delivery.created_at.isoformat(),
                'delivery_id': delivery.id,
                'data': delivery.payload
            }

        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'PrizmAI-Webhook/1.0',
            'X-Webhook-Event': delivery.event_type,
            'X-Webhook-Delivery': str(delivery.id),
        }

        # Add custom headers
        if webhook.custom_headers:
            headers.update(webhook.custom_headers)

        # Serialise the payload exactly once so the bytes we sign are the bytes
        # we send (avoids any divergence from requests' own JSON serialisation).
        payload_str = json.dumps(payload)
        payload_bytes = payload_str.encode('utf-8')

        # Add HMAC signature if secret is set
        if webhook.secret:
            signature = hmac.new(
                webhook.secret.encode('utf-8'),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()
            headers['X-Webhook-Signature'] = f'sha256={signature}'

        # SSRF guard: refuse to deliver to internal/private targets. Re-checked
        # here (after DNS resolution) as the authoritative enforcement point.
        # A blocked target is a permanent config error, so it is not retried.
        try:
            validate_webhook_target(webhook.url)
        except ValidationError as exc:
            delivery.status = 'failed'
            delivery.error_message = ('Blocked target: ' + '; '.join(exc.messages))[:500]
            delivery.save()
            if not is_retry:
                webhook.increment_delivery_stats(success=False)
            return {'error': 'blocked_target'}

        # Attempt delivery
        start_time = time.time()
        try:
            response = requests.post(
                webhook.url,
                data=payload_bytes,
                headers=headers,
                timeout=webhook.timeout_seconds,
                allow_redirects=False,
            )

            response_time_ms = int((time.time() - start_time) * 1000)

            # Update delivery record
            delivery.response_status_code = response.status_code
            delivery.response_body = response.text[:1000]
            delivery.response_time_ms = response_time_ms
            delivery.delivered_at = timezone.now()

            # Consider 2xx status codes as success
            if 200 <= response.status_code < 300:
                delivery.status = 'success'
                if is_retry:
                    # Convert the earlier failure tick into a success: total stays the same.
                    webhook.increment_delivery_stats(success=True, is_retry=True)
                else:
                    webhook.increment_delivery_stats(success=True)
            else:
                delivery.status = 'failed'
                delivery.error_message = f'HTTP {response.status_code}: {response.text[:200]}'
                if not is_retry:
                    # Only count the first attempt; retries don't add to failed_deliveries.
                    webhook.increment_delivery_stats(success=False)

                # Retry if eligible
                if delivery.is_retriable():
                    retry_delivery.apply_async(
                        args=[delivery_id],
                        countdown=webhook.retry_delay_seconds
                    )

            delivery.save()

            return {
                'success': delivery.status == 'success',
                'status_code': response.status_code,
                'response_time_ms': response_time_ms
            }

        except requests.exceptions.Timeout:
            delivery.status = 'failed'
            delivery.error_message = f'Request timeout after {webhook.timeout_seconds}s'
            delivery.save()

            if not is_retry:
                webhook.increment_delivery_stats(success=False)

            # Retry if eligible
            if delivery.is_retriable():
                retry_delivery.apply_async(
                    args=[delivery_id],
                    countdown=webhook.retry_delay_seconds
                )

            return {'error': 'timeout'}

        except requests.exceptions.RequestException as e:
            delivery.status = 'failed'
            delivery.error_message = str(e)[:500]
            delivery.save()

            if not is_retry:
                webhook.increment_delivery_stats(success=False)

            # Retry if eligible
            if delivery.is_retriable():
                retry_delivery.apply_async(
                    args=[delivery_id],
                    countdown=webhook.retry_delay_seconds
                )

            return {'error': str(e)}

    except Exception as e:
        # Catch-all: any unexpected error (bad custom_headers type, HMAC failure,
        # non-serialisable payload, etc.) must not leave the delivery in Pending.
        delivery.status = 'failed'
        delivery.error_message = f'Internal error: {type(e).__name__}: {str(e)[:400]}'
        try:
            delivery.save()
        except Exception:
            pass
        raise  # Re-raise so Celery marks the task as FAILURE and logs the traceback


@shared_task
def retry_delivery(delivery_id):
    """
    Retry a failed webhook delivery
    
    Args:
        delivery_id: ID of the WebhookDelivery to retry
    """
    try:
        delivery = WebhookDelivery.objects.get(id=delivery_id)
    except WebhookDelivery.DoesNotExist:
        return {'error': 'Delivery not found'}
    
    if not delivery.is_retriable():
        return {'error': 'Delivery not retriable'}
    
    # Increment retry count
    delivery.retry_count += 1
    delivery.status = 'retrying'
    delivery.save()
    
    # Attempt delivery — is_retry=True so stats aren't double-counted
    return deliver_webhook.apply_async(args=[delivery_id], kwargs={'is_retry': True})


@shared_task
def cleanup_old_deliveries(days=30):
    """
    Clean up old webhook delivery logs
    Runs periodically to prevent database bloat
    
    Args:
        days: Number of days to keep (default: 30)
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    
    deleted_count = WebhookDelivery.objects.filter(
        created_at__lt=cutoff_date,
        status__in=['success', 'failed']
    ).delete()[0]
    
    return {
        'deleted_count': deleted_count,
        'cutoff_date': cutoff_date.isoformat()
    }


@shared_task
def check_webhook_health():
    """
    Check health of all active webhooks
    Disable webhooks with too many consecutive failures
    """
    from webhooks.models import Webhook
    
    unhealthy_webhooks = Webhook.objects.filter(
        is_active=True,
        consecutive_failures__gte=10
    )
    
    disabled_count = 0
    for webhook in unhealthy_webhooks:
        webhook.status = 'failed'
        webhook.is_active = False
        webhook.save()
        disabled_count += 1
    
    return {
        'disabled_count': disabled_count,
        'checked_at': timezone.now().isoformat()
    }
