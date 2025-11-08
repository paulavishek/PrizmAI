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
from django.utils import timezone
from celery import shared_task
from webhooks.models import Webhook, WebhookDelivery


@shared_task(bind=True, max_retries=3)
def deliver_webhook(self, delivery_id):
    """
    Deliver a webhook to the target URL
    
    Args:
        delivery_id: ID of the WebhookDelivery to process
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
    
    # Prepare payload
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
    
    # Add HMAC signature if secret is set
    if webhook.secret:
        payload_str = json.dumps(payload)
        signature = hmac.new(
            webhook.secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        headers['X-Webhook-Signature'] = f'sha256={signature}'
    
    # Attempt delivery
    start_time = time.time()
    try:
        response = requests.post(
            webhook.url,
            json=payload,
            headers=headers,
            timeout=webhook.timeout_seconds
        )
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Update delivery record
        delivery.response_status_code = response.status_code
        delivery.response_body = response.text[:1000]  # Store first 1000 chars
        delivery.response_time_ms = response_time_ms
        delivery.delivered_at = timezone.now()
        
        # Consider 2xx status codes as success
        if 200 <= response.status_code < 300:
            delivery.status = 'success'
            webhook.increment_delivery_stats(success=True)
        else:
            delivery.status = 'failed'
            delivery.error_message = f'HTTP {response.status_code}: {response.text[:200]}'
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
        
        webhook.increment_delivery_stats(success=False)
        
        # Retry if eligible
        if delivery.is_retriable():
            retry_delivery.apply_async(
                args=[delivery_id],
                countdown=webhook.retry_delay_seconds
            )
        
        return {'error': str(e)}


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
    
    # Attempt delivery
    return deliver_webhook.delay(delivery_id)


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
